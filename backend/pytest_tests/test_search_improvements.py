from dataclasses import dataclass

import pytest

from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.types import ScoredResult
from backend.app.services.search_service import SearchService
from backend.app.services.question_service import QuestionService


@dataclass
class _FakeLoader:
    diagrams: list[CircuitDiagram]

    def get_all(self):
        return self.diagrams


def _mk_diagram(diagram_id: int, file_name: str, hierarchy: list[str] | None = None):
    return CircuitDiagram(
        id=diagram_id,
        hierarchy_path=hierarchy or ["电路图", "仪表模块", "商用车", "东风", "天龙"],
        file_name=file_name,
    )


def test_and_strict_with_synonym_family_and_normalization():
    """
    复现报告中的漏召回问题：
    用户说“仪表图”，应召回“仪表_电路图”这类下位词文件名。
    """
    d1 = _mk_diagram(2332, "东风_天龙旗舰版_仪表电路图.DOCX", hierarchy=["电路图", "仪表模块", "商用车", "东风", "天龙"])
    d2 = _mk_diagram(2333, "东风_天龙_天锦_仪表_电路图.DOCX", hierarchy=["电路图", "仪表模块", "商用车", "东风", "天龙"])
    # 天锦不应被“东风天龙”命中：hierarchy/model 不包含“天龙”
    d3 = _mk_diagram(2334, "东风_天锦_仪表_电路图.DOCX", hierarchy=["电路图", "仪表模块", "商用车", "东风", "天锦"])

    svc = SearchService(data_loader=_FakeLoader([d1, d2, d3]))

    results = svc.search(query="东风天龙 仪表图", logic="AND", max_results=20, use_fuzzy=True)
    ids = {r.diagram.id for r in results}

    assert 2332 in ids
    assert 2333 in ids
    assert 2334 not in ids  # 只命中“仪表图”，未命中“东风天龙”，不应混入


def test_and_term_group_accepts_family_variants():
    """“仪表图”组应能被“仪表电路图/仪表线路图/仪表接线图”等命中。"""
    d1 = _mk_diagram(1, "东风天龙_仪表线路图.pdf")
    d2 = _mk_diagram(2, "东风天龙_仪表接线图.pdf")
    svc = SearchService(data_loader=_FakeLoader([d1, d2]))

    results = svc.search(query="东风天龙 仪表图", logic="AND", max_results=20, use_fuzzy=True)
    assert {r.diagram.id for r in results} == {1, 2}


def test_question_service_extract_config_variants():
    d1 = _mk_diagram(1, "东风天龙KL_6x4牵引车_整车电路图.DOCX", hierarchy=["电路图", "整车电路图", "商用车", "东风", "天龙KL"])
    d2 = _mk_diagram(2, "东风天龙KL_4x2牵引车_整车电路图.DOCX", hierarchy=["电路图", "整车电路图", "商用车", "东风", "天龙KL"])
    d3 = _mk_diagram(3, "东风天龙KL_6x4载货车_整车电路图.DOCX", hierarchy=["电路图", "整车电路图", "商用车", "东风", "天龙KL"])

    qs = QuestionService()
    options = qs._extract_config_variants(
        results=[ScoredResult(diagram=d1, score=1.0), ScoredResult(diagram=d2, score=1.0), ScoredResult(diagram=d3, score=1.0)],
        max_options=10,
        context=None,
    )
    names = {o["name"] for o in options}
    assert "6x4 牵引车" in names
    assert "4x2 牵引车" in names
    assert "6x4 载货车" in names


def test_series_code_strict_contiguous_and_post_filter_config():
    """
    回归：查询包含短系列码（如 KL）时，不能把“TK.L0”这种跨标点的片段误判为 KL；
    同时在“系列码 + 电路图”场景下，剔除缺少明确 Dxxx 配置段的“用途/轴型”变体记录。
    """
    d_good = _mk_diagram(
        1,
        "东风天龙KL_6x4牵引车_D320.TL10.H1903_整车电路图.DOCX",
        hierarchy=["电路图", "整车电路图", "商用车", "东风", "天龙*系列", "天龙KL", "6×4牵引车"],
    )
    # 不应被“KL”命中：K 与 L 被点号分隔
    d_bad_punct = _mk_diagram(
        2,
        "东风天龙D310.D320_TK.L0_整车电路图.DOCX",
        hierarchy=["电路图", "整车电路图", "商用车", "东风", "天龙*系列", "天龙D310"],
    )
    # 角色变体但缺少 Dxxx 配置段：应在“天龙KL电路图”场景被后处理剔除
    d_missing_config = _mk_diagram(
        3,
        "东风天龙KL_6x4牵引车_整车电路图.DOCX",
        hierarchy=["电路图", "整车电路图", "商用车", "东风", "天龙*系列", "天龙KL", "6×4牵引车"],
    )

    svc = SearchService(data_loader=_FakeLoader([d_good, d_bad_punct, d_missing_config]))
    results = svc.search(query="天龙KL电路图", logic="AND", max_results=50, use_fuzzy=True)
    assert {r.diagram.id for r in results} == {1}


def test_question_service_first_question_groups_vehicle_variants(monkeypatch):
    """
    复现用户期望：
    用户：我要一个天龙KL电路图
    首轮选项应按“车型变体前缀”分组（合计10条，5类）。
    """
    # 10 条：4(环卫) + 1(天龙KL) + 3(牵引) + 1(新天龙KL) + 1(新天龙KL_D320)
    diagrams = [
        _mk_diagram(1, "东风天龙KL_6x4环卫车_D310.K93A_整车电路图.DOCX"),
        _mk_diagram(2, "东风天龙KL_6x4环卫车_D310.K94A_整车电路图.DOCX"),
        _mk_diagram(3, "东风天龙KL_6x4环卫车_D310.K97A_整车电路图.DOCX"),
        _mk_diagram(4, "东风天龙KL_6x4环卫车_D320.TR84_整车电路图.DOCX"),
        _mk_diagram(5, "东风天龙KL_整车电路图.DOCX"),
        _mk_diagram(6, "东风天龙KL_6x4牵引车_D320.TL10_整车电路图.DOCX"),
        _mk_diagram(7, "东风天龙KL_6x4牵引车_D320.TL11_整车电路图.DOCX"),
        _mk_diagram(8, "东风天龙KL_6x4牵引车_D320.TL12_整车电路图.DOCX"),
        _mk_diagram(9, "东风新天龙KL_整车电路图.DOCX"),
        _mk_diagram(10, "东风新天龙KL_D320_整车电路图.DOCX"),
    ]

    fake_svc = SearchService(data_loader=_FakeLoader(diagrams))

    # QuestionService 模块里已经导入了 get_search_service，需要同时 patch 两处
    import backend.app.services.search_service as search_service_mod
    import backend.app.services.question_service as question_service_mod

    monkeypatch.setattr(search_service_mod, "get_search_service", lambda: fake_svc)
    monkeypatch.setattr(question_service_mod, "get_search_service", lambda: fake_svc)

    qs = QuestionService()
    scored = [ScoredResult(diagram=d, score=1.0) for d in diagrams]
    qd = qs.generate_question(
        results=scored,
        min_options=2,
        max_options=5,
        excluded_types=None,
        context={"current_query": "天龙KL电路图"},
        use_llm=False,
    )
    assert qd is not None
    assert qd["option_type"] == "variant"
    got = {o["name"]: o["count"] for o in qd["options"]}
    assert got == {
        "东风天龙KL_6x4环卫车 系列": 4,
        "东风天龙KL 系列": 1,
        "东风天龙KL_6x4牵引车 系列": 3,
        "东风新天龙KL 系列": 1,
        "东风新天龙KL_D320 系列": 1,
    }


def test_keyword_diagram_word_should_not_match_root_category():
    """
    回归：关键词“电路图”不应因 hierarchy_path[0] == "电路图" 而命中所有资料。
    应仅在文件名中包含“电路图”时才算命中（避免把线束图/定义/原理图混进来）。
    """
    d_ok = _mk_diagram(1, "福田_时代康瑞H1_整车电路图【EDC17C81】.DOCX", hierarchy=["电路图", "整车电路图", "商用车", "福田"])
    d_bad = _mk_diagram(2, "福田_小卡之星3_整车线束图【EDC17C81】.DOCX", hierarchy=["电路图", "整车电路图", "商用车", "福田"])
    svc = SearchService(data_loader=_FakeLoader([d_ok, d_bad]))
    results = svc.search(query="福田 C81 电路图", logic="AND", max_results=50, use_fuzzy=True)
    assert {r.diagram.id for r in results} == {1}


def test_variant_grouping_for_ecu_code_query(monkeypatch):
    """
    回归：对 “C81电路图” 这种 ECU/代号查询，首轮应按车型前缀分组（4组：1/2/2/1）。
    """
    diagrams = [
        _mk_diagram(1, "福田奥铃_493_整车电路图【EDC17C81】【国五】.DOCX"),
        _mk_diagram(2, "福田_时代康瑞H1_L037001000WA0整车电路图【EDC17C81】【国五】.DOCX"),
        _mk_diagram(3, "福田_时代康瑞H1_L037601002VA0仪表电路图【EDC17C81】【国五】.DOCX"),
        _mk_diagram(4, "江淮_瑞风M5_整车电路图【EDC17C81】【2012款】.DOCX"),
        _mk_diagram(5, "江淮_瑞风M5_电路图概述、线束布置及部件位置【EDC17C81】【2012款】.DOCX"),
        _mk_diagram(6, "东风_凯普特D28_国四_整车电路图【EDC17C81】.DOCX"),
    ]
    fake_svc = SearchService(data_loader=_FakeLoader(diagrams))

    import backend.app.services.search_service as search_service_mod
    import backend.app.services.question_service as question_service_mod

    monkeypatch.setattr(search_service_mod, "get_search_service", lambda: fake_svc)
    monkeypatch.setattr(question_service_mod, "get_search_service", lambda: fake_svc)

    qs = QuestionService()
    scored = [ScoredResult(diagram=d, score=1.0) for d in diagrams]
    qd = qs.generate_question(
        results=scored,
        min_options=2,
        max_options=5,
        excluded_types=None,
        context={"current_query": "C81电路图"},
        use_llm=False,
    )
    assert qd is not None
    assert qd["option_type"] == "variant"

    got = {o["name"]: o["count"] for o in qd["options"]}
    assert got == {
        "福田奥铃_493 系列": 1,
        "福田_时代康瑞H1 系列": 2,
        "江淮_瑞风M5 系列": 2,
        "东风_凯普特D28_国四 系列": 1,
    }


