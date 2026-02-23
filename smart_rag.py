"""
Smart RAG - 智能检索增强生成系统
结合多种优化技术，达到最佳问答效果
"""

import os
from typing import List, Dict, Tuple
from semantic_retrieval import (
    get_embedding,
    cosine_similarity,
    prepare_chunks_for_retrieval
)
from qa_utils import chunk_transcript

# ====================================
# 配置
# ====================================
# 自动决策：短会议直接用全文，长会议用RAG
SHORT_MEETING_THRESHOLD = 3000  # 字符数阈值
CHUNK_SIZE = 600  # 增大chunk，保留更多上下文
CHUNK_OVERLAP = 100  # 增大重叠
TOP_K_INITIAL = 12  # 初步检索更多候选


# ====================================
# 核心功能
# ====================================

def smart_retrieve(
    question: str,
    transcript: str,
    cache_id: str = None
) -> Tuple[List[Dict], str, dict]:
    """
    智能检索：自动选择最佳策略

    返回:
        (chunks, mode, metadata)
        - chunks: 检索到的内容块
        - mode: "full_text" 或 "rag"
        - metadata: 额外信息（用于调试和展示）
    """
    transcript_len = len(transcript)

    # 策略1: 短会议，直接用全文
    if transcript_len < SHORT_MEETING_THRESHOLD:
        return (
            [{"id": 0, "text": transcript}],
            "full_text",
            {
                "reason": f"会议较短（{transcript_len}字），使用全文",
                "method": "直接全文输入"
            }
        )

    # 策略2: 长会议，使用优化的RAG
    # 2.1 切分chunks（更大的chunk保留更多上下文）
    chunks = chunk_transcript(transcript, chunk_size_chars=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

    # 2.2 语义检索
    try:
        chunks_embeddings = prepare_chunks_for_retrieval(chunks, cache_id=cache_id, use_cache=True)
        question_embedding = get_embedding(question)

        # 计算相似度
        similarities = []
        for i, chunk_emb in enumerate(chunks_embeddings):
            sim = cosine_similarity(question_embedding, chunk_emb)
            similarities.append((sim, chunks[i]))

        # 排序并取Top-K
        similarities.sort(key=lambda x: x[0], reverse=True)

        # 动态Top-K: 根据相似度阈值决定
        selected = []
        for sim, chunk in similarities[:TOP_K_INITIAL]:
            # 相似度阈值：只保留相关的chunks
            if sim > 0.3 or len(selected) < 4:  # 至少保留4个
                selected.append(chunk)

        # 如果检索到的chunks覆盖率很低，补充更多
        total_retrieved_chars = sum(len(c['text']) for c in selected)
        coverage = total_retrieved_chars / transcript_len

        if coverage < 0.3:  # 覆盖率低于30%，增加chunks
            selected = [chunk for _, chunk in similarities[:min(15, len(similarities))]]

        return (
            selected,
            "rag",
            {
                "reason": f"会议较长（{transcript_len}字），使用语义检索",
                "method": "语义向量检索",
                "chunks_count": len(selected),
                "coverage": f"{coverage*100:.1f}%",
                "avg_similarity": f"{sum(s for s, _ in similarities[:len(selected)])/len(selected):.2f}"
            }
        )

    except Exception as e:
        # 回退：如果语义检索失败，用全文
        return (
            [{"id": 0, "text": transcript}],
            "full_text",
            {
                "reason": f"语义检索失败，回退到全文: {e}",
                "method": "全文输入（回退）"
            }
        )


def build_smart_prompt(question: str, chunks: List[Dict], mode: str) -> str:
    """
    构建优化的Prompt

    改进点：
    1. 更自然的提示词
    2. 鼓励LLM综合推理
    3. 要求引用证据，但不强制
    """

    if mode == "full_text":
        # 全文模式：直接对话
        return f"""你是一个专业的会议助手。请基于以下会议内容回答用户的问题。

会议内容：
{chunks[0]['text']}

用户问题：
{question}

请提供准确、简洁的回答。如果可以，请引用会议中的关键信息。
"""

    else:
        # RAG模式：提供检索到的证据块
        evidence_blocks = []
        for chunk in chunks:
            evidence_blocks.append(f"[片段 {chunk['id']}]\n{chunk['text']}\n")

        context = "\n".join(evidence_blocks)

        return f"""你是一个专业的会议助手。请基于以下会议片段回答用户的问题。

会议相关片段（按相关度排序）：
{context}

用户问题：
{question}

回答要求：
1. 基于上述片段提供准确、有用的回答
2. 如果片段中信息充足，直接回答
3. 如果片段中信息不足，说明需要更多信息
4. 尽可能引用片段中的关键信息（例如："根据片段X，..."）

请提供你的回答：
"""


def answer_question(
    question: str,
    transcript: str,
    cache_id: str = None,
    provider: str | None = None,
) -> dict:
    """
    智能问答主函数。
    provider 为空时使用环境变量 LLM_PROVIDER（默认 openai）。

    返回:
    {
        "answer": "回答内容",
        "mode": "full_text" 或 "rag",
        "chunks": [...],
        "metadata": {...}
    }
    """
    from providers import chat_completion

    pid = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()

    # 1. 智能检索
    chunks, mode, metadata = smart_retrieve(question, transcript, cache_id)

    # 2. 构建prompt
    prompt = build_smart_prompt(question, chunks, mode)

    # 3. 调用当前选中的 LLM 提供商
    answer = chat_completion(
        provider_id=pid,
        system_prompt="你是一个专业、准确的会议助手。",
        user_prompt=prompt,
        temperature=0.3,
    )

    return {
        "answer": answer,
        "mode": mode,
        "chunks": chunks,
        "metadata": metadata
    }


# ====================================
# 便捷函数（用于测试）
# ====================================

def test_smart_rag():
    """测试Smart RAG"""

    # 短会议测试
    short_transcript = """
今天的会议主要讨论了项目的进展情况。
张三负责前端开发，目前完成了70%，预计下周五完成。
李四负责后端API，已经完成了用户认证模块。
    """.strip()

    # 长会议测试
    long_transcript = """
今天的会议主要讨论了项目的进展情况和下一步计划。

首先，张三汇报了前端开发的进度。目前已经完成了70%的工作，包括：
1. 用户登录界面（已完成）
2. 仪表盘页面（已完成）
3. 数据可视化组件（进行中）
4. 移动端适配（待开始）

张三提到，数据可视化组件比预期复杂，可能需要额外2天时间。预计整体在下周五前完成所有前端工作。

接着，李四说明了后端API的开发状态。目前已完成的模块包括：
1. 用户认证系统（已完成并测试）
2. 数据库连接层（已完成）
3. RESTful API框架（已完成）
4. 数据查询接口（进行中）

李四表示，用户认证模块已经过充分测试，安全性没有问题。数据查询接口预计本周内完成。

王五负责项目管理和PPT制作。他提到下周需要向客户进行演示，因此本周五前需要完成演示PPT。
PPT需要包含：
- 项目整体进度
- 核心功能演示
- 技术架构说明
- 下一步计划

会议最后，大家讨论了一些风险点：
1. 数据可视化组件的复杂度可能影响进度
2. 移动端适配时间可能不足
3. 演示环境的稳定性需要提前测试

为了应对这些风险，团队决定：
- 张三优先完成核心可视化功能，复杂功能放到V2
- 如果时间紧张，移动端先做基础适配
- 王五协调测试环境，确保演示当天不出问题

大家一致认为项目进展顺利，有信心按时完成。
    """.strip()

    questions = [
        "谁负责前端开发？",
        "前端什么时候完成？",
        "有哪些风险？",
        "团队如何应对风险？"
    ]

    print("=" * 80)
    print("Smart RAG 测试")
    print("=" * 80)

    for transcript, name in [(short_transcript, "短会议"), (long_transcript, "长会议")]:
        print(f"\n{'='*80}")
        print(f"测试场景: {name} ({len(transcript)}字)")
        print(f"{'='*80}\n")

        for question in questions:
            print(f"问题: {question}")

            try:
                result = answer_question(question, transcript, cache_id=f"test_{name}")

                print(f"模式: {result['mode']}")
                print(f"元数据: {result['metadata']}")
                print(f"回答: {result['answer'][:100]}...")
                print()

            except Exception as e:
                print(f"错误: {e}")
                print()


if __name__ == "__main__":
    test_smart_rag()