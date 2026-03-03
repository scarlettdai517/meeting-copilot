#!/usr/bin/env python3
"""
统一基准脚本：同一轮同时评估传统 RAG 与 Smart RAG（仅检索，不调用 LLM）。

输出：
- 一个统一 CSV：benchmark_traditional_vs_smart_rag_<ts>.csv
- 一个统一 MD： benchmark_traditional_vs_smart_rag_<ts>.md
"""

import argparse
import csv
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", message=".*google.generativeai.*", category=FutureWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

DATA_DIR = PROJECT_ROOT / "data" / "benchmark"
DEFAULT_OUTPUT_DIR = DATA_DIR / "reports"


def load_transcript(data_dir: Path, transcript_path: str) -> str:
    path = data_dir / transcript_path
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    lines = text.split("\n")
    while lines and lines[0].strip().startswith("#"):
        lines.pop(0)
    return "\n".join(lines).strip()


def compute_metrics(retrieved_ids: list, relevant_ids: list) -> dict:
    rel = set(relevant_ids)
    ret = set(retrieved_ids)
    tp = len(ret & rel)
    recall = tp / len(rel) if rel else 0.0
    precision = tp / len(ret) if ret else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "tp": tp,
    }


def choose_default_gt(use_prod: bool) -> tuple[Path, Path]:
    if use_prod:
        return DATA_DIR / "ground_truth_long.json", DATA_DIR / "ground_truth_short.json"
    return DATA_DIR / "ground_truth_long_test.json", DATA_DIR / "ground_truth_short_test.json"


def run_traditional(question: str, transcript: str, transcript_path: str, cache_id: str) -> dict:
    from smart_rag import retrieve_traditional

    return retrieve_traditional(
        question=question,
        transcript=transcript,
        data_dir=DATA_DIR,
        transcript_path=transcript_path,
        cache_id=cache_id,
        top_k=5,
    )


def run_smart(question: str, transcript: str, transcript_path: str, cache_id: str, reranker_model: str) -> dict:
    from smart_rag import retrieve_smart

    return retrieve_smart(
        question=question,
        transcript=transcript,
        data_dir=DATA_DIR,
        transcript_path=transcript_path,
        cache_id=cache_id,
        reranker_model=reranker_model,
    )


def build_row(method: str, session_name: str, question: str, relevant_ids: list, transcript: str, out: dict) -> dict:
    mode = out.get("mode", "rag")
    retrieved_ids = out.get("retrieved_chunk_ids", [])
    if method == "smart" and mode == "full_text":
        # 与历史规则一致：超短全文按 1.0 计
        m = {"recall": 1.0, "precision": 1.0, "f1": 1.0, "tp": len(set(relevant_ids))}
    else:
        m = compute_metrics(retrieved_ids, relevant_ids)

    sim_stats = out.get("sim_stats", {})
    meta = out.get("metadata", {}) or {}
    coverage = (sum(len(c.get("text", "")) for c in out.get("chunks", [])) / len(transcript)) if transcript else 0.0

    return {
        "method": method,
        "session": session_name,
        "question": question,
        "mode": mode,
        "meeting_type": out.get("meeting_type", ""),
        "chunk_source": out.get("chunk_source", ""),
        "retrieval_mode": meta.get("retrieval_mode", ""),
        "rerank_enabled": meta.get("rerank_enabled", ""),
        "cross_encoder_available": meta.get("cross_encoder_available", ""),
        "cross_encoder_error": meta.get("cross_encoder_error", ""),
        "rerank_method": meta.get("rerank_method", ""),
        "std_weight": meta.get("std_weight", ""),
        "dynamic_threshold": meta.get("dynamic_threshold", 0.0),
        "coverage": coverage,
        "chunks_count": len(out.get("chunks", [])),
        "recall": m["recall"],
        "precision": m["precision"],
        "f1": m["f1"],
        "tp": m["tp"],
        "num_relevant": len(set(relevant_ids)),
        "sim_max": sim_stats.get("sim_max", 0.0),
        "sim_min": sim_stats.get("sim_min", 0.0),
        "sim_avg": sim_stats.get("sim_avg", 0.0),
    }


def avg_metric(rows: list[dict], key: str) -> float:
    if not rows:
        return 0.0
    return sum(r[key] for r in rows) / len(rows)


def main():
    parser = argparse.ArgumentParser(description="统一跑分：传统 RAG vs Smart RAG")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="报告输出目录")
    parser.add_argument("--long-only", action="store_true", help="只跑长会议")
    parser.add_argument("--short-only", action="store_true", help="只跑短会议")
    parser.add_argument("--use-prod", action="store_true", help="改为使用非 test 的 ground truth（默认使用 *_test）")
    parser.add_argument("--gt-long", type=Path, default=None, help="自定义 long ground truth 路径")
    parser.add_argument("--gt-short", type=Path, default=None, help="自定义 short ground truth 路径")
    parser.add_argument(
        "--reranker-model",
        type=str,
        default="BAAI/bge-reranker-v2-m3",
        help="Smart RAG 使用的 cross-encoder 模型名",
    )
    args = parser.parse_args()

    d_long, d_short = choose_default_gt(args.use_prod)
    gt_long_path = args.gt_long or d_long
    gt_short_path = args.gt_short or d_short

    to_run = []
    if not args.short_only and gt_long_path.is_file():
        to_run.append(("long", gt_long_path))
    if not args.long_only and gt_short_path.is_file():
        to_run.append(("short", gt_short_path))
    if not to_run:
        print("错误：未找到可运行的 ground truth 文件")
        sys.exit(1)

    all_rows = []

    for session_name, gt_path in to_run:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        transcript_path = gt.get("transcript_path", f"transcript_{session_name}.txt")
        transcript = load_transcript(DATA_DIR, transcript_path)
        if not transcript:
            print(f"跳过 {session_name}: transcript 为空 {transcript_path}")
            continue

        questions = gt.get("questions", [])
        cache_seed = abs(hash(transcript[:2000])) % 100000
        print(f"\n===== {session_name}（{len(questions)}题） =====")
        print(f"GT: {gt_path.name} | transcript: {transcript_path}\n")

        for i, item in enumerate(questions):
            q = item.get("question", "")
            relevant_ids = item.get("relevant_chunk_ids", [])
            print(f"[{i+1}/{len(questions)}] {q[:45]}...")

            try:
                trad_out = run_traditional(
                    question=q,
                    transcript=transcript,
                    transcript_path=transcript_path,
                    cache_id=f"bench_trad_{session_name}_{cache_seed}",
                )
                trad_row = build_row(
                    method="traditional",
                    session_name=session_name,
                    question=q,
                    relevant_ids=relevant_ids,
                    transcript=transcript,
                    out=trad_out,
                )
                all_rows.append(trad_row)
                print(
                    f"  [traditional] recall={trad_row['recall']:.2%} "
                    f"precision={trad_row['precision']:.2%} f1={trad_row['f1']:.2%} "
                    f"chunks={trad_row['chunks_count']}"
                )
            except Exception as e:
                print(f"  [traditional] 失败: {e}")

            try:
                smart_out = run_smart(
                    question=q,
                    transcript=transcript,
                    transcript_path=transcript_path,
                    cache_id=f"bench_smart_{session_name}_{cache_seed}",
                    reranker_model=args.reranker_model,
                )
                smart_row = build_row(
                    method="smart",
                    session_name=session_name,
                    question=q,
                    relevant_ids=relevant_ids,
                    transcript=transcript,
                    out=smart_out,
                )
                all_rows.append(smart_row)
                print(
                    f"  [smart]       recall={smart_row['recall']:.2%} "
                    f"precision={smart_row['precision']:.2%} f1={smart_row['f1']:.2%} "
                    f"chunks={smart_row['chunks_count']}"
                )
            except Exception as e:
                print(f"  [smart]       失败: {e}")

            print()

    if not all_rows:
        print("无有效结果")
        sys.exit(0)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = args.output_dir / f"benchmark_traditional_vs_smart_rag_{ts}.csv"
    md_path = args.output_dir / f"benchmark_traditional_vs_smart_rag_{ts}.md"

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "method",
                "session",
                "question",
                "mode",
                "meeting_type",
                "chunk_source",
                "retrieval_mode",
                "rerank_enabled",
                "cross_encoder_available",
                "cross_encoder_error",
                "rerank_method",
                "std_weight",
                "dynamic_threshold",
                "coverage_pct",
                "chunks_count",
                "recall",
                "precision",
                "f1",
                "tp",
                "num_relevant",
                "sim_max",
                "sim_min",
                "sim_avg",
            ]
        )
        for r in all_rows:
            w.writerow(
                [
                    r["method"],
                    r["session"],
                    r["question"],
                    r["mode"],
                    r["meeting_type"],
                    r["chunk_source"],
                    r["retrieval_mode"],
                    r["rerank_enabled"],
                    r["cross_encoder_available"],
                    r["cross_encoder_error"],
                    r["rerank_method"],
                    r["std_weight"],
                    f"{r['dynamic_threshold']:.4f}" if isinstance(r["dynamic_threshold"], (float, int)) else "",
                    round(r["coverage"] * 100, 2),
                    r["chunks_count"],
                    f"{r['recall']:.4f}",
                    f"{r['precision']:.4f}",
                    f"{r['f1']:.4f}",
                    r["tp"],
                    r["num_relevant"],
                    f"{r['sim_max']:.4f}",
                    f"{r['sim_min']:.4f}",
                    f"{r['sim_avg']:.4f}",
                ]
            )
    print(f"CSV 已写入: {csv_path}")

    lines = [
        "# 传统 RAG vs Smart RAG 基准报告（统一脚本）",
        f"生成时间: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "- 本报告由 `scripts/benchmark_traditional_vs_smart_rag.py` 生成",
        "- 传统：语义 top-5（按会议类型分块）",
        "- Smart：短会语义+BM25+RRF+rerank+动态K；长会语义+rerkank+动态K",
        "",
        "| 方法 | 会议 | 问题 | 块数 | Recall | Precision | F1 |",
        "|------|------|------|------|--------|-----------|----|",
    ]
    for r in all_rows:
        q_short = r["question"][:28] + ("..." if len(r["question"]) > 28 else "")
        lines.append(
            "| {} | {} | {} | {} | {:.2%} | {:.2%} | {:.2%} |".format(
                r["method"],
                r["session"],
                q_short,
                r["chunks_count"],
                r["recall"],
                r["precision"],
                r["f1"],
            )
        )

    lines.append("")
    lines.append("## 汇总（方法 x 会议）")
    for method in ("traditional", "smart"):
        for session in ("long", "short"):
            subset = [r for r in all_rows if r["method"] == method and r["session"] == session]
            if not subset:
                continue
            lines.append(
                f"- **{method} / {session}**（{len(subset)}题）："
                f"Recall={avg_metric(subset, 'recall'):.2%} "
                f"Precision={avg_metric(subset, 'precision'):.2%} "
                f"F1={avg_metric(subset, 'f1'):.2%} "
                f"覆盖率={avg_metric(subset, 'coverage') * 100:.1f}%"
            )

    lines.append("")
    lines.append("## 汇总（方法总体）")
    for method in ("traditional", "smart"):
        subset = [r for r in all_rows if r["method"] == method]
        if not subset:
            continue
        lines.append(
            f"- **{method}**（{len(subset)}题）："
            f"Recall={avg_metric(subset, 'recall'):.2%} "
            f"Precision={avg_metric(subset, 'precision'):.2%} "
            f"F1={avg_metric(subset, 'f1'):.2%} "
            f"覆盖率={avg_metric(subset, 'coverage') * 100:.1f}%"
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown 已写入: {md_path}")
    print("完成。")


if __name__ == "__main__":
    main()
