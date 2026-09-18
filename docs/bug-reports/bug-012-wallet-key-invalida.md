# Bug #012: WALLET_PRIVATE_KEY inválida en .env bloquea la ejecución real

**Severidad:** Media
**Módulo:** Configuración / wallet (src/executor.py, .env)
**Entorno:** Linux, Python 3.12
**Fecha:** 2026-09-18
**Estado:** ⚠️ Config de usuario pendiente (código OK)

## Descripción

El dry-run de v2.0 detectó que la `WALLET_PRIVATE_KEY` cargada en `.env` **no es una
clave base58 válida** (22 caracteres + carácter `l`, que no pertenece al alfabeto
base58). El código la rechaza correctamente, pero hay que corregir la clave para
operar en real.

## Pasos para reproducir

1. Ejecutar el dry-run de humo (carga de wallet).
2. Ver en logs:
```
ERROR src.executor:load_wallet:209 - Private key inválida: InvalidChar(108)
```

## Resultado esperado

- Si la clave es inválida: rechazo claro y operación segura (sin intentos de firma).
- El bot no intenta enviar transacciones con una clave rota.

## Resultado obtenido

- `load_wallet` devuelve `None` (comportamiento correcto y seguro).
- El bot sigue funcionando en `DRY_RUN=true`.
- Con `DRY_RUN=false`, `get_wallet_keypair` muestra el aviso
  `⚠ Sin WALLET_PRIVATE_KEY válida` y no se operará.

## Causa raíz

La variable `WALLET_PRIVATE_KEY` contiene un valor placeholder/malformado
(22 caracteres). Una clave válida en base58 tiene ~43-44 caracteres (seed de 32
bytes) o ~87-88 (keypair completo de 64 bytes).

## Solución aplicada

- Mejora del mensaje de error en `load_wallet`, indicando el formato esperado
  (base58 de 32 o 64 bytes, no JSON ni frase semilla) para guiar al usuario.

## Acción pendiente (usuario)

Reemplazar `WALLET_PRIVATE_KEY` en `.env` por un keypair real:

```bash
# Generar un keypair Solana nuevo (CLI Solana):
solana-keygen new --no-outfile
# (o exportarlo desde Phantom/Backpack: "Exportar clave privada", es base58)
```

**Nunca** subir la clave al repositorio (`.env` está en `.gitignore`).

## Verificación

- `venv/bin/python -c "from src.executor import load_wallet; print(load_wallet('x' * 22))"`
  → `None` con el nuevo mensaje explicativo.
- Con un keypair real: `load_wallet` devuelve el objeto y `wallet_public_key` expone
  la dirección (cubierto por `test_load_wallet_valid_roundtrip`).

## Lección aprendida

- Validar siempre la longitud/formato de claves de forma amigable: un error críptico
  de `InvalidChar` no ayuda a un usuario que pega un JSON o una frase semilla.
- La clave nunca debe imprimirse ni loguearse (solo longitud/format hint).