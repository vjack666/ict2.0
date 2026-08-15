# LangGraph — F7 Backtest Validation

## Why LangGraph?

LangGraph provides a structured, observable way to orchestrate multi-step
validation pipelines. Instead of chaining functions manually or writing a
monolithic script, the validation flow is expressed as a **directed graph**
where each node is an independent, testable unit.

Key benefits for F7:
- **Modularity** — each validation step is its own node.
- **Observability** — state is explicit; easy to inspect, debug, resume.
- **Testability** — nodes can be tested in isolation via the harness.
- **Extensibility** — conditional edges (retry, abort, fallback) and parallel nodes.

## Graph Structure

```
load_data ──→ generate_signals ──→ simulate_bridge ──→ simulate_ea
  │                 │                    │                  │
  ├─(error)         ├─(error)            ├─(error)          ├─(error)
  ▼                 ▼                    ▼                  ▼
┌────────────────────── error_handler ──────────────────────┐
│                           │                               │
│                           ▼                               │
│                          END                              │
└───────────────────────────────────────────────────────────┘

simulate_ea ──→ compare_results ──→ generate_report ──→ END
                   │                      │
                   ├─(error)              ├─(error)
                   ▼                      ▼
             error_handler ──→ END
```

### Nodes

| Node | Description | Logic |
|------|-------------|-------|
| `load_data` | Load OHLC data via `_data_legacy.load_frame()` | Reads parquet, keeps last 5000 bars |
| `generate_signals` | Generate trading signals from price data | EMA20/50 crossover + ATR-based SL/TP |
| `simulate_bridge` | Simulate Bridge Module via real file I/O | Uses `SignalExporter` + `MT5Receiver` (tempdir) |
| `simulate_ea` | Execute via `MT5BacktestRunner` | Fixed 0.5 pip slippage, commission included |
| `compare_results` | Compare Python (OHLC walk) vs EA results | Realistic P&L via OHLC SL/TP hit simulation |
| `generate_report` | Produce text report via `ReportGenerator` | Full validation report with verdict |
| `error_handler` | Handle errors from any node | Captures errors, creates minimal report |

### Conditional Edges

Every node routes through a conditional edge. If the node sets `errors`,
the graph diverts to `error_handler` instead of continuing the main flow.

## State Schema

```python
class ValidationState(TypedDict):
    symbol: str
    timeframe: str
    data_dir: str
    total_bars: int
    signals: list[dict]       # Generated signals
    bridge_results: list[dict] # Bridge I/O results
    ea_results: list[dict]     # EA simulation results
    comparison: dict | None    # TradeComparator output
    report: str                # Formatted report text
    status: str                # Pipeline status
    errors: list[str]          # Accumulated errors
```

## Usage

### Via Python

```python
from smc_successor.orchestration.backtest_validation_graph import run_validation

result = run_validation(symbol="EURUSD", timeframe="M15")
print(result["status"])   # "report_generated"
print(result["report"])   # Full validation report
```

### Via test script

```bash
python scripts/test_validation_graph.py
python scripts/test_validation_graph.py --symbol GBPUSD --timeframe H1 --verbose
```

### Via harness

```bash
cd SMC_SUCCESSOR
python -m harness --scenarios harness/scenarios --adapters langgraph_validation
```

## Signal Generation

Signals are generated using EMA20/50 crossover logic:
- BUY when EMA20 crosses **above** EMA50
- SELL when EMA20 crosses **below** EMA50
- SL/TP set at 2× ATR / 3× ATR respectively
- Minimum 10 bars between signals to avoid clustering

## Comparison Methodology

- **Python trades**: P&L computed by walking OHLC bars forward from entry,
  checking if SL or TP is hit by the bar's high/low. If neither is hit
  within the available data, exit at the last close.
- **EA trades**: Simulated by `MT5BacktestRunner` which assumes TP is always
  hit (no OHLC context). This creates a realistic delta for validation.
- **Delta** = EA metric − Python metric. Positive delta means EA outperformed
  the realistic OHLC-walk simulation.

## Future Enhancements

- [ ] Replace EMA crossover with SMC signal pipeline (FVG, order blocks, etc.)
- [ ] Add parallel execution for comparison simulations
- [ ] Add checkpointing / resume from last completed node
- [ ] Integrate with real MT5 backtest data instead of simulated EA
- [ ] Add more conditional edges: retry on bridge I/O failure, skip on missing data
