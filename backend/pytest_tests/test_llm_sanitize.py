from backend.app.services.llm_service import LLMService


def test_sanitize_diagram_type_extracts_known_type_and_keeps_code():
    dt, extra = LLMService._sanitize_diagram_type("VGT线路图", "VGT线路图")
    assert dt == "线路图"
    assert "VGT" in extra


def test_sanitize_diagram_type_drops_unknown_type():
    # "VGT" is not a diagram type; it should not be treated as diagram_type.
    dt, extra = LLMService._sanitize_diagram_type("VGT", "VGT")
    assert dt is None
    assert extra == []


