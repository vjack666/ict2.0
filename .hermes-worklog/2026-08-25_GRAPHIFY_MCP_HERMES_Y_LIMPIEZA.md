# Cierre — Graphify MCP para Codex y Hermes

**AGENTE:** Codex
**DEPARTAMENTO:** D0 Dirección y gobierno + D7 Delivery/Tooling
**TAREA:** Verificar la fuente del grafo, retirar respaldos/visualizaciones antiguas y configurar Graphify MCP para Hermes/OpenCode.
**STATUS:** `COMPLETED` — ambos clientes configurados; sin push.

## EVIDENCIA

- `graphify-out/graph.json` se conserva como única fuente actual del grafo.
- Se conservaron `GRAPH_REPORT.md`, `manifest.json` y sidecars necesarios para diagnóstico/actualización.
- Se eliminaron respaldos antiguos `graphify-out/2026-08-22` a `graphify-out/2026-08-25`, `graph.html` y los dos árboles HTML comparativos.
- Codex tiene el MCP global `graphify` configurado en `C:\Users\v_jac\.codex\config.toml`.
- Hermes/OpenCode tiene `graphify` configurado en `opencode.json` con `C:\Python314\python.exe` y la ruta absoluta del `graph.json`.
- `opencode mcp list` verificó `graphify connected`, junto con Engram y Context7.
- Los agentes de OpenCode reciben permiso `graphify_*: allow`.
- Graphify fue actualizado después del cambio de configuración: grafo actual con 5.743 nodos y 9.870 relaciones.

## ARCHIVOS

- `opencode.json` — configuración MCP de Hermes/OpenCode.
- `.atl/skill-registry.md` y `.atl/.skill-registry.cache.json` — registro automático de skills actualizado al detectar Graphify.
- `graphify-out/graph.json` — fuente consumida por ambos MCP.
- Este worklog — evidencia del cambio.

## RIESGOS

- Si cambia `C:\Python314\python.exe` o la ubicación del checkout, deben actualizarse ambas configuraciones MCP.
- Las visualizaciones HTML antiguas ya no están disponibles; pueden regenerarse desde el `graph.json` actual si se necesita una vista visual.
- El MCP no actualiza el grafo automáticamente; después de cambios relevantes se debe ejecutar `graphify update .` desde el checkout operativo.

## SIGUIENTE ACCIÓN

Reiniciar o recargar Codex/OpenCode cuando sea necesario para que las sesiones existentes recojan la configuración; usar el mismo `graph.json` como fuente única.
