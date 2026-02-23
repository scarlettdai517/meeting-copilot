#!/usr/bin/env python3
"""
RAG检索方法对比测试
对比三种检索方式：关键词、语义、混合
"""

from qa_utils import chunk_transcript, keyword_retrieve
from semantic_retrieval import semantic_retrieve, hybrid_retrieve, prepare_chunks_for_retrieval

# 测试用例
TEST_CASES = [
    {
        "name": "同义词测试",
        "transcript": """
今天的会议主要讨论了项目的进展情况。
首先，张三汇报了前端开发的进度，目前完成了70%，预计下周五完成。
接着，李四说明了后端API的状态，已经完成了用户认证模块。
最后大家讨论了下周的演示准备工作，决定由王五负责PPT制作。
        """.strip(),
        "questions": [
            ("谁负责前端开发？", "精确匹配"),
            ("前端工程师是谁？", "同义词测试 - '工程师'不在原文"),
            ("UI开发由谁负责？", "同义词测试 - 'UI'='前端'"),
        ]
    },
    {
        "name": "语义理解测试",
        "transcript": """
会议决定将产品发布日期从3月15日推迟到4月1日。
主要原因是测试团队发现了一些严重的性能问题，需要额外的时间来修复。
市场部对这个延期表示理解，但建议我们尽快完成，因为竞争对手也在准备类似产品。
        """.strip(),
        "questions": [
            ("产品什么时候发布？", "精确匹配"),
            ("为什么要延期？", "需要理解'延期'='推迟'"),
            ("市场部的态度是什么？", "需要理解语义和总结"),
        ]
    },
    {
        "name": "改写鲁棒性测试",
        "transcript": """
张三负责前端开发，预计下周五完成。
李四负责后端API，已经完成了用户认证模块。
王五负责PPT制作。
        """.strip(),
        "questions": [
            ("谁负责前端？", "简短问法"),
            ("前端开发的负责人是谁？", "正式问法"),
            ("前端由哪位同事负责？", "口语化问法"),
            ("谁在做前端？", "极简问法"),
        ]
    }
]


def test_retrieval_comparison():
    """对比三种检索方法"""

    for test_case in TEST_CASES:
        print("=" * 80)
        print(f"测试场景: {test_case['name']}")
        print("=" * 80)
        print(f"转写文本: {test_case['transcript'][:100]}...")
        print()

        # 准备chunks
        chunks = chunk_transcript(test_case['transcript'], chunk_size_chars=250, overlap=50)
        print(f"生成了 {len(chunks)} 个chunks")

        # 准备embeddings（仅用于语义检索）
        print("⏳ 生成embeddings（仅首次需要）...")
        try:
            chunks_embeddings = prepare_chunks_for_retrieval(
                chunks,
                cache_id=f"test_{test_case['name']}",
                use_cache=True
            )
            semantic_available = True
        except Exception as e:
            print(f"⚠️ 语义检索不可用: {e}")
            semantic_available = False

        print()

        # 测试每个问题
        for question, description in test_case['questions']:
            print("-" * 80)
            print(f"问题: {question}")
            print(f"难度: {description}")
            print()

            # 1. 关键词检索
            print("1️⃣ 关键词检索（Naive RAG）:")
            keyword_results = keyword_retrieve(question, chunks, top_k=3)
            if keyword_results:
                print(f"   ✓ 检索到 {len(keyword_results)} 个chunks")
                for i, ch in enumerate(keyword_results[:2]):  # 只显示前2个
                    print(f"   - Top{i+1}: {ch['text'][:60]}...")
            else:
                print("   ✗ 未检索到相关内容")
            print()

            # 2. 语义检索
            if semantic_available:
                print("2️⃣ 语义检索（Advanced RAG）:")
                semantic_results = semantic_retrieve(question, chunks, chunks_embeddings, top_k=3)
                if semantic_results:
                    print(f"   ✓ 检索到 {len(semantic_results)} 个chunks")
                    for i, ch in enumerate(semantic_results[:2]):
                        print(f"   - Top{i+1}: {ch['text'][:60]}...")
                else:
                    print("   ✗ 未检索到相关内容")
                print()

                # 3. 混合检索
                print("3️⃣ 混合检索（Modular RAG）:")
                hybrid_results = hybrid_retrieve(
                    question, chunks, chunks_embeddings,
                    keyword_retrieve_fn=keyword_retrieve,
                    top_k=3
                )
                if hybrid_results:
                    print(f"   ✓ 检索到 {len(hybrid_results)} 个chunks")
                    for i, ch in enumerate(hybrid_results[:2]):
                        print(f"   - Top{i+1}: {ch['text'][:60]}...")
                else:
                    print("   ✗ 未检索到相关内容")
                print()

        print("\n")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    RAG检索方法对比测试                                        ║
║                                                                            ║
║  对比三种检索方式:                                                           ║
║  1. 关键词检索 (Naive RAG)      - 传统关键词匹配                             ║
║  2. 语义检索 (Advanced RAG)     - OpenAI Embeddings向量相似度               ║
║  3. 混合检索 (Modular RAG)      - 关键词+语义融合排序                        ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        test_retrieval_comparison()
        print("✅ 测试完成！")
        print("\n总结:")
        print("- 关键词检索: 快速但可能漏掉同义词/改写")
        print("- 语义检索: 理解语义，对改写鲁棒，但需要API调用")
        print("- 混合检索: 结合两者优势，准确率最高")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()