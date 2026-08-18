from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.market_object import ObjectType

def c(t,o,h,l,cl): return {"time":t,"open":o,"high":h,"low":l,"close":cl}

def test_bullish_fvg_confirmed_at_third_close():
    z=detect_fvg([c(0,1.10,1.105,1.095,1.102),c(1,1.102,1.11,1.101,1.109),c(2,1.109,1.12,1.112,1.118)],"H1","EURUSD")
    assert len(z)==1 and z[0].type==ObjectType.FVG and z[0].direction==1
    assert (z[0].candidate_bar,z[0].confirmation_bar,z[0].tradable_bar)==(0,2,2)

def test_bearish_fvg():
    z=detect_fvg([c(0,1.105,1.110,1.100,1.108),c(1,1.108,1.109,1.098,1.099),c(2,1.099,1.095,1.090,1.091)],"H1")
    assert len(z)==1 and z[0].direction==-1

def test_fvg_prefix_invariance():
    p=[c(0,1.10,1.105,1.095,1.102),c(1,1.102,1.11,1.101,1.109),c(2,1.109,1.12,1.112,1.118)]
    a=[x.to_dict() for x in detect_fvg(p,"H1")]
    b=[x.to_dict() for x in detect_fvg(p+[c(3,1.118,1.13,1.117,1.125)],"H1")]
    assert b[:len(a)]==a

def test_bullish_ob_requires_closed_followthrough():
    z=detect_order_blocks([c(0,1.10,1.11,1.095,1.099),c(1,1.098,1.125,1.097,1.12)],"H1",min_body_ratio=.2)
    assert len(z)==1 and z[0].direction==1 and z[0].candidate_bar==0 and z[0].tradable_bar==1

def test_bearish_ob_requires_closed_followthrough():
    z=detect_order_blocks([c(0,1.10,1.11,1.095,1.109),c(1,1.108,1.109,1.08,1.085)],"H1",min_body_ratio=.2)
    assert len(z)==1 and z[0].direction==-1

def test_ob_prefix_invariance():
    p=[c(0,1.10,1.11,1.095,1.099),c(1,1.098,1.125,1.097,1.12)]
    a=[x.to_dict() for x in detect_order_blocks(p,"H1",min_body_ratio=.2)]
    b=[x.to_dict() for x in detect_order_blocks(p+[c(2,1.12,1.14,1.115,1.135)],"H1",min_body_ratio=.2)]
    assert b[:len(a)]==a

def test_ob_has_no_signal_on_footprint_only():
    assert detect_order_blocks([c(0,1.10,1.11,1.095,1.099)],"H1",min_body_ratio=.2)==[]
