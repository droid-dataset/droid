# ruff: noqa
"""Aggregate per-rollout scores.json files into a per-policy summary table."""

import dataclasses
import json
import statistics
from collections import defaultdict
from pathlib import Path

import tyro


@dataclasses.dataclass
class Args:
    output_dir: Path = Path("runs")
    out: str = "md"  # "md" or "csv"


def _collect(output_dir: Path):
    rows = []
    for scores_path in output_dir.rglob("scores.json"):
        with scores_path.open() as f:
            rows.append(json.load(f))
    return rows


def _group(rows):
    grouped: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = (row["task"]["institution"], row["task"]["task_id"])
        grouped[key][row["policy"]["name"]].append(row)
    return grouped


def _milestone_names(rows: list[dict]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        for name in row["scores"].get("milestone_reached", {}):
            if name not in seen:
                seen.append(name)
    return seen


def _render_markdown(grouped) -> str:
    lines = []
    for (institution, task_id), per_policy in sorted(grouped.items()):
        lines.append(f"## {institution} / {task_id}\n")
        all_rows = [r for rows in per_policy.values() for r in rows]
        milestones = _milestone_names(all_rows)

        header = ["policy", "n", "mean highest", "task complete %"] + [f"{m} %" for m in milestones]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for policy_name, rows in sorted(per_policy.items()):
            n = len(rows)
            highest_vals = [r["scores"]["highest_milestone"] for r in rows]
            complete_vals = [bool(r["scores"].get("task_complete")) for r in rows]
            cells = [
                policy_name,
                str(n),
                f"{statistics.mean(highest_vals):.2f}" if highest_vals else "-",
                f"{100 * sum(complete_vals) / n:.0f}%" if n else "-",
            ]
            for m in milestones:
                reached = [bool(r["scores"].get("milestone_reached", {}).get(m, False)) for r in rows]
                cells.append(f"{100 * sum(reached) / n:.0f}%" if n else "-")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) if lines else "(no scores.json files found)\n"


def _render_csv(grouped) -> str:
    out = ["institution,task_id,policy_name,episode_idx,highest_milestone,task_complete,milestone,reached"]
    for (institution, task_id), per_policy in sorted(grouped.items()):
        for policy_name, rows in sorted(per_policy.items()):
            for row in rows:
                ep = row.get("episode_idx", "")
                highest = row["scores"]["highest_milestone"]
                complete = row["scores"].get("task_complete", "")
                for m, reached in row["scores"].get("milestone_reached", {}).items():
                    out.append(
                        f"{institution},{task_id},{policy_name},{ep},{highest},{complete},{m},{int(bool(reached))}"
                    )
    return "\n".join(out) + "\n"


def main(args: Args):
    rows = _collect(args.output_dir)
    grouped = _group(rows)
    if args.out == "csv":
        print(_render_csv(grouped))
    else:
        print(_render_markdown(grouped))


if __name__ == "__main__":
    main(tyro.cli(Args))
