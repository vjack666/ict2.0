# Runtime de uso diario

La lectura diaria usa el motor canónico y el feed MT5. El entrypoint canónico es
`scripts/daily/brief_lunes.py`; `scripts/brief_lunes.py` queda como wrapper de
compatibilidad. Esta carpeta define la frontera del uso diario frente al
laboratorio.

La versión y autoridad de esa frontera se declaran en
`runtime/engine_registry.json`. El runtime debe cargar el registro antes de
leer datos y fallar cerrado si `ACTIVE_ENGINE` deja de ser
`OBSERVE_ONLY_NO_ORDER` o si un candidato de laboratorio puede sustituirlo.

Flujo obligatorio:

```text
MT5 → engine → snapshot canónico → agents → orchestration → brief
```

No se entrena, no se generan órdenes y no se modifica la autoridad del motor
durante una lectura diaria.
