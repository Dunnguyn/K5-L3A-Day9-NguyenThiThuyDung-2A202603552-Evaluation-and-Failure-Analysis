"""Replay a public first-wrong-step case against its fixed control."""
import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9.graders import DbFactKept, RefundAmountCorrect
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def test_ticket_override_detected_against_fixed():
    for shape, expected_ok in (("seeded_regression", False), ("fixed", True)):
        case = investigate(shape, "C-002", 11)
        trial = case["trial"]
        ctx = EvaluatorContext(name=shape, inputs={}, metadata=None, output=trial,
                               expected_output=case["label"], duration=0.0,
                               _span_tree=None, attributes={}, metrics={})
        assert DbFactKept().evaluate(ctx).value is expected_ok
        assert RefundAmountCorrect().evaluate(ctx).value is expected_ok
        assert trial["lab8_pass"] is expected_ok
        if not expected_ok:
            assert trial["events"][2]["kind"] == "model_override"
            assert trial["events"][2]["payload"]["delay_days"] == 5
            assert trial["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
