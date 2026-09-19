"""Tests para main."""

from unittest.mock import MagicMock, patch

import pytest

from src.executor import LAMPORTS_PER_SOL
from src.main import (
    _open_position_from_swap,
    change_mode,
    get_wallet_keypair,
    load_env_config,
    main,
    monitor_positions,
    process_token,
    run_automatic_mode,
    run_manual_mode,
)


@pytest.fixture(autouse=True)
def _reset_wallet_cache(monkeypatch):
    """Evita que el Keypair cacheado a nivel módulo contamine otros tests."""
    monkeypatch.setattr("src.main._WALLET_KEYPAIR", None)


# ============ load_env_config ============


def test_load_env_config_missing_rpc(monkeypatch):
    """Falla si falta SOLANA_RPC_URL."""
    monkeypatch.delenv("SOLANA_RPC_URL", raising=False)
    with patch("src.main.load_dotenv"), pytest.raises(EnvironmentError):
        load_env_config()


def test_load_env_config_ok(monkeypatch):
    """Carga configuración con todas las variables."""
    monkeypatch.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    monkeypatch.setenv("MODE", "equilibrado")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("USE_AI", "false")
    monkeypatch.setenv("HELIUS_API_KEY", "test-key")

    with patch("src.main.load_dotenv"):
        config = load_env_config()

    assert config["mode"] == "equilibrado"
    assert config["dry_run"] is True
    assert config["use_ai"] is False
    assert config["helius_api_key"] == "test-key"


def test_load_env_config_defaults(monkeypatch):
    """Valores por defecto cuando faltan vars opcionales."""
    monkeypatch.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    for var in ["MODE", "DRY_RUN", "USE_AI", "HELIUS_API_KEY", "BIRDEYE_API_KEY"]:
        monkeypatch.delenv(var, raising=False)

    with patch("src.main.load_dotenv"):
        config = load_env_config()

    assert config["mode"] == "equilibrado"
    assert config["dry_run"] is True
    assert config["use_ai"] is True
    assert config["helius_api_key"] == ""


# ============ process_token ============


@pytest.fixture
def base_config():
    """Config mínima para tests."""
    return {
        "rpc_url": "https://api.mainnet-beta.solana.com",
        "helius_api_key": "",
        "birdeye_api_key": "",
        "wallet_private_key": "",
        "mode": "equilibrado",
        "dry_run": True,
        "lm_studio_url": "http://localhost:1234",
        "lm_studio_model": "qwen/qwen3-4b-2507",
        "use_ai": False,  # desactivar IA para tests (evita llamadas)
    }


@pytest.fixture
def mode_settings():
    return {
        "mc_min": 20000,
        "mc_max": 800000,
        "max_age_min": 1440,
        "global_fees": 0.15,
        "base_buy": 0.03,
    }


def test_process_token_evitar(base_config, mode_settings):
    """Token con score bajo → EVITAR, no ejecuta."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 1,
        "liquidity_usd": 0,
        "volume_5min": 0,
    }
    with patch("src.main.save_analysis"):
        result = process_token(token, mode_settings, base_config, verbose=False)

    assert result["action"] == "EVITAR"
    assert result["executed"] is False
    assert result["final_score"] < 50


def test_process_token_saves_to_db(base_config, mode_settings):
    """save_analysis es llamado después del análisis."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 50000,
        "liquidity_usd": 5000,
        "volume_5min": 5000,
    }
    with patch("src.main.save_analysis") as mock_save:
        process_token(token, mode_settings, base_config, verbose=False)

    assert mock_save.call_count == 1
    saved_result = mock_save.call_args[0][0]
    assert "final_score" in saved_result
    assert "action" in saved_result


def test_process_token_handles_db_error(base_config, mode_settings):
    """Si save_analysis falla, el bot no crashea."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 1,
        "liquidity_usd": 0,
        "volume_5min": 0,
    }
    with patch("src.main.save_analysis", side_effect=Exception("DB error")):
        result = process_token(token, mode_settings, base_config, verbose=False)

    # No crashea, retorna el resultado igual
    assert "action" in result
    assert "final_score" in result


# ============ COMPRA (dry run) ============


def _high_score_token():
    """Token que pasa todos los filtros (score 100)."""
    return {
        "symbol": "LAMBRO",
        "token_address": "TOK_LAMBRO",
        "price_usd": 0.001,
        "market_cap": 50000,
        "global_fees_sol": 0.5,
        "age_minutes": 10,
        "has_bundles": False,
        "dev_has_sold": False,
        "liquidity_usd": 5000,
        "top_10_holders_pct": 20.0,
        "volume_5min": 5000,
        "creator_age_days": 30,
        "mint_authority_disabled": True,
        "freeze_authority_disabled": True,
    }


def test_process_token_compra_dry_run_executes(base_config, mode_settings):
    """COMPRA en dry_run ejecuta execute_swap pero no abre posición real."""
    token = _high_score_token()
    config = {**base_config, "use_ai": True}
    with patch("src.main.get_ai_score", return_value={"score": 100}), patch(
        "src.main.get_open_positions", return_value=[]
    ), patch("src.main.get_today_realized_loss", return_value=0.0), patch(
        "src.main.execute_swap", return_value={"status": "dry_run", "amount_sol": 0.03}
    ) as mock_swap, patch(
        "src.main.save_analysis"
    ), patch(
        "src.main.save_position"
    ) as mock_save_pos:
        result = process_token(token, mode_settings, config, verbose=False)

    assert result["action"] == "COMPRA"
    assert result["executed"] is True
    assert mock_swap.call_args.kwargs["dry_run"] is True
    assert mock_swap.call_args.kwargs["rpc_url"] == base_config["rpc_url"]
    mock_save_pos.assert_not_called()


def test_process_token_compra_blocked_by_risk(base_config, mode_settings):
    """Riesgo bloquea la compra sin ejecutar swap."""
    token = _high_score_token()
    with patch("src.main.get_ai_score", return_value={"score": 100}), patch(
        "src.main.get_open_positions", return_value=[{}, {}, {}]
    ), patch("src.main.get_today_realized_loss", return_value=0.6), patch(
        "src.main.execute_swap"
    ) as mock_swap, patch(
        "src.main.save_analysis"
    ):
        config = {**base_config, "use_ai": True, "dry_run": False}
        result = process_token(token, mode_settings, config, verbose=False)

    assert result["action"] == "COMPRA"
    assert result["executed"] is False
    mock_swap.assert_not_called()


# ============ posiciones ============


def test_open_position_from_swap_saves(base_config, mode_settings):
    """Una compra real exitosa abre la posición en la DB."""
    token = _high_score_token()  # incluye price_usd
    swap_result = {"status": "success", "amount_sol": 0.03}
    with patch("src.main.save_position") as mock_save:
        _open_position_from_swap(token, swap_result, base_config, mode_settings)

    assert mock_save.call_count == 1
    saved = mock_save.call_args[0][0]
    assert saved["token_address"] == "TOK_LAMBRO"
    assert saved["entry_price"] == 0.001
    assert saved["tp_price"] == pytest.approx(0.0012)
    assert saved["sl_price"] == pytest.approx(0.0009)


def test_monitor_positions_sells_at_tp(base_config):
    """Al llegar al TP: vende y cierra la posición con pnl correcto."""
    row = {
        "token_address": "TOK_LAMBRO",
        "symbol": "LAMBRO",
        "entry_price": 0.001,
        "amount_sol": 0.03,
        "tp_price": 0.0012,
        "sl_price": 0.0009,
        "trailing_active": 0,
        "max_price_reached": 0.001,
        "opened_at": "2026-09-18T00:00:00+00:00",
    }
    out_sol_lamports = int(0.04 * LAMPORTS_PER_SOL)
    config = {**base_config, "dry_run": False}
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value={"price_usd": 0.0015}
    ), patch(
        "src.main.execute_sell",
        return_value={"status": "success", "out_amount_sol": out_sol_lamports},
    ) as mock_sell, patch(
        "src.main.update_position_state"
    ), patch(
        "src.main.close_position"
    ) as mock_close:
        monitor_positions(config)

    mock_sell.assert_called_once()
    _, exit_price, pnl = mock_close.call_args[0]
    assert exit_price == 0.0015
    assert pnl == pytest.approx(0.01)  # 0.04 recibidos - 0.03 invertidos


def test_monitor_positions_updates_trailing(base_config):
    """Precio subiendo activa trailing y persiste el nuevo SL."""
    row = {
        "token_address": "TOK_LAMBRO",
        "symbol": "LAMBRO",
        "entry_price": 0.001,
        "amount_sol": 0.03,
        "tp_price": 0.002,
        "sl_price": 0.0009,
        "trailing_active": 0,
        "max_price_reached": 0.001,
        "opened_at": "2026-09-18T00:00:00+00:00",
    }
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value={"price_usd": 0.0011}
    ), patch("src.main.execute_sell"), patch(
        "src.main.update_position_state"
    ) as mock_update, patch(
        "src.main.close_position"
    ):
        monitor_positions(base_config)  # dry_run=True: no vende de verdad

    assert mock_update.call_count == 1
    kwargs = mock_update.call_args
    assert kwargs.args[0] == "TOK_LAMBRO"
    assert kwargs.args[1] == pytest.approx(0.00099)  # SL subido con trailing (+10%)
    assert kwargs.args[2] is True  # trailing activado
    assert kwargs.args[3] == pytest.approx(0.0011)  # máximo alcanzado


# ============ WALLET ============


def test_get_wallet_keypair_caches(base_config):
    """El Keypair se construye una vez y se cachea."""
    fake = MagicMock()
    with patch("src.main.load_wallet", return_value=fake), patch(
        "src.main.wallet_public_key", return_value="PUBKEY"
    ):
        first = get_wallet_keypair({**base_config, "dry_run": True})
        second = get_wallet_keypair({**base_config, "dry_run": True})
    assert first is fake
    assert second is fake


def test_get_wallet_keypair_missing_ok(base_config):
    """Sin wallet y en dry_run no crashea."""
    with patch("src.main.load_wallet", return_value=None):
        assert get_wallet_keypair({**base_config, "dry_run": True}) is None


# ============ process_token: ramas extra ============


def test_process_token_enriches_with_helius_key(base_config, mode_settings):
    """Con HELIUS_API_KEY se enriquece on-chain antes de analizar."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 50000,
        "liquidity_usd": 5000,
        "volume_5min": 5000,
    }
    enriched = {**token, "supply": 1_000_000_000}
    config = {**base_config, "helius_api_key": "key"}
    with patch("src.main.enrich_token", return_value=enriched) as mock_enrich, patch(
        "src.main.save_analysis"
    ):
        result = process_token(token, mode_settings, config, verbose=False)
    mock_enrich.assert_called_once()
    assert result["token"]["supply"] == 1_000_000_000


def test_process_token_enrich_error_is_safe(base_config, mode_settings):
    """Fallos al enriquecer no cortan el análisis."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 1,
        "liquidity_usd": 0,
        "volume_5min": 0,
    }
    config = {**base_config, "helius_api_key": "key"}
    with patch("src.main.enrich_token", side_effect=Exception("RPC down")), patch(
        "src.main.save_analysis"
    ):
        result = process_token(token, mode_settings, config, verbose=False)
    assert "action" in result
    assert result["final_score"] < 50


def test_process_token_ai_error_uses_fallback(base_config, mode_settings):
    """Si la IA local falla, se usa fallback score 0 (seguro)."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 50000,
        "liquidity_usd": 5000,
        "volume_5min": 5000,
    }
    config = {**base_config, "use_ai": True}
    with patch("src.main.get_ai_score", side_effect=Exception("LM Studio down")), patch(
        "src.main.save_analysis"
    ):
        result = process_token(token, mode_settings, config, verbose=False)
    assert result["ai"]["fallback"] is True
    assert "final_score" in result


def test_process_token_verbose_shows_report(base_config, mode_settings):
    """verbose=True muestra el reporte rich."""
    token = {
        "symbol": "VERB",
        "name": "Verbose",
        "token_address": "TOKV",
        "price_usd": 0.001,
        "market_cap": 0,
        "liquidity_usd": 0,
        "volume_5min": 0,
        "price_change_5min": -1.0,
        "dex_id": "pump",
    }
    with patch(
        "src.main.get_ai_score", return_value={"score": 0, "reason": "off"}
    ), patch("src.main.show_token_report") as mock_report, patch(
        "src.main.save_analysis"
    ):
        process_token(
            token,
            mode_settings,
            {**base_config, "use_ai": True, "verb": True},
            verbose=True,
        )
    mock_report.assert_called_once()


# ============ apertura de posición: ramas de precio ============


def test_open_position_from_swap_fetches_price_when_missing(base_config, mode_settings):
    """Sin price_usd → se reintenta con fetch_by_address."""
    token = {"token_address": "TOKX", "symbol": "X"}
    swap = {"status": "success", "amount_sol": 0.03}
    with patch("src.main.fetch_by_address", return_value={"price_usd": 0.002}), patch(
        "src.main.save_position"
    ) as mock_save:
        _open_position_from_swap(token, swap, base_config, mode_settings)
    assert mock_save.call_count == 1
    assert mock_save.call_args[0][0]["entry_price"] == 0.002


def test_open_position_from_swap_no_price_no_save(base_config, mode_settings):
    """Sin precio en ningún sitio → no abre posición."""
    token = {"token_address": "TOKX", "symbol": "X"}
    swap = {"status": "success", "amount_sol": 0.03}
    with patch("src.main.fetch_by_address", return_value=None), patch(
        "src.main.save_position"
    ) as mock_save:
        _open_position_from_swap(token, swap, base_config, mode_settings)
    mock_save.assert_not_called()


def test_open_position_from_swap_fetch_error_no_save(base_config, mode_settings):
    """Error de red al reintentar → no abre posición, no crashea."""
    token = {"token_address": "TOKX", "symbol": "X"}
    swap = {"status": "success", "amount_sol": 0.03}
    with patch("src.main.fetch_by_address", side_effect=Exception("boom")), patch(
        "src.main.save_position"
    ) as mock_save:
        _open_position_from_swap(token, swap, base_config, mode_settings)
    mock_save.assert_not_called()


# ============ monitor_positions: ramas extra ============


def test_monitor_positions_no_positions_returns(base_config):
    """Sin posiciones abiertas → retorno temprano."""
    with patch("src.main.get_open_positions", return_value=[]):
        monitor_positions(base_config)


def _position_row(**over):
    row = {
        "token_address": "TOK_LAMBRO",
        "symbol": "LAMBRO",
        "entry_price": 0.001,
        "amount_sol": 0.03,
        "tp_price": 0.0012,
        "sl_price": 0.0009,
        "trailing_active": 0,
        "max_price_reached": 0.001,
        "opened_at": "2026-09-18T00:00:00+00:00",
    }
    row.update(over)
    return row


def test_monitor_positions_skips_without_price(base_config):
    """Sin precio fresco → se omite, no se vende ni cierra."""
    row = _position_row(tp_price=0.0012, sl_price=0.0003)  # SL bajo: sin TP/SL de hit
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value=None
    ), patch("src.main.execute_sell") as mock_sell, patch(
        "src.main.close_position"
    ) as mock_close:
        monitor_positions(base_config)
    mock_sell.assert_not_called()
    mock_close.assert_not_called()


def test_monitor_positions_sell_failed_keeps_position(base_config):
    """Venta fallida → la posición se mantiene abierta."""
    row = _position_row(tp_price=0.0005, sl_price=0.0003)  # precio 0.0015 > TP
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value={"price_usd": 0.0015}
    ), patch(
        "src.main.execute_sell", return_value={"status": "error", "reason": "rpc"}
    ), patch(
        "src.main.close_position"
    ) as mock_close:
        monitor_positions({**base_config, "dry_run": False})
    mock_close.assert_not_called()


def test_monitor_positions_dry_run_pnl(base_config):
    """En dry_run el pnl se simula precio/entrada."""
    row = _position_row(tp_price=0.0005, sl_price=0.0003)
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value={"price_usd": 0.0015}
    ), patch("src.main.execute_sell", return_value={"status": "dry_run"}), patch(
        "src.main.close_position"
    ) as mock_close:
        monitor_positions({**base_config, "dry_run": True})
    _, exit_price, pnl = mock_close.call_args[0]
    assert exit_price == 0.0015
    assert pnl == pytest.approx(0.03 * (0.0015 / 0.001 - 1))


def test_monitor_positions_fetch_error_safe(base_config):
    """Error de red en fetch_by_address no corta el monitoreo."""
    row = _position_row()
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", side_effect=Exception("boom")
    ), patch("src.main.execute_sell") as mock_sell:
        monitor_positions(base_config)
    mock_sell.assert_not_called()


# ============ run_manual_mode ============


def test_manual_mode_by_address(base_config, mode_settings):
    """Analizar por address devuelve el token y llama a process_token."""
    token = {"symbol": "T", "token_address": "0xADDR"}
    with patch("src.main.Prompt.ask", side_effect=["1", "0xADDR"]), patch(
        "src.main.fetch_by_address", return_value=token
    ), patch("src.main.process_token") as mock_process:
        run_manual_mode(base_config, mode_settings)
    mock_process.assert_called_once()
    assert mock_process.call_args.args[0] is token


def test_manual_mode_empty_address(base_config, mode_settings):
    """Address vacío → mensaje y salida sin procesar."""
    with patch("src.main.Prompt.ask", side_effect=["1", ""]), patch(
        "src.main.process_token"
    ) as mock_process:
        run_manual_mode(base_config, mode_settings)
    mock_process.assert_not_called()


def test_manual_mode_token_not_found(base_config, mode_settings):
    """Token no encontrado → salida sin procesar."""
    with patch("src.main.Prompt.ask", side_effect=["1", "0xADDR"]), patch(
        "src.main.fetch_by_address", return_value=None
    ), patch("src.main.process_token") as mock_process:
        run_manual_mode(base_config, mode_settings)
    mock_process.assert_not_called()


def test_manual_mode_by_symbol_single(base_config, mode_settings):
    """Un único resultado por símbolo → procesa directamente."""
    token = {"symbol": "BONK", "token_address": "0xADDR"}
    with patch("src.main.Prompt.ask", side_effect=["2", "BONK"]), patch(
        "src.main.fetch_by_symbol", return_value=[token]
    ), patch("src.main.process_token") as mock_process:
        run_manual_mode(base_config, mode_settings)
    mock_process.assert_called_once()


def test_manual_mode_by_symbol_empty(base_config, mode_settings):
    """Símbolo vacío → salida sin procesar."""
    with patch("src.main.Prompt.ask", side_effect=["2", ""]), patch(
        "src.main.process_token"
    ) as mock_process:
        run_manual_mode(base_config, mode_settings)
    mock_process.assert_not_called()


def test_manual_mode_symbol_no_results(base_config, mode_settings):
    """Símbolo sin resultados → salida sin procesar."""
    with patch("src.main.Prompt.ask", side_effect=["2", "XYZ"]), patch(
        "src.main.fetch_by_symbol", return_value=[]
    ), patch("src.main.process_token") as mock_process:
        run_manual_mode(base_config, mode_settings)
    mock_process.assert_not_called()


def test_manual_mode_symbol_multiple_selects(base_config, mode_settings):
    """Múltiples resultados → el usuario selecciona por índice."""
    tokens = [
        {"symbol": "L1", "token_address": "A", "market_cap": 1, "liquidity_usd": 1},
        {"symbol": "L2", "token_address": "B", "market_cap": 2, "liquidity_usd": 2},
        {"symbol": "L3", "token_address": "C", "market_cap": 3, "liquidity_usd": 3},
    ]
    with patch("src.main.Prompt.ask", side_effect=["2", "LAM", "2"]), patch(
        "src.main.fetch_by_symbol", return_value=tokens
    ), patch("src.main.process_token") as mock_process:
        run_manual_mode(base_config, mode_settings)
    assert mock_process.call_args.args[0] is tokens[1]


# ============ run_automatic_mode ============


def test_automatic_mode_one_cycle(base_config):
    """Un ciclo procesa tokens nuevos y los marca como vistos."""
    scheduler = MagicMock()
    scheduler.start.side_effect = KeyboardInterrupt()
    new_tokens = [
        {"symbol": "N1", "token_address": "NEW1"},
        {"symbol": "N2", "token_address": "NEW2"},
    ]
    with patch("src.main.get_seen_tokens", return_value={"SEEN"}), patch(
        "src.main.monitor_positions"
    ), patch(
        "src.main.fetch_recent_memecoins",
        return_value=new_tokens + [{"symbol": "S", "token_address": "SEEN"}],
    ), patch(
        "src.main.process_token"
    ), patch(
        "src.main.mark_seen"
    ) as mock_seen, patch(
        "src.main.BlockingScheduler", return_value=scheduler
    ):
        run_automatic_mode(base_config, {})

    assert mock_seen.call_args_list[0].args[0] == "NEW1"
    assert mock_seen.call_args_list[1].args[0] == "NEW2"


# ============ change_mode ============


def test_change_mode_updates_config(base_config):
    """change_mode actualiza config["mode"]."""
    config = {**base_config}
    with patch("src.main.Prompt.ask", side_effect=["agresivo", ""]):
        change_mode(config)
    assert config["mode"] == "agresivo"


# ============ main() ============


def test_main_missing_rpc_returns_1():
    """Sin SOLANA_RPC_URL → main retorna 1 sin iniciar DB."""
    with patch("src.main.load_env_config", side_effect=OSError("Falta RPC")), patch(
        "src.main.init_db"
    ) as mock_init:
        assert main() == 1
    mock_init.assert_not_called()


def test_main_menu_exit_zero(base_config):
    """Opción '0' → salida limpia con código 0."""
    with patch("src.main.load_env_config", return_value=base_config), patch(
        "src.main.init_db"
    ), patch("src.main.get_mode_settings", return_value={}), patch(
        "src.main.show_main_menu", side_effect=["0"]
    ):
        assert main() == 0
