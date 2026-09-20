"""
test_market_object_temporal.py — Comportamiento temporal de MarketObject.

Cobertura mínima exigida: transiciones de estado, terminalidad, precedencia
INVALIDATED > MITIGATED, contrato temporal (candidate <= confirmation <= tradable),
lineage contract, round-trip to_dict/from_dict.

Datos: puramente sintéticos y deterministas (no leen disco, no acceden red).
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from engine.market_object import (
    MarketObject,
    ObjectType,
    Role,
    ObjectState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fvg_bullish(
    direction: int = 1,
    state: ObjectState = ObjectState.CREATED,
    zone_high: float = 1.1500,
    zone_low: float = 1.1480,
    candidate_bar: int = 100,
    confirmation_bar: int = 102,
    tradable_bar: int = 103,
    **kwargs,
) -> MarketObject:
    """FVG alcista con valores por defecto inspeccionables."""
    return MarketObject(
        symbol="EURUSD",
        type=ObjectType.FVG,
        origin_tf="H1",
        role=Role.REFINEMENT,
        direction=direction,
        zone_high=zone_high,
        zone_low=zone_low,
        state=state,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        candidate_bar=candidate_bar,
        candidate_time=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        confirmation_bar=confirmation_bar,
        confirmation_time=datetime(2026, 1, 1, 10, 2, tzinfo=timezone.utc),
        tradable_bar=tradable_bar,
        tradable_time=datetime(2026, 1, 1, 10, 3, tzinfo=timezone.utc),
        **kwargs,
    )


# ===========================================================================
# 1. ESTADO INICIAL
# ===========================================================================

class TestInitialState:
    def test_nuevo_objeto_esta_en_created(self) -> None:
        obj = _fvg_bullish()
        assert obj.state is ObjectState.CREATED

    def test_is_terminal_falso_en_created(self) -> None:
        obj = _fvg_bullish()
        assert obj.is_terminal is False

    def test_origin_tf_es_obligatorio(self) -> None:
        with pytest.raises(TypeError, match="origin_tf es obligatorio"):
            MarketObject(symbol="X", type=ObjectType.FVG)  # tipo sin origin_tf

    def test_direction_solo_mas_menos_o_neutro(self) -> None:
        with pytest.raises(ValueError, match="direction debe ser"):
            _fvg_bullish(direction=2)
        with pytest.raises(ValueError, match="direction debe ser"):
            _fvg_bullish(direction=-2)

    def test_zone_high_no_puede_ser_menor_que_zone_low(self) -> None:
        with pytest.raises(ValueError, match="zone_high debe ser"):
            _fvg_bullish(zone_high=1.1470, zone_low=1.1480)


# ===========================================================================
# 2. TRANSICIONES DE ESTADO — can_transition_to / transition_to
# ===========================================================================

class TestTransitions:
    # CREATED → {ACTIVE, INVALIDATED, EXPIRED}
    def test_creates_puede_ir_a_active(self) -> None:
        obj = _fvg_bullish()
        assert obj.can_transition_to(ObjectState.ACTIVE) is True
        obj.transition_to(ObjectState.ACTIVE)
        assert obj.state is ObjectState.ACTIVE

    def test_creates_puede_ir_a_invalidated(self) -> None:
        obj = _fvg_bullish()
        assert obj.can_transition_to(ObjectState.INVALIDATED) is True
        obj.transition_to(ObjectState.INVALIDATED)
        assert obj.state is ObjectState.INVALIDATED

    def test_creates_puede_ir_a_expired(self) -> None:
        obj = _fvg_bullish()
        assert obj.can_transition_to(ObjectState.EXPIRED) is True
        obj.transition_to(ObjectState.EXPIRED)
        assert obj.state is ObjectState.EXPIRED

    def test_creates_NO_puede_ir_a_mitigated_directamente(self) -> None:
        obj = _fvg_bullish()
        assert obj.can_transition_to(ObjectState.MITIGATED) is False
        with pytest.raises(ValueError, match="Transición de estado inválida"):
            obj.transition_to(ObjectState.MITIGATED)

    # ACTIVE → {PARTIALLY_MITIGATED, MITIGATED, INVALIDATED, EXPIRED, CONSUMED}
    def test_active_puede_ir_a_mitigated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.ACTIVE)
        assert obj.can_transition_to(ObjectState.MITIGATED) is True
        obj.transition_to(ObjectState.MITIGATED)
        assert obj.state is ObjectState.MITIGATED

    def test_active_puede_ir_a_invalidated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.ACTIVE)
        assert obj.can_transition_to(ObjectState.INVALIDATED) is True
        obj.transition_to(ObjectState.INVALIDATED)
        assert obj.state is ObjectState.INVALIDATED

    def test_active_puede_ir_a_partially_mitigated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.ACTIVE)
        assert obj.can_transition_to(ObjectState.PARTIALLY_MITIGATED) is True
        obj.transition_to(ObjectState.PARTIALLY_MITIGATED)
        assert obj.state is ObjectState.PARTIALLY_MITIGATED

    def test_active_NO_puede_ir_a_created(self) -> None:
        obj = _fvg_bullish(state=ObjectState.ACTIVE)
        assert obj.can_transition_to(ObjectState.CREATED) is False
        with pytest.raises(ValueError, match="Transición de estado inválida"):
            obj.transition_to(ObjectState.CREATED)

    # PARTIALLY_MITIGATED → puede volver a PARTIALLY_MITIGATED (auto), MITIGATED, INVALIDATED…
    def test_partially_mitigated_puede_ir_a_mitigated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.PARTIALLY_MITIGATED)
        assert obj.can_transition_to(ObjectState.MITIGATED) is True
        obj.transition_to(ObjectState.MITIGATED)
        assert obj.state is ObjectState.MITIGATED

    def test_partially_mitigated_puede_ir_a_invalidated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.PARTIALLY_MITIGATED)
        assert obj.can_transition_to(ObjectState.INVALIDATED) is True
        obj.transition_to(ObjectState.INVALIDATED)
        assert obj.state is ObjectState.INVALIDATED

    # MITIGATED → INVALIDATED es válido (precedencia INVALIDATED > MITIGATED)
    def test_mitigated_puede_ir_a_invalidated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.MITIGATED)
        assert obj.can_transition_to(ObjectState.INVALIDATED) is True
        obj.transition_to(ObjectState.INVALIDATED)
        assert obj.state is ObjectState.INVALIDATED

    def test_mitigated_NO_es_terminal(self) -> None:
        obj = _fvg_bullish(state=ObjectState.MITIGATED)
        assert obj.is_terminal is False


# ===========================================================================
# 3. TERMINALIDAD
# ===========================================================================

class TestTerminality:
    TERMINAL = {ObjectState.INVALIDATED, ObjectState.EXPIRED, ObjectState.CONSUMED}

    @pytest.mark.parametrize("state", list(TERMINAL))
    def test_estados_terminales_reportan_is_terminal_verdadero(self, state: ObjectState) -> None:
        obj = _fvg_bullish(state=state)
        assert obj.is_terminal is True

    @pytest.mark.parametrize(
        "state",
        [ObjectState.CREATED, ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED, ObjectState.MITIGATED],
    )
    def test_estados_no_terminales_reportan_is_terminal_falso(self, state: ObjectState) -> None:
        obj = _fvg_bullish(state=state)
        assert obj.is_terminal is False

    def test_invalidado_no_puede_transicionar(self) -> None:
        obj = _fvg_bullish(state=ObjectState.INVALIDATED)
        assert obj.can_transition_to(ObjectState.ACTIVE) is False
        with pytest.raises(ValueError, match="Transición de estado inválida"):
            obj.transition_to(ObjectState.ACTIVE)

    def test_expired_no_puede_transicionar(self) -> None:
        obj = _fvg_bullish(state=ObjectState.EXPIRED)
        assert obj.can_transition_to(ObjectState.ACTIVE) is False

    def test_consumed_no_puede_transicionar(self) -> None:
        obj = _fvg_bullish(state=ObjectState.CONSUMED)
        assert obj.can_transition_to(ObjectState.ACTIVE) is False


# ===========================================================================
# 4. PRECEDENCIA INVALIDATED > MITIGATED
# ===========================================================================

class TestInvalidatedOverMitigatedPrecedence:
    """
    La convención metodológica (2026-08-28) dice:
    - MITIGATED NO es terminal.
    - Un objeto puede ser MITIGATED y luego INVALIDATED en la misma vela
      (o vela posterior) si cierra más allá del far_side.
    - La transición MITIGATED → INVALIDATED es explícitamente permitida.
    """

    def test_ruta_completa_creates_active_mitigated_invalidated(self) -> None:
        """Ciclo completo: CREATED → ACTIVE → MITIGATED → INVALIDATED."""
        obj = _fvg_bullish()
        assert obj.state is ObjectState.CREATED
        obj.transition_to(ObjectState.ACTIVE)
        assert obj.state is ObjectState.ACTIVE
        obj.transition_to(ObjectState.MITIGATED)
        assert obj.state is ObjectState.MITIGATED
        assert obj.is_terminal is False  # MITIGATED no es terminal
        obj.transition_to(ObjectState.INVALIDATED)
        assert obj.state is ObjectState.INVALIDATED
        assert obj.is_terminal is True  # INVALIDATED es terminal

    def test_mitigated_a_valid_invalidated_bar_cumple_contrato_temporal(
        self,
    ) -> None:
        """
        Cuando un objeto va de MITIGATED a INVALIDATED, el invalidated_bar
        debe ser >= candidate_bar (validación en _validate_temporal_contract).
        """
        obj = _fvg_bullish(
            state=ObjectState.MITIGATED,
            candidate_bar=100,
            invalidated_bar=105,  # válido: 105 >= 100
        )
        obj.transition_to(ObjectState.INVALIDATED)
        assert obj.state is ObjectState.INVALIDATED
        assert obj.invalidated_bar == 105

    def test_invalidated_bar_no_puede_ser_menor_que_candidate_bar(self) -> None:
        # confirmation_bar y tradable_bar deben ser válidos para que la
        # validación de invalidated_bar llegue a ejecutarse (no sea cortado
        # por _validate_temporal_contract).
        with pytest.raises(ValueError, match="invalidated_bar no puede preceder"):
            _fvg_bullish(
                state=ObjectState.MITIGATED,
                candidate_bar=200,
                confirmation_bar=202,
                tradable_bar=203,
                invalidated_bar=100,  # ilegal: 100 < 200
            )


# ===========================================================================
# 5. CONTRATO TEMPORAL (candidate <= confirmation <= tradable)
# ===========================================================================

class TestTemporalContract:
    def test_contrato_correcto_aceptado(self) -> None:
        obj = _fvg_bullish(
            candidate_bar=100,
            confirmation_bar=102,
            tradable_bar=103,
        )
        assert obj.candidate_bar == 100
        assert obj.confirmation_bar == 102
        assert obj.tradable_bar == 103

    def test_confirmation_no_puede_ser_menor_que_candidate(self) -> None:
        with pytest.raises(ValueError, match="Contrato temporal inválido"):
            _fvg_bullish(
                candidate_bar=100,
                confirmation_bar=99,  # ilegal: 99 < 100
            )

    def test_tradable_no_puede_ser_menor_que_confirmation(self) -> None:
        with pytest.raises(ValueError, match="Contrato temporal inválido"):
            _fvg_bullish(
                candidate_bar=100,
                confirmation_bar=102,
                tradable_bar=101,  # ilegal: 101 < 102
            )

    def test_tradable_requiere_confirmation(self) -> None:
        with pytest.raises(ValueError, match="tradable_bar requiere confirmation_bar"):
            _fvg_bullish(tradable_bar=103, confirmation_bar=None)  # type: ignore[arg-type]

    def test_first_touch_no_puede_ser_antes_de_tradable(self) -> None:
        # touch_count debe ser >= 1 para que first_touch_bar sea válido
        # (validación en _validate_foundational_invariants).
        with pytest.raises(ValueError, match="first_touch_bar no puede preceder"):
            _fvg_bullish(
                tradable_bar=103,
                first_touch_bar=100,  # ilegal: 100 < 103
                touch_count=1,
            )

    def test_tiempos_iguales_que_barras_validos(self) -> None:
        # Los tiempos por defecto de _fvg_bullish ya son deterministas y válidos;
        # no se pasan explícitamente para evitar kwargs duplicados.
        obj = _fvg_bullish()
        assert obj.candidate_time is not None
        assert obj.tradable_time is not None
        assert str(obj.candidate_time).startswith("2026-01-01")
        assert str(obj.tradable_time).startswith("2026-01-01")


# ===========================================================================
# 6. LINEAGE CONTRACT
# ===========================================================================

class TestLineageContract:
    def test_parent_no_puede_apuntar_a_si_mismo(self) -> None:
        obj_id = "my-fvg-001"
        with pytest.raises(ValueError, match="parent_object no puede apuntar"):
            _fvg_bullish(id=obj_id, parent_object=obj_id)

    def test_related_no_puede_contener_duplicados(self) -> None:
        with pytest.raises(ValueError, match="related_objects no puede contener duplicados"):
            _fvg_bullish(related_objects=["a", "a"])

    def test_related_no_puede_contener_id_vacio(self) -> None:
        with pytest.raises(ValueError, match="related_objects no puede contener ids vacíos"):
            _fvg_bullish(related_objects=["a", ""])

    def test_related_no_puede_contener_el_propio_id(self) -> None:
        my_id = "self-ref"
        with pytest.raises(ValueError, match="related_objects no puede contener el propio objeto"):
            _fvg_bullish(id=my_id, related_objects=[my_id])


# ===========================================================================
# 7. ROUND-TRIP to_dict / from_dict
# ===========================================================================

class TestRoundTrip:
    def test_round_trip_preserva_estado(self) -> None:
        obj = _fvg_bullish(state=ObjectState.ACTIVE)
        loaded = MarketObject.from_dict(obj.to_dict())
        assert loaded.state is ObjectState.ACTIVE
        assert loaded.type is ObjectType.FVG
        assert loaded.direction == 1
        assert loaded.zone_high == 1.1500
        assert loaded.zone_low == 1.1480

    def test_round_trip_preserva_timestamps(self) -> None:
        # Los tiempos por defecto de _fvg_bullish ya son deterministas;
        # no se pasan explícitamente para evitar kwargs duplicados.
        obj = _fvg_bullish()
        loaded = MarketObject.from_dict(obj.to_dict())
        assert str(loaded.candidate_time) == str(obj.candidate_time)
        assert str(loaded.tradable_time) == str(obj.tradable_time)

    def test_round_trip_preserva_meta_con_set(self) -> None:
        obj = _fvg_bullish()
        obj.meta["etiquetas"] = {"ICT", "BLOCK"}
        d = obj.to_dict()
        assert isinstance(d["meta"]["etiquetas"], list)
        loaded = MarketObject.from_dict(d)
        assert loaded.meta["etiquetas"] == {"ICT", "BLOCK"}

    def test_round_trip_desde_estado_mitigated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.MITIGATED)
        loaded = MarketObject.from_dict(obj.to_dict())
        assert loaded.state is ObjectState.MITIGATED
        assert loaded.is_terminal is False

    def test_round_trip_desde_estado_invalidated(self) -> None:
        obj = _fvg_bullish(state=ObjectState.INVALIDATED)
        loaded = MarketObject.from_dict(obj.to_dict())
        assert loaded.state is ObjectState.INVALIDATED
        assert loaded.is_terminal is True

    def test_saved_invalid_state_raises_en_from_dict(self) -> None:
        """from_dict con estado inexistente debe fallar explícitamente."""
        d = _fvg_bullish().to_dict()
        d["state"] = "GARBAGE_STATE"
        with pytest.raises(ValueError):
            MarketObject.from_dict(d)
