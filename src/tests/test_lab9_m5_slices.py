"""M5 slice pairing, missing data and threshold behavior."""
import copy

import pytest

from lab9.gate import slice_check

pytestmark = pytest.mark.student


def report(values):
    return {"rows": [{"item_id": f"E-{i}", "seed": seed, "slices": ["money_movement"], "pass_rate": value}
                     for i, value in enumerate(values) for seed in (11, 22)]}


def spec(**overrides):
    return {"slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.8,
                        "blocking": True, **overrides}]}


def test_floor_and_monitoring():
    base = report([1, 1, 1, 1])
    assert slice_check(base, base, spec())[0] == []
    assert slice_check(report([1, 0, 1, 0]), base, spec())[0] == ["slice:money_movement/pass_rate"]
    blocked, lines = slice_check(report([1, 0, 1, 0]), base, spec(blocking=False))
    assert not blocked and "warn" in lines[0]


def test_paired_ci_and_zero_boundary():
    base = report([1] * 8)
    blocked, lines = slice_check(report([0] * 8), base, spec(min=0, no_significant_drop=True))
    assert blocked and "CI" in lines[0]
    blocked, lines = slice_check(base, base, spec(min=0, no_significant_drop=True))
    assert not blocked and "+0.000" in lines[0]


def test_missing_empty_and_mismatched_seeds():
    base = report([1, 1])
    assert slice_check({"rows": []}, base, spec())[0]
    missing = copy.deepcopy(base)
    del missing["rows"][0]["pass_rate"]
    assert slice_check(missing, base, spec())[0]
    assert slice_check({"rows": base["rows"][1:]}, base, spec())[0]
    missing_both = {"manifest": {"seeds": [11, 22, 33]}, "rows": base["rows"]}
    assert slice_check(missing_both, missing_both, spec())[0]


def test_honest_equivalent_reordering():
    base = report([1, 0.5, 1])
    changed = {"rows": list(reversed(copy.deepcopy(base["rows"]))) }
    assert not slice_check(changed, base, spec(no_significant_drop=True))[0]
