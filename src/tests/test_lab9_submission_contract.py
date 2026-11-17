"""Submission-specific rubric floors and baseline manifest checks."""
import json
from pathlib import Path

import pytest

from lab9.eval import load_spec
from lab9.evalset import load_jsonl, sha12

pytestmark = pytest.mark.student


def test_v2_rubric_requirements():
    spec = load_spec(Path("config/metric_spec_v2.yaml"))
    metrics = {m["id"]: m for m in spec["metrics"]}
    reliability = metrics["pass_hat_5"]
    assert reliability["kind"] == "capability" and reliability["blocking"]
    assert reliability["threshold"]["min"] >= 0.8
    reply = metrics["reply_amount_matches_ledger"]
    assert reply["kind"] == "capability" and reply["blocking"]
    slices = {s["name"]: s for s in spec["slices"]}
    for name in ("money_movement", "adversarial"):
        assert slices[name]["metric"] == "pass_rate" and slices[name]["blocking"]


def test_v2_baseline_matches_dataset_and_spec():
    spec = load_spec(Path("config/metric_spec_v2.yaml"))
    baseline = json.loads(Path("reports/baseline_v2.json").read_text(encoding="utf8"))
    items = load_jsonl(Path(spec["eval_set"]))
    manifest = baseline["manifest"]
    assert baseline["shape"] == "swarm" and baseline["evaluator_failures"] == []
    assert manifest["eval_set_sha"] == sha12(Path(spec["eval_set"]))
    assert manifest["metric_spec_version"] == spec["metric_spec_version"]
    assert manifest["items"] == len(items) and manifest["seeds"] == spec["seeds"]
    expected = {(item["item_id"], seed) for item in items for seed in spec["seeds"]}
    rows = baseline["rows"]
    assert len(rows) == len(expected)
    assert {(row["item_id"], row["seed"]) for row in rows} == expected
