from scripts.opening_readiness import check


def test_readiness_check_is_fail_closed():
    assert check("example", True, "ok")["status"] == "PASS"
    assert check("example", False, "blocked")["status"] == "BLOCK"
