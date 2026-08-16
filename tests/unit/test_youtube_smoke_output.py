from scripts.smoke_youtube import _safe_failure


def test_smoke_failure_output_contains_only_approved_fields() -> None:
    output = _safe_failure("authentication_error")
    assert set(output) == {
        "api_connection_success",
        "keyword",
        "videos_found",
        "japan_guardrail_passed_videos",
        "comments_collected",
        "eligible_records",
        "partial_or_failure",
        "error_type",
    }
    assert "api_key" not in output
    assert "records" not in output
    assert "content" not in output
