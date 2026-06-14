from __future__ import annotations

from typing import Any

from droid.evaluation.task_config import TaskConfig


def prompt_rubric(task: TaskConfig) -> dict[str, Any]:
    """Prompt the operator for the highest milestone reached.

    Milestones are cumulative and ordered: reaching milestone N implies all
    milestones 1..N-1 were also reached. The operator picks a single integer
    in [0, len(milestones)], where 0 means none were reached.
    """
    n = len(task.milestones)
    print(f"\n=== Milestones: {task.institution}/{task.task_id} ===")
    if task.success_criteria:
        print(f"Success criteria: {task.success_criteria}")
    print("Pick the highest milestone reached (cumulative):")
    print("  0: none")
    for i, m in enumerate(task.milestones, start=1):
        print(f"  {i}: {m.name} — {m.description}")

    while True:
        raw = input(f"\n  highest milestone reached [0-{n}]: ").strip()
        try:
            value = int(raw)
        except ValueError:
            print("  invalid input (not an integer), try again")
            continue
        if not (0 <= value <= n):
            print(f"  invalid input (out of range), expected 0..{n}")
            continue
        highest = value
        break

    notes = input("  notes (optional, blank to skip): ").strip()

    milestone_reached = {m.name: (i <= highest) for i, m in enumerate(task.milestones, start=1)}
    return {
        "highest_milestone": highest,
        "milestone_reached": milestone_reached,
        "task_complete": highest == n,
        "notes": notes,
    }
