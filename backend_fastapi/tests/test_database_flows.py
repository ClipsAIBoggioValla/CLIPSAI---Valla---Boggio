from __future__ import annotations


def test_database_module_imports():
    import backend_fastapi.app.database as dbmod  # noqa: F401

    assert dbmod is not None
