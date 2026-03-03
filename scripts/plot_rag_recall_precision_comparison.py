#!/usr/bin/env python3
"""
生成“Traditional -> Smart RAG”升级趋势图（长/短会 Recall & Precision）。
输出到: data/benchmark/reports/rag_recall_precision_comparison.png
"""

from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "data" / "benchmark" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "rag_recall_precision_comparison.png"

    x_labels = ["Traditional", "Smart RAG"]
    x = [0, 1]

    # 你的汇总数据（百分比）
    long_recall = [70.56, 93.33]
    long_precision = [40.00, 52.22]
    short_recall = [51.51, 70.71]
    short_precision = [50.00, 73.61]

    plt.figure(figsize=(10, 6))

    # 长会：蓝色系
    plt.plot(
        x, long_recall,
        color="#0B3D91", marker="o", linewidth=2.6, label="Long Recall"
    )
    plt.plot(
        x, long_precision,
        color="#76B7FF", marker="o", linewidth=2.6, label="Long Precision"
    )

    # 短会：红色系（Recall 浅红/粉色，Precision 深红）
    plt.plot(
        x, short_recall,
        color="#F6A5C0", marker="o", linewidth=2.6, label="Short Recall"
    )
    plt.plot(
        x, short_precision,
        color="#8B0000", marker="o", linewidth=2.6, label="Short Precision"
    )

    # 节点数值标注（百分比）
    def annotate_series(xs, ys, color, y_offset=1.2):
        for xi, yi in zip(xs, ys):
            plt.text(
                xi,
                yi + y_offset,
                f"{yi:.2f}%",
                color=color,
                fontsize=9,
                ha="center",
                va="bottom",
            )

    annotate_series(x, long_recall, "#0B3D91", y_offset=1.4)
    annotate_series(x, long_precision, "#76B7FF", y_offset=1.4)
    annotate_series(x, short_recall, "#F6A5C0", y_offset=-3.2)
    annotate_series(x, short_precision, "#8B0000", y_offset=1.4)

    plt.xticks(x, x_labels)
    plt.ylim(0, 100)
    plt.ylabel("Score (%)")
    plt.xlabel("RAG Strategy")
    plt.title("Recall & Precision Improvement from Traditional to Smart RAG")
    plt.grid(alpha=0.25, linestyle="--")
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()

    print(f"图已生成: {out_path}")


if __name__ == "__main__":
    main()
