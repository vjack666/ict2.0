# SEQUENCE_PIT_INTEGRITY

- Estado: **PASS**
- Alcance: EURUSD H1 checkpoints through bar 5000; full run used as reference
- Checkpoints revisados: `40` / `450`
- Violaciones: `0`
- Cadenas FULL: `12100`
- Dataset: `datasets/eurusd_dukascopy_20y/EURUSD_H1.csv`
- Dataset SHA256: `2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022`
- Git HEAD: `4804ec5540618aae12eb7a0253cbefca2b829922`
- Worktree limpio antes de ejecutar: `True`

La comparación excluye el estado final y los nodos posteriores al checkpoint; solo compara la trayectoria observable hasta cada barra.
