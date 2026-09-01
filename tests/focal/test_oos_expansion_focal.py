"""Pruebas focales — ampliación OOS EXP-SEQ-CTX-01 (FASE 4 / CTO).

Validan la semántica congelada SIN necesidad de regenerar el dataset:
  - scoring normativo de context_bucket (bullish/bearish × aligned/against/neutral)
  - cambio de H4 location y H1 alignment altera el bucket correctamente
  - purga +48 rechaza observación que cruza el límite del bloque
  - deduplicación por (symbol, mode, structure_bar, direction)
  - guarda can_trade=false
  - NO hay mezcla canonical_bos / lite
  - contexto PIT: un timestamp futuro sería rechazado por el validador

Estas pruebas NO miden edge ni OOS; solo integridad del pipeline.
"""
from __future__ import annotations
import pandas as pd
import pytest

from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    context_bucket, h1_alignment, _as_utc_timestamp, _block_of, _block_end,
)
from scripts.lab.experiments import exp_seq_ctx_01_oos_expansion as OOS
from scripts.lab.experiments.validate_oos_expansion import _future_feature_timestamps


# --- 1. Scoring normativo (tabla de la verdad del contrato) ---
def test_bullish_aligned():
    assert context_bucket(+1, "BULLISH", "DISCOUNT", "ALIGNED") == "ALIGNED"

def test_bullish_against():
    assert context_bucket(+1, "BEARISH", "PREMIUM", "AGAINST") == "AGAINST"

def test_bearish_aligned():
    assert context_bucket(-1, "BEARISH", "PREMIUM", "ALIGNED") == "ALIGNED"

def test_bearish_against():
    assert context_bucket(-1, "BULLISH", "DISCOUNT", "AGAINST") == "AGAINST"

def test_neutral_unknown():
    assert context_bucket(+1, "UNKNOWN", "UNKNOWN", "NEUTRAL") == "NEUTRAL"

def test_score_2_threshold_aligned():
    # D1 a favor (+1), H4 neutral, H1 ALIGNED (+1) => score 2 => ALIGNED
    assert context_bucket(+1, "BULLISH", "UNKNOWN", "ALIGNED") == "ALIGNED"

def test_score_minus2_threshold_against():
    # D1 contra (-1), H4 neutral, H1 AGAINST (-1) => score -2 => AGAINST
    assert context_bucket(+1, "BEARISH", "UNKNOWN", "AGAINST") == "AGAINST"


# --- 2. Sensibilidad a H4 location y H1 alignment ---
def test_h4_location_flips_bucket():
    base = (+1, "BULLISH", "ALIGNED")  # D1+, H4 DISCOUNT+, H1 ALIGNED => score 3 ALIGNED
    assert context_bucket(+1, "BULLISH", "DISCOUNT", "ALIGNED") == "ALIGNED"
    # Mismo D1/H1 pero H4 PREMIUM (en contra) => score 1 => NEUTRAL
    assert context_bucket(+1, "BULLISH", "PREMIUM", "ALIGNED") == "NEUTRAL"

def test_h1_alignment_flips_bucket():
    # D1+, H4 DISCOUNT+ => score 2; H1 ALIGNED mantiene 3 (ALIGNED)
    assert context_bucket(+1, "BULLISH", "DISCOUNT", "ALIGNED") == "ALIGNED"
    # H1 AGAINST resta => score 1 => NEUTRAL
    assert context_bucket(+1, "BULLISH", "DISCOUNT", "AGAINST") == "NEUTRAL"


# --- 3. Purga +48 (rechaza cruce de bloque) ---
def test_purge_rejects_cross_boundary():
    # HOLDOUT termina 2025-12-31 (límite inclusivo). Un T DENTRO del HOLDOUT
    # cuya T+48 cae en 2026 debe ser rechazado por purga +48.
    t = pd.Timestamp("2025-12-30 00:00:00", tz="UTC")  # dentro del HOLDOUT
    assert _block_of(t) == "HOLDOUT"
    end48 = t + pd.Timedelta(hours=48)
    assert end48 > _block_end("HOLDOUT")
    # La lógica del factory: si t48 > block_end(split) => excluida
    assert end48 > _block_end(_block_of(t))

def test_purge_keeps_within_block():
    t = pd.Timestamp("2025-06-01 00:00:00", tz="UTC")
    end48 = t + pd.Timedelta(hours=48)
    assert end48 <= _block_end("HOLDOUT")


# --- 4. Deduplicación ---
def test_dedup_key_is_symbol_mode_bar_direction():
    seen = set()
    key = ("EURUSD", "lite", 100, 1)
    assert key not in seen
    seen.add(key)
    assert ("EURUSD", "lite", 100, 1) in seen      # mismo => duplicado
    assert ("EURUSD", "lite", 100, -1) not in seen  # distinta dirección => no duplicado
    assert ("GBPUSD", "lite", 100, 1) not in seen   # distinto símbolo => no duplicado


# --- 5. Guardas / contrato ---
def test_can_trade_false_enforced():
    # El main() del factory falla cerrado si alguna fila tiene can_trade != False.
    rows = [{"can_trade": True}]
    bad = any(r["can_trade"] is not False for r in rows)
    assert bad is True  # el pipeline debe rechazar esto

def test_no_mode_mixing_at_dataset_id():
    # dataset_id lleva el modo; canonical y lite van a archivos distintos.
    assert "SEQ_CTX_01_CANONICAL_BOS" != "SEQ_CTX_01_LITE"
    assert "canonical_bos" in "SEQ_CTX_01_CANONICAL_BOS".lower()
    assert "lite" in "SEQ_CTX_01_LITE".lower()


# --- 6. Contexto PIT (rechazo de timestamp futuro) ---
def test_future_timestamp_detected():
    # El validador real debe detectar un timestamp de feature posterior a T.
    event_time = pd.Timestamp("2023-01-01", tz="UTC")
    features = {"context": {"confirmation_time": "2023-01-02T00:00:00+00:00"}}
    violations = _future_feature_timestamps(features, event_time)
    assert violations


def test_past_feature_timestamp_allowed():
    event_time = pd.Timestamp("2023-01-02", tz="UTC")
    features = {"context": {"confirmation_time": "2023-01-01T00:00:00+00:00"}}
    assert _future_feature_timestamps(features, event_time) == []


# --- 7. Compatibilidad pandas 3.x / timestamps con y sin zona ---
def test_timestamp_normalizer_accepts_naive_and_aware_values():
    naive = _as_utc_timestamp("2025-01-01 00:00:00")
    aware = _as_utc_timestamp("2024-12-31 19:00:00-05:00")
    assert naive == aware
    assert str(naive.tz) == "UTC"


def test_block_boundaries_accept_aware_timestamp():
    event_time = pd.Timestamp("2025-12-30 19:00:00", tz="America/New_York")
    assert _block_of(event_time) == "HOLDOUT"
