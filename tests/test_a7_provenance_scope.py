from audits.codigo.a7_completion_audit import _a7_technical_provenance_pass


def _report(**overrides):
    report = {
        "provenance_scope": "TECHNICAL_FUNNEL_ONLY",
        "provenance_mechanical_ok": True,
        "a7_provenance_ok": True,
        "provenance_ok": True,
        "commit": "abc123",
        "config": {"causal_mode": "strict"},
        "contract_version": "CONTRATO_FUNNEL_AUDIT.md#A7",
        "provenance_source": {"metadata_sha256": "meta-hash"},
    }
    report.update(overrides)
    return report


def test_a7_technical_provenance_does_not_require_source_authorization():
    report = _report(
        provenance_source={
            "metadata_sha256": "meta-hash",
            "source_provenance_complete": False,
            "license_review_status": "REVIEW_BLOCKED",
        }
    )
    assert _a7_technical_provenance_pass(report)


def test_old_or_unscoped_report_cannot_pass_oe_a79():
    assert not _a7_technical_provenance_pass(_report(provenance_scope=None))
