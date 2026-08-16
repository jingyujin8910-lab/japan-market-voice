from scripts.smoke_gemini import _output


def test_gemini_smoke_output_is_aggregate_only() -> None:
    output = _output(success=False, model="test", error_type="timeout")
    assert set(output) == {
        "structured_output_success",
        "model",
        "analyzed_records",
        "sentiment",
        "topics_count",
        "positive_drivers_count",
        "negative_drivers_count",
        "representative_voc_validated",
        "marketing_insights_count",
        "error_type",
    }
    assert "prompt" not in output
    assert "content" not in output
    assert "api_key" not in output
