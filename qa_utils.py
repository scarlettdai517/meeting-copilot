# qa_utils.py
import re
from typing import List, Dict, Tuple
from collections import Counter

# 中文停用词（常见的无意义词）
CHINESE_STOPWORDS = set([
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '什么', '吗', '呢', '啊', '吧'
])

def _tokenize(text: str) -> List[str]:
    """
    改进的分词策略（轻量级）：
    - 英文/数字：按单词切分
    - 中文：按单个字符切分（提高召回率）
    - 移除停用词（提高精确度）
    """
    text = text.lower()
    tokens = []

    # 提取英文单词和数字
    for match in re.finditer(r"[a-z0-9]+", text):
        tokens.append(match.group())

    # 提取中文字符（每个汉字都是一个token）
    for match in re.finditer(r"[\u4e00-\u9fff]", text):
        char = match.group()
        # 过滤停用词
        if char not in CHINESE_STOPWORDS:
            tokens.append(char)

    return tokens

def chunk_transcript(transcript: str, chunk_size_chars: int = 250, overlap: int = 50) -> List[Dict]:
    """
    把长转写切成小块，便于检索 + 引用。
    默认: 每段约250字（200-300字范围），overlap 50字
    返回: [{id, text}]
    """
    t = transcript.strip()
    if not t:
        return []

    chunks = []
    start = 0
    cid = 0
    n = len(t)
    while start < n:
        end = min(n, start + chunk_size_chars)
        chunk = t[start:end]
        chunks.append({"id": cid, "text": chunk})
        cid += 1
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def keyword_retrieve(query: str, chunks: List[Dict], top_k: int = 6) -> List[Dict]:
    """
    轻量级关键词检索：
    1. 计算 query tokens 和 chunk tokens 的重叠度
    2. 使用 TF（词频）加权
    3. 考虑覆盖率（query中有多少词在chunk中出现）

    评分公式：
    - coverage: query中有多少比例的词在chunk中出现（重要！）
    - tf_score: 匹配词在chunk中的总出现次数（频率）
    - final_score = coverage * 10 + tf_score
    """
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scored = []
    q_counter = Counter(q_tokens)
    q_set = set(q_tokens)

    for ch in chunks:
        text = ch["text"]
        t_tokens = _tokenize(text)
        if not t_tokens:
            continue

        t_counter = Counter(t_tokens)

        # 1. Coverage: query中有多少比例的词在chunk中找到
        matched_q_tokens = sum(1 for tok in q_set if tok in t_counter)
        coverage = matched_q_tokens / len(q_set) if q_set else 0

        # 2. TF Score: 匹配的词在chunk中的总频率
        tf_score = sum(min(q_counter[tok], t_counter[tok]) for tok in q_set if tok in t_counter)

        # 3. 综合评分（coverage更重要）
        score = coverage * 10.0 + tf_score

        if score > 0:
            scored.append((score, ch))

    # 按分数降序排序
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in scored[:top_k]]

def build_qa_prompt(question: str, retrieved_chunks: List[Dict]) -> str:
    """
    让模型：只根据证据回答；不确定就说不知道；并输出 Evidence 引用。
    """
    context_blocks = []
    for ch in retrieved_chunks:
        # 给每块一个编号，方便模型引用
        context_blocks.append(f"[Evidence {ch['id']}]\n{ch['text']}\n")

    context = "\n".join(context_blocks) if context_blocks else "(no evidence)"
    prompt = f"""
You are a meeting QA assistant.

Rules:
- Answer ONLY using the evidence blocks below.
- If the evidence is insufficient, say you don't know.
- Keep the answer concise and actionable.
- Always return two parts:
  1) Answer
  2) Evidence: list the Evidence IDs you used

Question:
{question}

Evidence blocks:
{context}
"""
    return prompt.strip()
