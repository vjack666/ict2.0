"""Live structure table — stream BOS / CHOCH / FVG / sweep / OB as they appear.

Writes continuously to CSV (flush each row) and optionally prints a rolling
console table so the operator sees structure form in real time during a v2 run.

Also updates HERMES_PROGRESS_FILE when present (runner monitor %).
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd


HEADERS = (
    "seq",
    "time",
    "tf",
    "event",
    "direction",
    "level",
    "status",
    "price",
    "note",
)


@dataclass
class StructureEvent:
    time: str
    tf: str
    event: str  # BOS | CHOCH | FVG | SWEEP | OB | SIGNAL | TRADE
    direction: str  # LONG | SHORT | —
    level: str
    status: str
    price: str
    note: str = ""


def _write_progress(current: str, done: int, total: int, unit: str = "events") -> None:
    path = (os.environ.get("HERMES_PROGRESS_FILE") or "").strip()
    if not path:
        return
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {
                    "current": current,
                    "done": int(done),
                    "total": int(total),
                    "unit": unit,
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _dir_label(v: Any) -> str:
    try:
        d = int(v)
    except (TypeError, ValueError):
        return "—"
    if d > 0:
        return "LONG"
    if d < 0:
        return "SHORT"
    return "—"


def _fmt_level(v: Any) -> str:
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return ""
        return f"{float(v):.5f}"
    except (TypeError, ValueError):
        return str(v) if v is not None else ""


class LiveStructureTable:
    """Append-only live table (CSV + optional EventLog).

    Professional console policy (default):
      - Do NOT print every row (no terminal spam).
      - Write CSV with flush so operators can `Get-Content -Wait` if they want.
      - Print only compact milestone lines (every N events) + final summary.
    """

    def __init__(
        self,
        path: Path,
        *,
        console: bool = False,
        console_every: int = 0,
        milestone_every: int = 250,
        event_log_append: Callable[..., int] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # console=True only for explicit verbose mode (row dump)
        self.console = console
        self.console_every = max(1, console_every) if console_every else 0
        self.milestone_every = max(0, int(milestone_every))
        self._event_log_append = event_log_append
        self._seq = 0
        self._counts: dict[str, int] = {}
        self._fh = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=HEADERS)
        self._writer.writeheader()
        self._fh.flush()
        # One professional open line — never a header grid dump
        print(f"[live] Structure table (CSV, streaming) → {self.path}", flush=True)
        print(
            "[live] No row spam. Tail if needed: "
            f'Get-Content "{self.path}" -Wait -Tail 20',
            flush=True,
        )

    def close(self) -> None:
        try:
            self._fh.flush()
            self._fh.close()
        except Exception:
            pass
        self.print_summary()

    def __enter__(self) -> "LiveStructureTable":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def print_summary(self) -> None:
        """Professional end-of-stream summary (counts only)."""
        if self._seq <= 0:
            print("[live] Structure table: 0 events.", flush=True)
            return
        parts = [f"{k}={v}" for k, v in sorted(self._counts.items())]
        print(
            f"[live] Structure table complete: {self._seq} rows "
            f"({', '.join(parts)}) → {self.path}",
            flush=True,
        )

    def emit(self, ev: StructureEvent, *, progress_total: int | None = None) -> int:
        self._seq += 1
        self._counts[ev.event] = self._counts.get(ev.event, 0) + 1
        row = {
            "seq": self._seq,
            "time": ev.time,
            "tf": ev.tf,
            "event": ev.event,
            "direction": ev.direction,
            "level": ev.level,
            "status": ev.status,
            "price": ev.price,
            "note": ev.note,
        }
        self._writer.writerow(row)
        # Live flush so Excel / tail / UI can read while running
        self._fh.flush()
        try:
            os.fsync(self._fh.fileno())
        except OSError:
            pass

        if self._event_log_append is not None:
            try:
                self._event_log_append(
                    ev.event,
                    ts=ev.time,
                    tf=ev.tf,
                    payload={
                        "direction": ev.direction,
                        "level": ev.level,
                        "status": ev.status,
                        "price": ev.price,
                        "note": ev.note,
                        "seq": self._seq,
                    },
                )
            except Exception:
                pass

        # Explicit verbose only: dump rows every console_every
        if self.console and self.console_every and (self._seq % self.console_every == 0):
            print(
                f"  · {ev.event:<7} {ev.direction:<5} {ev.tf} @ {ev.time} "
                f"lvl={ev.level or '—'} {ev.status}",
                flush=True,
            )
        # Quiet milestones (professional): every N events, one compact line
        elif self.milestone_every and (self._seq % self.milestone_every == 0):
            top = ", ".join(
                f"{k}={v}" for k, v in sorted(self._counts.items(), key=lambda x: -x[1])[:5]
            )
            print(
                f"[live] … {self._seq} events written ({top})",
                flush=True,
            )

        if progress_total is not None and progress_total > 0:
            # Progress without noisy "current" per BOS row
            if self._seq == 1 or self._seq == progress_total or (
                self.milestone_every and self._seq % self.milestone_every == 0
            ):
                _write_progress(
                    current=f"structure table {self._seq}/{progress_total}",
                    done=self._seq,
                    total=progress_total,
                    unit="events",
                )
        return self._seq

    @property
    def count(self) -> int:
        return self._seq


def stream_structure_from_ms(
    ms_by_tf: dict[str, pd.DataFrame],
    table: LiveStructureTable,
    *,
    tfs: Iterable[str] | None = None,
    sample_every: int = 1,
) -> int:
    """Walk structure frames in time order and emit events on *onset* only.

    Onset = first bar where a flag becomes true / status becomes active.
    This keeps the table dynamic without flooding every bar of an active BOS.
    """
    order = list(tfs) if tfs is not None else list(ms_by_tf.keys())
    # Collect all onsets then sort by time (no console flood while scanning).
    buffer: list[StructureEvent] = []

    for tf in order:
        df = ms_by_tf.get(tf)
        if df is None or len(df) == 0:
            continue
        d = df
        n = len(d)
        # time column
        if "time" in d.columns:
            times = pd.to_datetime(d["time"], utc=True, errors="coerce")
        else:
            times = pd.to_datetime(d.index, utc=True, errors="coerce")

        closes = d["close"].to_numpy() if "close" in d.columns else np.full(n, np.nan)

        bos_dir = d["bos_dir"].to_numpy() if "bos_dir" in d.columns else np.zeros(n)
        bos_status = (
            d["bos_status"].astype(str).to_numpy()
            if "bos_status" in d.columns
            else np.array([""] * n)
        )
        bos_level = d["bos_level"].to_numpy() if "bos_level" in d.columns else np.full(n, np.nan)

        choch_dir = d["choch_dir"].to_numpy() if "choch_dir" in d.columns else np.zeros(n)
        choch_status = (
            d["choch_status"].astype(str).to_numpy()
            if "choch_status" in d.columns
            else np.array([""] * n)
        )

        # Optional feature columns (may exist from build_features)
        sweep_up = (
            d["sweep_up"].to_numpy().astype(bool)
            if "sweep_up" in d.columns
            else np.zeros(n, dtype=bool)
        )
        sweep_down = (
            d["sweep_down"].to_numpy().astype(bool)
            if "sweep_down" in d.columns
            else np.zeros(n, dtype=bool)
        )
        fvg_up = None
        fvg_dn = None
        for cand in ("fvg_bullish", "bullish_fvg", "fvg_up"):
            if cand in d.columns:
                fvg_up = d[cand].to_numpy()
                break
        for cand in ("fvg_bearish", "bearish_fvg", "fvg_down"):
            if cand in d.columns:
                fvg_dn = d[cand].to_numpy()
                break
        # fvg_state string column from observador-style frames
        fvg_state = (
            d["fvg_state"].astype(str).to_numpy()
            if "fvg_state" in d.columns
            else None
        )
        ob_dir = d["ob_dir"].astype(str).to_numpy() if "ob_dir" in d.columns else None

        prev_bos_active = False
        prev_choch_active = False
        prev_sweep_up = False
        prev_sweep_dn = False
        prev_fvg_state = ""
        prev_ob = ""

        for i in range(0, n, max(1, sample_every)):
            t = times.iloc[i] if hasattr(times, "iloc") else times[i]
            t_s = str(t)
            px = _fmt_level(closes[i])

            # BOS onset: status becomes active and dir != 0
            bos_active = str(bos_status[i]) == "active" and int(bos_dir[i]) != 0
            if bos_active and not prev_bos_active:
                buffer.append(
                    StructureEvent(
                        time=t_s,
                        tf=tf,
                        event="BOS",
                        direction=_dir_label(bos_dir[i]),
                        level=_fmt_level(bos_level[i]),
                        status="active",
                        price=px,
                    )
                )
            prev_bos_active = bos_active

            choch_active = str(choch_status[i]) == "active" and int(choch_dir[i]) != 0
            if choch_active and not prev_choch_active:
                buffer.append(
                    StructureEvent(
                        time=t_s,
                        tf=tf,
                        event="CHOCH",
                        direction=_dir_label(choch_dir[i]),
                        level="",
                        status="active",
                        price=px,
                    )
                )
            prev_choch_active = choch_active

            su = bool(sweep_up[i])
            if su and not prev_sweep_up:
                buffer.append(
                    StructureEvent(
                        time=t_s,
                        tf=tf,
                        event="SWEEP",
                        direction="LONG",
                        level="",
                        status="up",
                        price=px,
                        note="BSL",
                    )
                )
            prev_sweep_up = su

            sd = bool(sweep_down[i])
            if sd and not prev_sweep_dn:
                buffer.append(
                    StructureEvent(
                        time=t_s,
                        tf=tf,
                        event="SWEEP",
                        direction="SHORT",
                        level="",
                        status="down",
                        price=px,
                        note="SSL",
                    )
                )
            prev_sweep_dn = sd

            if fvg_state is not None:
                fs = str(fvg_state[i] or "")
                if fs and fs != "none" and fs != prev_fvg_state:
                    direction = "LONG" if "bull" in fs.lower() else (
                        "SHORT" if "bear" in fs.lower() else "—"
                    )
                    buffer.append(
                        StructureEvent(
                            time=t_s,
                            tf=tf,
                            event="FVG",
                            direction=direction,
                            level="",
                            status=fs,
                            price=px,
                        )
                    )
                prev_fvg_state = fs
            else:
                if fvg_up is not None:
                    try:
                        fu = bool(fvg_up[i]) if not (
                            isinstance(fvg_up[i], float) and np.isnan(fvg_up[i])
                        ) else False
                    except Exception:
                        fu = False
                    # rising edge only would need prev — use non-zero onset
                if fvg_dn is not None:
                    pass  # covered via fvg_state when present

            if ob_dir is not None:
                od = str(ob_dir[i] or "")
                if od and od not in ("", "none", "nan") and od != prev_ob:
                    direction = "LONG" if "bull" in od.lower() else (
                        "SHORT" if "bear" in od.lower() else "—"
                    )
                    buffer.append(
                        StructureEvent(
                            time=t_s,
                            tf=tf,
                            event="OB",
                            direction=direction,
                            level="",
                            status=od,
                            price=px,
                        )
                    )
                prev_ob = od

    # Chronological merge across TFs
    def _key(e: StructureEvent) -> str:
        return e.time

    buffer.sort(key=_key)
    total = max(len(buffer), 1)
    for e in buffer:
        table.emit(e, progress_total=total)
    return len(buffer)


def emit_signal_row(
    table: LiveStructureTable,
    *,
    time: str,
    tf: str,
    direction: int,
    entry: float,
    sl: float,
    tp: float,
    note: str = "",
) -> None:
    table.emit(
        StructureEvent(
            time=str(time),
            tf=tf,
            event="SIGNAL",
            direction=_dir_label(direction),
            level=_fmt_level(entry),
            status="entry",
            price=_fmt_level(entry),
            note=note or f"SL={_fmt_level(sl)} TP={_fmt_level(tp)}",
        )
    )


def emit_trade_row(
    table: LiveStructureTable,
    *,
    time: str,
    tf: str,
    direction: int,
    exit_reason: str,
    pnl_r: float,
) -> None:
    table.emit(
        StructureEvent(
            time=str(time),
            tf=tf,
            event="TRADE",
            direction=_dir_label(direction),
            level="",
            status=str(exit_reason),
            price="",
            note=f"pnl_r={pnl_r:.3f}",
        )
    )
