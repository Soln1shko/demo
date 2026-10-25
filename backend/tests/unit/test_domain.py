import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain import state_machine as sm
from app.domain.finance import ProductSpec, QuoteInput, annuity_payment, quote_error, quote_math
from app.domain.matching import MatchProfile, match_product
from app.domain.scoring import RiskInputs, ScoringRules, assess

LOAN = ProductSpec(
    "working", "Кредит", "loan", "annuity", False, "working", 300_000, 30_000_000, 12, 60, 9, 23.5
)
OVERDRAFT = ProductSpec(
    "overdraft", "Овердрафт", "overdraft", "bullet", False, "gap", 100_000, 5_000_000, 1, 1, 9, 20
)


def test_annuity_known_value():
    assert annuity_payment(1_000_000, 12, 24) == pytest.approx(94_559.6, abs=0.5)


def test_annuity_schedule_pays_off_loan():
    res = quote_math(LOAN, QuoteInput(1_000_000, 24, 30, 23.5, "annuity", 0))
    assert len(res.rows) == 24
    assert res.rows[-1].balance == pytest.approx(0, abs=0.01)
    assert sum(r.principal for r in res.rows) == pytest.approx(1_000_000, abs=0.5)
    assert res.total == pytest.approx(1_000_000 + res.interest)


def test_diff_has_equal_principal_and_decreasing_payment():
    res = quote_math(LOAN, QuoteInput(1_200_000, 12, 30, 20, "diff", 0))
    assert all(r.principal == pytest.approx(100_000) for r in res.rows)
    assert res.first > res.last


def test_overdraft_interest_by_days():
    res = quote_math(OVERDRAFT, QuoteInput(1_000_000, 1, 30, 20, "bullet", 0))
    assert res.interest == pytest.approx(1_000_000 * 0.2 * 30 / 365)


def test_quote_error_bounds():
    assert quote_error(LOAN, QuoteInput(100_000, 24, 30, 23.5)) is not None
    assert quote_error(LOAN, QuoteInput(1_000_000, 6, 30, 23.5)) is not None
    assert quote_error(LOAN, QuoteInput(1_000_000, 24, 30, 23.5)) is None


@given(st.floats(300_000, 30_000_000), st.integers(12, 60), st.floats(1, 60))
def test_annuity_property_balance_never_negative(amount, months, rate):
    res = quote_math(LOAN, QuoteInput(amount, months, 30, rate, "annuity", 0))
    assert all(r.balance >= -0.01 for r in res.rows)
    assert res.interest >= 0


def test_scoring_good_company_is_approved():
    peak = quote_math(LOAN, QuoteInput(1_500_000, 24, 30, 23.5)).peak
    r = assess(LOAN, RiskInputs(1_500_000, 2_400_000, 1_750_000, 120_000, 36, False), peak, ScoringRules())
    assert r.result == "approved"
    assert 0 <= r.score <= 100


def test_scoring_overloaded_company_gets_alternative_or_rejection():
    peak = quote_math(LOAN, QuoteInput(6_000_000, 24, 30, 23.5)).peak
    r = assess(LOAN, RiskInputs(6_000_000, 1_200_000, 900_000, 150_000, 24, False), peak, ScoringRules())
    assert r.result in ("alternative", "rejected", "review")
    assert r.reasons


def test_scoring_is_deterministic_and_versioned():
    inputs = RiskInputs(1_000_000, 2_000_000, 1_400_000, 80_000, 12, True)
    rules = ScoringRules(version=7)
    a, b = assess(LOAN, inputs, 60_000, rules), assess(LOAN, inputs, 60_000, rules)
    assert a == b
    assert a.rules_version == 7


def test_matching_prefers_overdraft_for_cash_gap():
    p = MatchProfile(goal="Кассовый разрыв", amount=500_000, months=1)
    assert match_product(OVERDRAFT, p).score > match_product(LOAN, p).score


def test_state_machine_happy_path():
    s = "submitted"
    for action, target in [("assign", None), ("decide", "approved"), ("sign", None), ("fund", None)]:
        s = sm.apply(s, action, target)
    assert s == "funded"


def test_state_machine_rejects_invalid():
    with pytest.raises(sm.InvalidTransition):
        sm.apply("funded", "sign")
    with pytest.raises(sm.InvalidTransition):
        sm.apply("review", "decide", "signed")
    with pytest.raises(sm.InvalidTransition):
        sm.apply("checking", "check_result")  # цель обязательна


def test_next_actions_by_role():
    assert "sign" in sm.next_actions("approved", "client")
    assert "decide" in sm.next_actions("review", "bank")
    assert sm.next_actions("approved", "bank") == ["decide"]  # пересмотр автоматического решения
    assert sm.next_actions("signed", "bank") == []
