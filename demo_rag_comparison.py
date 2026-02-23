#!/usr/bin/env python3
"""
RAG检索方法对比演示（无需API，模拟效果）
展示三种RAG方法在不同场景下的表现差异
"""

from qa_utils import chunk_transcript, keyword_retrieve, _tokenize

# 测试场景
print("""
╔═══════════════════════════════════════════════════════════════════════╗
║              RAG 检索方法对比演示                                        ║
║                                                                       ║
║  场景：会议转写中提到"张三负责前端开发"                                  ║
║  测试：用不同问法提问，看哪种RAG能找到答案                              ║
╚═══════════════════════════════════════════════════════════════════════╝
""")

# 测试数据
transcript = """
今天的会议主要讨论了项目的进展情况。
首先，张三汇报了前端开发的进度，目前完成了70%，预计下周五完成。
接着，李四说明了后端API的状态，已经完成了用户认证模块。
最后大家讨论了下周的演示准备工作，决定由王五负责PPT制作。
会议结束时，大家一致认为项目进展顺利。
"""

# 准备chunks
chunks = chunk_transcript(transcript, chunk_size_chars=250, overlap=50)

# 测试问题
test_questions = [
    ("谁负责前端开发？", "精确匹配", "🟢 容易"),
    ("前端工程师是谁？", "同义词（'工程师'不在原文）", "🟡 中等"),
    ("UI开发由谁负责？", "同义词（'UI'='前端'）", "🔴 困难"),
    ("谁在做前端？", "口语化表达", "🟡 中等"),
]

print("=" * 80)
print("原文内容：")
print("-" * 80)
print(transcript.strip())
print("=" * 80)
print()

for question, difficulty, level in test_questions:
    print("━" * 80)
    print(f"问题: {question}")
    print(f"难度: {difficulty} {level}")
    print("━" * 80)
    print()

    # ============================================
    # 1. 关键词检索 (Naive RAG)
    # ============================================
    print("1️⃣  关键词检索 (Naive RAG - 传统搜索)")
    print("-" * 80)

    # 显示分词结果
    q_tokens = _tokenize(question)
    print(f"   问题分词: {q_tokens}")

    # 检索
    retrieved = keyword_retrieve(question, chunks, top_k=3)

    if retrieved:
        print(f"   ✅ 检索成功！找到 {len(retrieved)} 个相关chunks")

        # 显示第一个chunk的匹配信息
        chunk_text = retrieved[0]['text']
        chunk_tokens = _tokenize(chunk_text)

        # 计算匹配的tokens
        q_set = set(q_tokens)
        c_set = set(chunk_tokens)
        matched = q_set & c_set

        print(f"   匹配的词: {list(matched)[:10]}")  # 只显示前10个
        print(f"   覆盖率: {len(matched)}/{len(q_set)} = {len(matched)/len(q_set)*100:.0f}%")
        print(f"   检索到内容: {chunk_text[:60]}...")
    else:
        print("   ❌ 检索失败！未找到相关内容")

    print()

    # ============================================
    # 2. 语义检索 (Advanced RAG) - 模拟
    # ============================================
    print("2️⃣  语义检索 (Advanced RAG - AI理解语义)")
    print("-" * 80)

    # 模拟语义相似度（基于我们对语义的理解）
    # 这里用规则模拟，真实情况是用Embedding计算
    semantic_scores = []

    for chunk in chunks:
        text = chunk['text'].lower()
        score = 0.0

        # 模拟语义理解规则
        if "谁负责" in question or "谁在做" in question:
            if "负责" in text or "汇报" in text:
                score += 0.3

        if "前端" in question or "ui" in question:
            if "前端" in text:
                score += 0.4

        if "工程师" in question or "开发" in question:
            if "开发" in text or "进度" in text:
                score += 0.3

        semantic_scores.append((score, chunk))

    semantic_scores.sort(key=lambda x: x[0], reverse=True)
    best_score = semantic_scores[0][0]

    if best_score > 0.5:
        print(f"   ✅ 语义匹配成功！相似度: {best_score:.2f}")
        print(f"   理解: 问题询问'谁' → 寻找包含人名和职责的段落")
        if "工程师" in question:
            print(f"   理解: '工程师' ≈ '开发' ≈ '负责'（同义词理解）")
        if "ui" in question.lower():
            print(f"   理解: 'UI' ≈ '前端'（领域知识）")
        print(f"   检索到内容: {semantic_scores[0][1]['text'][:60]}...")
    else:
        print(f"   ⚠️  语义匹配弱，相似度: {best_score:.2f}")

    print()

    # ============================================
    # 3. 混合检索 (Modular RAG) - 模拟
    # ============================================
    print("3️⃣  混合检索 (Modular RAG - 关键词+语义融合)")
    print("-" * 80)

    # 融合分数（70%语义 + 30%关键词）
    keyword_score = 1.0 if retrieved else 0.0
    hybrid_score = 0.7 * best_score + 0.3 * keyword_score

    print(f"   关键词检索: {'✅ 成功' if keyword_score > 0 else '❌ 失败'} (权重30%)")
    print(f"   语义检索: {best_score:.2f} (权重70%)")
    print(f"   融合得分: {hybrid_score:.2f}")

    if hybrid_score > 0.4:
        print(f"   ✅ 混合检索成功！")
        print(f"   优势: 即使单一方法失败，另一种方法也能补充")
    else:
        print(f"   ⚠️  混合检索置信度较低")

    print()
    print()


# ============================================
# 总结对比
# ============================================
print("=" * 80)
print("📊 三种RAG方法总结对比")
print("=" * 80)
print()

summary = """
┌─────────────────────────────────────────────────────────────────────────┐
│ 1️⃣  关键词检索 (Naive RAG)                                               │
├─────────────────────────────────────────────────────────────────────────┤
│ 工作原理: 分词 → 计算词重叠 → 排序                                        │
│ 优势: ✅ 快速（<100ms）、零成本、无依赖                                    │
│ 劣势: ❌ 不理解同义词、对改写不鲁棒                                        │
│ 适用: 原型验证、精确匹配场景                                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 2️⃣  语义检索 (Advanced RAG) ⭐ 推荐                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ 工作原理: Embedding向量化 → 计算余弦相似度 → 排序                         │
│ 优势: ✅ 理解语义、同义词匹配、对改写鲁棒                                  │
│ 劣势: ⚠️  需要API、有微小成本（<0.01元/会议）                              │
│ 适用: 生产环境、用户问法多样化                                            │
│ 示例: "前端工程师" ≈ "前端开发" ≈ "UI负责人"                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 3️⃣  混合检索 (Modular RAG)                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ 工作原理: 关键词检索 + 语义检索 → RRF融合排序                             │
│ 优势: ✅ 准确率最高、两种方法互补                                          │
│ 劣势: ⚠️  稍慢、实现复杂                                                   │
│ 适用: 关键业务、对准确率要求极高                                          │
└─────────────────────────────────────────────────────────────────────────┘
"""

print(summary)

print()
print("🎯 实际效果预测（同义词场景）：")
print()
print("  问题: '前端工程师是谁？'（原文是'前端开发'）")
print()
print("  关键词检索: 🟡 可能找到，但评分低（'工程师'不匹配）")
print("  语义检索:   🟢 能找到！（理解'工程师'≈'开发'）")
print("  混合检索:   🟢 能找到！（语义检索补充了关键词的不足）")
print()

print("=" * 80)
print("💡 建议：")
print("=" * 80)
print("""
1. 开发测试阶段: 使用关键词检索（快速、无成本）
2. 生产环境: 使用语义检索（准确、成本极低）⭐
3. 关键业务: 使用混合检索（最准确）

要体验真实的语义检索，请：
1. 设置环境变量: OPENAI_API_KEY=your_key
2. 重新运行: python test_rag_comparison.py
3. 或在Streamlit UI中选择 "🧠 语义（Advanced RAG）"
""")
