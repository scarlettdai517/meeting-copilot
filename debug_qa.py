#!/usr/bin/env python3
# 调试 QA 检索功能

from qa_utils import chunk_transcript, keyword_retrieve, _tokenize

# 测试数据
transcript = "今天的会议是关于RAG的，我们来测试一下上次的功能，下周要展示了"
question = "今天的会议是关于什么的？"

print("=" * 60)
print("测试用例")
print("=" * 60)
print(f"转写文本: {transcript}")
print(f"问题: {question}")
print()

# 1. 测试 tokenize
print("=" * 60)
print("1. Tokenize 测试")
print("=" * 60)
q_tokens = _tokenize(question)
t_tokens = _tokenize(transcript)
print(f"问题 tokens: {q_tokens}")
print(f"转写 tokens: {t_tokens}")
print()

# 2. 测试 chunking
print("=" * 60)
print("2. Chunking 测试")
print("=" * 60)
chunks = chunk_transcript(transcript, chunk_size_chars=200, overlap=50)
print(f"Chunks 数量: {len(chunks)}")
for ch in chunks:
    print(f"  - Chunk {ch['id']}: {ch['text'][:50]}...")
print()

# 3. 测试检索
print("=" * 60)
print("3. 检索测试")
print("=" * 60)
retrieved = keyword_retrieve(question, chunks, top_k=4)
print(f"检索到的 chunks 数量: {len(retrieved)}")
for ch in retrieved:
    print(f"  - Chunk {ch['id']}: {ch['text']}")
print()

# 4. 分析为什么检索不到
print("=" * 60)
print("4. 问题分析")
print("=" * 60)
q_set = set(q_tokens)
print(f"问题 token 集合: {q_set}")
print()

for ch in chunks:
    ch_tokens = _tokenize(ch['text'])
    ch_set = set(ch_tokens)
    print(f"Chunk {ch['id']} tokens: {ch_tokens}")
    print(f"Chunk {ch['id']} token 集合: {ch_set}")

    # 计算交集
    intersection = q_set & ch_set
    print(f"交集: {intersection}")

    # 计算score
    t_counter = {}
    for tok in ch_tokens:
        t_counter[tok] = t_counter.get(tok, 0) + 1

    hits = sum(t_counter.get(tok, 0) for tok in q_set)
    coverage = sum(1 for tok in q_set if tok in t_counter) / max(1, len(q_set))
    score = hits + 2.0 * coverage

    print(f"Hits: {hits}, Coverage: {coverage:.2f}, Score: {score:.2f}")
    print()
