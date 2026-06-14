# PolaRiS Bench Evals

## Setup

### 1. Clone the repository (with submodules)

```bash
git clone --recurse-submodules https://github.com/arhanjain/droid
```

If you already cloned without `--recurse-submodules`, initialize them with:

```bash
git submodule update --init --recursive
```

### 2. Install `uv`

If you don't already have `uv` installed, follow the official instructions: https://docs.astral.sh/uv/getting-started/installation/

### 3. Sync dependencies

```bash
uv sync
```

### 4. ZED Python API

You most likely already have the ZED SDK installed. To grab the Python bindings (`.so`) into the current working directory, run:

```bash
python /usr/local/zed/get_python_api.py
```

Then install the downloaded wheel into the project environment:

```bash
uv pip install [filename].whl
# e.g. uv pip install pyzed-4.0-cp310-cp310-linux_x86_64.whl
```

## Defining a task

Each evaluation task lives in its own file under `tasks/{institution}/{task_id}.yaml`. A task specifies the language instruction sent to the policy and an **ordered, cumulative list of milestones**. After each rollout the operator answers a single question — "what is the highest milestone reached?" — so scoring is deterministic and reproducible across institutions.

For `pick_red_block`, milestones might be `reached_red_block` → `lifted_red_block` → `released_in_bowl`. A rollout scored `2` means the policy reached and lifted the block but never released it in the bowl.

See `tasks/_schema.md` for the full schema and `tasks/example_institution/pick_red_block.yaml` for a working example. Copy the example into `tasks/{your_institution}/` and edit.

## Running an evaluation

### Host the policy

The bench script is a websocket **client** — you need a policy server already running. Use [openpi](./submodules/openpi/) (already a submodule) to host the policy (can be local or remote, only requires ~8-9 GB).  See [`POLICIES.md`](./POLICIES.md) for the openpi setup and the exact host command per policy.

### Run the client

The bench entry point is `scripts/evaluation/evaluate_bench.py`. It connects to the openpi server (default `0.0.0.0:8000`), runs `n_episodes` rollouts of the given task, records each rollout as HDF5 + per-camera MP4 streams via the existing `TrajectoryWriter`, and prompts the operator for the milestone score after each episode.

```bash
python scripts/evaluation/evaluate_bench.py \
  --task-config tasks/example_institution/pick_red_block.yaml \
  --policy-name pi0_fast_droid_jointpos \
  --operator arhan \
  --n-episodes 5 \
  --external-camera left \
  --remote-host 0.0.0.0 \
  --remote-port 8000
```

`--external-camera` selects which external camera (`left` or `right`) is fed to the policy — the model is trained on a single external view, so this must match the camera you want it to look through. Defaults to `left`.

Each episode produces:

```
runs/
  {institution}/
    {task_id}/
      {policy_name}/
        {YYYY_MM_DD_HH:MM:SS}/
          trajectory.h5        # observations + actions + per-cam MP4 blobs + scores in HDF5 attrs
          scores.json          # rubric + task/policy/operator metadata
          video_preview.mp4    # quick side-by-side preview
```

## Aggregating results

Once you have a set of rollouts under `runs/`, summarize them as a per-policy markdown table:

```bash
python scripts/evaluation/aggregate_scores.py --output-dir runs
# or, for a flat CSV:
python scripts/evaluation/aggregate_scores.py --output-dir runs --out csv
```

