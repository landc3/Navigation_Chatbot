from dataclasses import dataclass

import pytest

from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.types import ScoredResult
from backend.app.models.intent import IntentResult
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


def test_extract_keywords_splits_guo_emission_and_howoqi():
    svc = SearchService(data_loader=_FakeLoader([]))
    kws = svc._extract_keywords("重汽豪沃国六电路图")
    # 关键点：不能出现“豪沃国”这种粘连；国六必须可独立成为关键词
    assert "豪沃国" not in kws
    assert "国六" in kws
    # 同时应能保留品牌的可组合关键词（至少包含 重汽/豪沃 之一）
    assert ("重汽" in kws) or ("豪沃" in kws)


def test_extract_keywords_dashboard_pin_should_split_into_two_terms():
    svc = SearchService(data_loader=_FakeLoader([]))
    # Use unicode escapes to avoid Windows encoding issues in source files.
    q = "\u4e1c\u98ce\u5929\u9f99\u4eea\u8868\u9488\u811a\u56fe"  # 东风天龙仪表针脚图
    kws = svc._extract_keywords(q)
    assert "\u4e1c\u98ce\u5929\u9f99" in kws  # 东风天龙
    assert "\u4eea\u8868" in kws  # 仪表
    # 首轮更严格：若用户显式“针脚图”，会优先保留“针脚图”；放宽后可退到“针脚”
    assert ("\u9488\u811a" in kws) ^ ("\u9488\u811a\u56fe" in kws)


def test_search_and_relax_removes_zero_hit_keyword_like_differential():
    d = _mk_diagram(
        1,
        "乘龙H7_整车电路图.DOCX",
        hierarchy=["电路图", "整车电路图", "商用车", "东风", "乘龙H7"],
    )
    svc = SearchService(data_loader=_FakeLoader([d]))
    strict = svc.search(query="乘龙H7差速器电路图", logic="AND", max_results=50, use_fuzzy=True)
    assert strict == []

    relaxed, meta = svc.search_and_relax(query="乘龙H7差速器电路图", max_results=50, use_fuzzy=True, intent_result=None)
    assert {r.diagram.id for r in relaxed} == {1}
    assert "差速器" in (meta.get("removed_keywords") or [])
    assert "差速器" not in (meta.get("used_keywords") or [])


def test_search_and_relax_prefers_remove_low_combinability_term():
    """
    复现“1 2 3 4”场景：
    - 1+3+4 能组合命中
    - 1+2 能组合，但 2 与 3/4 不能组合
    => 应优先剔除 2
    """
    d134 = _mk_diagram(1, "term1_term3_term4")
    d12 = _mk_diagram(2, "term1_term2")
    svc = SearchService(data_loader=_FakeLoader([d134, d12]))

    relaxed, meta = svc.search_and_relax(query="term1 term2 term3 term4", max_results=50, use_fuzzy=True, intent_result=None)
    assert {r.diagram.id for r in relaxed} == {1}
    assert "term2" in (meta.get("removed_keywords") or [])
    assert meta.get("used_keywords") == ["term1", "term3", "term4"]


def test_search_should_not_inject_ecu_type_when_user_did_not_say_ecu(capsys):
    """
    回归：用户说“电脑版针角图”不等于显式说 ECU，不应自动注入“ECU电路图”关键词。
    """
    d = _mk_diagram(
        1,
        "\u4e0a\u6c7d\u5927\u901a_V80_\u7535\u8111\u7248\u9488\u811a\u56fe_2012\u6b3e.DOCX",  # 上汽大通_V80_电脑版针脚图_2012款.DOCX
        hierarchy=["电路图", "针脚图", "商用车", "上汽大通", "V80"],
    )
    svc = SearchService(data_loader=_FakeLoader([d]))

    intent = IntentResult(
        brand=None,
        model=None,
        diagram_type="ECU\u7535\u8def\u56fe",  # ECU电路图
        vehicle_category=None,
        keywords=[],
        original_query="12\u5e74\u4e0a\u6c7d\u5927\u901aV80\u7535\u8111\u7248\u9488\u89d2\u56fe",  # 12年上汽大通V80电脑版针角图
        confidence=0.9,
    )
    _ = svc.search(
        query="12\u5e74\u4e0a\u6c7d\u5927\u901aV80\u7535\u8111\u7248\u9488\u89d2\u56fe",
        logic="AND",
        max_results=50,
        use_fuzzy=True,
        intent_result=intent,
    )
    out = capsys.readouterr().out
    # 如果被注入，match_stats 里会出现该 key（注意：query 里可能会包含它，这是允许的）
    assert "match_stats" in out
    for line in out.splitlines():
        if "match_stats" in line:
            assert "ECU\u7535\u8def\u56fe" not in line


def test_strict_filename_and_should_fail_then_relax(monkeypatch):
    """
    用户需求A：严格AND必须在文件名中同时命中所有关键词组。
    场景：文件名里没有“针脚图”，只有“针脚定义”，因此严格AND应失败并触发放宽（去掉/替换该关键词）。
    """
    svc = SearchService(data_loader=_FakeLoader([]))

    q = "\u4e1c\u98ce\u5929\u9f99\u4eea\u8868\u9488\u811a\u56fe"  # 东风天龙仪表针脚图
    d1 = _mk_diagram(1, "\u4e1c\u98ce\u5929\u9f99_\u4eea\u8868_\u9488\u811a\u5b9a\u4e49.DOCX")
    d2 = _mk_diagram(2, "\u4e1c\u98ce\u5929\u9f99_\u4eea\u8868_\u9488\u811a\u56fe.DOCX")
    svc = SearchService(data_loader=_FakeLoader([d1, d2]))

    stats = svc.strict_filename_and_stats(q)
    assert stats["and_count"] == 1
    assert set(stats["and_ids"]) == {2}

    # 如果只剩 d1，则严格AND失败；放宽时强制移除“针脚图”应能找到 d1
    svc2 = SearchService(data_loader=_FakeLoader([d1]))
    stats2 = svc2.strict_filename_and_stats(q)
    assert stats2["and_count"] == 0
    removed_terms = [t for t, c in (stats2["term_counts"] or {}).items() if int(c) <= 0]
    relaxed, meta = svc2.search_and_relax(q, max_results=50, use_fuzzy=True, intent_result=None, force_remove_terms=removed_terms)
    assert {r.diagram.id for r in relaxed} == {1}
    assert removed_terms


