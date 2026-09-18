# Bug #021: El código prioriza el TP sobre el SL; la documentación afirma lo contrario

**Severidad:** Baja
**Módulo:** Monitoreo de riesgo (`src/main.py:469-472`) vs documentación (`docs/riesgo.md`)
**Entorno:** v2.1
**Fecha:** 2026-09-18

## Descripción

En `monitor_positions`, cuando en un mismo tick se disparan TP y SL, la decisión
es `"TP" if hit_tp else "SL"` — es decir, **TP gana**. `docs/riesgo.md` declaraba
exactamente lo inverso: "**SL siempre tiene prioridad sobre TP** si ambos se
disparan". El comportamiento real y el documentado no coinciden.

> Nota de análisis: geométricamente los dos no pueden dispararse con la misma
> muestra de precio (exigiría `price >= tp` y `price <= sl`, con `tp > sl`), así
> que la rama es **código muerto real** hoy. No obstante, la contradicción
> documental es un defecto de diseño: si mañana cambian los umbrales (por
> ejemplo un SL que se mueve por encima del TP tras trailing extremo), la
> prioridad efectiva será la opuesta a la que los usuarios leen en la doc.

## Pasos para reproducir

1. Leer `docs/riesgo.md` "Take Profit (TP) y Stop Loss (SL)" → afirma prioridad SL.
2. Leer `src/main.py:469-472` → verificación TP primero.
3. (Teórico) Inyectar mock donde `hit_tp and hit_sl` → verificar que se actúa TP.

## Resultado esperado

- Doc y código coinciden, o la prioridad está documentada como no determinista
  con razón explícita.

## Resultado obtenido

- Código: TP tiene la prioridad en la rama conjunta.
- Doc: dice SL.
- Sin cobertura de tests para el caso conjunto (`test_risk.py` cubre TP y SL por
  separado, nunca `hit_tp and hit_sl`).

## Causa raíz

El branch de prioridad fue escrito sin que un requisito resolviera el caso y la
doc se escribió desde el "deseo" (proteger capital) sin auditar la
implementación. La condición `if hit_tp or hit_sl` con `reason = TP if hit_tp`
fue un atajo de legibilidad, no una decisión de negocio explicitada.

## Impacto en la decisión

- Nulo hoy (caso inalcanzable), **riesgo latente** ante futuros cambios de
  parámetros. La desalineación doc/código mina la auditabilidad del sistema de
  riesgo — justo lo que un revisor de riesgo debe señalar.

## Evidencia de código

```python
# src/main.py:469-472
hit_tp = check_take_profit(position, price)
hit_sl = check_stop_loss(position, price)
if hit_tp or hit_sl:
    reason = "TP" if hit_tp else "SL"
```

## Recomendación

1. Elegir y documentar una prioridad (recomendado: **SL**, la pérdida controlada
   siempre manda) y reescribir como `if hit_tp and hit_sl: ... SL ...`.
2. Añadir un test que cubra `hit_tp and hit_sl` para fijar el contrato.
3. Actualizar `docs/riesgo.md` para que refleje la decisión final.

## Lección aprendida

La documentación de un mecanismo de riesgo debe escribirse **desde el codigo
ejecutado**, no desde la intención, y los casos dobles de disparo deben tener
una regla explícita + test que la fijen. Contratos de seguridad que dependen de
la lectura minuciosa de una condición son el primer lugar donde una futura
refactor rompe el sistema silenciosamente.