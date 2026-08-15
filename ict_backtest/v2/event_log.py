"""Canonical event log (BACKTEST_V2_SPEC §5.3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ict_backtest.v2.contracts import EventLogRecord


class EventLog:
    def __init__(self) -> None:
        self._records: list[EventLogRecord] = []
        self._seq = 0

    def append(
        self,
        kind: str,
        *,
        ts: str = "",
        plan_id: str | None = None,
        order_id: str | None = None,
        trade_id: str | None = None,
        tf: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        self._seq += 1
        rec = EventLogRecord(
            ts=ts or "",
            seq=self._seq,
            kind=kind,
            plan_id=plan_id,
            order_id=order_id,
            trade_id=trade_id,
            tf=tf,
            payload=payload or {},
        )
        self._records.append(rec)
        return rec.seq

    def extend(self, records: Iterable[EventLogRecord]) -> None:
        for r in records:
            self._seq = max(self._seq, r.seq)
            self._records.append(r)

    @property
    def records(self) -> list[EventLogRecord]:
        return list(self._records)

    def for_trade(self, trade_id: str) -> list[EventLogRecord]:
        return [r for r in self._records if r.trade_id == trade_id]

    def for_plan(self, plan_id: str) -> list[EventLogRecord]:
        return [r for r in self._records if r.plan_id == plan_id]

    def to_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for r in self._records:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    def __len__(self) -> int:
        return len(self._records)
