import asyncio


def _mk_result(diagram_id: int, brand: str, model: str):
    from backend.app.models.circuit_diagram import CircuitDiagram
    from backend.app.models.types import ScoredResult

    d = CircuitDiagram(
        id=diagram_id,
        hierarchy_path=["电路图", "整车电路图", "商用车", brand, model],
        file_name=f"{brand}_{model}_整车电路图_{diagram_id}.DOCX",
    )
    return ScoredResult(diagram=d, score=1.0)


def test_fallback_option_labels_expand_beyond_e(monkeypatch):
    """
    回归：当 generate_question 返回 None 且 fallback 生成的选项数 > 5 时，
    /api/chat 不应因 option_labels 越界而 500，且 label 应能扩展到 F/G...
    """
    from backend.app.api import chat as chat_api
    from backend.app.models.conversation import get_conversation_manager
    from backend.app.services.question_service import QuestionService

    # 7 个品牌（>5）触发 label 扩展到 F/G
    brands = ["东风", "解放", "重汽", "福田", "乘龙", "红岩", "欧曼"]
    results = [_mk_result(i + 1, b, f"{b}M") for i, b in enumerate(brands)]

    class StubSearch:
        def search(self, *args, **kwargs):
            return list(results)

        def deduplicate_results(self, rs):
            return rs

    class StubLLM:
        def parse_intent(self, q):
            return None

        def generate_question_text(self, *args, **kwargs):
            return "请选择一个选项："

    class StubQuestion:
        # 复用真实的动态 label 生成逻辑（A..Z, AA..）
        _make_option_labels = staticmethod(QuestionService._make_option_labels)

        def generate_question(self, *args, **kwargs):
            # 强制走 chat.py 内的 fallback 逻辑
            return None

        def _extract_options_from_hierarchy(self, *args, **kwargs):
            return None

        def _generate_question_text(self, *args, **kwargs):
            return "请选择一个选项："

        def format_question_message(self, question_data):
            lines = [question_data.get("question", "").strip()]
            for opt in question_data.get("options", []):
                lines.append(f"{opt.get('label')}. {opt.get('name')}（{opt.get('count')}个结果）")
            return "\n".join([x for x in lines if x])

    monkeypatch.setattr(chat_api, "get_search_service", lambda: StubSearch())
    monkeypatch.setattr(chat_api, "get_llm_service", lambda: StubLLM())
    monkeypatch.setattr(chat_api, "get_question_service", lambda: StubQuestion())

    sid = "reg-labels"
    cm = get_conversation_manager()
    cm.clear_conversation(sid)

    out = asyncio.run(
        chat_api.chat(
            chat_api.ChatRequest(message="测试选项标签扩展", logic="OR", max_results=5, session_id=sid)
        )
    )
    assert out.needs_choice is True
    assert out.options is not None
    labels = {o.get("label") for o in out.options}
    # labels 应至少包含到 G（因为 7 个选项）
    assert labels == {"A", "B", "C", "D", "E", "F", "G"}


