"""PR-MON-6 §8 (P1-4): operation-level cost evidence and the per-pack gate (hermetic; no database).

Every number here is a test value. The product has no FX, margin, evidence floor or credit price (H-1, H-7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

import pytest

from writing_coach.billing.cost_model import (
    GateInputs,
    OperationCost,
    evaluate_gate,
    load_gate_inputs,
    meter_stats,
)

D = Decimal


@dataclass(frozen=True)
class Pack:
    amount_minor: int
    credit_units: int


def op(op_id, meter, units, *calls):
    return OperationCost(op_id, meter, units, tuple(calls))


def paid(cost):
    return ("estimated", "paid", D(cost))


def free(cost="0"):
    return ("estimated", "free", D(cost))


INPUTS = GateInputs(fx_usd_vnd=D("25000"), fx_source="test", fx_date="2026-10-15", margin_floor=D("0.5"),
                    min_operations=2, min_quality=D("0.5"))


def test_cost_is_summed_per_operation_before_it_is_divided_per_unit():
    stats = meter_stats([
        op("a", "writing.review", 1, paid("0.010"), paid("0.020"), free()),   # three rounds of one operation
        op("b", "writing.review", 2, paid("0.040")),
    ])["writing.review"]
    # a: 0.030 per unit, b: 0.020 per unit; per-call figures (0.010, 0.020, 0.040) never enter the percentiles
    assert stats.complete_paid == 2 and stats.max_paid == D("0.030") and stats.p50_paid == D("0.020")


def test_an_unpriced_partial_or_unattributed_operation_is_incomplete_never_usd_zero():
    stats = meter_stats([
        op("a", "writing.review", 1, paid("0.010"), ("unpriced", "paid", None)),
        op("b", "writing.review", 1, ("partial", "paid", D("0.001"))),
        op("c", "writing.review", 1),                       # no attributed call at all
        op("d", "writing.review", 1, paid("0.050")),
    ])["writing.review"]
    assert (stats.settled, stats.complete, stats.incomplete) == (4, 1, 3)
    assert stats.quality == D("0.25") and stats.p95_paid == D("0.050") and stats.zero_cost == 0


def test_the_zero_cost_share_is_reported_apart_and_never_lowers_the_paid_p95():
    operations = [op(f"z{i}", "orena.message", 1, free()) for i in range(18)]
    operations += [op("p1", "orena.message", 1, paid("0.100")), op("p2", "orena.message", 1, paid("0.200"))]
    stats = meter_stats(operations)["orena.message"]
    assert stats.zero_cost == 18 and stats.zero_cost_share == D("0.9")
    assert stats.p95_paid == D("0.200")          # only paid-reaching operations
    assert stats.p95_all <= D("0.200")


def test_no_gate_inputs_pass_nothing():
    result = evaluate_gate(packs={"credits:a:payos": Pack(100000, 100)}, prices={"writing.review": 5},
                           stats={}, inputs=None)
    assert result.meters == {"writing.review": False} and result.packs == {"credits:a:payos": False}
    assert result.reasons["*"] == "no_gate_inputs"


def test_each_pack_is_judged_on_its_own_effective_vnd_per_credit():
    stats = meter_stats([op(f"o{i}", "writing.review", 1, paid("0.020")) for i in range(3)])
    # floor = 0.020 USD x 25000 x 1.5 = 750 VND per unit; price 1 credit per unit
    packs = {"credits:full:payos": Pack(100_000, 100),     # 1000 VND per credit: passes
             "credits:bulk:payos": Pack(140_000, 200)}     # 700 VND per credit (discount): fails
    result = evaluate_gate(packs=packs, prices={"writing.review": 1}, stats=stats, inputs=INPUTS)
    assert result.meter_ok("writing.review")
    assert result.pack_ok("credits:full:payos") and not result.pack_ok("credits:bulk:payos")


def test_a_pack_must_pass_for_every_meter_its_credits_may_fund():
    cheap = [op(f"r{i}", "writing.review", 1, paid("0.010")) for i in range(3)]
    dear = [op(f"m{i}", "orena.message", 1, paid("0.050")) for i in range(3)]
    stats = meter_stats(cheap + dear)
    packs = {"credits:a:payos": Pack(100_000, 100)}       # 1000 VND per credit
    # review floor 375 VND (passes at price 1); message floor 1875 VND (needs price 2)
    one = evaluate_gate(packs=packs, prices={"writing.review": 1, "orena.message": 1}, stats=stats, inputs=INPUTS)
    assert one.meter_ok("writing.review") and not one.meter_ok("orena.message")
    assert one.pack_ok("credits:a:payos")   # it passes for every meter that is credit-eligible
    two = evaluate_gate(packs=packs, prices={"writing.review": 1, "orena.message": 2}, stats=stats, inputs=INPUTS)
    assert two.meter_ok("orena.message") and two.pack_ok("credits:a:payos")
    assert one.gate_id != two.gate_id      # the id names exactly the inputs it judged


def test_too_little_evidence_or_quality_passes_nothing():
    few = meter_stats([op("o1", "writing.review", 1, paid("0.001"))])
    result = evaluate_gate(packs={"credits:a:payos": Pack(100_000, 100)}, prices={"writing.review": 10}, stats=few,
                           inputs=INPUTS)
    assert not result.meter_ok("writing.review") and result.reasons["writing.review"] == "insufficient_evidence"


def test_gate_inputs_come_only_from_the_humans_file_and_are_validated(tmp_path):
    assert load_gate_inputs({}) is None
    path = tmp_path / "gate.json"
    path.write_text(json.dumps({"fx_usd_vnd": "25000", "fx_source": "", "fx_date": "2026-10-15", "margin_floor": "0.3",
                                "min_operations": 50, "min_quality": "0.9"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_gate_inputs({"BILLING_COST_GATE_FILE": str(path)})


def test_meter_prices_come_only_from_the_humans_file_and_never_for_media_import(tmp_path):
    from writing_coach.billing.funding import load_meter_prices

    assert load_meter_prices({}) == {}
    path = tmp_path / "prices.json"
    for bad in ([{"meter": "media.import", "credit_price": 1, "hold_ttl_seconds": 60, "revision": "r"}],
                [{"meter": "writing.review", "credit_price": 0, "hold_ttl_seconds": 60, "revision": "r"}],
                [{"meter": "writing.review", "credit_price": 1, "hold_ttl_seconds": 1801, "revision": "r"}],
                [{"meter": "languages.target", "credit_price": 1, "hold_ttl_seconds": 60, "revision": "r"}]):
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            load_meter_prices({"BILLING_METER_PRICES_FILE": str(path)})
