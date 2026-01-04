import re
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


_EXT_RE = re.compile(r"\.(docx|doc|pdf|pptx|ppt|xlsx|xls)$", flags=re.IGNORECASE)


def _base_name(s: str) -> str:
    s = (s or "").strip()
    s = _EXT_RE.sub("", s)
    s = re.sub(r"\s+", "", s)
    return s


def _chat(session_id: str, message: str, max_results: int = 5):
    resp = client.post(
        "/api/chat",
        json={"message": message, "session_id": session_id, "max_results": max_results},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ensure_options_for_query(query: str) -> dict:
    """
    Many of these queries first enter NEEDS_CONFIRM (AND 无结果 -> 放宽关键词询问“是否需要”).
    This helper completes that flow and returns the final response that contains options.
    """
    session_id = str(uuid.uuid4())
    r1 = _chat(session_id, query, max_results=5)
    if r1.get("needs_choice") and r1.get("options"):
        return r1
    # if it's the confirm flow, reply with “需要”
    r2 = _chat(session_id, "需要", max_results=5)
    assert r2.get("needs_choice") and r2.get("options"), r2
    return r2


def _assert_merged_when_many(options: list[dict]):
    if len(options) <= 5:
        return
    # No exact duplicates by (extension-stripped, whitespace-stripped) base name
    bases = [_base_name(o.get("name", "")) for o in options]
    assert len(bases) == len(set(bases)), f"duplicate options remain: {bases}"

    # Any merged bucket must carry ids consistent with count
    for o in options:
        cnt = int(o.get("count") or 0)
        ids = o.get("ids")
        if cnt > 1:
            assert isinstance(ids, list) and len(ids) == cnt, o


def test_merge_vgt_line_diagram_options():
    r = _ensure_options_for_query("VGT线路图")
    options = r["options"]
    _assert_merged_when_many(options)

    # Regression expectations from user-provided example:
    # - VGT执行器_诊断指导 should be merged (>=2)
    # - 涡轮增压器转速传感器_诊断指导 should be merged (>=2)
    # - 推荐解放动力(锡柴)FAW_52E/91E ... should be merged (>=4)
    bases = { _base_name(o.get("name","")): o for o in options }

    vgt_key = _base_name("VGT执行器_诊断指导")
    turbo_key = _base_name("涡轮增压器转速传感器_诊断指导")
    assert vgt_key in bases and int(bases[vgt_key].get("count") or 0) >= 2, options
    assert turbo_key in bases and int(bases[turbo_key].get("count") or 0) >= 2, options

    # startswith match for the 推荐 group (name may be trimmed to base)
    found_reco = None
    for o in options:
        if _base_name(o.get("name", "")).startswith(_base_name("【推荐】解放动力(锡柴)FAW_52E/91E")):
            found_reco = o
            break
    assert found_reco is not None and int(found_reco.get("count") or 0) >= 4, options


def test_merge_examples_confirm_flow():
    for q in ["欧曼ETX左电动门窗线路图", "玉柴EDC7电脑版电路图", "天龙KL灯光电路图"]:
        r = _ensure_options_for_query(q)
        _assert_merged_when_many(r["options"])


def test_selecting_merged_group_expands_to_concrete_files():
    """
    Regression for the UI issue:
    - selecting a merged result group (count>1) must expand to multiple concrete file options next round,
      not loop back to the same single merged option.
    """
    session_id = str(uuid.uuid4())
    r1 = _chat(session_id, "玉柴EDC7电脑版电路图", max_results=5)
    if not (r1.get("needs_choice") and r1.get("options")):
        r1 = _chat(session_id, "需要", max_results=5)
    opts = r1.get("options") or []
    assert opts, r1

    # pick the first merged bucket if any
    merged = None
    for o in opts:
        if int(o.get("count") or 0) > 1 and isinstance(o.get("ids"), list) and len(o.get("ids")) == int(o.get("count") or 0):
            merged = o
            break
    if merged is None:
        # If this dataset doesn't yield a merged bucket, nothing to assert here.
        return

    r2 = _chat(session_id, merged.get("label", "A"), max_results=5)
    assert r2.get("needs_choice") and r2.get("options"), r2
    # should expand to multiple options (or at least not be a single option with same count)
    assert len(r2["options"]) >= 2, r2["options"]


