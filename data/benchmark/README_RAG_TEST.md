# RAG 跑分说明（test 数据）

本说明对应当前唯一跑分脚本：

- `smart_rag.py`：检索核心
- `scripts/benchmark_traditional_vs_smart_rag.py`

## 1) 策略摘要

### 传统 RAG（基线）
- 分块按会议类型：
  - 长会：`512/100`
  - 其他（含短会/超短）：`256/50`
- 检索：语义相似度 `top-5`
- 无动态阈值、无动态 top-k
- 固定系统提示词：`基于以下会议片段回答问题，如果片段中无相关信息，请说明无法回答。`
- 指标：Recall / Precision / F1 + 相似度 max/min/avg

### Smart RAG（升级版）
- 超短：`<3000 token` 直接全文（评估记为 Recall=Precision=F1=1）
- 短会：
  - 语义 top-12 + BM25 top-12
  - RRF 合并
  - rerank（优先 cross-encoder，失败回退启发式）
  - 动态阈值：`threshold=max(mu-0.2*sigma, 0.30)`，最多 6 块
- 长会：
  - 语义 top-15（默认不启用 BM25）+ rerank
  - 动态阈值：`threshold=max(mu-0.4*sigma, 0.30)`，最多 6 块

## 2) 数据与对齐

test 数据文件：
- `ground_truth_long_test.json`
- `ground_truth_short_test.json`

脚本会优先复用同名 `chunks_*.json`（如 `chunks_long_test.json` / `chunks_short_test.json`）来保证 chunk id 空间与 GT 对齐。

## 3) 运行命令

在项目根目录执行（默认使用 `*_test` 文件）：

```bash
python scripts/benchmark_traditional_vs_smart_rag.py
```

如果只跑短会：

```bash
python scripts/benchmark_traditional_vs_smart_rag.py --short-only
```

如果只跑长会：

```bash
python scripts/benchmark_traditional_vs_smart_rag.py --long-only
```

如果要切回旧数据（非 test）：

```bash
python scripts/benchmark_traditional_vs_smart_rag.py --use-prod
```

## 4) 报告输出

默认输出目录：`data/benchmark/reports/`

- 统一报告：`benchmark_traditional_vs_smart_rag_<ts>.csv/.md`

## 5) 依赖说明

- 必需：`openai`（语义 embedding）、`numpy`
- 建议：`jieba`（更好的中文 BM25 分词）
- 可选：`sentence-transformers`（启用 cross-encoder rerank）

未安装 `sentence-transformers` 时，Smart RAG 会自动回退到启发式重排，不会阻塞跑分。
