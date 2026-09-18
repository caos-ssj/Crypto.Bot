# Bug #017: Valores centinela colisionan con datos reales (el "scoring honesto" no es honesto cuando Helius falla)

**Severidad:** Media
**Módulo:** On-chain / Análisis (`src/chain_data.py:98-151` → `src/analyzer.py`)
**Entorno:** v2.1, con `HELIUS_API_KEY` pero RPC caído o limitado
**Fecha:** 2026-09-18

## Descripción

Dos consultas on-chain devuelven **valores numéricos centinela** en lugar de
`None` cuando fallan:

- `get_top_holders_pct` → **100.0** ("todo el supply en 10 wallets")
- `get_creator_age_days` → **0** días ("wallet recién creada")

El analyzer no puede distinguir "RPC caído" de "token realmente concentrado /
creador recién nacido". Ambos casos producen `status: "fail"` idéntico, lo que
contradice la política documentada de que un dato no verificado debe marcarse
como **`missing`** y quedarse con 0 pts sin engañar al observador. En un corte
de Helius, todos los tokens aparecen como máximo riesgo sin que exista señal
real.

## Pasos para reproducir

1. Configurar `HELIUS_API_KEY` válido; cortar/depreciar el endpoint RPC
   (o inyectar mock que devuelva error en `getTokenLargestAccounts` /
   `getSignaturesForAddress`).
2. Modo manual → analizar cualquier token.
3. En el reporte: "Top-10 holders 100.00%" y "Creador 0 días" con marca roja ✗
   `fail` — idéntico a un token genuinamente apilado.
4. En el reporte del analyzer, `status` es `"fail"`, nunca `"missing"`.

## Resultado esperado

- Fallo de RPC → campo `None` → filtro `0 pts` + `status: "missing"` (⚠).
- El observador (línea de bajada / panel) puede identificar que no hubo datos.

## Resultado obtenido

- Fallo de RPC → números reales (100.0 / 0) → `status: "fail"`.
- Dos señales totalmente distintas (RPC muerto vs token concentrado) se
  representan igual en el brillo de decisión.

## Causa raíz

`MISSING_INDICATORS` (`analyzer.py:13-23`) solo marga `missing` cuando el campo
es `None`. Pero:

```python
# src/chain_data.py:109-114
if not largest or not largest.get("value"):
    return 100.0                     # centinela de fallo
...
if not supply_data or not supply_data.get("value"):
    return 100.0

# src/chain_data.py:141-142
if not result or not isinstance(result, list) or len(result) == 0:
    return 0                         # centinela de fallo = 0 días
```

Los centinelas elegidos coinciden con extremos reales posibles (100 % de
concentración, creador de 0 días), así que el dato es **intrínsecamente
ambiguo**.

## Impacto en la decisión

- **Integridad del scoring**: durante las caídas de Helius el score se degrada
  igual para safe y para dangerous — ruido de señal exactamente donde el bot
  más necesita su lógica conservadora.
- **Auditabilidad**: un reporte con "Top-10 100%" durante un incidente de RPC no
  es distinguible del evento de concentración que el filtro pretende detectar.
- La heurística de creador penaliza con "0 días" real a wallets nuevas
  (diseño), pero también a wallets antiguas con >1000 txs y a cualquier wallet
  cuyo RPC falla.

## Evidencia de código

```python
# src/chain_data.py:98-103 — docstring promete None, código entrega 100.0
def get_top_holders_pct(token_address: str, api_key: str) -> float:
    """...
    Returns:
        Porcentaje (0-100). Retorna 100.0 si no puede calcular (conservador).
    """
```

## Recomendación

1. Retornar `None` (o un marcador explícito `None`/`"unknown"`) cuando hay
   fallo de RPC en `get_top_holders_pct` y `get_creator_age_days`, y mapearlos
   en `MISSING_INDICATORS`.
2. Añadir un reflector de estado del RPC (`rpc_ok: true/false`) en el resultado
   de `enrich_token` para diagnóstico.
3. Test: mockear RPC caído → assert campos `None` y `status == "missing"`.

## Lección aprendida

Nunca usar valores "imposibles por convención" como banderas de fallo cuando el
dominio admite esos mismos valores como legítimos. El fallo debe propagarse con
su propio tipo de estado (`None`/raising/metadata), jamás en el espacio del dato.