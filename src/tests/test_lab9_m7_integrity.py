"""Integrity checks against the actual v2 report contract."""
import copy
import json
from pathlib import Path

import pytest

from lab9.eval import load_spec
from lab9.gate import check, integrity_check

pytestmark = pytest.mark.student


@pytest.fixture
def inputs():
    report = json.loads(Path("reports/baseline_v2.json").read_text(encoding="utf8"))
    spec = load_spec(Path("config/metric_spec_v2.yaml"))
    return report, spec


def test_baseline_valid(inputs):
    base, spec = inputs
    assert integrity_check(base, base, spec, spec) == []
    assert check(base, base, spec, spec)[0] == []


@pytest.mark.parametrize("attack", ["nan", "inf", "missing_metric", "none_row", "failures", "drop",
                                    "replace_duplicate", "duplicate", "seed", "missing_seed", "item", "tags",
                                    "tag_inconsistent", "bad_manifest", "bad_row", "forged_aggregate", "forged_hat", "huge"])
def test_report_attacks(inputs, attack):
    base, spec = inputs
    pr = copy.deepcopy(base)
    if attack == "nan": pr["metrics"]["pass_rate"] = float("nan")
    elif attack == "inf": pr["metrics"]["pass_rate"] = float("inf")
    elif attack == "missing_metric": del pr["metrics"]["pass_hat_5"]
    elif attack == "none_row": pr["rows"][0]["pass_rate"] = None
    elif attack == "failures": pr["evaluator_failures"] = ["grader crashed"]
    elif attack == "drop": pr["rows"].pop()
    elif attack == "replace_duplicate": pr["rows"][0] = copy.deepcopy(pr["rows"][1])
    elif attack == "duplicate": pr["rows"].append(copy.deepcopy(pr["rows"][0]))
    elif attack == "seed":
        original = pr["manifest"]["seeds"][0]
        pr["manifest"]["seeds"][0] = 777
        for row in pr["rows"]:
            if row["seed"] == original: row["seed"] = 777
    elif attack == "missing_seed": pr["rows"].pop(0)
    elif attack == "item":
        original = pr["rows"][0]["item_id"]
        for row in pr["rows"]:
            if row["item_id"] == original: row["item_id"] = "E-FAKE"
    elif attack == "tags":
        original = pr["rows"][0]["item_id"]
        for row in pr["rows"]:
            if row["item_id"] == original: row["slices"] = ["invented"]
    elif attack == "tag_inconsistent": pr["rows"][0]["slices"] = ["invented"]
    elif attack == "bad_manifest": pr["manifest"] = None
    elif attack == "bad_row": pr["rows"][0] = None
    elif attack == "forged_aggregate": pr["metrics"]["pass_rate"] = 0.5
    elif attack == "forged_hat": pr["metrics"]["pass_hat_5"] = 0.5
    elif attack == "huge": pr["metrics"]["pass_rate"] = 10 ** 500
    assert integrity_check(pr, base, spec), attack
    assert check(pr, base, spec)[0] == ["integrity"]


@pytest.mark.parametrize("attack", ["reduce_min", "increase_max", "disable", "delete_metric", "delete_slice",
                                    "remove_nsd", "slice_floor", "slice_metric", "slice_disable"])
def test_ratchet(inputs, attack):
    base, original = inputs
    changed = copy.deepcopy(original)
    metrics = {m["id"]: m for m in changed["metrics"]}
    if attack == "reduce_min": metrics["pass_rate"]["threshold"]["min"] = 0.1
    elif attack == "increase_max": metrics["secret_leak"]["threshold"]["max"] = 1
    elif attack == "disable": metrics["pass_rate"]["blocking"] = False
    elif attack == "delete_metric": changed["metrics"].remove(metrics["pass_rate"])
    elif attack == "delete_slice": changed["slices"].pop()
    elif attack == "remove_nsd": metrics["pass_rate"]["threshold"].pop("no_significant_drop")
    elif attack == "slice_floor": changed["slices"][0]["min"] = 0.1
    elif attack == "slice_metric": changed["slices"][0]["metric"] = "other"
    elif attack == "slice_disable": changed["slices"][0]["blocking"] = False
    assert any("ratchet" in p for p in integrity_check(base, base, changed, original))


def test_slice_order_not_significant(inputs):
    base, spec = inputs
    pr = copy.deepcopy(base)
    for row in pr["rows"]: row["slices"].reverse()
    assert integrity_check(pr, base, spec) == []
