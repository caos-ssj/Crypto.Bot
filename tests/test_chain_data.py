"""Tests para chain_data (Helius)."""

from unittest.mock import patch

from src.chain_data import (
    _fetch_parsed_transactions,
    analyze_security,
    enrich_token,
    get_creator_age_days,
    get_dev_address,
    get_earliest_signature,
    get_mint_info,
    get_top_holders_pct,
)


def test_get_mint_info_disabled():
    """Authorities deshabilitadas correctamente."""
    fake_result = {
        "value": {
            "data": {
                "parsed": {
                    "info": {
                        "mintAuthority": None,
                        "freezeAuthority": None,
                        "supply": "1000000000",
                        "decimals": 9,
                    }
                }
            }
        }
    }
    with patch("src.chain_data._rpc_call", return_value=fake_result):
        info = get_mint_info("MINT", "key")
    assert info["mint_authority_disabled"] is True
    assert info["freeze_authority_disabled"] is True
    assert info["supply"] == 1000000000


def test_get_mint_info_enabled():
    """Authorities activas → disabled=False."""
    fake_result = {
        "value": {
            "data": {
                "parsed": {
                    "info": {
                        "mintAuthority": "WALLET123",
                        "freezeAuthority": "WALLET123",
                        "supply": "1000",
                        "decimals": 6,
                    }
                }
            }
        }
    }
    with patch("src.chain_data._rpc_call", return_value=fake_result):
        info = get_mint_info("MINT", "key")
    assert info["mint_authority_disabled"] is False
    assert info["freeze_authority_disabled"] is False


def test_get_mint_info_null_response():
    """Si el RPC no devuelve nada, defaults seguros."""
    with patch("src.chain_data._rpc_call", return_value=None):
        info = get_mint_info("MINT", "key")
    assert info["mint_authority_disabled"] is False
    assert info["supply"] == 0


def test_get_top_holders_pct_valid():
    """Calcula bien el porcentaje."""
    largest = {"value": [{"amount": "100"}, {"amount": "100"}]}
    supply = {"value": {"amount": "1000"}}

    with patch("src.chain_data._rpc_call", side_effect=[largest, supply]):
        pct = get_top_holders_pct("MINT", "key")
    assert pct == 20.0


def test_get_top_holders_pct_empty():
    """Si no hay holders, retorna 100 (conservador)."""
    with patch("src.chain_data._rpc_call", return_value=None):
        pct = get_top_holders_pct("MINT", "key")
    assert pct == 100.0


def test_get_creator_age_days_valid():
    """Calcula edad a partir de la firma más antigua."""
    import time

    now = int(time.time())
    signatures = [{"blockTime": now - 86400 * 5}]  # 5 días atrás

    with patch("src.chain_data._rpc_call", return_value=signatures):
        age = get_creator_age_days("WALLET", "key")
    assert 4 <= age <= 6  # tolerancia por tiempo entre llamadas


def test_get_creator_age_days_empty():
    """Sin firmas → 0 días."""
    with patch("src.chain_data._rpc_call", return_value=[]):
        age = get_creator_age_days("WALLET", "key")
    assert age == 0


def test_enrich_token_adds_fields():
    """enrich_token añade los campos on-chain."""
    token = {"token_address": "MINT", "symbol": "T"}
    fake_mint = {
        "mint_authority_disabled": True,
        "freeze_authority_disabled": True,
        "supply": 1_000_000,
        "decimals": 6,
    }
    fake_security = {
        "dev_address": "CREATOR123",
        "has_bundles": False,
        "dev_has_sold": False,
    }

    with patch("src.chain_data.get_mint_info", return_value=fake_mint), patch(
        "src.chain_data.get_top_holders_pct", return_value=25.0
    ), patch("src.chain_data.analyze_security", return_value=fake_security), patch(
        "src.chain_data.get_creator_age_days", return_value=30
    ):
        result = enrich_token(token, "key")

    assert result["mint_authority_disabled"] is True
    assert result["top_10_holders_pct"] == 25.0
    assert result["creator_age_days"] == 30
    assert result["dev_address"] == "CREATOR123"
    assert result["has_bundles"] is False
    assert result["dev_has_sold"] is False
    assert result["global_fees_sol"] is None


def test_enrich_token_without_security_data():
    """Sin datos on-chain → campos de seguridad None (no inventar)."""
    token = {"token_address": "MINT2", "symbol": "T"}
    fake_mint = {
        "mint_authority_disabled": False,
        "freeze_authority_disabled": False,
        "supply": 1_000_000,
        "decimals": 6,
    }
    fake_security = {
        "dev_address": None,
        "has_bundles": None,
        "dev_has_sold": None,
    }

    with patch("src.chain_data.get_mint_info", return_value=fake_mint), patch(
        "src.chain_data.get_top_holders_pct", return_value=100.0
    ), patch("src.chain_data.analyze_security", return_value=fake_security):
        result = enrich_token(token, "key")

    assert result["creator_age_days"] is None
    assert result["has_bundles"] is None
    assert result["dev_has_sold"] is None
    assert result["global_fees_sol"] is None


# ============ Análisis de seguridad on-chain ============


def test_get_earliest_signature_single_page():
    """Sin paginación: la última firma del lote es la más antigua."""
    signatures = [
        {"signature": "SIG2", "blockTime": 200},
        {"signature": "SIG1", "blockTime": 100},
    ]
    with patch("src.chain_data._rpc_call", return_value=signatures):
        oldest = get_earliest_signature("MINT", "key")
    assert oldest == "SIG1"


def test_get_earliest_signature_paginates():
    """Si la página está llena, sigue paginando hacia atrás."""
    full_page = [
        {"signature": f"S{i}"} for i in range(100, 0, -1)
    ]  # 100 firmas = página llena
    last_page = [
        {"signature": "S2", "blockTime": 50},
        {"signature": "S1", "blockTime": 10},
    ]
    with patch("src.chain_data._rpc_call", side_effect=[full_page, last_page]):
        oldest = get_earliest_signature("MINT", "key")
    assert oldest == "S1"


def test_get_earliest_signature_no_data():
    """Sin transacciones → None."""
    with patch("src.chain_data._rpc_call", return_value=None):
        assert get_earliest_signature("MINT", "key") is None


def test_get_dev_address_from_creation_tx():
    """El fee payer de la tx más antigua es el dev."""
    signatures = [{"signature": "CRE1", "blockTime": 100}]
    tx = {
        "transaction": {
            "message": {"accountKeys": [{"pubkey": "DEVWALLET"}, {"pubkey": "OTHER"}]}
        }
    }
    with patch(
        "src.chain_data._rpc_call",
        side_effect=[signatures, tx],
    ):
        dev = get_dev_address("MINT", "key")
    assert dev == "DEVWALLET"


def test_get_dev_address_no_tx():
    """Sin transacción de creación → None."""
    with patch("src.chain_data._rpc_call", return_value=None):
        assert get_dev_address("MINT", "key") is None


def test_fetch_parsed_transaction_uses_getTransaction():
    """get_dev_address usa getTransaction (método RPC estándar)."""
    signatures = [{"signature": "CRE1", "blockTime": 100}]
    tx = {"transaction": {"message": {"accountKeys": [{"pubkey": "DEVWALLET"}]}}}
    with patch(
        "src.chain_data._rpc_call",
        side_effect=[signatures, tx],
    ) as mock_rpc:
        dev = get_dev_address("MINT", "key")
    assert dev == "DEVWALLET"
    method = mock_rpc.call_args_list[1][0][0]
    assert method == "getTransaction"


def test_fetch_parsed_transactions_batch():
    """Filtra nulls y solo conserva dicts válidos."""
    with patch(
        "src.chain_data._rpc_call",
        return_value=[{"a": 1}, None, {"b": 2}],
    ) as mock_rpc:
        result = _fetch_parsed_transactions(["S1", "S2", "S3"], "key")
    assert len(result) == 2
    assert mock_rpc.call_args_list[0][0][0] == "getMultipleTransactions"


def test_fetch_parsed_transactions_fallback_single():
    """Sin getMultipleTransactions → fallback secuencial a getTransaction."""
    side_effects = [
        None,  # getMultipleTransactions no soportado
        {"tx": 1},  # getTransaction S1
        None,  # getTransaction S2 falla
        {"tx": 3},  # getTransaction S3
    ]
    with patch("src.chain_data._rpc_call", side_effect=side_effects) as mock_rpc:
        result = _fetch_parsed_transactions(["S1", "S2", "S3"], "key")
    assert result == [{"tx": 1}, {"tx": 3}]
    methods = [call[0][0] for call in mock_rpc.call_args_list]
    assert (
        methods
        == ["getMultipleTransactions", "getTransaction"] * 1 + ["getTransaction"] * 2
    )


def _make_tx(balances):
    """Construye una tx parseada con los balances indicados."""
    return {
        "meta": {
            "preTokenBalances": [],
            "postTokenBalances": [
                {"mint": mint, "owner": owner, "uiTokenAmount": {"amount": amount}}
                for mint, owner, amount in balances
            ],
        }
    }


def test_analyze_security_detects_bundle():
    """Una firma con >1 comprador nuevo → bundle detectado."""
    mint = "MINT_BUNDLE"
    creation_signatures = [{"signature": "CRE1", "blockTime": 1}]
    creation_tx = {"transaction": {"message": {"accountKeys": [{"pubkey": "DEV"}]}}}
    recent = [{"signature": "B1"}]
    tx_bundle = _make_tx(
        [
            (mint, "BUYER1", "100"),
            (mint, "BUYER2", "200"),
        ]
    )

    with patch(
        "src.chain_data._rpc_call",
        side_effect=[creation_signatures, creation_tx, recent, [tx_bundle]],
    ):
        result = analyze_security(mint, "key")

    assert result["dev_address"] == "DEV"
    assert result["has_bundles"] is True
    assert result["dev_has_sold"] is False


def test_analyze_security_detects_dev_sell():
    """La venta del dev (saldo decreciente) se detecta."""
    mint = "MINT_DEVSELL"
    creation_signatures = [{"signature": "CRE1", "blockTime": 1}]
    creation_tx = {"transaction": {"message": {"accountKeys": [{"pubkey": "DEV"}]}}}
    recent = [{"signature": "S1"}]
    tx_sell = {
        "meta": {
            "preTokenBalances": [
                {"mint": mint, "owner": "DEV", "uiTokenAmount": {"amount": "1000"}}
            ],
            "postTokenBalances": [
                {"mint": mint, "owner": "DEV", "uiTokenAmount": {"amount": "0"}}
            ],
        }
    }

    with patch(
        "src.chain_data._rpc_call",
        side_effect=[creation_signatures, creation_tx, recent, [tx_sell]],
    ):
        result = analyze_security(mint, "key")

    assert result["has_bundles"] is False
    assert result["dev_has_sold"] is True


def test_analyze_security_clean_token():
    """Token sin bundles ni ventas del dev → both False."""
    mint = "MINT_CLEAN"
    creation_signatures = [{"signature": "CRE1", "blockTime": 1}]
    creation_tx = {"transaction": {"message": {"accountKeys": [{"pubkey": "DEV"}]}}}
    recent = [{"signature": "S1"}]
    tx_clean = _make_tx([(mint, "BUYER1", "500")])  # un solo comprador

    with patch(
        "src.chain_data._rpc_call",
        side_effect=[creation_signatures, creation_tx, recent, [tx_clean]],
    ):
        result = analyze_security(mint, "key")

    assert result["has_bundles"] is False
    assert result["dev_has_sold"] is False


def test_analyze_security_failure_is_conservative():
    """Un fallo completo → None (el analyzer dará 0 pts, nunca infla)."""
    with patch("src.chain_data._rpc_call", return_value=None):
        result = analyze_security("MINT_FAIL", "key")
    assert result["dev_address"] is None
    assert result["has_bundles"] is None
    assert result["dev_has_sold"] is None
