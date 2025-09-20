from __future__ import annotations


def test_websocket_connection_manager_imports_without_fastapi():
    import importlib

    mod = importlib.import_module("src.websocket.connection_manager")
    assert hasattr(mod, "ConnectionManager")

