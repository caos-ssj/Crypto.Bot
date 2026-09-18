"""Tests para el analizador de tokens (11 filtros)."""

import pytest
from src.analyzer import (
    check_market_cap,
    check_global_fees,
    check_age,
    check_security,
    check_liquidity_ratio,
    check_top_holders,
    check_volume,
    check_creator_age,
    check_authorities,
    check_bundles,
    check_dev_sell,
    calculate_score,
    decide,
)
from src.config import get_mode_settings


@pytest.fixture
def mode_eq():
    """Modo equilibrado para tests."""
    return get_mode_settings("equilibrado")


def test_check_market_cap_pass(mode_eq):
    pts, _ = check_market_cap({"market_cap": 50000}, mode_eq)
    assert pts == 20


def test_check_market_cap_fail_low(mode_eq):
    pts, _ = check_market_cap({"market_cap": 10000}, mode_eq)
    assert pts == 0


def test_check_market_cap_boundary(mode_eq):
    """MC exactamente en el límite es válido."""
    pts, _ = check_market_cap({"market_cap": 20000}, mode_eq)
    assert pts == 20


def test_check_global_fees_pass():
    pts, _ = check_global_fees({"global_fees_sol": 0.5}, {"global_fees": 0.15})
    assert pts == 20


def test_check_age_pass(mode_eq):
    pts, _ = check_age({"age_minutes": 100}, mode_eq)
    assert pts == 15


def test_check_security_pass():
    token = {"has_bundles": False, "dev_has_sold": False}
    pts, _ = check_security(token)
    assert pts == 25


def test_check_security_fail():
    token = {"has_bundles": True, "dev_has_sold": False}
    pts, _ = check_security(token)
    assert pts == 0


def test_check_liquidity_ratio_pass():
    token = {"liquidity_usd": 5000, "market_cap": 50000}  # 10%
    pts, _ = check_liquidity_ratio(token)
    assert pts == 5


def test_check_liquidity_ratio_fail():
    token = {"liquidity_usd": 1000, "market_cap": 50000}  # 2%
    pts, _ = check_liquidity_ratio(token)
    assert pts == 0


def test_check_top_holders_pass():
    pts, _ = check_top_holders({"top_10_holders_pct": 30.0})
    assert pts == 5


def test_check_volume_pass():
    pts, _ = check_volume({"volume_5min": 5000})
    assert pts == 5


def test_check_creator_age_pass():
    pts, _ = check_creator_age({"creator_age_days": 30})
    assert pts == 5


def test_check_authorities_pass():
    token = {"mint_authority_disabled": True, "freeze_authority_disabled": True}
    pts, _ = check_authorities(token)
    assert pts == 5


def test_check_bundles_pass():
    pts, _ = check_bundles({"has_bundles": False})
    assert pts == 5


def test_check_dev_sell_pass():
    pts, _ = check_dev_sell({"dev_has_sold": False})
    assert pts == 5


def test_calculate_score_perfect(mode_eq):
    """Token perfecto: todos los filtros pasan."""
    token = {
        "market_cap": 50000,
        "global_fees_sol": 1.0,
        "age_minutes": 100,
        "has_bundles": False,
        "dev_has_sold": False,
        "liquidity_usd": 10000,
        "top_10_holders_pct": 20.0,
        "volume_5min": 10000,
        "creator_age_days": 30,
        "mint_authority_disabled": True,
        "freeze_authority_disabled": True,
    }
    score, details = calculate_score(token, mode_eq)
    assert score == 100
    assert len(details) == 11


def test_calculate_score_zero(mode_eq):
    """Token basura: todos los filtros fallan."""
    token = {
        "market_cap": 1,
        "global_fees_sol": 0.0,
        "age_minutes": 100000,
        "has_bundles": True,
        "dev_has_sold": True,
        "liquidity_usd": 0,
        "top_10_holders_pct": 90.0,
        "volume_5min": 0,
        "creator_age_days": 0,
        "mint_authority_disabled": False,
        "freeze_authority_disabled": False,
    }
    score, _ = calculate_score(token, mode_eq)
    assert score == 0


def test_decide_compra():
    assert decide(85) == "COMPRA"


def test_decide_observar():
    assert decide(60) == "OBSERVAR"


def test_decide_evitar():
    assert decide(30) == "EVITAR"

def test_security_unknown_does_not_get_points():
    """Datos de seguridad desconocidos no deben convertirse en una señal positiva."""
    from src.analyzer import check_security
    points, _ = check_security({"has_bundles": None, "dev_has_sold": None})
    assert points == 0


def test_security_requires_explicit_safe_values():
    from src.analyzer import check_security
    points, _ = check_security({"has_bundles": False, "dev_has_sold": False})
    assert points == 25
