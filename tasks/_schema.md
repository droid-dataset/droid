# Task definition schema

Each task is a single YAML file under `tasks/{institution}/{task_id}.yaml`.
JSON also works (YAML is a superset) — pick whichever your institution prefers.

## Scoring model

Each task defines an **ordered, cumulative list of milestones**. Milestones must be designed so that reaching milestone N implies all earlier milestones were also reached. After each rollout the operator answers a single question — "what is the highest milestone reached?" — which makes scoring deterministic and unambiguous.

The recorded score for a rollout is the integer `highest_milestone` in `[0, N]` (where `0` means none were reached and `N` means the task completed). Per-milestone pass flags are derived from this single number.

## Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `institution` | string | yes | Short identifier for your lab (used in the output directory). |
| `task_id` | string | yes | Unique-per-institution short id (e.g. `pick_red_block`). |
| `language_instruction` | string | yes | Sent to the policy each step as the language prompt. |
| `success_criteria` | string | no | Free-form description shown to the operator at scoring time. |
| `max_timesteps` | int | no | Optional per-task override of the default rollout length. |
| `milestones` | list of milestones | yes | Ordered, cumulative. See below. |

### Milestone

| Field | Type | Notes |
|---|---|---|
| `name` | string | Short snake_case id; used as the key in `scores.json` and the HDF5 attrs. |
| `description` | string | Single-line description shown to the operator at scoring time. Should be objective enough that two operators would agree on the same milestone. |

## Annotated example

```yaml
institution: example_institution
task_id: pick_red_block
language_instruction: Pick up the red block and place it in the bowl.
success_criteria: |
  The red block ends up inside the bowl and the gripper releases it.
max_timesteps: 450
milestones:
  - name: reached_red_block
    description: Gripper made contact with the red block.
  - name: lifted_red_block
    description: Red block was lifted clear off the table.
  - name: released_in_bowl
    description: Red block was released and rests inside the bowl.
```

For this task, an operator would see prompts like:

```
Pick the highest milestone reached (cumulative):
  0: none
  1: reached_red_block — Gripper made contact with the red block.
  2: lifted_red_block — Red block was lifted clear off the table.
  3: released_in_bowl — Red block was released and rests inside the bowl.

  highest milestone reached [0-3]: 2
```

A score of `2` records `reached_red_block=True`, `lifted_red_block=True`, `released_in_bowl=False`, `task_complete=False`.
