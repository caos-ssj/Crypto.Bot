"""Tests para el ejecutor de swaps (Jupiter)."""

import base64
from unittest.mock import MagicMock, patch

from solders.hash import Hash
from solders.instruction import CompiledInstruction
from solders.keypair import Keypair
from solders.message import MessageHeader, MessageV0
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from src.executor import (
    _request_swap_transaction,
    _send_transaction,
    _sign_swap_transaction,
    build_swap_request,
    execute_sell,
    execute_swap,
    get_quote,
    load_wallet,
    parse_quote_response,
    wallet_public_key,
)

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    """Encoder base58 mínimo (para construir private keys en tests)."""
    n = int.from_bytes(data, "big")
    chars = []
    while n:
        n, rem = divmod(n, 58)
        chars.append(_ALPHABET[rem])
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + "".join(reversed(chars))


def _make_tx_b64(payer: Keypair) -> str:
    """Construye una VersionedTransaction serializable (para firma)."""
    message = MessageV0(
        MessageHeader(
            num_required_signatures=1,
            num_readonly_signed_accounts=0,
            num_readonly_unsigned_accounts=1,
        ),
        [payer.pubkey(), Pubkey.default()],
        Hash.default(),
        [CompiledInstruction(program_id_index=0, accounts=b"\x01", data=b"\x00")],
        [],
    )
    tx = VersionedTransaction.populate(message, [Signature.default()])
    return base64.b64encode(bytes(tx)).decode()


def test_build_swap_request_basic():
    """Construye el request de swap con los campos necesarios."""
    request = build_swap_request(
        quote_response={"data": "fake_quote"},
        user_public_key="PUBKEY123",
        slippage_bps=100,
    )
    assert request["userPublicKey"] == "PUBKEY123"
    assert request["slippageBps"] == 100
    assert "quoteResponse" in request


def test_parse_quote_response_valid():
    """Parsea quote válida."""
    raw = {
        "inputMint": "SOL",
        "outputMint": "TOKEN",
        "inAmount": "1000000000",
        "outAmount": "50000000000",
        "priceImpactPct": "0.005",
        "routePlan": [{"swapInfo": {}}],
    }
    result = parse_quote_response(raw)
    assert result is not None
    assert result["input_mint"] == "SOL"
    assert result["out_amount"] == 50000000000
    assert result["price_impact_pct"] == 0.005


def test_parse_quote_response_missing_fields():
    """Retorna None si faltan campos obligatorios."""
    raw = {"inputMint": "SOL"}
    result = parse_quote_response(raw)
    assert result is None


def test_parse_quote_response_invalid_price_impact():
    """Maneja priceImpactPct no numérico sin crashear."""
    raw = {
        "inputMint": "SOL",
        "outputMint": "T",
        "inAmount": "1000",
        "outAmount": "2000",
        "priceImpactPct": "invalid",
    }
    result = parse_quote_response(raw)
    assert result is not None
    assert result["price_impact_pct"] == 0.0


def test_get_quote_success():
    """Quote obtenida correctamente."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "inputMint": "SOL",
        "outputMint": "T",
        "inAmount": "1000",
        "outAmount": "2000",
        "priceImpactPct": "0.01",
    }
    with patch("src.executor._http_get", return_value=mock_response):
        result = get_quote("SOL", "T", amount_lamports=1000)
    assert result is not None
    assert result["out_amount"] == 2000


def test_get_quote_failure():
    """Retorna None si la API falla."""
    with patch("src.executor._http_get", side_effect=ConnectionError("no net")):
        result = get_quote("SOL", "T", amount_lamports=1000)
    assert result is None


def test_execute_swap_dry_run():
    """En modo DRY_RUN no envía transacción real."""
    with patch("src.executor.get_quote") as mock_quote:
        mock_quote.return_value = {
            "input_mint": "SOL",
            "output_mint": "T",
            "in_amount": 1000,
            "out_amount": 2000,
            "price_impact_pct": 0.01,
        }
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=True,
        )
    assert result["status"] == "dry_run"
    assert result["amount_sol"] == 0.01


def test_execute_swap_high_price_impact_aborts():
    """Si priceImpactPct > 5%, aborta."""
    with patch("src.executor.get_quote") as mock_quote:
        mock_quote.return_value = {
            "input_mint": "SOL",
            "output_mint": "T",
            "in_amount": 1000,
            "out_amount": 2000,
            "price_impact_pct": 6.0,  # 6% > límite 5%
        }
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=False,
        )
    assert result["status"] == "aborted"
    assert "price impact" in result["reason"].lower()


def test_execute_swap_acceptable_price_impact_passes():
    """Price impact moderado (< 5%) no aborta la operación."""
    with patch("src.executor.get_quote") as mock_quote:
        mock_quote.return_value = {
            "input_mint": "SOL",
            "output_mint": "T",
            "in_amount": 1000,
            "out_amount": 2000,
            "price_impact_pct": 0.4,  # 0.4% (efecto real de un snipe típico)
        }
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=True,
        )
    assert result["status"] == "dry_run"


def test_execute_swap_no_quote():
    """Si no hay quote, retorna failed."""
    with patch("src.executor.get_quote", return_value=None):
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=False,
        )
    assert result["status"] == "failed"


def test_load_wallet_empty():
    """Private key vacía → None (sin wallet)."""
    assert load_wallet("") is None


def test_load_wallet_invalid():
    """Private key inválida → None."""
    assert load_wallet("no-es-una-clave-vaLida") is None


def test_load_wallet_valid_roundtrip():
    """Round-trip: keypair → base58 → Keypair con mismo pubkey."""
    keypair = Keypair()
    b58 = _b58encode(bytes(keypair.secret()) + bytes(keypair.pubkey()))
    loaded = load_wallet(b58)
    assert loaded is not None
    assert str(loaded.pubkey()) == str(keypair.pubkey())


def test_wallet_public_key():
    """Expone la public key del keypair."""
    keypair = Keypair()
    assert wallet_public_key(keypair) == str(keypair.pubkey())


def test_sign_swap_transaction_valid():
    """Firma una transacción real de solders (round-trip verificado)."""
    payer = Keypair()
    b64 = _make_tx_b64(payer)
    signed_b64 = _sign_swap_transaction(b64, payer)
    assert signed_b64 is not None
    signed = VersionedTransaction.from_bytes(base64.b64decode(signed_b64))
    assert len(signed.signatures) == 1


def test_sign_swap_transaction_invalid_base64():
    """Base64 inválido → None (sin crash)."""
    assert _sign_swap_transaction("@@@", Keypair()) is None


def _quote_response(impact: float = 0.4):
    return {
        "input_mint": "SOL",
        "output_mint": "T",
        "in_amount": 1000,
        "out_amount": 2000,
        "price_impact_pct": impact,
    }


def test_execute_swap_real_success():
    """Swap real: firma y envía la tx; retorna success con signature."""
    keypair = Keypair()
    with patch("src.executor.get_quote", return_value=_quote_response()), patch(
        "src.executor._request_swap_transaction", return_value="TXB64"
    ), patch("src.executor._sign_swap_transaction", return_value="SIGNED"), patch(
        "src.executor._send_transaction", return_value="SIG123"
    ) as mock_send:
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=keypair,
            dry_run=False,
            rpc_url="https://rpc",
        )
    assert result["status"] == "success"
    assert result["signature"] == "SIG123"
    assert result["amount_sol"] == 0.01
    mock_send.assert_called_once()
    assert mock_send.call_args[0][1] == "https://rpc"


def test_execute_swap_real_without_rpc():
    """Sin rpc_url el swap real no se ejecuta (comportamiento seguro)."""
    keypair = Keypair()
    with patch("src.executor.get_quote", return_value=_quote_response()):
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=keypair,
            dry_run=False,
            rpc_url="",
        )
    assert result["status"] == "failed"
    assert result["reason"] == "no_rpc_url"


def test_request_swap_transaction_success():
    """Pide el swapTransaction a Jupiter y lo retorna."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"swapTransaction": "TX123"}
    with patch("src.executor._http_post", return_value=mock_response) as mock_post:
        result = _request_swap_transaction(
            {"raw": {"a": 1}}, "PUBKEY", slippage_bps=100
        )
    assert result == "TX123"
    payload = mock_post.call_args[0][1]
    assert payload["prioritizationFeeLamports"] == "auto"
    assert payload["dynamicComputeUnitLimit"] is True


def test_request_swap_transaction_missing_field():
    """Si Jupiter no devuelve swapTransaction → None."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "no route"}
    with patch("src.executor._http_post", return_value=mock_response):
        result = _request_swap_transaction({"raw": {}}, "PUBKEY", slippage_bps=100)
    assert result is None


def test_send_transaction_ok():
    """sendTransaction exitoso devuelve la signature."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": "SIGABC"}
    with patch("src.executor._http_post", return_value=mock_response):
        signature = _send_transaction("SIGNEDB64", "https://rpc")
    assert signature == "SIGABC"


def test_send_transaction_rpc_error():
    """RPC con error → None."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": {"message": "no funds"}}
    with patch("src.executor._http_post", return_value=mock_response):
        signature = _send_transaction("SIGNEDB64", "https://rpc")
    assert signature is None


def test_execute_sell_dry_run():
    """Venta simulada no consulta balance ni envía tx."""
    keypair = Keypair()
    with patch("src.executor._get_token_balance") as mock_balance:
        result = execute_sell("T", keypair, "https://rpc", dry_run=True)
    mock_balance.assert_not_called()
    assert result["status"] == "dry_run"


def test_execute_sell_no_balance():
    """Sin saldo del token → failed/no_balance."""
    keypair = Keypair()
    with patch("src.executor._get_token_balance", return_value=None), patch(
        "src.executor.get_quote"
    ) as mock_quote:
        result = execute_sell("T", keypair, "https://rpc", dry_run=False)
    mock_quote.assert_not_called()
    assert result["status"] == "failed"
    assert result["reason"] == "no_balance"


def test_execute_sell_success():
    """Venta real: vende todo el balance del token."""
    keypair = Keypair()
    with patch("src.executor._get_token_balance", return_value=5_000_000), patch(
        "src.executor.get_quote", return_value=_quote_response()
    ), patch("src.executor._request_swap_transaction", return_value="TXB64"), patch(
        "src.executor._sign_swap_transaction", return_value="SIGNED"
    ), patch(
        "src.executor._send_transaction", return_value="SELLSIG"
    ):
        result = execute_sell("T", keypair, "https://rpc", dry_run=False)
    assert result["status"] == "success"
    assert result["amount_tokens"] == 5_000_000
    assert result["signature"] == "SELLSIG"
