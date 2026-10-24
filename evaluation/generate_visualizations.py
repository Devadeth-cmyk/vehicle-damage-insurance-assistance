"""Create clean SVG charts from evaluation/model_metrics.json.

Run from the repository root:
    python evaluation/generate_visualizations.py

This intentionally uses only the Python standard library so the figures can be
regenerated without installing plotting packages. Inputs are recorded notebook
validation metrics; see MODEL_EVALUATION.md for provenance and caveats.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "visualizations"
WIDTH = 1200
FONT = "Inter, Segoe UI, Arial, sans-serif"
INK = "#12233f"
MUTED = "#64748b"
GRID = "#e2e8f0"
BLUE = "#0788c9"
TEAL = "#10a37f"
PURPLE = "#7157d9"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def svg_start(height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
        '<rect width="100%" height="100%" rx="24" fill="#f8fafc"/>',
        f'<text x="48" y="58" fill="{INK}" font-family="{FONT}" font-size="27" font-weight="700">{esc(title)}</text>',
        f'<text x="48" y="91" fill="{MUTED}" font-family="{FONT}" font-size="15">{esc(subtitle)}</text>',
    ]


def write_svg(name: str, lines: list[str]) -> None:
    lines.append("</svg>")
    (OUT / name).write_text("\n".join(lines), encoding="utf-8")


def bar_chart(path: str, title: str, subtitle: str, rows: list[tuple[str, float]], color: str) -> None:
    row_h, top, left, right = 34, 145, 255, 1080
    height = top + len(rows) * row_h + 62
    max_value = 1.0
    chart_w = right - left
    lines = svg_start(height, title, subtitle)
    for tick in range(0, 11, 2):
        x = left + chart_w * tick / 10
        lines.append(f'<line x1="{x:.1f}" y1="{top-10}" x2="{x:.1f}" y2="{height-45}" stroke="{GRID}"/>')
        lines.append(f'<text x="{x:.1f}" y="{height-20}" text-anchor="middle" fill="{MUTED}" font-family="{FONT}" font-size="12">{tick/10:.1f}</text>')
    for idx, (label, value) in enumerate(rows):
        y = top + idx * row_h
        bar_w = chart_w * max(0.0, min(value, max_value))
        lines.append(f'<text x="{left-14}" y="{y+18}" text-anchor="end" fill="{INK}" font-family="{FONT}" font-size="13">{esc(label)}</text>')
        lines.append(f'<rect x="{left}" y="{y}" width="{chart_w}" height="20" rx="7" fill="#edf2f7"/>')
        lines.append(f'<rect x="{left}" y="{y}" width="{bar_w:.1f}" height="20" rx="7" fill="{color}"/>')
        lines.append(f'<text x="{min(left+bar_w+10, right+12):.1f}" y="{y+16}" fill="{INK}" font-family="{FONT}" font-size="12" font-weight="600">{value:.3f}</text>')
    write_svg(path, lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads((Path(__file__).resolve().parent / "model_metrics.json").read_text(encoding="utf-8"))
    damage = data["damage_detection"]
    parts = data["part_segmentation"]
    rag = data["rag_retrieval"]

    lines = svg_start(420, "Recorded validation metrics", "Two distinct computer-vision tasks • values are mAP on the notebook validation splits")
    groups = [
        ("Damage detection", damage["overall"]["map50"], damage["overall"]["map50_95"], BLUE),
        ("Part segmentation · boxes", parts["overall"]["box_map50"], parts["overall"]["box_map50_95"], TEAL),
        ("Part segmentation · masks", parts["overall"]["mask_map50"], parts["overall"]["mask_map50_95"], PURPLE),
    ]
    left, top, chart_w = 330, 160, 700
    for tick in range(0, 11, 2):
        x = left + chart_w * tick / 10
        lines.append(f'<line x1="{x}" y1="140" x2="{x}" y2="345" stroke="{GRID}"/>')
        lines.append(f'<text x="{x}" y="370" text-anchor="middle" fill="{MUTED}" font-family="{FONT}" font-size="12">{tick/10:.1f}</text>')
    for i, (label, map50, mapall, color) in enumerate(groups):
        y = top + i * 68
        lines.append(f'<text x="{left-18}" y="{y+24}" text-anchor="end" fill="{INK}" font-family="{FONT}" font-size="14" font-weight="600">{esc(label)}</text>')
        for j, (metric, val, opacity) in enumerate((("mAP50", map50, "1"), ("mAP50–95", mapall, "0.55"))):
            yy = y + j * 23
            lines.append(f'<rect x="{left}" y="{yy}" width="{chart_w*val:.1f}" height="15" rx="6" fill="{color}" opacity="{opacity}"/>')
            lines.append(f'<text x="{left+chart_w*val+9:.1f}" y="{yy+12}" fill="{INK}" font-family="{FONT}" font-size="11">{val:.3f} {metric}</text>')
    lines.append(f'<text x="{left}" y="402" fill="{MUTED}" font-family="{FONT}" font-size="12">Solid = mAP50  ·  lighter = mAP50–95</text>')
    write_svg("overall_map_comparison.svg", lines)

    bar_chart(
        "damage_detection_by_class.svg",
        "Damage detection · per-class mAP50–95",
        f"Validation: {damage['validation_images']} images, {damage['validation_instances']} labeled instances • higher is better",
        [(c["name"], c["map50_95"]) for c in sorted(damage["classes"], key=lambda x: x["map50_95"])],
        BLUE,
    )
    bar_chart(
        "part_segmentation_by_class.svg",
        "Vehicle parts · per-class mask mAP50–95",
        f"Validation: {parts['validation_images']} images, {parts['validation_instances']} labeled instances • class sample counts vary",
        [(c["name"], c["mask_map50_95"]) for c in sorted(parts["classes"], key=lambda x: x["mask_map50_95"])],
        PURPLE,
    )
    rag_rows = [
        (q["question"], q["best_similarity"])
        for q in rag["queries"]
        if q.get("best_similarity") is not None
    ]
    bar_chart(
        "rag_top1_similarity.svg",
        f"RAG retrieval · top result similarity ({rag['hits']}/{rag['questions']} keyword hits)",
        f"Pooled index: {rag['index_chunks']:,} chunks across {rag['indexed_insurers']} insurers • general exclusions uses section matching",
        sorted(rag_rows, key=lambda row: row[1]),
        TEAL,
    )
    print(f"Wrote SVG charts to {OUT}")


if __name__ == "__main__":
    main()
