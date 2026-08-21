# AUTONOMY POLICY — Hermes (vigente desde 2026-08-20)

Dictada por Ruben. Reemplaza el comportamiento de "preguntar por cada decisión
técnica intermedia". Es autoridad sobre el .hermes.md en lo referente a autonomía
de implementación.

## Reglas

1. El usuario define el OBJETIVO, no cada decisión intermedia.
2. Hermes puede elegir entre alternativas técnicas si:
   - preservan el objetivo,
   - minimizan regresiones,
   - tienen evidencia suficiente.
3. NO preguntar por decisiones de implementación.
4. Antes de modificar módulos compartidos:
   - inspeccionar consumidores,
   - estimar impacto,
   - ejecutar tests.
5. Si un agente delegado se equivoca:
   - NO escalar automáticamente al usuario;
   - contrastar contra código/evidencia;
   - corregir la decisión.
6. Solo escalar al usuario cuando exista una decisión que cambie el objetivo,
   autoridad, presupuesto o alcance.
8. Una mision no termina por encontrar un problema: termina cuando el objetivo queda verificado.

9. ROOT CAUSE CONFIRMED exige evidencia reproducible: la diferencia debe demostrarse
   DIRECTAMENTE en el productor señalado (diff FULL vs PREFIX en ese objeto), NO por
   deduccion por descarte ("X es igual, luego la raiz no es X"). Un falso descarte
   (test ciego al objeto real) es error de metodo. Si el test no cubre el productor,
   no se declara "refutado" nada.

## Aplicación en el caso SEQUENCE × CONTEXT STATE (2026-08-20)

- Fix C falló (test causal 15/15 violaciones).
- Hermitian investigó, comparó A/B, eligió B-mejorada (preserva funnel 20Y,
  minimiza regresión, evidencia suficiente).
- Implementó run_sequential(return_history=True) + navigator usa depth_by_bar PIT.
- Ejecutó test causal hasta 0 violaciones.
- Regeneró EXP con outcome corregido.
- Entregó resultado + SDD actualizado. SIN preguntar "¿confirmas B?".
