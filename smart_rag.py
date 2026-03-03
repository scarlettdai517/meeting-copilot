"""
Smart RAG 核心检索策略（基线 + 升级版）。

设计要点：
- 会议按 token 数分类：
  - 超短: <3000 -> Smart 直接全文
  - 短会: 3000~9999 -> 256/50
  - 长会: >=10000 -> 512/100
- 基线（traditional）：
  - 分块按会议类型（短 256/50，长 512/100）
  - 纯语义 top-5
- Smart：
  - 长短会分流：长会语义优先（默认不启用 BM25），短会语义+BM25
  - 启用 BM25 时使用 RRF 合并
  - 轻量 cross-encoder（可选）重排序；不可用时启发式回退
  - 动态阈值选块：threshold=max(mu-std_weight*sigma, abs_floor)
"""

from __future__ import annotations

import json
import math
import re
import statistics
from pathlib import Path
from typing import Dict, List, Tuple

from semantic_retrieval import (
    cosine_similarity,
    get_embedding,
    prepare_chunks_for_retrieval,
)

# ---------- 全局参数 ----------
ULTRASHORT_THRESHOLD = 3000
LONG_THRESHOLD = 10000

SHORT_CHUNK_TOKENS = 256
SHORT_OVERLAP_TOKENS = 50
LONG_CHUNK_TOKENS = 512
LONG_OVERLAP_TOKENS = 100

SHORT_CANDIDATES = 12
LONG_CANDIDATES = 15

SHORT_MAX_CHUNKS = 6
LONG_MAX_CHUNKS = 6

RRF_K = 60
LONG_STD_WEIGHT = 0.4
SHORT_STD_WEIGHT = 0.2
DYNAMIC_ABS_FLOOR = 0.30

# Smart v2 检索开关（长短会分流）：
# - 长会默认关闭 BM25（提升 precision）
# - 短会默认开启 BM25（补关键词召回）
SMART_V2_USE_BM25_FOR_LONG = False
SMART_V2_USE_BM25_FOR_SHORT = True
# 若设为 True，则长短会都只走语义候选（覆盖以上两个开关）
SMART_V2_SEMANTIC_ONLY = False

# Smart v2 重排序开关：
# True  -> 启用 rerank（优先 cross-encoder，不可用回退启发式）
# False -> 关闭 rerank，直接用候选分数（语义模式下为语义相似度）做动态K
SMART_V2_ENABLE_RERANK = True

_TS_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s*")
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+|[^\s]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")

_CROSS_ENCODER = None
_CROSS_ENCODER_NAME = None
_CROSS_ENCODER_LAST_ERROR = ""

RAG_SYSTEM_PROMPT = "基于以下会议片段回答问题，如果片段中无相关信息，请说明无法回答。"


def _tokenize_for_length(text: str) -> List[str]:
    return _TOKEN_RE.findall(text or "")


def estimate_token_count(text: str) -> int:
    return len(_tokenize_for_length(text))


def classify_meeting(transcript: str) -> Tuple[str, int]:
    n_tokens = estimate_token_count(transcript)
    if n_tokens < ULTRASHORT_THRESHOLD:
        return "ultrashort", n_tokens
    if n_tokens < LONG_THRESHOLD:
        return "short", n_tokens
    return "long", n_tokens


def _split_to_units(transcript: str) -> List[str]:
    """
    尽量按时间戳 + 句号边界切分为语义单元。
    """
    units: List[str] = []
    for raw_line in transcript.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # 时间戳前缀保留在第一个句子上
        ts_match = _TS_RE.match(line)
        ts_prefix = ts_match.group(0) if ts_match else ""
        content = line[len(ts_prefix):].strip() if ts_match else line
        parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(content) if p.strip()]
        if not parts:
            continue
        for i, part in enumerate(parts):
            if i == 0 and ts_prefix:
                units.append(f"{ts_prefix}{part}".strip())
            else:
                units.append(part)
    return units


def build_chunks_by_semantic_units(
    transcript: str,
    chunk_tokens: int,
    overlap_tokens: int,
) -> List[Dict]:
    """
    按语义单元聚合成目标 token 大小的 chunk，并保留 overlap。
    """
    units = _split_to_units(transcript)
    if not units:
        return []

    unit_tokens = [estimate_token_count(u) for u in units]
    chunks: List[Dict] = []
    cid = 0
    i = 0
    n = len(units)

    while i < n:
        cur_units: List[str] = []
        cur_tokens = 0
        j = i
        while j < n:
            t = unit_tokens[j]
            if cur_units and cur_tokens + t > chunk_tokens:
                break
            cur_units.append(units[j])
            cur_tokens += t
            j += 1

        if not cur_units:
            # 理论上不会发生，兜底防死循环
            cur_units = [units[i]]
            j = i + 1

        chunks.append({"id": cid, "text": "\n".join(cur_units).strip()})
        cid += 1

        if j >= n:
            break

        # 计算 overlap：从当前 chunk 尾部回溯到 overlap_tokens
        back_tokens = 0
        keep_idx = len(cur_units) - 1
        while keep_idx >= 0 and back_tokens < overlap_tokens:
            back_tokens += estimate_token_count(cur_units[keep_idx])
            keep_idx -= 1
        next_i = i + max(0, keep_idx + 1)
        if next_i <= i:
            next_i = i + 1
        i = next_i

    return chunks


def _chunks_file_for_transcript(data_dir: Path, transcript_path: str) -> Path:
    name = Path(transcript_path).name
    stem = name.replace("transcript_", "chunks_").replace(".txt", ".json")
    return data_dir / stem


def load_or_build_chunks(
    data_dir: Path,
    transcript_path: str,
    transcript: str,
    chunk_tokens: int,
    overlap_tokens: int,
    prefer_existing: bool = True,
) -> Tuple[List[Dict], str]:
    """
    优先复用 chunks_*.json（保证与 GT chunk id 空间一致），否则按 v2 规则现算。
    """
    chunks_path = _chunks_file_for_transcript(data_dir, transcript_path)
    if prefer_existing and chunks_path.is_file():
        try:
            arr = json.loads(chunks_path.read_text(encoding="utf-8"))
            if isinstance(arr, list):
                normalized = []
                ok = True
                for idx, x in enumerate(arr):
                    if not isinstance(x, dict):
                        ok = False
                        break
                    # 兼容两种字段：id / chunk_id
                    cid = x.get("id", x.get("chunk_id"))
                    text = x.get("text")
                    if cid is None or text is None:
                        ok = False
                        break
                    try:
                        cid = int(cid)
                    except Exception:
                        cid = idx
                    normalized.append({"id": cid, "text": str(text)})
                if ok:
                    # 防止外部文件 id 无序/重复，按顺序重建稳定 id，保证评测一致
                    normalized.sort(key=lambda z: z["id"])
                    stable = [{"id": i, "text": z["text"]} for i, z in enumerate(normalized)]
                    return stable, f"existing:{chunks_path.name}"
        except Exception:
            pass

    return (
        build_chunks_by_semantic_units(
            transcript=transcript,
            chunk_tokens=chunk_tokens,
            overlap_tokens=overlap_tokens,
        ),
        "generated:v2_semantic_boundary",
    )


def _tokenize_for_bm25(text: str) -> List[str]:
    text = (text or "").strip().lower()
    if not text:
        return []

    # 优先 jieba；不可用时回退到字符/词混合切分
    try:
        import jieba  # type: ignore

        tokens = [t.strip() for t in jieba.lcut(text) if t.strip()]
        return [t for t in tokens if not re.fullmatch(r"\W+", t)]
    except Exception:
        tokens = _TOKEN_RE.findall(text)
        return [t for t in tokens if t.strip()]


class BM25Index:
    def __init__(self, docs_tokens: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.docs_tokens = docs_tokens
        self.k1 = k1
        self.b = b
        self.n_docs = len(docs_tokens)
        self.doc_lens = [len(x) for x in docs_tokens]
        self.avgdl = (sum(self.doc_lens) / self.n_docs) if self.n_docs else 0.0

        self.df = {}
        for toks in docs_tokens:
            for tok in set(toks):
                self.df[tok] = self.df.get(tok, 0) + 1

        self.idf = {}
        for tok, df in self.df.items():
            # BM25 常用平滑 idf
            self.idf[tok] = math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))

        self.tf = []
        for toks in docs_tokens:
            c = {}
            for t in toks:
                c[t] = c.get(t, 0) + 1
            self.tf.append(c)

    def score(self, query_tokens: List[str], doc_idx: int) -> float:
        if doc_idx < 0 or doc_idx >= self.n_docs:
            return 0.0
        if not query_tokens:
            return 0.0
        tf_map = self.tf[doc_idx]
        dl = self.doc_lens[doc_idx]
        score = 0.0
        for tok in query_tokens:
            if tok not in tf_map:
                continue
            f = tf_map[tok]
            idf = self.idf.get(tok, 0.0)
            denom = f + self.k1 * (1.0 - self.b + self.b * (dl / (self.avgdl + 1e-9)))
            score += idf * (f * (self.k1 + 1.0)) / (denom + 1e-9)
        return float(score)

    def top_k(self, query: str, k: int) -> List[Tuple[int, float]]:
        q_tokens = _tokenize_for_bm25(query)
        scored = []
        for i in range(self.n_docs):
            s = self.score(q_tokens, i)
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


def _rrf_fuse(semantic_rank_ids: List[int], bm25_rank_ids: List[int], k: int = RRF_K) -> List[int]:
    scores = {}
    for r, cid in enumerate(semantic_rank_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r)
    for r, cid in enumerate(bm25_rank_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r)
    return [cid for cid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _get_cross_encoder(model_name: str):
    global _CROSS_ENCODER, _CROSS_ENCODER_NAME, _CROSS_ENCODER_LAST_ERROR
    if _CROSS_ENCODER is not None and _CROSS_ENCODER_NAME == model_name:
        return _CROSS_ENCODER
    try:
        from sentence_transformers import CrossEncoder  # type: ignore

        _CROSS_ENCODER = CrossEncoder(model_name)
        _CROSS_ENCODER_NAME = model_name
        _CROSS_ENCODER_LAST_ERROR = ""
        return _CROSS_ENCODER
    except Exception as e:
        _CROSS_ENCODER_LAST_ERROR = str(e)
        return None


def rerank_candidates(
    question: str,
    candidates: List[Dict],
    reranker_model: str = "BAAI/bge-reranker-v2-m3",
) -> Tuple[List[Dict], str]:
    """
    候选重排：
    - 优先 cross-encoder（logit->sigmoid 得 0~1）
    - 回退启发式（RRF 名次 + 语义相似度 + BM25 归一化）
    """
    if not candidates:
        return [], "none"

    model = _get_cross_encoder(reranker_model)
    if model is not None:
        pairs = [(question, c["text"]) for c in candidates]
        logits = model.predict(pairs)
        scores = [_sigmoid(float(x)) for x in logits]
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates, f"cross_encoder:{reranker_model}"

    # fallback：启发式相关度（优先保留 RRF 排序信号，避免把关键词优势冲掉）
    max_bm25 = max((c.get("bm25_score", 0.0) for c in candidates), default=0.0) or 1.0
    denom_rank = max(1, len(candidates) - 1)
    for c in candidates:
        # RRF rank: 1最好，映射到[0,1]
        rank = int(c.get("rrf_rank", len(candidates)))
        rrf_norm = 1.0 - float(rank - 1) / float(denom_rank)
        sem = (float(c.get("semantic_sim", 0.0)) + 1.0) / 2.0  # [-1,1] -> [0,1]
        bm = float(c.get("bm25_score", 0.0)) / max_bm25
        c["rerank_score"] = 0.45 * rrf_norm + 0.35 * sem + 0.20 * bm
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates, "heuristic_fallback"


def rank_without_rerank(candidates: List[Dict], semantic_only: bool) -> Tuple[List[Dict], str]:
    """
    关闭 rerank 时的候选打分：
    - 语义专用模式：仅用 semantic_sim
    - 混合模式：用 rrf_rank + semantic + bm25 的轻量组合
    """
    if not candidates:
        return [], "rerank_disabled"

    if semantic_only:
        for c in candidates:
            sem = (float(c.get("semantic_sim", 0.0)) + 1.0) / 2.0
            c["rerank_score"] = sem
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates, "rerank_disabled_semantic"

    max_bm25 = max((c.get("bm25_score", 0.0) for c in candidates), default=0.0) or 1.0
    denom_rank = max(1, len(candidates) - 1)
    for c in candidates:
        rank = int(c.get("rrf_rank", len(candidates)))
        rrf_norm = 1.0 - float(rank - 1) / float(denom_rank)
        sem = (float(c.get("semantic_sim", 0.0)) + 1.0) / 2.0
        bm = float(c.get("bm25_score", 0.0)) / max_bm25
        c["rerank_score"] = 0.45 * rrf_norm + 0.35 * sem + 0.20 * bm
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates, "rerank_disabled_mixed"


def dynamic_select_by_scores(
    ranked: List[Dict],
    max_chunks: int,
    std_weight: float = LONG_STD_WEIGHT,
    abs_floor: float = DYNAMIC_ABS_FLOOR,
) -> Tuple[List[Dict], Dict]:
    if not ranked:
        return [], {"mu": 0.0, "sigma": 0.0, "threshold": 0.0}

    scores = [float(x.get("rerank_score", 0.0)) for x in ranked]
    mu = float(statistics.fmean(scores))
    sigma = float(statistics.pstdev(scores)) if len(scores) > 1 else 0.0
    threshold = max(mu - std_weight * sigma, 0.0, abs_floor)

    selected = []
    for item in ranked:
        if len(selected) >= max_chunks:
            break
        if float(item.get("rerank_score", 0.0)) < threshold:
            break
        selected.append(item)

    if not selected:
        selected = [ranked[0]]

    return selected, {"mu": mu, "sigma": sigma, "threshold": threshold}


def _semantic_rank(
    question: str,
    chunks: List[Dict],
    cache_id: str,
    top_k: int,
) -> Tuple[List[Tuple[int, float]], Dict[int, float]]:
    """
    返回 [(chunk_id, sim), ...] 和 sim_map
    """
    embeddings = prepare_chunks_for_retrieval(chunks, cache_id=cache_id, use_cache=True)
    q_emb = get_embedding(question)
    scored = []
    for i, c_emb in enumerate(embeddings):
        sim = cosine_similarity(q_emb, c_emb)
        scored.append((chunks[i]["id"], float(sim)))
    scored.sort(key=lambda x: x[1], reverse=True)
    sim_map = {cid: s for cid, s in scored}
    return scored[:top_k], sim_map


def _build_bm25_rank(question: str, chunks: List[Dict], top_k: int) -> List[Tuple[int, float]]:
    docs_tokens = [_tokenize_for_bm25(c["text"]) for c in chunks]
    bm25 = BM25Index(docs_tokens)
    raw = bm25.top_k(question, top_k)
    # raw index -> chunk id
    out = []
    for doc_idx, score in raw:
        out.append((chunks[doc_idx]["id"], float(score)))
    return out


def _sim_stats(sims: List[float]) -> Dict[str, float]:
    if not sims:
        return {"sim_max": 0.0, "sim_min": 0.0, "sim_avg": 0.0}
    return {
        "sim_max": float(max(sims)),
        "sim_min": float(min(sims)),
        "sim_avg": float(sum(sims) / len(sims)),
    }


def build_rag_context(chunks: List[Dict]) -> str:
    """
    组装可送入 LLM 的证据上下文（按当前排序顺序拼接）。
    """
    parts = []
    for c in chunks:
        parts.append(f"[chunk {c.get('id', '?')}]\n{c.get('text', '').strip()}")
    return "\n\n".join(parts).strip()


def retrieve_traditional(
    question: str,
    transcript: str,
    data_dir: Path,
    transcript_path: str,
    cache_id: str,
    top_k: int = 5,
) -> Dict:
    """
    基线：
    - 分块按会议类型：短 256/50，长 512/100
    - 纯语义 top-5
    """
    meeting_type, n_tokens = classify_meeting(transcript)
    if meeting_type == "long":
        chunk_tokens, overlap_tokens = LONG_CHUNK_TOKENS, LONG_OVERLAP_TOKENS
    else:
        chunk_tokens, overlap_tokens = SHORT_CHUNK_TOKENS, SHORT_OVERLAP_TOKENS

    chunks, chunk_source = load_or_build_chunks(
        data_dir=data_dir,
        transcript_path=transcript_path,
        transcript=transcript,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
        prefer_existing=True,
    )
    if not chunks:
        return {
            "mode": "rag",
            "meeting_type": meeting_type,
            "meeting_tokens": n_tokens,
            "chunk_source": chunk_source,
            "chunks": [],
            "retrieved_chunk_ids": [],
            "sim_stats": {"sim_max": 0.0, "sim_min": 0.0, "sim_avg": 0.0},
        }

    sem_top, sim_map = _semantic_rank(
        question=question,
        chunks=chunks,
        cache_id=f"{cache_id}_trad_{meeting_type}",
        top_k=min(top_k, len(chunks)),
    )
    selected_ids = [cid for cid, _ in sem_top]
    id_to_chunk = {c["id"]: c for c in chunks}
    selected_chunks = [id_to_chunk[cid] for cid in selected_ids if cid in id_to_chunk]
    sim_stats = _sim_stats([sim for _, sim in sem_top])

    return {
        "mode": "rag",
        "meeting_type": meeting_type,
        "meeting_tokens": n_tokens,
        "chunk_source": chunk_source,
        "chunks": selected_chunks,
        "retrieved_chunk_ids": selected_ids,
        "system_prompt": RAG_SYSTEM_PROMPT,
        "context_text": build_rag_context(selected_chunks),
        "sim_stats": sim_stats,
    }


def retrieve_smart(
    question: str,
    transcript: str,
    data_dir: Path,
    transcript_path: str,
    cache_id: str,
    reranker_model: str = "BAAI/bge-reranker-v2-m3",
) -> Dict:
    """
    Smart：
    - 超短：全文
    - 短会：候选15（语义+BM25，可配） -> rerank -> 动态阈值 -> max 6
    - 长会：候选15（语义为主，可配） -> rerank -> 动态阈值 -> max 6

    说明：
    - 默认 SMART_V2_SEMANTIC_ONLY=False：
      - 短会默认启用 BM25+RRF（由 SMART_V2_USE_BM25_FOR_SHORT 控制）
      - 长会默认关闭 BM25（由 SMART_V2_USE_BM25_FOR_LONG 控制）
    - 是否启用 rerank 由 SMART_V2_ENABLE_RERANK 控制。
    """
    meeting_type, n_tokens = classify_meeting(transcript)
    if meeting_type == "ultrashort":
        return {
            "mode": "full_text",
            "meeting_type": meeting_type,
            "meeting_tokens": n_tokens,
            "chunks": [{"id": 0, "text": transcript}],
            "retrieved_chunk_ids": [],
            "system_prompt": RAG_SYSTEM_PROMPT,
            "context_text": transcript,
            "sim_stats": {"sim_max": 1.0, "sim_min": 1.0, "sim_avg": 1.0},
            "metadata": {"reason": "ultrashort_full_text"},
        }

    if meeting_type == "long":
        chunk_tokens, overlap_tokens = LONG_CHUNK_TOKENS, LONG_OVERLAP_TOKENS
        candidate_k = LONG_CANDIDATES
        max_chunks = LONG_MAX_CHUNKS
        std_weight = LONG_STD_WEIGHT
        use_bm25 = SMART_V2_USE_BM25_FOR_LONG
    else:
        chunk_tokens, overlap_tokens = SHORT_CHUNK_TOKENS, SHORT_OVERLAP_TOKENS
        candidate_k = SHORT_CANDIDATES
        max_chunks = SHORT_MAX_CHUNKS
        std_weight = SHORT_STD_WEIGHT
        use_bm25 = SMART_V2_USE_BM25_FOR_SHORT

    if SMART_V2_SEMANTIC_ONLY:
        use_bm25 = False

    chunks, chunk_source = load_or_build_chunks(
        data_dir=data_dir,
        transcript_path=transcript_path,
        transcript=transcript,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
        prefer_existing=True,
    )
    if not chunks:
        return {
            "mode": "rag",
            "meeting_type": meeting_type,
            "meeting_tokens": n_tokens,
            "chunk_source": chunk_source,
            "chunks": [],
            "retrieved_chunk_ids": [],
            "sim_stats": {"sim_max": 0.0, "sim_min": 0.0, "sim_avg": 0.0},
            "metadata": {"reason": "empty_chunks"},
        }

    sem_top, sim_map = _semantic_rank(
        question=question,
        chunks=chunks,
        cache_id=f"{cache_id}_smart_{meeting_type}",
        top_k=min(candidate_k, len(chunks)),
    )

    sem_ids = [cid for cid, _ in sem_top]
    if use_bm25:
        bm25_top = _build_bm25_rank(question=question, chunks=chunks, top_k=min(candidate_k, len(chunks)))
        bm25_ids = [cid for cid, _ in bm25_top]
        fused_ids = _rrf_fuse(sem_ids, bm25_ids, k=RRF_K)[: min(candidate_k, len(chunks))]
        bm25_map = {cid: score for cid, score in bm25_top}
    else:
        fused_ids = sem_ids[: min(candidate_k, len(chunks))]
        bm25_map = {}

    id_to_chunk = {c["id"]: c for c in chunks}

    candidates = []
    for rank, cid in enumerate(fused_ids, start=1):
        if cid not in id_to_chunk:
            continue
        candidates.append(
            {
                "id": cid,
                "text": id_to_chunk[cid]["text"],
                "rrf_rank": rank,
                "semantic_sim": float(sim_map.get(cid, 0.0)),
                "bm25_score": float(bm25_map.get(cid, 0.0)),
            }
        )

    if SMART_V2_ENABLE_RERANK:
        reranked, rerank_method = rerank_candidates(
            question=question,
            candidates=candidates,
            reranker_model=reranker_model,
        )
    else:
        reranked, rerank_method = rank_without_rerank(
            candidates=candidates,
            semantic_only=SMART_V2_SEMANTIC_ONLY,
        )
    selected, dyn_meta = dynamic_select_by_scores(
        ranked=reranked,
        max_chunks=max_chunks,
        std_weight=std_weight,
        abs_floor=DYNAMIC_ABS_FLOOR,
    )

    selected_ids = [c["id"] for c in selected]
    sim_stats = _sim_stats([float(c.get("semantic_sim", 0.0)) for c in selected])

    return {
        "mode": "rag",
        "meeting_type": meeting_type,
        "meeting_tokens": n_tokens,
        "chunk_source": chunk_source,
        "chunks": [{"id": c["id"], "text": c["text"]} for c in selected],
        "retrieved_chunk_ids": selected_ids,
        "system_prompt": RAG_SYSTEM_PROMPT,
        "context_text": build_rag_context(selected),
        "sim_stats": sim_stats,
        "metadata": {
            "retrieval_mode": "semantic_only" if not use_bm25 else "semantic_bm25_rrf",
            "rerank_enabled": SMART_V2_ENABLE_RERANK,
            "cross_encoder_available": rerank_method.startswith("cross_encoder:"),
            "cross_encoder_error": _CROSS_ENCODER_LAST_ERROR,
            "candidate_k": candidate_k,
            "max_chunks": max_chunks,
            "std_weight": std_weight,
            "rerank_method": rerank_method,
            "dynamic_threshold": dyn_meta["threshold"],
            "dynamic_mu": dyn_meta["mu"],
            "dynamic_sigma": dyn_meta["sigma"],
        },
    }


def answer_question(
    question: str,
    transcript: str,
    cache_id: str = "runtime",
    provider: str = "openai",
    reranker_model: str = "BAAI/bge-reranker-v2-m3",
) -> Dict:
    """
    应用入口：对单条问题执行 Smart 检索并调用 LLM 生成答案。
    返回结构兼容 app.py 中的问答展示逻辑。
    """
    from providers import chat_completion

    if not (question or "").strip():
        raise ValueError("问题不能为空")
    if not (transcript or "").strip():
        raise ValueError("会议文本不能为空")

    data_dir = Path("data/benchmark")
    out = retrieve_smart(
        question=question,
        transcript=transcript,
        data_dir=data_dir,
        transcript_path="transcript_runtime.txt",
        cache_id=cache_id,
        reranker_model=reranker_model,
    )

    prompt = (
        f"问题：{question}\n\n"
        f"会议片段：\n{out.get('context_text', '').strip()}\n\n"
        "请直接给出准确答案；如果片段不足以回答，明确说明无法回答。"
    )
    answer = chat_completion(
        provider_id=provider,
        system_prompt=RAG_SYSTEM_PROMPT,
        user_prompt=prompt,
        temperature=0.2,
    )

    chunks = out.get("chunks", []) or []
    sim_stats = out.get("sim_stats", {}) or {}
    total_chars = max(len(transcript), 1)
    covered_chars = sum(len(c.get("text", "")) for c in chunks)

    return {
        "answer": answer,
        "mode": out.get("mode", "rag"),
        "chunks": chunks,
        "metadata": {
            "method": out.get("metadata", {}).get("retrieval_mode", out.get("mode", "rag")),
            "reason": out.get("metadata", {}).get("reason", "smart_retrieval"),
            "chunks_count": len(chunks),
            "coverage": f"{covered_chars / total_chars:.2%}",
            "avg_similarity": f"{float(sim_stats.get('sim_avg', 0.0)):.4f}",
            "meeting_type": out.get("meeting_type", ""),
            "rerank_method": out.get("metadata", {}).get("rerank_method", ""),
            "dynamic_threshold": out.get("metadata", {}).get("dynamic_threshold", 0.0),
        },
    }
