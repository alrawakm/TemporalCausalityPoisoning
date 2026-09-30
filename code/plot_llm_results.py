"""Figure: accuracy and misattribution vs. perturbation multiple, both vendors,
both corpus conditions. Built from the tables already reported in the
manuscript, not recomputed here, so the two stay in sync by construction.

    python plot_llm_results.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# multiple -> value, per series. Codex has 7 points; Anthropic has 3.
codex_a = {"mult": [0.0, 0.5, 1.0, 1.25, 1.5, 1.75, 2.0],
           "correct": [78.3, 85.0, 91.7, 61.7, 55.0, 53.3, 51.7],
           "mis":     [3.3, 1.7, 3.3, 15.0, 18.3, 25.0, 30.0]}
codex_b = {"mult": [0.0, 1.0, 2.0],
           "correct": [58.3, 70.0, 20.0],
           "mis":     [18.3, 28.3, 58.3]}
claude_a = {"mult": [0.0, 1.0, 2.0],
            "correct": [58, 23, 0],
            "mis":     [7, 50, 87]}
claude_b = {"mult": [0.0, 1.0, 2.0],
            "correct": [28, 10, 0],
            "mis":     [5, 62, 88]}

series = [
    (codex_a, "Codex, condition A", "o", "-", "#1b1b1b"),
    (codex_b, "Codex, condition B", "o", "--", "#1b1b1b"),
    (claude_a, "Claude, condition A", "s", "-", "#6a6a6a"),
    (claude_b, "Claude, condition B", "s", "--", "#6a6a6a"),
]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.6), sharex=True)

for data, label, marker, ls, color in series:
    ax1.plot(data["mult"], data["correct"], marker=marker, linestyle=ls,
              color=color, linewidth=1.4, markersize=5, label=label)
    ax2.plot(data["mult"], data["mis"], marker=marker, linestyle=ls,
              color=color, linewidth=1.4, markersize=5, label=label)

ax1.set_title("Correct origin")
ax2.set_title("Misattributed (own baseline)")
for ax in (ax1, ax2):
    ax.set_xlabel("Perturbation, multiple of the clock-sorter's own minimum")
    ax.set_ylabel("Rate (%)")
    ax.set_ylim(-3, 100)
    ax.axvline(1.0, color="#c0c0c0", linewidth=1.0, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

ax1.text(1.02, 96, "sorter\nthreshold", fontsize=7, color="#909090")

handles, labels = ax1.get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False,
           bbox_to_anchor=(0.5, -0.06), fontsize=8)

fig.tight_layout(rect=[0, 0.08, 1, 1])
fig.savefig("../fig_llm_results.pdf", bbox_inches="tight")
print("wrote ../fig_llm_results.pdf")
