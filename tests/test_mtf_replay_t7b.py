from audits.codigo.mtf_replay_t7b import _state_and_context
from audits.codigo.mtf_replay_t7 import derive_h4
from tests.test_historical_event_objects import _m15


def test_t7b_context_uses_latest_published_bos_only():
    m15 = _m15(640)
    _, context, population = _state_and_context({"M15": m15, "H4": derive_h4(m15)})
    bos = [obj for obj in population["objects"] if obj.type.value == "BOS"]
    if bos:
        assert context(bos[0].tradable_time)["direction"] == bos[0].direction
