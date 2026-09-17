# Bug #010: Qwen3 devuelve content=None por thinking mode

**Severidad:** Alta
**Módulo:** Integración IA (src/ai.py)
**Entorno:** LM Studio + Qwen3 4B 2507, Python 3.12
**Fecha:** 2026-09-17

## Descripción

Al llamar a Qwen3 4B vía LM Studio (API OpenAI-compatible), la respuesta falla con `'NoneType' object is not subscriptable`. El score de IA siempre es 0 y aparece `fallback: True`.

## Pasos para reproducir

1. Tener LM Studio corriendo con Qwen3 4B 2507 cargado.
2. Ejecutar `python -m src.main` → opción 1 → buscar "BONK".
3. Ver en logs: `IA no disponible: 'NoneType' object is not subscriptable`

## Resultado esperado

La IA devuelve `{"score": X, "reason": "..."}` parseable.

## Resultado obtenido
WARNING src.ai:get_ai_score:122 - IA no disponible:
'NoneType' object is not subscriptable. Usando fallback.

text

## Causa raíz

**Qwen3 4B tiene "thinking mode" activado por defecto.** El modelo genera tokens de razonamiento interno (`reasoning_content`) antes de emitir la respuesta final (`content`).

Con `max_tokens=200`, el presupuesto se agota **durante el pensamiento**, y el campo `content` llega como `None`. Al hacer `response.choices[0].message.content`, el código crashea al intentar parsear JSON de un `None`.

Evidencia de LM Studio Server Logs:
```json
"message": {
  "role": "assistant",
  "content": "{\"score\": 10, ...}",
  "reasoning_content": ""
}
Solución aplicada
Aumentar max_tokens de 200 a 1500 en _call_lm_studio.

Directiva /no_think al inicio del prompt — instrucción nativa de Qwen3 que desactiva el thinking mode.

Validación defensiva en get_ai_score: si content es None o vacío, retornar fallback limpio en vez de crashear.

python
content = message.content
if not content:
    logger.warning("Respuesta vacía de IA (posible thinking mode)")
    return {"score": 0, "reason": "Respuesta vacía", "fallback": True}
Verificación
bash
python -m src.main
# Opción 1 → 2 → BONK
Log esperado:

text
INFO src.ai:get_ai_score:116 - IA evaluó Bonk: score=10
Reporte final incluye: Score IA: 10/100 + razón generada por IA.

Lección aprendida
Los LLMs modernos (Qwen3, DeepSeek-R1, Claude con thinking) pueden gastar tokens en razonamiento interno sin producir output visible.

Siempre usar max_tokens generoso (1000+) al integrar modelos con thinking mode.

Directiva /no_think es específica de Qwen3 y reduce latencia/costo dramáticamente.

Validar content is not None antes de parsear respuestas de APIs de IA.
