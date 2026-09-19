# Bug #024: IA local siempre en fallback — doble `/v1` en la URL de LM Studio

**Severidad:** Alta (la IA del pipeline nunca llega a puntuar con la config documentada)
**Módulo:** `src/ai.py` (`_call_lm_studio`) ↔ `src/main.py` (`load_env_config`) ↔ `.env`
**Entorno:** v2.2.4, descubierto en vivo al activar Bionic/LM Studio en `:1234` (2026-09-18)
**Fecha:** 2026-09-18
**Estado:** ✅ Corregido y cubierto por tests

## Descripción

`load_env_config()` toma `LM_STUDIO_URL` tal cual del `.env`:
`http://localhost:1234/v1` (con sufijo `/v1`, tal como documenta `.env.example`).
Ese valor se pasa directo a `get_ai_score(base_url=...)` y de ahí a
`_call_lm_studio`, que construye `f"{base_url}/v1"` → resultado:
`http://localhost:1234/v1/v1`.

LM Studio responde `{"error":"Unexpected endpoint or method. (POST /v1/v1/chat/completions)"}`
y el cliente OpenAI obtiene un `ChatCompletion` con `choices=None`; al hacer
`response.choices[0]` → `'NoneType' object is not subscriptable`, que el
`try/except` de `get_ai_score` convierte en fallback. **Cada token quedaba con
`ai_score=0` y motivo "IA no disponible"** aunque Qwen3 estuviera sirviendo.

Con la config por defecto del código (`http://localhost:1234`, sin `/v1`) sí
funcionaba, por eso el fallo solo aparecía con la configuración real del proyecto.

## Pasos para reproducir

```bash
# .env:  LM_STUDIO_URL=http://localhost:1234/v1  (documentado en .env.example)
venv/bin/python - <<'EOF'
from src.ai import get_ai_score
print(get_ai_score({"symbol": "T", "market_cap": 1, "liquidity_usd": 1,
                    "volume_5min": 1, "top_10_holders_pct": 50.0, "age_minutes": 5}))
EOF
```

## Resultado obtenido (antes del fix)

```
WARNING | src.ai:get_ai_score:109 - IA no disponible: 'NoneType' object is not subscriptable. Usando fallback.
{'score': 0, 'reason': 'IA no disponible', 'fallback': True}

# y en el ciclo automático:
WIF | Reglas= 39 | IA= 0 | Final= 27 | EVITAR   ← todos los tokens con IA=0
```

## Causa raíz

Convención duplicada del sufijo `/v1`: el `.env` (y `.env.example`) lo incluyen,
pero `_call_lm_studio` vuelve a añadirlo. La función debía aceptar **ambas**
convenciones y normalizar.

## Fix aplicado (src/ai.py)

```python
base_url = base_url.rstrip("/")
base_url = base_url.removesuffix("/v1")
client = OpenAI(base_url=f"{base_url}/v1", api_key="not-needed")
```

Ahora sirve tanto `http://localhost:1234` como `http://localhost:1234/v1`.

## Tests añadidos (tests/test_ai.py)

`test_call_lm_studio_normaliza_v1_duplicado` (no genera `/v1/v1`) y
`test_call_lm_studio_sin_v1_le_añade` (añade el sufijo una sola vez). Suite tras
el lote: **176 tests · 82.87 % de cobertura** (`make check` verde).

## Verificación en vivo (Bionic/LM Studio activo en :1234)

```
IA evaluó WIF: score=0
WIF | Reglas=48 | IA=0 | Final=34 | EVITAR     ← IA real (razonamiento de Qwen3 en ai_reason)
INFO | src.ai:get_ai_score:119 - IA evaluó LIVE-TEST: score=30  (fallback=False)
```

## Lección aprendida

Los valores de configuración con estructura de URL (host vs. host+path) deben
normalizarse en la frontera de la función que los consume, no confiar en que
quien documenta el `.env` y quien escribe el cliente coincidan. Un fallback
"seguro" (score 0) enmascaró el bug como degradación silenciosa durante días;
solo se hizo visible al activar el servicio real.