"""Tests para gestión de riesgo."""

import pytest

from src.risk import (
    Position,
    calculate_tp_sl,
    can_open_position,
    check_daily_limit,
    check_stop_loss,
    check_take_profit,
    update_trailing_stop,
)


def test_position_creation():
    """Crea posición con valores correctos."""
    pos = Position(
        token_address="TOK1",
        symbol="T1",
        entry_price=1.0,
        amount_sol=0.05,
        tp_price=1.2,
        sl_price=0.9,
    )
    assert pos.token_address == "TOK1"
    assert pos.entry_price == 1.0
    assert pos.trailing_active is False
    assert pos.max_price_reached == 1.0


def test_calculate_tp_sl():
    """TP = +20%, SL = -10%."""
    tp, sl = calculate_tp_sl(entry_price=1.0)
    assert tp == 1.2
    assert sl == 0.9


def test_check_take_profit_triggered():
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    assert check_take_profit(pos, current_price=1.25) is True
    assert check_take_profit(pos, current_price=1.2) is True  # exacto


def test_check_take_profit_not_triggered():
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    assert check_take_profit(pos, current_price=1.15) is False


def test_check_stop_loss_triggered():
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    assert check_stop_loss(pos, current_price=0.85) is True
    assert check_stop_loss(pos, current_price=0.9) is True


def test_check_stop_loss_not_triggered():
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    assert check_stop_loss(pos, current_price=0.95) is False


def test_update_trailing_stop_activates_after_gain():
    """Trailing se activa tras +5% de ganancia."""
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    update_trailing_stop(pos, current_price=1.06)  # +6%
    assert pos.trailing_active is True
    assert pos.max_price_reached == 1.06


def test_update_trailing_stop_moves_sl_up():
    """SL sube al 90% del precio máximo alcanzado."""
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    pos.trailing_active = True
    update_trailing_stop(pos, current_price=1.5)
    assert pos.max_price_reached == 1.5
    assert pos.sl_price == pytest.approx(1.35, rel=1e-3)  # 1.5 * 0.9


def test_update_trailing_stop_ignores_lower_price():
    """Si el precio baja, no cambia el máximo ni el SL."""
    pos = Position("T", "T", 1.0, 0.05, 1.2, 0.9)
    pos.trailing_active = True
    pos.max_price_reached = 1.5
    pos.sl_price = 1.35
    update_trailing_stop(pos, current_price=1.3)
    assert pos.max_price_reached == 1.5
    assert pos.sl_price == 1.35


def test_can_open_position_below_max():
    positions = [Position("A", "A", 1, 0.01, 1.2, 0.9)]
    assert can_open_position(positions, max_positions=3) is True


def test_can_open_position_at_max():
    positions = [
        Position("A", "A", 1, 0.01, 1.2, 0.9),
        Position("B", "B", 1, 0.01, 1.2, 0.9),
        Position("C", "C", 1, 0.01, 1.2, 0.9),
    ]
    assert can_open_position(positions, max_positions=3) is False


def test_check_daily_limit_ok():
    assert check_daily_limit(current_loss_sol=0.2, limit_sol=0.5) is True


def test_check_daily_limit_exceeded():
    assert check_daily_limit(current_loss_sol=0.6, limit_sol=0.5) is False