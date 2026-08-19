# Lógica anti-look-ahead — Multi-TF Navigation + Secuencia

**Estado:** NORMATIVO  
**Módulos:** `engine/mtf_navigation.py`, `engine/sequential_events.py`  
**Fecha:** 2026-08-18

---

## 1. Principio

En el timestamp de decisión \(t\) (TF de ejecución):

> Solo puede usarse información cuya **barra de confirmación** sea conocida en \(t\),  
> es decir, velas con `close_time ≤ t` en **cada** temporalidad consultada.

Nada de lo futuro puede cambiar una decisión ya tomada en \(t\).

---

## 2. Multi-TF (`MTFNavigator`)

### 2.1 Selección de barra HTF (`_asof_index`)

```text
asof_bar(TF, t) = max { i | time_TF[i] ≤ t }
```

- Si no hay barra con `time ≤ t` → esa capa no aporta snapshot (`None`).
- Las barras HTF con `time > t` **no existen** para el navegador en esa decisión.

### 2.2 Snapshots por capa

Cada `LayerSnapshot` se calcula **solo** sobre el prefijo:

```text
df_TF.iloc[0 : asof_bar + 1]
```

Incluye:

| Insumo | Regla anti-lookahead |
|--------|----------------------|
| Swings estructurales | Pivotes **causales** (`left` barras a cada lado ya cerradas; confirmación en `j+left`) |
| Dealing range | High/low del lookback terminado en `asof_bar` |
| EQH/EQL | Solo swings con `bar ≤ asof_bar` |
| Displacement | Prefijo hasta `asof_bar` |
| BOS (`detect_bos`) | Prefijo hasta `asof_bar`; *caveat*: el detector interno usa swings centrados — ver §5 |

### 2.3 Orden del grafo

```text
D1 → H4 → H1 → LTF
```

Cada pregunta solo lee el snapshot ya acotado por \(t\). No se “pide prestada” una vela H4 que cierra después de \(t\).

### 2.4 Constraints

`ContextConstraints` se deriva únicamente de los snapshots as-of \(t\).  
Policy: `CONTEXT_ONLY_NOT_ENTRY` — no es orden.

---

## 3. Secuencia (`run_sequential`) cableada al grafo

### 3.1 Índice point-in-time

Tras `run_sequential` en el TF de secuencia (por defecto H1):

```text
depth_visible(i) = max { len(chain.nodes) | chain.last_bar ≤ i }
complete_seen(i) = #{ chain | status=COMPLETE ∧ last_bar ≤ i }
```

- Una cadena con `last_bar = 5000` **no** incrementa `depth_visible` en barras `< 5000`.
- En `HAS_SEQUENCE_DEPTH`, el grafo usa `depth_visible(asof_bar)` del H1 as-of \(t\).

### 3.2 Etapas de la cadena

Cada nodo de `SequentialChain` exige `bar > bar` del nodo anterior.  
No hay co-ocurrencia de flags en la misma vela como sustituto de orden.

### 3.3 Fallback

Si no hay índice secuencial (TF ausente o `precompute_sequences=False`):

```text
depth_proxy = 1[structure] + 1[displacement_recent]
source = "proxy"
```

Queda etiquetado en `answers` para auditoría.

---

## 4. Test de integridad (definición operativa)

Para un prefijo de datos hasta \(t\) y el mismo prefijo más futuro \(t' > t\):

1. `navigate(t)` sobre historia completa vs historia cortada en \(t\) debe coincidir en:
   - `asof_bar` por capa
   - `depth_visible` en el TF de secuencia
   - `direction_hint` / zonas derivadas solo de datos ≤ \(t\)
2. Añadir barras `> t` **no** debe alterar el `MarketState` ya computado en \(t\).

Tests unitarios cubren el caso D1 futuro ignorado (`test_asof_ignores_future_htf_bars`).

---

## 5. Caveats conocidos (no ocultar)

| Componente | Riesgo | Mitigación |
|------------|--------|------------|
| `detectors.bos.detect_bos` | Swings `center=True` usan velas futuras *dentro del prefijo* para etiquetar pivotes | Documentado; deuda PIT: portar pivotes solo causales al BOS |
| Prefijo BOS en snapshot | Al cortar en `asof_bar`, el centrado cerca del borde es incompleto | Aceptable como conservador; no usa datos `> t` del frame multi-TF |
| `WAITING_RETEST` | Requiere feed FVG activo | Respuesta `None` hasta cablear zonas FVG al grafo |

---

## 6. Qué queda prohibido

- Usar `merge` de HTF con `direction="forward"` o centrado en el timestamp de ejecución.
- Re-etiquetar decisiones pasadas cuando llega una vela HTF nueva.
- Tratar `ContextConstraints` o `HAS_SEQUENCE_DEPTH` como orden de entrada.
- EMA como definición normativa de bias HTF (ver SDD Context State).
