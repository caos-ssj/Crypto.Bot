"""Gestión de riesgo: TP, SL, trailing stop, límites."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from loguru import logger


TAKE_PROFIT_PCT = 0.20   # +20%
STOP_LOSS_PCT = 0.10     # -10%
TRAILING_ACTIVATION = 0.05  # activa al +5%
TRAILING_DISTANCE = 0.10    # 10% por debajo del máximo


@dataclass
class Position:
    """Representa una posición abierta."""
    token_address: str
    symbol: str
    entry_price: float
    amount_sol: float
    tp_price: float
    sl_price: float
    trailing_active: bool = False
    max_price_reached: float = 0.0
    opened_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if self.max_price_reached == 0.0:
            self.max_price_reached = self.entry_price


def calculate_tp_sl(entry_price: float) -> tuple[float, float]:
    """Calcula precios de TP y SL a partir del precio de entrada.
    
    Args:
        entry_price: Precio de entrada.
    
    Returns:
        Tupla (tp_price, sl_price).
    """
    tp = entry_price * (1 + TAKE_PROFIT_PCT)
    sl = entry_price * (1 - STOP_LOSS_PCT)
    return round(tp, 8), round(sl, 8)


def check_take_profit(position: Position, current_price: float) -> bool:
    """Verifica si se alcanzó el take profit."""
    return current_price >= position.tp_price


def check_stop_loss(position: Position, current_price: float) -> bool:
    """Verifica si se alcanzó el stop loss."""
    return current_price <= position.sl_price


def update_trailing_stop(position: Position, current_price: float) -> None:
    """Actualiza el trailing stop si el precio sube.
    
    Activa el trailing al +5% y lo mueve al 90% del máximo alcanzado.
    
    Args:
        position: Posición a actualizar (modificada in-place).
        current_price: Precio actual del token.
    """
    # Activar trailing si alcanza el umbral
    if not position.trailing_active:
        gain_pct = (current_price - position.entry_price) / position.entry_price
        if gain_pct >= TRAILING_ACTIVATION:
            position.trailing_active = True
            logger.info(
                f"Trailing activado para {position.symbol} "
                f"(+{gain_pct * 100:.1f}%)"
            )
    
    # Solo actualizar si el precio sube
    if current_price > position.max_price_reached:
        position.max_price_reached = current_price
        if position.trailing_active:
            new_sl = round(current_price * (1 - TRAILING_DISTANCE), 8)
            if new_sl > position.sl_price:
                position.sl_price = new_sl
                logger.info(
                    f"SL subido a {new_sl} para {position.symbol}"
                )


def can_open_position(
    positions: list[Position],
    max_positions: int = 3,
) -> bool:
    """Verifica si se puede abrir una nueva posición."""
    return len(positions) < max_positions


def check_daily_limit(current_loss_sol: float, limit_sol: float = 0.5) -> bool:
    """Verifica si aún se puede operar según el límite diario.
    
    Returns:
        True si aún se puede operar, False si se alcanzó el límite.
    """
    if current_loss_sol >= limit_sol:
        logger.warning(
            f"Límite diario alcanzado: {current_loss_sol:.3f} SOL "
            f"(límite: {limit_sol} SOL)"
        )
        return False
    return True