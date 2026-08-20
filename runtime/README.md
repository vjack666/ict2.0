# Runtime de uso diario

La lectura diaria usa el motor canónico y el feed MT5. El entrypoint canónico es
`scripts/daily/brief_lunes.py`; `scripts/brief_lunes.py` queda como wrapper de
compatibilidad. Esta carpeta define la frontera del uso diario frente al
laboratorio.

Flujo obligatorio:

```text
MT5 → engine → snapshot canónico → agents → orchestration → brief
```

No se entrena, no se generan órdenes y no se modifica la autoridad del motor
durante una lectura diaria.
