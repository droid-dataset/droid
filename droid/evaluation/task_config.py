from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Milestone:
    name: str
    description: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Milestone.name must be non-empty")
        if not self.description:
            raise ValueError(f"Milestone.description must be non-empty for {self.name!r}")


@dataclass
class TaskConfig:
    institution: str
    task_id: str
    language_instruction: str
    milestones: list[Milestone] = field(default_factory=list)
    success_criteria: str = ""
    max_timesteps: int | None = None

    def __post_init__(self):
        if not self.language_instruction.strip():
            raise ValueError("TaskConfig.language_instruction must be non-empty")
        if not self.milestones:
            raise ValueError("TaskConfig.milestones must be non-empty")
        names = [m.name for m in self.milestones]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate milestone names: {names}")


def load_task(path: str | Path) -> TaskConfig:
    path = Path(path)
    with path.open("r") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Task file {path} must contain a mapping at the top level")

    milestones = [
        Milestone(name=m["name"], description=m["description"])
        for m in raw.get("milestones", [])
    ]
    return TaskConfig(
        institution=raw["institution"],
        task_id=raw["task_id"],
        language_instruction=raw["language_instruction"],
        milestones=milestones,
        success_criteria=raw.get("success_criteria", ""),
        max_timesteps=raw.get("max_timesteps"),
    )
