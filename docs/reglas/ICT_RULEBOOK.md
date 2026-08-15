# ICT Concepts — Operational Rulebook

> Reference specification for Inner Circle Trader concepts used in SMC_SUCCESSOR.
> This document defines detection, validation, and failure conditions for each concept.
> These are **not** trading rules — they are machine-readable specifications that modules may reference.

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
Each swing high is higher than the last; each swing low is higher than the last.

### Downtrend Definition
```
LH + LL  →  Bearish structure
```
Each swing high is lower than the last; each swing low is lower than the last.

### Neutral / Transitional
- HH + LL: possible trend reversal or range expansion
- LH + HL: contraction / consolidation

### Validation Conditions
- At least 2 consecutive HH/HL pairs for uptrend confidence
- At least 2 consecutive LH/LL pairs for downtrend confidence
- Swing points should be confirmed by volume or momentum divergence

### Failure Conditions
- Price fails to exceed prior swing by at least the minimum swing threshold
- False breakout: price exceeds prior swing but closes back inside the prior range
- Three consecutive swings failing to make progress → trend exhaustion

---

## 2. Break of Structure (BOS)

### Definition
A Break of Structure occurs when price moves beyond a key swing point, confirming trend continuation.

- **Bullish BOS**: Price breaks above a prior HH in an uptrend
- **Bearish BOS**: Price breaks below a prior LL in a downtrend

### Detection Conditions
1. Confirm existing market structure (uptrend requires HH/HL, downtrend requires LH/LL).
2. Price must close **above** the prior swing high (bullish) or **below** the prior swing low (bearish).
3. The break must be on a closing basis, not merely an intraday wick.

### Validation Conditions
- Candle closes beyond the swing point.
- Break accompanied by above-average volume or momentum.
- Retest of the broken level holds (old resistance becomes support, or old support becomes resistance).

### Failure Conditions
- Wicky break: price exceeds the level intraday but closes back within the prior range.
- False break / liquidity grab: price spikes beyond the level, reverses immediately.
- Break occurs during low-volume / holiday session.
- No follow-through within N bars → failed BOS.

---

## 3. Change of Character (CHOCH / Market Structure Shift)

### Definition
A Change of Character (also called Market Structure Shift) signals a potential trend reversal. It occurs when price breaks a key structure point **against** the prevailing trend.

- **Bullish CHOCH**: In a downtrend (LH/LL), price breaks above the most recent LH.
- **Bearish CHOCH**: In an uptrend (HH/HL), price breaks below the most recent HL.

### Detection Conditions
1. Confirm prevailing trend direction.
2. Identify the most recent swing high (bearish trend) or swing low (bullish trend) that has not been broken.
3. Price must close **beyond** that level in the opposite direction of the trend.

### Validation Conditions
- Break of the swing point with a closing candle.
- At least one follow-through bar confirming the new direction.
- Volume divergence or momentum shift at the break point.
- The broken level is subsequently respected as support/resistance.

### Failure Conditions
- Price returns inside the prior structure within N bars → failed shift.
- The break is a liquidity grab (wick beyond, close inside).
- Trend resumes and breaks beyond the CHOCH point → trap.

---

## 4. Liquidity Pools

### Definition
Liquidity pools are clusters of pending stop orders / limit orders that price is expected to target. ICT identifies several types:

| Pool | Location | Target |
|------|----------|--------|
| Buy-side liquidity (BSL) | Above swing highs | Stops above prior HHs |
| Sell-side liquidity (SSL) | Below swing lows | Stops below prior LLs |
| Trend-line liquidity | Along trend lines | Breakout stops |
| Range liquidity | Both sides of a range | Stops above/below range bounds |

### Detection Conditions (BSL)
1. Identify sequence of swing highs.
2. Each swing high represents a cluster of stop-loss orders from short positions.
3. The highest level of buy-side liquidity is typically above the most recent HH.

### Detection Conditions (SSL)
1. Identify sequence of swing lows.
2. Each swing low represents a cluster of stop-loss orders from long positions.
3. The lowest level of sell-side liquidity is typically below the most recent LL.

### Validation Conditions
- Multiple swing points converge near the same price level → high-liquidity zone.
- Volume increases as price approaches the level.
- Price reacts sharply after reaching the zone.

### Failure Conditions
- Price reaches the zone but reverses without taking stops.
- Price absorbs the liquidity and continues in the same direction (run on stops that fuels further movement).

---

## 5. Liquidity Sweep / Stop Hunt

### Definition
A liquidity sweep occurs when price briefly moves beyond a known liquidity pool (swing high/low) to trigger stop orders, then reverses.

### Detection Conditions
1. Identify a liquidity pool (above a swing high or below a swing low).
2. Price exceeds the pool level (intraday wick or small close).
3. Price immediately reverses and closes back within the prior range.
4. The move beyond the level is typically on high volume.

### Validation Conditions
- Wick beyond the level, close back inside.
- High volume on the sweep candle.
- Subsequent price action moves opposite to the sweep direction.
- Often precedes a BOS or CHOCH.

### Failure Conditions
- Price closes beyond the level and continues → not a sweep, it is a true break.
- Low volume break → not enough stops triggered.
- Price hovers at the level without piercing it.

---

## 6. Displacement

### Definition
Displacement is a strong, directional price movement characterised by a large candle body with little to no wick, breaking out of a consolidation or order block zone.

### Detection Conditions
1. Presence of a tight range / consolidation prior to the move.
2. A candle with a body that is significantly larger than the preceding N candles (e.g., 2x+ average range).
3. Small wick relative to body (efficiency).
4. The move breaks out of a key level (order block, FVG, swing point).

### Validation Conditions
- Body-to-range ratio > 0.7 (small wick).
- Candle range > 1.5x ATR or > 2x average of prior N candles.
- Break of a structural level.
- High volume / tick volume confirming the move.

### Failure Conditions
- Large wick → rejection, not displacement.
- Low volume move → lacks conviction.
- Price returns into the prior range within N bars.
- Displacement occurs into a known liquidity pool → likely a sweep, not a directional move.

---

## 7. Fair Value Gap (FVG)

### Definition
A Fair Value Gap is a price imbalance created when consecutive candles leave a gap between the wick of the first candle and the wick of the third candle, where price did not trade. ICT views these as "inefficiencies" that price is likely to return to and fill.

### Detection — Bullish FVG
```
Candle 1: low
Candle 2: high
Candle 3: low

FVG region = [Candle 1 low, Candle 3 high]
Condition: Candle 1 low > Candle 2 high  (gap exists)
Direction: Bullish
```

### Detection — Bearish FVG
```
Candle 1: high
Candle 2: low
Candle 3: high

FVG region = [Candle 3 low, Candle 1 high]
Condition: Candle 1 high < Candle 2 low  (gap exists)
Direction: Bearish
```

### Validation Conditions
- The gap must be between the **wick** (not body) of C1 and C3.
- Gap size > minimum threshold (e.g., 0.1 ATR).
- Candle 2 must be a displacement candle (large range, small wick).

### Failure Conditions
- Gap is immediately filled on the next candle.
- Gap appears during low-volatility / low-volume conditions.
- Gap size is negligible (< threshold).
- Multiple FVGs in close proximity → noise, not structural.

### Partial Fill / Inversion
- Price may partially fill the FVG and reverse → "inversion" — the unfilled portion acts as a new support/resistance zone.
- If price fills the entire gap and continues, the FVG is considered "used" and no longer relevant.

---

## 8. Order Blocks (OB)

### Definition
An Order Block is the last candle (or zone) before a strong directional move. ICT identifies these as institutional orders left unfilled. OBs are identified in the direction opposite to the impulse move.

### Detection — Bullish OB
1. Identify a bullish displacement move.
2. The **last bearish candle** (or consolidation zone) immediately before the displacement is the bullish OB.
3. The base of the OB is typically the low of that candle or the low of the consolidation zone.

### Detection — Bearish OB
1. Identify a bearish displacement move.
2. The **last bullish candle** (or consolidation zone) immediately before the displacement is the bearish OB.
3. The base of the OB is typically the high of that candle or the high of the consolidation zone.

### Validation Conditions
- The displacement must exceed the prior N candles' average range (e.g., 2x ATR).
- The OB candle must be within the displacement's "radius" — typically within 5-10 bars before the displacement.
- OB zone should have clear support/resistance levels (low for bullish, high for bearish).
- Volume confirmation on the displacement candle.

### Failure Conditions
- Price reaches the OB zone and continues through without reaction.
- Multiple overlapping OBs → zone is diluted.
- Displacement was a false breakout → OB is invalid.
- OB is too old (e.g., > 20 bars back) → likely already filled or irrelevant.

### Migration
- If price sweeps below a bullish OB (or above a bearish OB) and immediately reverses, the OB is considered to have "migrated" — the sweep collected liquidity and the OB level is now validated.

---

## 9. Premium / Discount Zones

### Definition
Price is divided into premium (overvalued) and discount (undervalued) zones relative to a reference point, typically the range between a recent swing low and swing high.

- **Discount zone**: Below the 50% (midpoint) of the range — institutional buying zone.
- **Premium zone**: Above the 50% (midpoint) of the range — institutional selling zone.
- **Optimal Trade Entry (OTE)**: 68-80% retracement into the discount zone for long entries; 20-32% retracement into the premium zone for short entries.

### Detection Conditions
1. Identify a clear swing low and swing high (the reference range).
2. Compute midpoint = (high + low) / 2.
3. Compute Fibonacci levels: 0.618, 0.70, 0.79 (discount entries), 0.21, 0.30, 0.382 (premium entries).
4. Current price relative to the range determines the zone.

### Reference Range Types
- **Intraday range**: Asian session low → high.
- **Daily range**: Previous day's low → high.
- **Swing range**: Multi-day swing low → swing high.

### Validation Conditions
- Price entering the discount zone after a bullish displacement confirms buying interest.
- Price entering the premium zone after a bearish displacement confirms selling interest.
- OTE entries should be validated with a reaction (wick, reversal candle) at the level.

### Failure Conditions
- Blow-through: price cuts through the discount zone without a reaction.
- Range expansion invalidates the reference range — new swing points require recalculation.
- OTE level is hit but no reaction → zone is weak.

---

## 10. Multi-Timeframe Analysis (MTF)

### Definition
ICT emphasises alignment across multiple timeframes. The Higher Timeframe (HTF) sets the bias; the Lower Timeframe (LTF) is used for entries.

| TF Role | Examples | Purpose |
|---------|----------|---------|
| HTF Context | D1, H4 | Trend direction, key levels, premium/discount |
| LTF Execution | M15, M5 | Entries, FVG, OB, sweep detection |

### Hierarchy
```
HTF (D1) → bias direction
 │
 ├── Intermediate (H4) → confirms HTF, finer structure
 │    │
 │    └── LTF (M15/M5) → execute in HTF direction
```

### Detection Conditions
1. HTF market structure must be clearly defined (uptrend or downtrend).
2. LTF must align: in HTF uptrend, look for LTF bullish setups only.
3. If HTF is ranging, LTF trades are filtered out (no clear bias).
4. Conflicting timeframes → no trade (highest-probability setups require alignment).

### Validation Conditions
- HTF trend confirmed by at least 2 swing points.
- LTF shows a CHOCH or BOS in the HTF direction.
- LTF entry at a premium/discount zone of the HTF range.
- LTF sweep of HTF liquidity is a high-confluence setup.

### Failure Conditions
- HTF is ranging → MTF analysis is inconclusive.
- LTF CHOCH occurs against HTF trend → likely a pullback, not a reversal.
- LTF entry at HTF premium (in HTF uptrend) → buying overvalued zone.
- LTF and HTF in opposite alignment → high risk, avoid.

---

## Appendix: Confluence Scoring (Reference)

When multiple ICT concepts align, the signal strength increases. SMC_SUCCESSOR may use these weights for future scoring:

| Concept | Weight | Notes |
|---------|--------|-------|
| MTF alignment | 3 | HTF and LTF in the same direction |
| Displacement | 2 | Large candle with small wick |
| FVG | 2 | Unfilled gap in the direction of trade |
| Order Block | 2 | Last candle before displacement |
| Liquidity sweep | 2 | Stop hunt of the opposite pool |
| BOS in HTF direction | 1 | Continuation confirmation |
| CHOCH in HTF direction | 3 | Potential reversal in HTF direction |
| Premium/Discount OTE | 1 | Entry at optimal retracement level |

> These weights are **not tuned** — they are starting values for future optimisation.
