# Auditoría de conflictos de reglas — 2026-09-10

**Alcance:** motor ICT/Wyckoff, Context State, snapshot MT5 y flujo manual del bot mecánico. No cambia datasets, estrategia ni autorización de trading.

## Dictamen

**REVIEW / NO PROMOCIÓN.** El sistema no tiene una sola regla de dirección. Tiene capas con responsabilidades distintas, pero el visor las presenta juntas y el snapshot conserva `can_trade=false` y `entry_authorized=false`. Los conflictos observados son principalmente conflictos de contexto, no errores que deban resolverse forzando una dirección.

## Evidencia actual

| Capa | Estado observado | Autoridad |
|---|---|---|
| D1 ICT | `COMPRESSION`, `MIXED`, direction hint `BULLISH` | contexto superior |
| H4 ICT | `TREND_BULL`, `BULLISH` | contexto intermedio |
| M15 ICT | `TREND_BEAR`, `BEARISH`, BOS bajista reciente | ejecución/observación |
| Wyckoff | `DISTRIBUTION`, alineación `CONFLICT` | contexto explicativo |
| Bot | selección manual `SELL` + espera estocástico | decisión del operador |

## Causas raíz

1. `direction_hint`, `structure_bias`, `last_bos_direction` y `wyckoff.phase` se muestran como si fueran la misma dirección.
2. Wyckoff clasifica oposición como `TRANSITION` si no hay evento de transición; no es una señal negativa ni un veto.
3. `allow_short=false` pertenece a Context State automático; el flujo manual es otra autoridad y debe mostrarse separado.
4. El estocástico M15 es un gatillo temporal, no un resolutor de conflictos HTF.
5. El snapshot normativo es observación solamente; el bot mecánico manual puede operar bajo autorización explícita, pero debe marcarse como `MANUAL_OVERRIDE`.

## Reglas consolidadas propuestas

- **Contexto:** reportar D1/H4/M15 por separado; no promediar ni sobrescribir.
- **Alineación:** `ALIGNED`, `AGAINST`, `MIXED` o `UNRESOLVED`; el conflicto no se convierte automáticamente en BUY/SELL.
- **Contratendencia:** solo etiquetar `COUNTERTREND` con evento Wyckoff explícito y confirmación M15 cerrada.
- **Entrada automática:** requiere permiso Context State, snapshot fresco confirmado y gatillo M15.
- **Entrada manual:** requiere activación, lado elegido, sesión válida y gatillo estocástico; se etiqueta `MANUAL_OVERRIDE`.
- **Salida:** un único ciclo, recompras configuradas y cierre por flotante agregado.

## Riesgos y acciones

**BLOCKED para producción:** no existe evidencia de edge ni certificación de costes; `can_trade=false` permanece protegido. La siguiente acción es implementar el contrato de arbitraje y actualizar el visor para que no mezcle contexto con autorización.
