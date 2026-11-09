import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PALETTE = ["#0075de", "#f64932", "#ffb110", "#62aef0", "#02093a", "#b18164", "#e89d01"]


def render_chart(spec: dict) -> str:
    """Render grafik dari ChartSpec -> data URI PNG (resolusi 300 DPI-ish)."""
    series = spec.get("series") or []
    labels = [s.get("label", "?") for s in series]
    values = [float(s.get("value", 0)) for s in series]
    kind = spec.get("kind", "bar")

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#cccccc",
        "axes.labelcolor": "#333333",
    })
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(values))]

    if kind == "pie":
        ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.0f%%",
            startangle=90,
            wedgeprops={"linewidth": 1.2, "edgecolor": "white"},
            textprops={"fontsize": 9},
        )
        ax.set_aspect("equal")
    elif kind == "line":
        ax.plot(labels, values, marker="o", color=PALETTE[0], linewidth=2.2)
        for i, v in enumerate(values):
            ax.annotate(f"{v:g}", (i, v), textcoords="offset points", xytext=(0, 8), fontsize=8, ha="center")
        ax.grid(axis="y", color="#eeeeee", zorder=0)
        ax.set_axisbelow(True)
    else:
        bars = ax.bar(labels, values, color=colors, zorder=3)
        for bar, v in zip(bars, values):
            ax.annotate(f"{v:g}", (bar.get_x() + bar.get_width() / 2, v), ha="center", va="bottom", fontsize=8)
        ax.grid(axis="y", color="#eeeeee", zorder=0)
        ax.set_axisbelow(True)

    ax.set_title(spec.get("title") or "Grafik", fontsize=12, color="#111111")
    if spec.get("xlabel"):
        ax.set_xlabel(spec["xlabel"], fontsize=9)
    if spec.get("ylabel"):
        ax.set_ylabel(spec["ylabel"], fontsize=9)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
