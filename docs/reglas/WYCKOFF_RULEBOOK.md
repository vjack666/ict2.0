# Wyckoff Concepts — Operational Rulebook

> Reference specification for Wyckoff market cycle concepts used in SMC_SUCCESSOR.
> This document defines detection logic and confirmation requirements for each Wyckoff phase.
> These are **not** trading rules — they are machine-readable specifications that modules may reference.

---

## Wyckoff Market Cycle Overview

```
Accumulation → Markup → Distribution → Markdown
      ↑                                      │
      └──────────────────────────────────────┘
```

The cycle repeats. Each phase has characteristic price and volume behaviour.

| Phase | Character | Institutional Activity |
|-------|-----------|----------------------|
| Accumulation | Sideways / ranging | Buying while public sells |
| Markup | Rising price | Price moves up, pullbacks on low volume |
| Distribution | Sideways / ranging | Selling while public buys |
| Markdown | Falling price | Price moves down, bounces on low volume |

---

## 1. Accumulation

### Definition
A horizontal trading range after a prolonged markdown, where informed capital accumulates positions. Characterised by price testing support multiple times with decreasing volume.

### Detection Logic
1. Identify a prior downtrend (LH + LL series).
2. Price enters a sideways range (bounded by horizontal support and resistance).
3. At least 3 touches of support and 3 touches of resistance within the range.
4. Volume characteristics:
   - Volume decreases on support tests over time (selling pressure drying up).
   - Volume spikes on up-moves within the range (preparation for markup).
   - Volume is lower than during the prior markdown.
5. A **Spring** may occur near the end (see Section 5).

### Confirmation Requirements
- Width of accumulation range: typically 15-30% of the prior markdown range.
- Duration: longer accumulations tend to produce stronger markups (Wyckoff: "time = force").
- Volume drying up at support.
- A Spring or Last Point of Support (LPS) near the bottom of the range.

---

## 2. Distribution

### Definition
A horizontal trading range after a prolonged markup, where informed capital distributes its holdings to the public. Characterised by price testing resistance multiple times with decreasing volume.

### Detection Logic
1. Identify a prior uptrend (HH + HL series).
2. Price enters a sideways range (bounded by horizontal support and resistance).
3. At least 3 touches of resistance and 3 touches of support within the range.
4. Volume characteristics:
   - Volume decreases on resistance tests (buying pressure drying up).
   - Volume spikes on down-moves within the range (distribution bars).
   - Volume is lower than during the prior markup.
5. An **Upthrust** may occur near the end (see Section 6).

### Confirmation Requirements
- Width of distribution range: typically 15-30% of the prior markup range.
- Duration signals the strength of the subsequent markdown.
- Volume drying up at resistance.
- An Upthrust or Last Point of Supply (LPSY) near the top of the range.

---

## 3. Markup

### Definition
The phase following accumulation where price breaks out of the range and trends upward. Markup consists of a series of higher highs and higher lows.

### Detection Logic
1. Break above the accumulation range resistance.
2. Price makes HH + HL swings.
3. Volume characteristics:
   - Volume increases on breakout and on up-legs.
   - Volume decreases on pullbacks (low-volume corrections).
   - Effort (volume) matches or leads Result (price).
4. Pullbacks are short in both duration and price retracement (< 50% of prior leg).

### Confirmation Requirements
- Breakout of accumulation range on > 1.5x average volume.
- First pullback holds above the breakout level (support turn).
- Higher lows establish a rising trend line.
- No distribution signs within the move.

---

## 4. Markdown

### Definition
The phase following distribution where price breaks below the range and trends downward.

### Detection Logic
1. Break below the distribution range support.
2. Price makes LH + LL swings.
3. Volume characteristics:
   - Volume increases on breakdown and on down-legs.
   - Volume decreases on bounces (low-volume corrections).
   - Effort matches Result on the downside.
4. Bounces are short in both duration and price retracement (< 50% of prior leg).

### Confirmation Requirements
- Breakdown of distribution range on > 1.5x average volume.
- First bounce holds below the breakdown level (resistance turn).
- Lower highs establish a falling trend line.
- No accumulation signs within the move.

---

## 5. Spring (UTAD — Upthrust After Distribution)

### Definition
A Spring is a brief move below the accumulation range support that immediately reverses back inside the range. It is the final shakeout before markup begins. The Spring "takes out" stops of weak longs and traps late shorts.

### Detection Logic
1. Accumulation range has been identified (horizontal support/resistance).
2. Price briefly breaks below support, usually by 1-3% of the range width.
3. The break is intraday or closes only slightly below.
4. Price immediately reverses back into the range.
5. Volume characteristics:
   - High volume on the spring candle (stop-loss triggering and shorts entering).
   - Lower volume on the recovery bars (absorbtion complete).
6. After the Spring, a **LPS** (Last Point of Support) often forms at the range support.

### Confirmation Requirements
- The Spring must occur near the end of the accumulation period (not early).
- Wick below support, close back inside.
- No follow-through below the Spring low.
- A higher-low test (LPS) after the Spring confirms the Spring.

### Failure Conditions
- Price breaks support and continues downward → failed Spring, continuation of markdown.
- Low volume on the Spring → not enough stops triggered, accumulation not ready.
- Multiple Springs → range is not accumulation, it is a re-accumulation or distribution.

---

## 6. Upthrust (UTAD — Upthrust After Distribution)

### Definition
An Upthrust is a brief move above the distribution range resistance that immediately reverses back inside the range. It is the final lure before markdown begins.

### Detection Logic
1. Distribution range has been identified (horizontal support/resistance).
2. Price briefly breaks above resistance, usually by 1-3% of the range width.
3. Price immediately reverses back into the range.
4. Volume characteristics:
   - High volume on the upthrust candle (stop triggering by late buyers).
   - Lower volume on the decline back into range.
5. After the Upthrust, a **LPSY** (Last Point of Supply) often forms at the range resistance.

### Confirmation Requirements
- The Upthrust must occur near the end of the distribution period.
- Wick above resistance, close back inside.
- No follow-through above the Upthrust high.
- A lower-high test (LPSY) after the Upthrust confirms.

### Failure Conditions
- Price breaks resistance and continues upward → failed Upthrust, continuation of markup.
- Low volume on the Upthrust → not enough liquidity taken.
- Multiple Upthrusts → range is not distribution.

---

## 7. Sign of Strength (SOS)

### Definition
A SOS is a price move (usually a wide-range candle) that demonstrates strong buying pressure within or after an accumulation range. SOS confirms that accumulation is progressing toward markup.

### Detection Logic
1. Occurs within an accumulation range or immediately after a Spring.
2. Price moves up with a wide-range candle (range > 1.5x average of prior 20 candles).
3. Volume is significantly above average (1.5x+).
4. The move closes near its high (small upper wick).
5. It breaks above a prior swing high or tests the range resistance.

### Confirmation Requirements
- At least one SOS should appear before the markup breakout.
- Multiple SOS signals increase confidence.
- An SOS that breaks above range resistance is the "breakout" — confirms markup has started.
- Subsequent pullback on low volume into the SOS level confirms.

---

## 8. Sign of Weakness (SOW)

### Definition
A SOW is a price move (usually a wide-range candle) that demonstrates strong selling pressure within or after a distribution range.

### Detection Logic
1. Occurs within a distribution range or immediately after an Upthrust.
2. Price moves down with a wide-range candle (range > 1.5x average of prior 20 candles).
3. Volume is significantly above average (1.5x+).
4. The move closes near its low (small lower wick).
5. It breaks below a prior swing low or tests the range support.

### Confirmation Requirements
- At least one SOW should appear before the markdown breakdown.
- Multiple SOW signals increase confidence.
- A SOW that breaks below range support confirms markdown has started.

---

## 9. Last Point of Support (LPS)

### Definition
LPS is the final pullback / support test before markup begins. It is typically a higher low compared to the Spring low, occurring on low volume.

### Detection Logic
1. Accumulation range has been identified.
2. A Spring has occurred (or the range has been tested at support multiple times).
3. Price pulls back toward the range support (or previous spring level).
4. Volume characteristics:
   - Low volume on the pullback (no selling pressure).
   - Narrow-range candles (low volatility).
5. The pullback does **not** break below the Spring low or range support.

### Confirmation Requirements
- LPS must occur after a Spring or after a SOS.
- Volume on LPS must be significantly lower than on the Spring or SOS candles.
- After LPS, the next up-move should be a SOS or the markup breakout.
- Multiple LPS levels → strongest one is the last one before breakout.

---

## 10. Last Point of Supply (LPSY)

### Definition
LPSY is the final bounce / resistance test before markdown begins. It is typically a lower high compared to the Upthrust high, occurring on low volume.

### Detection Logic
1. Distribution range has been identified.
2. An Upthrust has occurred (or the range has been tested at resistance multiple times).
3. Price bounces toward the range resistance (or previous upthrust level).
4. Volume characteristics:
   - Low volume on the bounce (no buying pressure).
   - Narrow-range candles.
5. The bounce does **not** break above the Upthrust high or range resistance.

### Confirmation Requirements
- LPSY must occur after an Upthrust or after a SOW.
- Volume on LPSY must be significantly lower than on the Upthrust or SOW candles.
- After LPSY, the next down-move should be a SOW or the markdown breakdown.

---

## 11. Volume / Price Relationship

### Summary Table

| Behaviour | Interpretation |
|-----------|---------------|
| Price up, Volume up | Strong buying (markup, SOS, breakout) |
| Price up, Volume down | Weak buying (potential distribution, divergence) |
| Price down, Volume up | Strong selling (markdown, SOW, breakdown) |
| Price down, Volume down | Weak selling (potential accumulation, drying up) |
| Price narrow range, Volume low | Indecision / consolidation |
| Price narrow range, Volume high | Potential climax / turning point |

### Detection Logic
Compare volume of the current candle/bar to:
- Rolling average of the prior 20 bars (relative volume).
- Rolling average of the same period in the same session (to adjust for intraday patterns).

### Confirmation Requirements
- A volume spike > 2x the 20-bar average is significant.
- A volume drought < 0.5x the 20-bar average indicates disinterest.
- Volume confirmation increases the reliability of price action signals.

---

## 12. Effort vs Result

### Definition
Wyckoff's principle of Effort vs Result compares the **volume** (effort) to the **price range** (result). When effort and result diverge, it signals potential reversal.

| Effort | Result | Interpretation |
|--------|--------|----------------|
| High volume | Small range | Effort without result → absorption → potential reversal |
| High volume | Large range in direction | Effort = Result → healthy trend |
| Low volume | Large range | Effort less than Result → low-conviction move |
| Low volume | Small range | Effort = Result → low activity, consolidation |

### Detection Logic
1. Compute the N-bar average range (ATR or true range).
2. Compute the N-bar average volume.
3. For each bar, compare range/ATR to volume/average_volume.
4. Identify clusters of divergence (2+ consecutive bars).

### Confirmation Requirements
- 2+ consecutive bars of effort without result → absorption likely occurring.
- Absorption at range boundaries (support/resistance) is significant.
- Absorption after a prolonged move → potential climax.
- High-volume narrow-range candles at a swing point = potential reversal zone.

---

## Appendix A: Phase Transition Signal Matrix

| Current Phase | Signal | Next Phase | Confidence |
|--------------|--------|------------|------------|
| Markdown | Accumulation range forms + Spring | Accumulation | High |
| Accumulation | SOS + breakout above range | Markup | High |
| Markup | Distribution range forms + Upthrust | Distribution | High |
| Distribution | SOW + breakdown below range | Markdown | High |
| Accumulation | SOS without Spring | Markup | Medium |
| Distribution | SOW without Upthrust | Markdown | Medium |
| Markup | Failed breakout (back in range) | Distribution possible | Low |
| Markdown | Failed breakdown (back in range) | Accumulation possible | Low |

> Confidence levels are **not tuned** — they are starting values for future optimisation.
