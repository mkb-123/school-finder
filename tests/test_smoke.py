"""Smoke test to verify the test infrastructure works."""


def test_imports():
    """Verify core dependencies can be imported."""
    import fastapi
    import httpx
    import pydantic
    import sqlalchemy

    assert fastapi.__version__
    assert sqlalchemy.__version__
    assert httpx.__version__
    assert pydantic.__version__
