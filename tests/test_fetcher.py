"""Tests para fetcher (DexScreener): normalización + búsquedas."""

from unittest.mock import patch

import pytest

from src.fetcher import (
    _calc_age_minutes,
    _get_json,
    _normalize_pair,
    fetch_by_address,
    fetch_by_symbol,
    fetch_recent_memecoins,
)

# Fecha fija: 1_700_000_000_000 ms (epoch) y reloj a +500 min
CREATED_MS = 1_700_000_000_000
NOW_TIME = 1_700_030_000_000_000 / 1_000_000  # ms convertido a segundos


def _pair(**over):
    """Par DexScreener de ejemplo (solana)."""
    pair = {
        "chainId": "solana",
        "baseToken": {"address": "TOK1", "symbol": "TST", "name": "Test"},
        "pairAddress": "PAIR1",
        "priceUsd": "0.001",
        "marketCap": 50000,
        "fdv": 80000,
        "liquidity": {"usd": 5000},
        "volume": {"m5": 500, "h24": 10000},
        "priceChange": {"m5": 12.5, "h24": -5.0},
        "pairCreatedAt": CREATED_MS,
        "dexId": "pump",
    }
    pair.update(over)
    return pair


@pytest.fixture
def freeze_clock(monkeypatch):
    """Congela time.time en src.fetcher para edades deterministas."""
    monkeypatch.setattr("src.fetcher.time.time", lambda: NOW_TIME)


# ============ _normalize_pair ============


def test_normalize_pair_full(freeze_clock):
    """Token completo se normaliza con todos los campos."""
    token = _normalize_pair(_pair())
    assert token["token_address"] == "TOK1"
    assert token["symbol"] == "TST"
    assert token["name"] == "Test"
    assert token["pair_address"] == "PAIR1"
    assert token["price_usd"] == pytest.approx(0.001)
    assert token["market_cap"] == pytest.approx(50000)
    assert token["liquidity_usd"] == pytest.approx(5000)
    assert token["volume_5min"] == pytest.approx(500)
    assert token["volume_24h"] == pytest.approx(10000)
    assert token["price_change_5min"] == pytest.approx(12.5)
    assert token["pair_created_at"] == CREATED_MS
    assert token["dex_id"] == "pump"
    assert token["age_minutes"] == 500


def test_normalize_pair_missing_address_returns_none():
    """Sin dirección de base token → None (par inutilizable)."""
    assert _normalize_pair({"baseToken": {}}) is None
    assert _normalize_pair({}) is None


def test_normalize_pair_market_cap_falls_back_to_fdv():
    """marketCap ausente/0 → cae al fdv."""
    token = _normalize_pair(_pair(marketCap=None, fdv=90000))
    assert token["market_cap"] == pytest.approx(90000)

    token2 = _normalize_pair(_pair(marketCap=0, fdv=70000))
    assert token2["market_cap"] == pytest.approx(70000)


def test_normalize_pair_defaults_and_safe_values():
    """Campos ausentes → defaults ("?", "", 0.0, None); valores inválidos → 0.0."""
    raw = {
        "chainId": "solana",
        "baseToken": {"address": "TOK2"},
        "pairAddress": "PAIR2",
        "priceUsd": "abc",
        "marketCap": 0,
        "fdv": 0,
        "liquidity": None,
        "volume": None,
        "priceChange": None,
        "pairCreatedAt": None,
    }
    token = _normalize_pair(raw)
    assert token["symbol"] == "?"
    assert token["name"] == "?"
    assert token["dex_id"] == "?"
    assert token["liquidity_usd"] == 0.0
    assert token["volume_5min"] == 0.0
    assert token["volume_24h"] == 0.0
    assert token["price_change_5min"] == 0.0
    assert token["market_cap"] == 0.0
    assert token["price_usd"] == 0.0
    assert token["age_minutes"] is None


# ============ _calc_age_minutes ============


def test_calc_age_minutes_valid(freeze_clock):
    assert _calc_age_minutes(CREATED_MS) == 500


def test_calc_age_minutes_future_clamps_to_zero(freeze_clock):
    assert _calc_age_minutes(NOW_TIME * 1000 + 999_999_999) == 0


def test_calc_age_minutes_invalid():
    """Fecha inválida o ausente → None, nunca crash."""
    assert _calc_age_minutes(None) is None
    assert _calc_age_minutes("") is None
    assert _calc_age_minutes("cadena") is None
    assert _calc_age_minutes(float("nan")) is None


# ============ _get_json ============


def test_get_json_happy_path():
    """GET con retry → devuelve el JSON."""
    resp = type(
        "R",
        (),
        {"raise_for_status": lambda self: None, "json": lambda self: {"pairs": []}},
    )()
    with patch("src.fetcher.requests.get", return_value=resp) as mock_get:
        data = _get_json("https://api.dexscreener.com/x")
    assert data == {"pairs": []}
    assert mock_get.call_args.kwargs["timeout"] == 10


def test_get_json_retries_then_succeeds():
    """Un fallo HTTP → reintenta y la segunda llamada tiene éxito."""
    failing = type(
        "R",
        (),
        {
            "raise_for_status": lambda self: (_ for _ in ()).throw(
                ConnectionError("boom")
            ),
            "json": lambda self: {},
        },
    )()
    ok = type(
        "R",
        (),
        {"raise_for_status": lambda self: None, "json": lambda self: {"pairs": []}},
    )()
    with patch(
        "src.fetcher.requests.get", side_effect=[failing, ok]
    ) as mock_get, patch("src.utils.time.sleep") as mock_sleep:
        data = _get_json("https://api.dexscreener.com/x")
    assert data == {"pairs": []}
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


# ============ fetch_by_address ============


def test_fetch_by_address_best_liquidity(freeze_clock):
    """Devuelve el par solana con más liquidez."""
    pairs = {
        "pairs": [
            _pair(
                baseToken={"address": "B", "symbol": "B1", "name": "one"},
                liquidity={"usd": 100},
            ),
            _pair(
                baseToken={"address": "A", "symbol": "A1", "name": "two"},
                liquidity={"usd": 5000},
            ),
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs) as mock_get:
        token = fetch_by_address("0xAAAA")
    assert mock_get.call_count == 1
    assert token["token_address"] == "A"
    assert token["liquidity_usd"] == pytest.approx(5000)


def test_fetch_by_address_filters_non_solana(freeze_clock):
    """Pares de otras cadenas se ignoran → el único solana gana."""
    pairs = {
        "pairs": [
            _pair(
                chainId="bsc", baseToken={"address": "X", "symbol": "X", "name": "x"}
            ),
            _pair(
                baseToken={"address": "S", "symbol": "S1", "name": "s"},
                liquidity={"usd": 700},
            ),
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs):
        token = fetch_by_address("0xSSSS")
    assert token["token_address"] == "S"


def test_fetch_by_address_no_solana_returns_none():
    """Sin pares o sin pares solana → None."""
    with patch("src.fetcher._get_json", return_value={"pairs": []}):
        assert fetch_by_address("0xAAAA") is None
    with patch("src.fetcher._get_json", return_value={"pairs": [_pair(chainId="eth")]}):
        assert fetch_by_address("0xAAAA") is None


def test_fetch_by_address_error_returns_none():
    """Error HTTP/API → None (fallback seguro), nunca crash."""
    with patch("src.fetcher._get_json", side_effect=Exception("boom")):
        assert fetch_by_address("0xAAAA") is None


# ============ fetch_by_symbol ============


def test_fetch_by_symbol_sorted_top5():
    """Devuelve top 5 por liquidez desc, solo solana y normalizados."""
    pairs = {
        "pairs": [
            _pair(
                baseToken={"address": f"T{i}", "symbol": f"T{i}", "name": "n"},
                liquidity={"usd": i * 100},
            )
            for i in range(1, 8)  # 7 pares solana
        ]
        + [
            _pair(
                chainId="eth", baseToken={"address": "ETH", "symbol": "ET", "name": "e"}
            )
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs):
        result = fetch_by_symbol("TST")
    assert len(result) == 5
    liquidities = [t["liquidity_usd"] for t in result]
    assert liquidities == sorted(liquidities, reverse=True)
    assert all(t["token_address"].startswith("T") for t in result)


def test_fetch_by_symbol_skips_malformed_pair():
    """bug-023: un par malformado no debe tumbar la búsqueda."""
    pairs = {
        "pairs": [
            _pair(baseToken=None, liquidity=None),  # malformado
            _pair(
                baseToken={"address": "OK", "symbol": "OK", "name": "ok"},
                liquidity={"usd": 100},
            ),
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs):
        result = fetch_by_symbol("TST")
    assert [t["token_address"] for t in result] == ["OK"]


def test_fetch_by_symbol_error_returns_empty():
    """Error → lista vacía, sin crash."""
    with patch("src.fetcher._get_json", side_effect=Exception("boom")):
        assert fetch_by_symbol("TST") == []


# ============ fetch_recent_memecoins ============


def test_fetch_recent_memecoins_query_and_filters():
    """Ciclo automático: query elegida, solo solana normalizados."""
    pairs = {
        "pairs": [
            _pair(
                baseToken={"address": "R1", "symbol": "R1", "name": "r"},
                liquidity={"usd": 10},
            ),
            _pair(
                chainId="eth", baseToken={"address": "R2", "symbol": "R2", "name": "r2"}
            ),
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs) as mock_get, patch(
        "random.choice", return_value="pump"
    ):
        result = fetch_recent_memecoins()
    assert mock_get.call_args.args[1] == {"q": "pump"}
    assert [t["token_address"] for t in result] == ["R1"]


def test_fetch_recent_memecoins_skips_malformed_pair():
    """bug-023: pares malformados se saltan sin tumbar el ciclo."""
    pairs = {
        "pairs": [
            _pair(baseToken=None),
            _pair(baseToken={"address": "R3", "symbol": "R3"}),
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs), patch(
        "random.choice", return_value="jup"
    ):
        result = fetch_recent_memecoins()
    assert [t["token_address"] for t in result] == ["R3"]


def test_fetch_recent_memecoins_dedup_by_mint():
    """Dedup: la API repite el mismo par; solo se conserva el primer mint."""
    pairs = {
        "pairs": [
            _pair(
                baseToken={"address": "R1", "symbol": "R1", "name": "r"},
                liquidity={"usd": 10},
            ),
            _pair(
                baseToken={"address": "R1", "symbol": "R1", "name": "r"},
                liquidity={"usd": 20},
            ),
            _pair(baseToken={"address": "R2", "symbol": "R2", "name": "r2"}),
        ]
    }
    with patch("src.fetcher._get_json", return_value=pairs), patch(
        "random.choice", return_value="bonk"
    ):
        result = fetch_recent_memecoins()
    assert [t["token_address"] for t in result] == ["R1", "R2"]


def test_fetch_recent_memecoins_error_returns_empty():
    """Error de red → lista vacía, el ciclo continúa."""
    with patch("src.fetcher._get_json", side_effect=Exception("boom")), patch(
        "random.choice", return_value="bonk"
    ):
        assert fetch_recent_memecoins() == []
