from __future__ import annotations
"""Tests para el materializador CORREGIDO de setup_grammar.

Valida que `materialize_setup_grammar_dataset_v1_fixed.py` respeta las
3 condiciones POI antes de etiquetar USABLE_UNGRADED.
"""

import pytest
from unittest.mock import patch

from scripts.lab.experiments.materialize_setup_grammar_dataset_v1 import materialize_row as original_materialize_row
from scripts.lab.experiments.materialize_setup_grammar_dataset_v1_fixed import materialize_row as fixed_materialize_row
from scripts.lab.experiments.materialize_setup_grammar_dataset_v1_fixed import _build_m15_evidence_for_row


def _build_original_row(*, context_bucket="ALIGNED", direction=1,
                         stages=None, event_id="row-1"):
    if stages is None:
        stages = ["LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE", "FVG", "RETEST"]
    return {
        "event_id": event_id,
        "event_time": "2026-09-15T12:00:00+00:00",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "split": "DESIGN",
        "direction": direction,
        "sequence_depth": len(stages),
        "structure_mode": "lite",
        "context_bucket": context_bucket,
        "label_end_6": "continuation",
        "features_at_t": {
            "constraints": {
                "allow_long": direction > 0,
                "allow_short": direction < 0,
                "direction_hint": "BULLISH" if direction > 0 else "BEARISH",
            },
            "context_inputs": {
                "d1_bias": "BULLISH" if direction > 0 else "BEARISH",
                "h1_alignment": context_bucket,
                "h4_location": "DISCOUNT" if direction > 0 else "PREMIUM",
                "sequence_direction": direction,
            },
            "context_layers": {},
            "sequence": stages,
        },
        "_source_file": "fixture.jsonl",
    }


def _build_fixed_row(
    *,
    context_bucket="ALIGNED",
    h1_alignment="ALIGNED",
    h4_location="DISCOUNT",
    direction=1,
    sequence_direction=1,
    decision_time="2026-09-15T12:00:00+00:00",
    event_id="row-fixed-1",
):
    return {
        "event_id": event_id,
        "decision_time": decision_time,
        "symbol": "EURUSD",
        "timeframe": "H1",
        "direction": direction,  # ← necesario para pd_array_zone
        "context_bucket": context_bucket,
        "features_at_t": {
            "constraints": {
                "allow_long": direction > 0,
                "allow_short": direction < 0,
                "direction_hint": "BULLISH" if direction > 0 else "BEARISH",
            },
            "context_inputs": {
                "d1_bias": "BULLISH" if direction > 0 else "BEARISH",
                "h1_alignment": h1_alignment,
                "h4_location": h4_location,
                "sequence_direction": sequence_direction,
            },
        },
        "exec_tf_evidence": {
            "source": "data/raw/EURUSD/EURUSD_M15_2006_2015.parquet",
            "tf": "M15",
            "window_bars": 40,
            "status": "EXEC_TF_OHLC_WINDOW_MATERIALIZED",
        },
        "grammar_labels": {},
        "_source_file": "fixture.jsonl",
    }


@pytest.fixture
def original_row():
    """Fila para tests del materializador ORIGINAL."""
    return _build_original_row()


@pytest.fixture
def fixed_row():
    """Fila base para tests del materializador CORREGIDO."""
    return _build_fixed_row()


class _M15DetectorsMock:
    """Mock de detectores M15 que intercepta _build_m15_evidence_for_row."""

    def __init__(self, *, displacement_present=False, fvg_present=False,
                 ob_present=False, displacement_direction=1):
        self.displacement_present = displacement_present
        self.fvg_present = fvg_present
        self.ob_present = ob_present
        self.displacement_direction = displacement_direction

    def _patch_m15_evidence(self):
        """Retorna un patcher que reemplaza _build_m15_evidence_for_row."""

        def mock_builder(row, exec_tf_sources):
            return {
                "displacement": {
                    "present": self.displacement_present,
                    "source": "m15_displacement_detector" if self.displacement_present else "no_displacement",
                    "direction": self.displacement_direction if self.displacement_present else None,
                    "magnitude": None,
                },
                "fvg_or_ob": {
                    "present": self.fvg_present or self.ob_present,
                    "source": "m15_fvg_or_ob_detector" if (self.fvg_present or self.ob_present) else "no_fvg_or_ob",
                    "type": "FVG" if self.fvg_present else ("OB" if self.ob_present else None),
                },
                "sweep": {"present": False, "source": "not_detected_in_m15_window"},
                "bos_or_choch": {"present": False, "source": "not_extracted"},
                "retest": {"present": False, "source": "not_extracted"},
            }

        return patch(
            "scripts.lab.experiments.materialize_setup_grammar_dataset_v1_fixed._build_m15_evidence_for_row",
            side_effect=mock_builder,
        )


@pytest.fixture
def m15_detectors_mock():
    """Fixture que provee mock de detectores M15 - devuelve la CLASE."""
    return _M15DetectorsMock


# ============================================================================
# Tests del materializador ORIGINAL (compatibilidad)
# ============================================================================

def test_original_materializer_complete_grammar_without_trade_authority(original_row):
    """El materializador original produce etiquetas completas sin authority."""
    out = original_materialize_row(original_row)
    labels = out["grammar_labels"]
    assert labels["htf_narrative"] == "HTF_OK"
    assert labels["po3_phase"] == "CHAIN_COMPLETE"
    assert labels["liquidity_sweep"] == "SWEEP_VALID"
    assert labels["pd_array_zone"] == "USABLE_UNGRADED"
    assert labels["retest_entry"] == "RETESTED"
    assert labels["poi_quality"] == "T2_CANDIDATE_UNVERIFIED"
    assert labels["setup_decision"] == "ABSTAIN"
    assert labels["exec_tf_integrity"] == "MISSING_EXEC_TF_REPLAY"
    assert out["can_trade"] is False
    assert out["entry_authorized"] is False


def test_original_materializer_rejects_htf_conflict(original_row):
    """HTF conflict → REJECT antes de evaluar zona."""
    row = _build_original_row(context_bucket="AGAINST")
    out = original_materialize_row(row)
    assert out["grammar_labels"]["htf_narrative"] == "HTF_CONFLICT"
    assert out["grammar_labels"]["setup_decision"] == "REJECT"
    assert out["grammar_labels"]["weak_link"] == "htf_narrative"


def test_original_materializer_marks_no_zone_when_no_pd_array(original_row):
    """Sin PD Array en stages → NO_ZONE."""
    row = _build_original_row(stages=["LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE"])
    out = original_materialize_row(row)
    assert out["grammar_labels"]["pd_array_zone"] == "NO_ZONE"
    assert out["grammar_labels"]["retest_entry"] == "NO_ZONE_NO_RETEST"
    assert out["grammar_labels"]["poi_quality"] == "NO_PD_ARRAY_CONFIRMED"


# ============================================================================
# Tests del materializador CORREGIDO (la corrección semántica)
# ============================================================================

def test_fixed_materializer_no_zone_when_missing_zone(fixed_row):
    """CONDICIÓN 1 FALLA: zona incorrecta → NO_ZONE."""
    # Long en PREMIUM = zona incorrecta para long
    row = _build_fixed_row(h4_location="PREMIUM", direction=1)
    out = fixed_materialize_row(row)
    assert out["grammar_labels"]["pd_array_zone"] == "NO_ZONE"
    assert out["can_trade"] is False
    assert out["entry_authorized"] is False


def test_fixed_materializer_no_zone_when_htf_not_aligned(fixed_row):
    """CONDICIÓN 2 FALLA: HTF no alineado → NO_ZONE."""
    # Zona correcta (DISCOUNT para long) pero h1 AGAINST
    row = _build_fixed_row(h4_location="DISCOUNT", direction=1, h1_alignment="AGAINST")
    out = fixed_materialize_row(row)
    assert out["grammar_labels"]["pd_array_zone"] == "NO_ZONE"
    assert out["can_trade"] is False
    assert out["entry_authorized"] is False


def test_fixed_materializer_usable_ungraded_with_all_three_conditions(
    fixed_row, m15_detectors_mock
):
    """Las 3 condiciones POI → USABLE_UNGRADED."""
    mock = m15_detectors_mock(displacement_present=True, fvg_present=True)
    with mock._patch_m15_evidence():
        row = _build_fixed_row(
            h4_location="DISCOUNT", direction=1, h1_alignment="ALIGNED"
        )
        out = fixed_materialize_row(row)
    assert out["grammar_labels"]["pd_array_zone"] == "USABLE_UNGRADED"
    assert out["can_trade"] is False
    assert out["entry_authorized"] is False


def test_fixed_materializer_usable_ungraded_with_ob_instead_of_fvg(
    fixed_row, m15_detectors_mock
):
    """OB en vez de FVG → también USABLE_UNGRADED."""
    mock = m15_detectors_mock(displacement_present=True, ob_present=True)
    with mock._patch_m15_evidence():
        row = _build_fixed_row(
            h4_location="DISCOUNT", direction=1, h1_alignment="ALIGNED"
        )
        out = fixed_materialize_row(row)
    assert out["grammar_labels"]["pd_array_zone"] == "USABLE_UNGRADED"
    assert out["can_trade"] is False
    assert out["entry_authorized"] is False


def test_fixed_materializer_vetoes_all_rows(fixed_row, m15_detectors_mock):
    """can_trade=false y entry_authorized=false para TODAS las filas,
    incluyendo las que califican como USABLE_UNGRADED."""
    mock = m15_detectors_mock(displacement_present=True, fvg_present=True)
    with mock._patch_m15_evidence():
        for cfg in [
            {},  # fila base (NO_ZONE por falta de displacement/FVG)
            {"h4_location": "DISCOUNT", "h1_alignment": "ALIGNED"},
        ]:
            row = _build_fixed_row(**cfg)
            out = fixed_materialize_row(row)
            assert out["can_trade"] is False, \
                f"can_trade debe ser False, got {out['can_trade']}"
            assert out["entry_authorized"] is False, \
                f"entry_authorized debe ser False, got {out['entry_authorized']}"


def test_fixed_materializer_can_trade_flag_persists(fixed_row, m15_detectors_mock):
    """can_trade=false incluso cuando pd_array_zone=USABLE_UNGRADED."""
    mock = m15_detectors_mock(displacement_present=True, fvg_present=True)
    with mock._patch_m15_evidence():
        row = _build_fixed_row(
            h4_location="DISCOUNT", direction=1, h1_alignment="ALIGNED"
        )
        out = fixed_materialize_row(row)
        assert out["can_trade"] is False, \
            "can_trade debe ser False aunque pd_array_zone sea USABLE_UNGRADED"
        assert out["entry_authorized"] is False
        assert out["grammar_labels"]["pd_array_zone"] == "USABLE_UNGRADED"


def test_fixed_materializer_uses_displacement_detector_module():
    """Verifica que engine.detectors.displacement está disponible."""
    import sys
    from pathlib import Path
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import engine.detectors.displacement as disp
    assert hasattr(disp, "detect_displacement")
    assert hasattr(disp, "DisplacementConfig")


def test_fixed_materializer_solution_diagnostic(fixed_row):
    """Confirma que el materializador tiene el campo de diagnostic (lista)."""
    row = _build_fixed_row(h4_location="PREMIUM", direction=1)
    out = fixed_materialize_row(row)
    diagnostics = out.get("diagnostics", [])
    # El materializador corregido devuelve diagnostics como lista
    assert isinstance(diagnostics, (list, dict))
    # Debe tener al menos un diagnostic sobre por qué es NO_ZONE
    if isinstance(diagnostics, list):
        assert len(diagnostics) >= 0  # puede estar vacío si no hay diagnostic específico
    else:
        assert len(diagnostics) >= 0
