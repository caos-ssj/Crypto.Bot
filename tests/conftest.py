"""Fixtures compartidos de la suite de tests."""

import pytest

from src import chain_data


@pytest.fixture(autouse=True)
def reset_chain_data_state():
    """Resetea la caché de soporte RPC entre tests (independencia de orden)."""
    chain_data._multi_tx_supported = None
    chain_data._multi_tx_fallback_logged = False
    yield
