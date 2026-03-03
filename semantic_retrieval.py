"""
语义检索模块 - Advanced RAG 实现
使用 OpenAI Embeddings API 实现语义向量检索
"""

import os
import json
import hashlib
from typing import List, Dict
from openai import OpenAI
import numpy as np

# ====================================
# 配置
# ====================================
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI的最新小模型，便宜且快
CACHE_DIR = "data/embeddings_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


# ====================================
# Embedding 生成
# ====================================
def get_openai_client():
    """获取OpenAI客户端：优先用界面配置，再回退到环境变量"""
    try:
        from providers import get_provider_config
        c = get_provider_config("openai")
        api_key = (c.get("api_key") or "").strip()
        base_url = (c.get("base_url") or "").strip()
    except Exception:
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "")

    if not api_key:
        raise RuntimeError(
            "Smart RAG 的语义检索需要 OpenAI API Key。请在上方「配置当前模型 API」中选择 OpenAI 并填写 Key，或在 .env 中设置 OPENAI_API_KEY。"
        )

    return OpenAI(api_key=api_key, base_url=base_url or None)


def get_embedding(text: str) -> List[float]:
    """
    获取文本的embedding向量
    使用 text-embedding-3-small 模型
    """
    client = get_openai_client()

    # OpenAI建议先清理文本
    text = text.replace("\n", " ").strip()

    if not text:
        # 空文本返回零向量
        return [0.0] * 1536

    response = client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL
    )

    return response.data[0].embedding


def get_embeddings_batch(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """
    批量获取embeddings（节省API调用次数）
    OpenAI允许一次最多2048个文本
    """
    client = get_openai_client()

    # 清理文本
    texts = [text.replace("\n", " ").strip() for text in texts]

    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        response = client.embeddings.create(
            input=batch,
            model=EMBEDDING_MODEL
        )

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


# ====================================
# 缓存机制
# ====================================
def _get_cache_key(text: str) -> str:
    """生成文本的缓存key（MD5哈希）"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def save_embeddings_cache(chunks: List[Dict], embeddings: List[List[float]], cache_id: str):
    """
    保存embeddings到缓存
    cache_id: 通常用会议的file_id或transcript的hash
    """
    cache_file = os.path.join(CACHE_DIR, f"{cache_id}.json")

    cache_data = {
        "chunks": chunks,
        "embeddings": embeddings,
        "model": EMBEDDING_MODEL
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def load_embeddings_cache(cache_id: str) -> tuple[List[Dict], List[List[float]]] | None:
    """
    从缓存加载embeddings
    返回: (chunks, embeddings) 或 None
    """
    cache_file = os.path.join(CACHE_DIR, f"{cache_id}.json")

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        # 检查模型是否匹配
        if cache_data.get("model") != EMBEDDING_MODEL:
            return None

        return cache_data["chunks"], cache_data["embeddings"]
    except Exception:
        return None


# ====================================
# 向量相似度计算
# ====================================
def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算两个向量的余弦相似度"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    # 余弦相似度 = dot(A, B) / (||A|| * ||B||)
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


# ====================================
# 语义检索
# ====================================
def semantic_retrieve(
    question: str,
    chunks: List[Dict],
    chunks_embeddings: List[List[float]],
    top_k: int = 6,
    min_sim: float = None
) -> List[Dict]:
    """
    基于语义相似度检索最相关的chunks

    参数:
        question: 用户问题
        chunks: chunk列表 [{"id": 0, "text": "..."}, ...]
        chunks_embeddings: chunks对应的embeddings
        top_k: 返回top-k个结果
        min_sim: 可选；若给出则只保留相似度>=min_sim的块，再取前top_k个（不足则全返回）

    返回:
        List[Dict]: 按相似度排序的chunks
    """
    # 1. 获取问题的embedding
    question_embedding = get_embedding(question)

    # 2. 计算每个chunk的相似度
    similarities = []
    for i, chunk_emb in enumerate(chunks_embeddings):
        sim = cosine_similarity(question_embedding, chunk_emb)
        similarities.append((sim, chunks[i]))

    # 3. 按相似度降序排序
    similarities.sort(key=lambda x: x[0], reverse=True)

    # 4. 若设 min_sim 则先过滤再取 top_k
    if min_sim is not None:
        filtered = [item for item in similarities if item[0] >= min_sim]
        return [chunk for _, chunk in filtered[:top_k]]
    return [chunk for _, chunk in similarities[:top_k]]


# ====================================
# 混合检索（可选）
# ====================================
def hybrid_retrieve(
    question: str,
    chunks: List[Dict],
    chunks_embeddings: List[List[float]],
    keyword_retrieve_fn,
    top_k: int = 6,
    semantic_weight: float = 0.7
) -> List[Dict]:
    """
    混合检索：结合语义检索和关键词检索

    参数:
        question: 用户问题
        chunks: chunk列表
        chunks_embeddings: chunks对应的embeddings
        keyword_retrieve_fn: 关键词检索函数
        top_k: 返回top-k个结果
        semantic_weight: 语义检索权重（0-1），剩余为关键词权重

    返回:
        List[Dict]: 融合排序后的chunks
    """
    # 1. 语义检索
    semantic_results = semantic_retrieve(question, chunks, chunks_embeddings, top_k=top_k*2)

    # 2. 关键词检索
    keyword_results = keyword_retrieve_fn(question, chunks, top_k=top_k*2)

    # 3. 融合分数（RRF - Reciprocal Rank Fusion）
    chunk_scores = {}

    # 语义检索分数
    for rank, chunk in enumerate(semantic_results):
        chunk_id = chunk['id']
        # RRF公式: 1 / (rank + k)，k通常取60
        chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + semantic_weight * (1.0 / (rank + 60))

    # 关键词检索分数
    keyword_weight = 1.0 - semantic_weight
    for rank, chunk in enumerate(keyword_results):
        chunk_id = chunk['id']
        chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + keyword_weight * (1.0 / (rank + 60))

    # 4. 按融合分数排序
    scored_chunks = [(score, chunk) for chunk in chunks if chunk['id'] in chunk_scores
                     for score in [chunk_scores[chunk['id']]]]
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # 5. 返回Top-K
    return [chunk for _, chunk in scored_chunks[:top_k]]


# ====================================
# 便捷函数
# ====================================
def prepare_chunks_for_retrieval(
    chunks: List[Dict],
    cache_id: str | None = None,
    use_cache: bool = True
) -> List[List[float]]:
    """
    为chunks准备embeddings（支持缓存）

    参数:
        chunks: chunk列表
        cache_id: 缓存标识（如file_id）
        use_cache: 是否使用缓存

    返回:
        List[List[float]]: chunks对应的embeddings
    """
    # 1. 尝试从缓存加载
    if use_cache and cache_id:
        cached = load_embeddings_cache(cache_id)
        if cached:
            cached_chunks, cached_embeddings = cached
            # 验证chunks是否匹配
            if len(cached_chunks) == len(chunks) and all(
                c1['text'] == c2['text'] for c1, c2 in zip(cached_chunks, chunks)
            ):
                print(f"✓ 从缓存加载embeddings (cache_id: {cache_id})")
                return cached_embeddings

    # 2. 生成新的embeddings
    print(f"⏳ 生成 {len(chunks)} 个chunks的embeddings...")
    chunk_texts = [chunk['text'] for chunk in chunks]
    embeddings = get_embeddings_batch(chunk_texts)

    # 3. 保存到缓存
    if use_cache and cache_id:
        save_embeddings_cache(chunks, embeddings, cache_id)
        print(f"✓ Embeddings已缓存 (cache_id: {cache_id})")

    return embeddings
