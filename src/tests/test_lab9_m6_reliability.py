"""Reliability estimators and item-level aggregation."""
import math

import pytest

from lab9.eval import aggregate
from lab9.stats import pass_at_k, pass_hat_k
from lab9.gate import check

pytestmark = pytest.mark.student


@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 1, 0),
                                  (5, 1, 6), (5.0, 1, 1), (5, True, 1), (5, 1, None)])
def test_reject_bad_inputs(args):
    for fn in (pass_at_k, pass_hat_k):
        with pytest.raises(ValueError):
            fn(*args)


def test_boundaries_and_invariant():
    for n in range(1, 25):
        for c in range(n + 1):
            for k in range(1, n + 1):
                assert 0 <= pass_hat_k(n, c, k) <= pass_at_k(n, c, k) <= 1
        assert pass_at_k(n, 0, n) == pass_hat_k(n, 0, n) == 0
        assert pass_at_k(n, n, n) == pass_hat_k(n, n, n) == 1
    assert pass_hat_k(5, 2, 3) == 0
    assert math.isclose(pass_at_k(10000, 50, 1), 0.005)


def test_item_level_and_insufficient_trials():
    rows = [{"item_id": item, "pass_rate": passed, "cost": 1} for item, scores in
            [("a", [True] * 5), ("b", [True] * 4 + [False])] for passed in scores]
    result = aggregate(rows, ["pass_rate"], [1, 3, 5, 6])
    assert result["pass_at_1"] == result["pass_hat_1"] == 0.9
    assert result["pass_hat_3"] == 0.7
    assert result["pass_hat_5"] == 0.5
    assert result["pass_at_6"] is None and result["pass_hat_6"] is None
    assert aggregate(rows[:-1], ["pass_rate"], [5])["pass_hat_5"] is None


def test_aggregated_pass_hat_5_blocks_floor():
    baseline = {"manifest": {"eval_set_sha": "x"}, "rows": [], "metrics": {"pass_hat_5": 1.0}}
    pr = {**baseline, "metrics": {"pass_hat_5": 0.5}}
    spec = {"metrics": [{"id": "pass_hat_5", "kind": "capability", "blocking": True,
                         "threshold": {"min": 0.8}}]}
    assert check(pr, baseline, spec)[0] == ["pass_hat_5"]
