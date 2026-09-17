python
"""Test placeholder para verificar que CI funciona."""


def test_ci_funciona():
    """Test trivial que siempre pasa."""
    assert True


def test_python_version():
    """Verifica que Python es 3.11+."""
    import sys
    assert sys.version_info >= (3, 11)
