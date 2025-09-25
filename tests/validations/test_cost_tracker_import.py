from __future__ import annotations


def test_cost_tracker_import_and_api():
    import importlib

    m = importlib.import_module("lib.cost_tracker")
    assert hasattr(m, "record_cost")
    assert hasattr(m, "get_total_cost")
    assert hasattr(m, "record_gdw_cost")
