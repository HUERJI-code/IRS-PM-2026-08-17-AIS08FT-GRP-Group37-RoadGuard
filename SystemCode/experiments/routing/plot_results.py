"""Optional figures from a saved routing experiment directory (requires matplotlib).

matplotlib is not part of the backend CI dependencies; install it locally only to
regenerate figures. Figures are derived solely from raw_runs.csv / ga_convergence.csv.

Usage (repository root):
    python SystemCode/experiments/routing/plot_results.py SystemCode/experiments/routing/results/simulated-v1
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    raw = read_rows(args.run_dir / "raw_runs.csv")
    counts = sorted({int(row["task_count"]) for row in raw})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for axis, metric, label in zip(axes, ("objective_value", "makespan_minutes", "total_travel_minutes"),
                                   ("Objective (weighted minutes)", "Makespan (min)", "Total travel (min)")):
        ga = [[float(r[metric]) for r in raw if r["algorithm"] == "ga" and int(r["task_count"]) == c] for c in counts]
        greedy = [float(next(r[metric] for r in raw if r["algorithm"] == "greedy" and int(r["task_count"]) == c))
                  for c in counts]
        axis.boxplot(ga, positions=range(len(counts)), widths=0.5)
        axis.scatter(range(len(counts)), greedy, marker="D", color="#c0392b", zorder=3, label="Greedy")
        axis.set_xticks(range(len(counts)), [f"{c} tasks" for c in counts])
        axis.set_title(label)
        axis.grid(axis="y", alpha=0.3)
    axes[0].legend(loc="upper left")
    fig.suptitle("Four crews, simulated matrix: GA across seeds (box) vs Greedy (diamond)")
    fig.tight_layout()
    fig.savefig(args.run_dir / "ga_vs_greedy.png", dpi=150)

    convergence = defaultdict(list)
    for row in read_rows(args.run_dir / "ga_convergence.csv"):
        convergence[(int(row["task_count"]), int(row["seed"]))].append(float(row["best_objective"]))
    fig, axes = plt.subplots(1, len(counts), figsize=(4.3 * len(counts), 3.6), squeeze=False)
    for axis, count in zip(axes[0], counts):
        for (task_count, _), history in sorted(convergence.items()):
            if task_count == count:
                axis.plot(history, linewidth=0.9, alpha=0.7)
        axis.set_title(f"{count} tasks")
        axis.set_xlabel("Generation")
        axis.grid(alpha=0.3)
    axes[0][0].set_ylabel("Best objective")
    fig.suptitle("GA best-so-far objective per seed")
    fig.tight_layout()
    fig.savefig(args.run_dir / "ga_convergence.png", dpi=150)


if __name__ == "__main__":
    main()
