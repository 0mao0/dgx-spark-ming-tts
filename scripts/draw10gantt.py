#!/usr/bin/env python3
"""Render the 10-way concurrency baseline chart.

Data: one run on a DGX Spark, 10 streaming requests, 302 Chinese characters
total, warm cache. TTFT is the first audio byte; wall is the last byte.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

DATA = [
    (3.80, 16.77, 43), (3.80, 15.03, 29), (3.80, 14.86, 34), (3.80, 9.50, 13),
    (3.49, 15.82, 30), (3.76, 16.81, 40), (3.79, 16.90, 41), (3.76, 15.51, 26),
    (3.79, 14.51, 21), (3.79, 14.79, 25),
]
TOTAL_WALL = 16.91

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, "assets", "10-way-gantt.png")

order = sorted(range(len(DATA)), key=lambda i: DATA[i][1])
fig, ax = plt.subplots(figsize=(5.4, 3.4))
for k, i in enumerate(order):
    ttft, wall, chars = DATA[i]
    y = 9 - k
    ax.add_patch(Rectangle((ttft, y - 0.34), wall - ttft, 0.68, color="#4C9FE8", ec="none"))
    ax.plot([ttft], [y], marker="D", ms=5.5, color="#F2A03D", zorder=5)
    ax.text(wall + 0.22, y, f"{chars} ch", va="center", fontsize=8)

ax.set_xlim(0, 19.5)
ax.set_ylim(-0.8, 9.6)
ax.set_yticks(range(10))
ax.set_yticklabels([f"#{i + 1}" for i in order], fontsize=8)
ax.set_xlabel("seconds", fontsize=9)
ax.set_title("10 concurrent streams: wall clock and first audio", fontsize=10)
ax.axvline(TOTAL_WALL, color="#999", ls="--", lw=1)
ax.text(TOTAL_WALL + 0.15, 9.25, f"wall {TOTAL_WALL:.1f} s", fontsize=8, color="#666")
for spine in ("top", "right", "left"):
    ax.spines[spine].set_visible(False)
ax.grid(axis="x", color="#EEEEEE", lw=0.8)
ax.set_axisbelow(True)

bar = mpatches.Patch(color="#4C9FE8", label="audio stream (first to last byte)")
diamond = plt.Line2D([], [], color="#F2A03D", marker="D", ls="", label="TTFT 3.5-3.8 s")
ax.legend(handles=[bar, diamond], fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)

plt.tight_layout()
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=220, bbox_inches="tight")
im = Image.open(out)
im.save(out, dpi=(96, 96))
print("saved", out, im.size)
