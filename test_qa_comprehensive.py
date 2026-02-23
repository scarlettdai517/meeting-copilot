#!/usr/bin/env python3
# 全面测试 QA 检索功能

from qa_utils import chunk_transcript, keyword_retrieve, _tokenize

# 测试用例集
test_cases = [
    {
        "name": "简单短文本",
        "transcript": "今天的会议是关于RAG的，我们来测试一下上次的功能，下周要展示了",
        "questions": [
            "今天的会议是关于什么的？",
            "什么时候展示？",
            "要测试什么？"
        ]
    },
    {
        "name": "较长文本（多段落）",
        "transcript": """
今天的会议主要讨论了项目的进展情况。
首先，张三汇报了前端开发的进度，目前完成了70%，预计下周五完成。
接着，李四说明了后端API的状态，已经完成了用户认证模块。
最后大家讨论了下周的演示准备工作，决定由王五负责PPT制作。
        """.strip(),
        "questions": [
            "谁负责前端开发？",
            "后端完成了什么模块？",
            "谁负责PPT制作？",
            "前端什么时候完成？"
        ]
    },
    {
        "name": "包含英文和数字",
        "transcript": "我们讨论了使用GPT-4和Claude的API，预算是5000美元，deadline是2025年3月15日",
        "questions": [
            "预算是多少？",
            "deadline是什么时候？",
            "使用了哪些API？"
        ]
    }
]

def run_tests():
    for test_case in test_cases:
        print("=" * 70)
        print(f"测试: {test_case['name']}")
        print("=" * 70)
        print(f"转写文本: {test_case['transcript'][:100]}...")
        print()

        # Chunking
        chunks = chunk_transcript(test_case['transcript'])
        print(f"生成了 {len(chunks)} 个 chunks")
        for ch in chunks:
            print(f"  - Chunk {ch['id']}: {ch['text'][:60]}...")
        print()

        # 测试每个问题
        for question in test_case['questions']:
            print(f"问题: {question}")

            # 检索
            retrieved = keyword_retrieve(question, chunks, top_k=3)

            if retrieved:
                print(f"✓ 检索到 {len(retrieved)} 个相关chunks:")
                for ch in retrieved:
                    print(f"    - Chunk {ch['id']}: {ch['text'][:50]}...")
            else:
                print("✗ 没有检索到相关内容")

            print()

        print()

if __name__ == "__main__":
    run_tests()