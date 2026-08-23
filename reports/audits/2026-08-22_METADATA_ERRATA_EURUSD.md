# Fe de erratas — metadata EURUSD Dukascopy 20Y

**Fecha:** 2026-08-22
**Alcance:** corregir la representación de conteos de procedencia; no modificar los CSV.
**Fuente:** `datasets/eurusd_dukascopy_20y/` generado con `dukascopy-node`.

## Corrección

La metadata anterior registraba en `n` el conteo previo a la limpieza OHLC,
mientras que los CSV versionados contienen las filas limpias consumidas por
TNA. La metadata ahora conserva ambos conteos:

| TF | `n_raw` | Eliminadas por OHLC inválido | `n_clean` / `n` |
|---|---:|---:|---:|
| H1 | 124390 | 13 | 124377 |
| H4 | 32137 | 4 | 32133 |
| D1 | 6258 | 0 | 6258 |

## Integridad

Los CSV no se modifican. Sus SHA256 versionados permanecen:

```text
EURUSD_D1.csv  9738c970f3b9ef75e83aad3509a69d267a895fb47ac8176f75b78a24bf1665d2
EURUSD_H1.csv  c83e608678f98c55fbddeecc1b363ff3c6c3b8cee0ac95c3c34318a5a24a1139
EURUSD_H4.csv  91b985650a95882552511ccb36726f4914174d4e95cb192b52f9a194deacfc8b
```

`n_clean` es el conteo canónico para auditorías que consumen los CSV. `n_raw`
queda como trazabilidad del input Dukascopy previo a la limpieza. Esta errata
no es una sustitución de feed: el snapshot no proviene de MT5.
