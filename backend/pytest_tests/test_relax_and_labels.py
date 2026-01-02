from dataclasses import dataclass

from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.services.search_service import SearchService
from backend.app.services.question_service import QuestionService


@dataclass
class _FakeLoader:
    diagrams: list[CircuitDiagram]

    def get_all(self):
        return self.diagrams


def _mk_diagram(diagram_id: int, file_name: str):
    return CircuitDiagram(
        id=diagram_id,
        hierarchy_path=["电路图", "整车电路图", "商用车", "东风"],
        file_name=file_name,
    )


def test_option_labels_expand_beyond_5():
    labels = QuestionService._make_option_labels(30)
    assert len(labels) == 30
    assert labels[0] == "A"
    assert labels[4] == "E"
    assert labels[25] == "Z"
    assert labels[26] == "AA"
    assert labels[29] == "AD"


def test_search_and_relax_prefers_drop_generic_keeps_series_code():
    """
    回归：查询 “VGT线路图” 这类（系列码 + 泛类型词）AND 无结果时，
    VGT 若确实 0 命中，应被剔除；同时返回的 meta 应能反映这一点。
    """
    # 数据集中不存在 VGT，因此严格 AND 必然失败；放宽后应返回“线路图/电路图”相关。
    d1 = _mk_diagram(1, "东风_整车电路图.DOCX")
    d2 = _mk_diagram(2, "东风_仪表线路图.DOCX")
    svc = SearchService(data_loader=_FakeLoader([d1, d2]))

    results, meta = svc.search_and_relax(query="VGT线路图", max_results=50, use_fuzzy=True, intent_result=None)

    assert {r.diagram.id for r in results} == {1, 2}
    assert "VGT" in (meta.get("removed_keywords") or [])
    assert "VGT" not in (meta.get("used_keywords") or [])


