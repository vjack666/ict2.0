# ICT Concepts — Operational Rulebook

> Reference specification for Inner Circle Trader concepts used in ICT SYSTEM.
> This document defines detection, validation, and failure conditions for each concept.
> These are **not** trading rules — they are machine-readable specifications that modules may reference.
>
> **ICT SYSTEM policy:** OTE (Optimal Trade Entry) is intentionally excluded. Entry is based on liquidity, structure, displacement and return to FVG/OB zones.

---

## 1. Market Structure (HH / HL / LH / LL)

### Definition
Market structure describes the sequence of swing highs and swing lows that define the prevailing trend direction.

| Term | Meaning |
|------|---------|
| HH | Higher High — current swing high exceeds prior swing high |
| HL | Higher Low — current swing low exceeds prior swing low |
| LH | Lower High — current swing high is below prior swing high |
| LL | Lower Low — current swing low is below prior swing low |

### Detection Conditions
1. Identify swing points using a zigzag method: a local high/low is confirmed when price reverses by at least N ATR units or N consecutive bars in the opposite direction.
2. Compare each new swing high to the prior swing high: if higher → HH, if lower → LH.
3. Compare each new swing low to the prior swing low: if higher → HL, if lower → LL.

### Uptrend Definition
```
HH + HL  →  Bullish structure
```

### Downtrend Definition
```
LH + LL  →  Bearish structure
```

### Failure Conditions
- Price fails to exceed prior swing by at least the minimum swing threshold.
- False breakout: price exceeds prior swing but closes back inside the prior range.
- Three consecutive swings failing to make progress → trend exhaustion.

---

## 2. Break of Structure (BOS)

### Definition
A Break of Structure occurs when price moves beyond a key swing point, confirming trend continuation.

- **Bullish BOS:** price closes above a prior HH in an uptrend.
- **Bearish BOS:** price closes below a prior LL in a downtrend.

### Validation Conditions
- Candle closes beyond the swing point.
- Break is structural, not merely an intraday wick.

---

## 3. Change of Character (CHOCH / Market Structure Shift)

### Definition
A CHOCH signals a potential trend reversal when price breaks a key structure point against the prevailing trend.

- **Bullish CHOCH:** in a downtrend, price breaks above the most recent LH.
- **Bearish CHOCH:** in an uptrend, price breaks below the most recent HL.

### Validation Conditions
- Break of the swing point with a closing candle.
- Follow-through confirms the new direction.
- The broken level is subsequently respected as support/resistance.

---

## 4. Liquidity Pools

### Definition
Liquidity pools are clusters of stop orders around meaningful swing highs/lows.

| Pool | Location | Target |
|------|----------|--------|
| Buy-side liquidity (BSL) | Above swing highs | Stops above prior highs |
| Sell-side liquidity (SSL) | Below swing lows | Stops below prior lows |
| Range liquidity | Both sides of a range | Stops above/below range bounds |

### Validation Conditions
- Multiple swing points converge near the same price level.
- Price reacts sharply after reaching the zone.

---

## 5. Liquidity Sweep / Stop Hunt

### Definition
A liquidity sweep occurs when price briefly moves beyond a known liquidity pool and reverses.

### Detection Conditions
1. Identify a liquidity pool above a swing high or below a swing low.
2. Price exceeds the pool level.
3. Price immediately reverses and closes back within the prior range.

### Validation Conditions
- Wick beyond the level, close back inside.
- Subsequent price action moves opposite to the sweep direction.
- Often precedes BOS or CHOCH.

### Failure Conditions
- Price closes beyond the level and continues → true break, not sweep.
- Price hovers at the level without piercing it.

---

## 6. Displacement

### Definition
Displacement is a strong directional price movement characterised by a large candle body with little to no wick, breaking structure or leaving an imbalance.

### Validation Conditions
- Body-to-range ratio > 0.7.
- Candle range is materially larger than surrounding candles.
- Break of a structural level or creation of an actionable imbalance.

### Failure Conditions
- Large wick → rejection, not clean displacement.
- Price immediately returns into the prior range.

---

## 7. Fair Value Gap (FVG)

### Definition
A Fair Value Gap is a three-candle price imbalance where the first and third candles do not overlap across the displacement candle.

### Detection — Bullish FVG
```
low[i] > high[i-2]
```

### Detection — Bearish FVG
```
high[i] < low[i-2]
```

### Validation Conditions
- Uses closed candles only.
- Gap is between wicks, not merely candle bodies.
- Preferably created by displacement.
- Track fill state: unfilled / mitigated / used.

### Failure Conditions
- Gap is immediately filled.
- Gap is negligible or clearly noisy.

### Entry Principle
A valid FVG is an **entry zone on retrace**, not a reason to chase the displacement candle.

---

## 8. Order Blocks (OB)

### Definition
An Order Block is the last opposing candle or compact opposing zone before a strong directional displacement.

### Detection — Bullish OB
1. Identify bullish displacement.
2. The last bearish candle before the displacement is the bullish OB.

### Detection — Bearish OB
1. Identify bearish displacement.
2. The last bullish candle before the displacement is the bearish OB.

### Validation Conditions
- Displacement must be meaningful and structural.
- The OB must be available for a later return/retest.
- Track status: active / invalidated / aged.

### Failure Conditions
- Price closes through the invalidation boundary.
- Zone is already fully consumed.
- Displacement was a false break.

### Entry Principle
The OB is an **entry zone on return/retest** after confirmation, not a chase entry on the impulse candle.

---

## 9. Premium / Discount Context (EQ 50%)

### Definition
Premium/discount remains a contextual dealing-range tool. It is **not an OTE system** and does not require Fibonacci retracement levels.

- **Discount:** price below the 50% equilibrium of the reference range.
- **Premium:** price above the 50% equilibrium.
- **EQ:** midpoint of the reference range.

### Detection Conditions
1. Identify a valid reference range.
2. Compute midpoint = `(high + low) / 2`.
3. Classify current price as PREMIUM, DISCOUNT or EQ.

### Operational Role
- Premium/discount may provide contextual alignment for long/short POIs.
- It may contribute to quality/context when explicitly configured.
- **No Fibonacci 62–79% retracement is calculated.**
- **No OTE gate, score, or entry refinement exists.**

---

## 10. Multi-Timeframe Analysis (MTF)

### Definition
HTF establishes bias/context; ITF establishes the actionable FVG/OB zone; exec TF handles entry timing.

| TF Role | Purpose |
|---------|---------|
| HTF | Bias, liquidity and dealing-range context |
| ITF | Structure and FVG/OB zone |
| EXEC | Return/retest entry and structural SL |

### Validation Conditions
- HTF bias is established from closed candles.
- ITF produces a valid structural setup.
- EXEC waits for the return to the FVG/OB zone.
- No OTE requirement exists at any timeframe.

---

## 11. ICT Entry Chain — Canonical

The preferred operating sequence is:

```text
HTF bias
  ↓
Liquidity target / pool
  ↓
Sweep
  ↓
Displacement
  ↓
BOS / CHOCH / MSS
  ↓
FVG and/or Order Block
  ↓
Return / Retest to FVG/OB
  ↓
Entry on EXEC TF
  ↓
Structural SL
  ↓
Opposing liquidity TP
```

### Hard principles
- No entry on the displacement chase.
- No entry merely because price touched a Fibonacci level.
- No OTE calculation.
- No OTE gate.
- No OTE score.
- A setup can remain valid without reaching any Fibonacci retracement level, provided the ICT structural conditions are satisfied.

---

## Appendix: Confluence Scoring (Reference)

When multiple ICT concepts align, signal strength may increase. Suggested reference weights:

| Concept | Weight | Notes |
|---------|--------|-------|
| MTF alignment | 3 | HTF and EXEC agree |
| Displacement | 2 | Strong directional move |
| FVG | 2 | Valid actionable imbalance |
| Order Block | 2 | Valid pre-displacement zone |
| Liquidity sweep | 2 | Stop hunt / liquidity event |
| BOS in HTF direction | 1 | Continuation confirmation |
| CHOCH in HTF direction | 3 | Potential reversal confirmation |
| FVG + OB stacking | 3 | Confluence of primary PD Arrays |

> **OTE is deliberately absent from the scoring model.** These weights are reference values, not tuned performance claims.
