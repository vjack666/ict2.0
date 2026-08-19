> ⚠️ **DESCARTADO 2026-08-19.** Se creó la cuenta AWS (nueva, free-tier post-2025-07-15)
> y el IAM user `hermes-ict2-0`, pero se decidió **NO usar EC2**. Los procesos pesados
> (Funnel 20Y, TNA 20Y, backtest) se ejecutan en **Grok** (servidores de la nube del Director).
> Ver `docs/EXECUTION_STRATEGY.md`. Los scripts de `scripts/aws/` quedan como referencia
> histórica y **no se usarán**.
>
> La traza de gobernanza sambias aquí abajo por integridad.

# AWS_EXECUTION_HOST — Gobernanza de costos y边界 (ICT 2.0)

Este documento define el marco de operacion de la EC2 `hermes-ict2-0`
(AWS_EXECUTION_HOST). Es vinculante: Hermes NO crea/modifica IAM/borra recursos
sin OK explicito de Ruben.

## 1. Tipo de instancia y free-tier (verificado contra docs AWS 2026)

| Cuenta | Free-tier eligible | Duracion | Nota |
|---|---|---|---|
| Antes 2025-07-15 | `t2.micro`, `t3.micro` | 12 meses | `t4g.small` NO gratis aqui |
| 2025-07-15 o despues | `t3.micro`, `t3.small`, `t4g.micro`, `t4g.small`, `c7i-flex.large`, `m7i-flex.large` | 6 meses / creditos | capado, no excede limite |

**Plan:** arrancar con `t4g.small` (ARM64/Graviton2, 2 vCPU/2 GB) y BENCHMARK.
Si es lento -> `t4g.medium` (4 GB). Solo subir si la evidencia lo exige.

## 2. Trampas de factura (no son las horas de instancia)

1. **EBS huérfano:** el disco se factura AUNQUE la instancia este apagada.
   -> Al terminar: `stop` + ELIMINAR volume.
2. **Data egress:** trafico de salida a internet se cobra.
   -> No servir web publica; usar solo para procesar y `git push`.
3. **Elastic IP libre / snapshots / region equivocada.**
   -> Region fija `us-east-1`; sin EIP.
4. **t4g = ARM64:** usar AMI Ubuntu 24.04 ARM64 o no arranca.
5. Pool 750 hr/mes compartido entre instancias.

## 3. Autorizaciones requeridas (Ruben)

| Accion | Quien |
|---|---|
| Crear EC2 / SG / key pair / EBS | Ruben (OK explicito) |
| Modificar IAM / roles | Ruben (OK explicito) |
| Borrar instancia / volume / datos | Ruben (OK explicito) |
| Preparar scripts IaC / bootstrap / benchmark | Hermes (autonomo) |
| Ejecutar auditorias/experimentos dentro de la host | Hermes (autonomo, tras arranque) |
| git pull / run / commit / push a GitHub | Hermes (autonomo) |

## 4. Arranque automatico (tras creacion manual)

```
EC2 up -> git pull -> lee .hermes-index -> ejecuta tarea pendiente
       -> audita -> corrige -> tests -> repite -> reporte -> commit
```

## 5. Aviso

AWS Budgets/alertas de costo DEBEN configurarse en la consola ANTES del lanzamiento.
