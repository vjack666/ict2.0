# Auditoría independiente — baseline PASS_EDGE intradía

**Fecha:** 2026-09-02  
**Resultado global:** `BLOCKED`  
**Resultado económico diagnóstico:** `NO_EDGE_PROXY`

## Matriz de gates

| Gate | Estado | Evidencia |
|---|---|---|
| Baseline sin IA | `PASS_DIAGNOSTIC` | 16 JSON trimestrales, 315 trades y 81 outcomes |
| Costes congelados | `PASS_DIAGNOSTIC` | spread 1 pip, slippage 0,3 pip, US$5/lote/lado |
| Periodos/sesiones/regímenes | `REVIEW` | 2022–2025; sesiones negativas; H4 bullish/bearish negativos |
| Estadística temporal | `PASS_DIAGNOSTIC` | bootstrap 16 clusters; IC `[-1,348208R, -0,604024R]` |
| Cobertura del diseño completo | `BLOCKED` | el proxy Parquet no cubre DESIGN 2006–2016 ni VALIDATION 2016–2021 M15 homogéneamente |
| Procedencia/licencia/ adquisición | `BLOCKED` | provider, adquisición y permitted use no están cerrados de extremo a extremo |
| Reproducibilidad certificable | `BLOCKED` | worktree actual está DIRTY; no puede emitirse certificado CLEAN |
| IA contra baseline | `NOT_RUN` | correctamente retenida hasta cerrar el baseline científico |

## Conclusión

En el proxy disponible, el baseline sin IA es negativo después de costes en
2022–2025, por sesiones y por los dos regímenes H4 observados. La evidencia
económica apunta a `NO_EDGE_PROXY`, pero el SDD no permite convertir ese
resultado en `NO_EDGE` global mientras cobertura, procedencia y reproducibilidad
certificada sigan bloqueadas.

No se autoriza entrenamiento, comparación IA, holdout confirmatorio, paper/demo,
broker ni `can_trade=true`. La próxima acción es cerrar los gates de datos y
repetir la auditoría desde un worktree limpio; solo entonces se decidirá
`NO_EDGE` o `REVIEW` global.
