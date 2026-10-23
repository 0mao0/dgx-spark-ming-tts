#!/usr/bin/env python3
"""Render the deployment topology diagram (assets/architecture.png)."""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, "assets", "architecture.png")

BLUE = "#4C9FE8"
DARK = "#1F3B57"
GREY = "#F3F6F9"
ORANGE = "#F2A03D"

fig, ax = plt.subplots(figsize=(5.4, 4.3))
ax.set_xlim(0, 10)
ax.set_ylim(0, 12)
ax.axis("off")


def box(x, y, w, h, title, sub="", fc=BLUE, tc="white", fs=9.2, subfs=7.4):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.2",
        linewidth=0, facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2 + (0.18 if sub else 0), title, ha="center", va="center",
            fontsize=fs, color=tc, fontweight="bold")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.32, sub, ha="center", va="center",
                fontsize=subfs, color=tc, alpha=0.92)


def arrow(x1, y1, x2, y2, label="", rad=0.0, color=DARK):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11,
        linewidth=1.3, color=color, connectionstyle=f"arc3,rad={rad}",
    ))
    if label:
        ax.text((x1 + x2) / 2 + 0.16, (y1 + y2) / 2, label, fontsize=7.2,
                color="#555555", ha="left", va="center")


box(2.4, 10.4, 5.2, 1.05, "Client", "POST /api/ming/v1/audio/speech")
arrow(5.0, 10.3, 5.0, 9.5, "HTTPS · Bearer token")

box(1.9, 8.35, 6.2, 1.05, "VPS nginx  :443", "TLS · token gate · /api/ming/v1 → upstream")
arrow(5.0, 8.25, 5.0, 7.45, "Tailscale")

# DGX host area
host = FancyBboxPatch((1.15, 1.55), 7.7, 5.75, boxstyle="round,pad=0.06,rounding_size=0.25",
                      linewidth=1.0, edgecolor="#C9D4DF", facecolor=GREY)
ax.add_patch(host)
ax.text(1.4, 6.95, "DGX Spark (GB10)", fontsize=8.6, color="#44576B", fontweight="bold")
ax.text(8.6, 6.95, "87 GiB used incl. other services", fontsize=6.6, color="#7A8A99", ha="right")

box(1.5, 5.55, 7.0, 0.95, "nginx  :8101", "streaming proxy · buffering off", fs=8.8, subfs=7.1)
arrow(5.0, 5.45, 5.0, 4.95, "localhost")
box(1.5, 3.85, 7.0, 0.95, "vLLM-Omni  :8094", "stage 0 AR (MoE) → stage 1 flow decoder", fs=8.8, subfs=7.1)

arrow(5.0, 3.75, 5.0, 2.9, "")
box(1.6, 1.75, 6.8, 1.0, "Ming-3.0-tts-tiny", "17 GiB weights · 44100 Hz mono PCM16 · max 10 seqs",
    fc=DARK, fs=8.8, subfs=7.1)

# Return path: streamed audio back to the client, drawn outside the host box.
ax.add_patch(FancyArrowPatch((9.35, 2.25), (9.35, 10.55), arrowstyle="-|>",
                             mutation_scale=11, linewidth=1.3, color=ORANGE))
ax.text(9.55, 6.4, "streamed PCM back to client · 44.1 kHz mono", fontsize=6.6,
        color=ORANGE, rotation=90, ha="left", va="center")

ax.text(0.2, 0.55, "Cold start after reboot: ~190 s to ready; one warmup request absorbs graph capture.",
        fontsize=6.6, color="#7A8A99")

plt.tight_layout()
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
im = Image.open(out)
im.save(out, dpi=(96, 96))
print("saved", out, im.size)
