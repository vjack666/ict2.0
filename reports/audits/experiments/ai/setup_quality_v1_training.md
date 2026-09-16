# setup_quality_v1 Training

**Estado:** `REVIEW`
**Trading:** `can_trade=false`, `shadow_mode=true`

## Resultado

- TensorFlow: `2.21.0`
- Input dim: `36`
- Epochs completados: `113`
- Best val_loss: `0.743758`
- Modelo: `data\ml\tensorflow\setup_quality_v1\model.keras`
- Modelo sha256: `44f7f3a2288e3d2d8b7533e5131a0c9edf95e54c5ab31a6c28026bd7330b6e46`

## Metricas

### TRAIN
- setup_decision accuracy: `0.9917`; balanced_accuracy: `0.7500`
- weak_link accuracy: `1.0000`; balanced_accuracy: `1.0000`
- failure_risk accuracy: `0.8917`; balanced_accuracy: `0.7547`

### VALIDATION
- setup_decision accuracy: `0.9167`; balanced_accuracy: `0.9076`
- weak_link accuracy: `0.8854`; balanced_accuracy: `0.8203`
- failure_risk accuracy: `0.7708`; balanced_accuracy: `0.5400`

### TEST_OOS
- setup_decision accuracy: `0.8421`; balanced_accuracy: `0.6246`
- weak_link accuracy: `0.8684`; balanced_accuracy: `0.7913`
- failure_risk accuracy: `0.6447`; balanced_accuracy: `0.4992`

## Lectura

Primera red multi-head entrenada sobre gramatica de setup sin aceptar `UNKNOWN`. Estado `REVIEW`: sirve para shadow diagnostics, no para operar ni modificar el motor.
