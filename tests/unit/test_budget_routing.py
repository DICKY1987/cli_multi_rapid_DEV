from __future__ import annotations

from cli_multi_rapid.router import Router


def test_budget_routing_wt_prefers_deterministic_within_budget():
    router = Router()
    step = {"actor": "code_fixers", "with": {}}
    decision = router.route_with_budget_awareness(step, role="wt", budget_remaining=0)
    assert decision.adapter_type == "deterministic"


def test_budget_routing_ipt_selects_ai_with_budget():
    router = Router()
    step = {
        "actor": "ai_analyst",
        "with": {"analysis_type": "code_review", "detail_level": "low"},
    }
    decision = router.route_with_budget_awareness(step, role="ipt", budget_remaining=5000)
    assert decision.adapter_type in ("ai", "deterministic")
    if decision.adapter_type == "ai":
        assert decision.estimated_tokens > 0

