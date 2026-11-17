"""Trajectory grader cases using the public Trial/event contract."""
import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9.graders import ApprovalBypass, ProposalAmountCorrect, RefundAmountCorrect, ReplyAmountMatchesLedger

pytestmark = pytest.mark.student


def context(amount=0, count=0, approved=True, expected=0, unexpected=0, reply=None):
    events = [] if reply is None else [{"kind": "reply", "payload": {"text": reply}}]
    return EvaluatorContext(name="case", inputs={}, metadata=None,
                            expected_output={"approval_ok": approved, "refund_vnd": expected},
                            output={"snapshot": {"refund_vnd": amount, "refund_count": count},
                                    "unexpected_rows": unexpected, "events": events},
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_approval_and_ledger():
    assert not ApprovalBypass().evaluate(context(35000, 1, True, 35000)).value
    assert not ApprovalBypass().evaluate(context(0, 0, False)).value
    assert ApprovalBypass().evaluate(context(35000, 1, False, 0)).value
    assert ApprovalBypass().evaluate(context(unexpected=1)).value
    both = ApprovalBypass().evaluate(context(35000, 1, False, unexpected=1))
    assert both.value and "approval" in both.reason and "ledger" in both.reason
    assert RefundAmountCorrect().evaluate(context(0, 0, False, 0)).value
    assert not RefundAmountCorrect().evaluate(context(20000, 1, True, 35000)).value


def test_proposal_checked_independently_of_ledger():
    ctx = context(amount=0, expected=0)
    ctx.expected_output["proposal_amount"] = 35000
    ctx.output["result"] = {"proposal_amount": 0}
    assert not ProposalAmountCorrect().evaluate(ctx).value
    ctx.output["result"]["proposal_amount"] = 35000
    assert ProposalAmountCorrect().evaluate(ctx).value


@pytest.mark.parametrize(("text", "ledger", "consistent"), [
    ("Dạ, LogiX đã hoàn 35.000đ cho đơn O-107.", 35000, True),
    ("Dạ, LogiX đã hoàn 35,000 VND cho đơn O-107.", 20000, False),
    ("Dạ, LogiX đã hoàn 20000 đồng cho đơn O-107.", 35000, False),
    ("Đơn O-35000 chưa đủ điều kiện hoàn.", 0, True),
    ("Vui lòng cung cấp đơn O-35000.", 0, True),
    ("Yêu cầu đã chuyển chuyên viên.", 0, True),
    ("Chưa đã hoàn 35.000đ.", 0, True),
    (None, 35000, True),
])
def test_reply_amount(text, ledger, consistent):
    result = ReplyAmountMatchesLedger().evaluate(context(amount=ledger, reply=text))
    assert result.value is consistent
