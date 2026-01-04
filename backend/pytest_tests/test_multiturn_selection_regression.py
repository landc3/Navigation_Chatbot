import asyncio


def _mk_result(diagram_id: int, file_name: str = "X", hierarchy_path=None, score: float = 1.0):
    from backend.app.models.circuit_diagram import CircuitDiagram
    from backend.app.models.types import ScoredResult

    if hierarchy_path is None:
        hierarchy_path = ["电路图", "电路图", "商用车", "重汽", "TX"]
    d = CircuitDiagram(id=diagram_id, hierarchy_path=hierarchy_path, file_name=file_name)
    return ScoredResult(diagram=d, score=score)


def test_multiturn_choice_does_not_rerun_global_search(monkeypatch):
    """
    回归：当用户已经选择了某个选项，但筛选后仍然>max_results时，
    系统应继续基于“已筛选候选集”生成下一轮选择题，而不是把 query 改成选项文本再跑一次全量 AND 搜索。
    否则会出现 UI 上显示 7/33 条，下一轮却变成 0/1 条的问题。
    """
    from backend.app.api import chat as chat_api
    from backend.app.models.conversation import get_conversation_manager, ConversationStateEnum

    # --- stub services ---
    calls = {"search": 0, "parse_intent": 0, "filter": 0, "gen_question": 0}

    class StubLLM:
        def parse_intent(self, q):
            calls["parse_intent"] += 1
            return None

    class StubSearch:
        def __init__(self):
            self._first = [_mk_result(i, file_name=f"file_{i}") for i in range(10)]

        def search_with_intent(self, *args, **kwargs):
            raise AssertionError("search_with_intent should not be called in this regression test")

        def search(self, *args, **kwargs):
            calls["search"] += 1
            # first turn: return 10 results; second turn must NOT call this again
            if calls["search"] > 1:
                raise AssertionError("Global search() must not be re-run after option selection")
            return list(self._first)

        def deduplicate_results(self, results):
            return results

        def filter_by_hierarchy(self, results, brand=None, model=None, diagram_type=None, vehicle_category=None):
            calls["filter"] += 1
            # after selecting option A, return 7 results (>5) to force another question
            return list(results[:7])

        def strict_filename_and_stats(self, *args, **kwargs):
            return {"and_count": 1, "term_counts": {}}

    class StubQuestion:
        @staticmethod
        def _make_option_labels(n: int):
            import string
            letters = string.ascii_uppercase
            return [letters[i] for i in range(min(n, len(letters)))]

        def generate_question(self, results, min_options=2, max_options=5, excluded_types=None, context=None, use_llm=True):
            calls["gen_question"] += 1
            # first time: ask brand; second time: ask type (just to prove pipeline continues)
            if calls["gen_question"] == 1:
                return {
                    "question": "请选择品牌：",
                    "option_type": "brand",
                    "options": [
                        # Provide ids so selection can be precisely applied
                        {"label": "A", "name": "重汽", "count": len(results), "type": "brand", "ids": [r.diagram.id for r in results[:7]]},
                        {"label": "B", "name": "其他", "count": 1, "type": "brand"},
                    ],
                }
            return {
                "question": "请选择类型：",
                "option_type": "type",
                "options": [
                    {"label": "A", "name": "整车电路图", "count": len(results), "type": "type"},
                    {"label": "B", "name": "CAN总线图", "count": 1, "type": "type"},
                ],
            }

        def format_question_message(self, question_data):
            # Minimal formatter compatible with chat.py expectations
            lines = [question_data.get("question", "").strip()]
            for opt in question_data.get("options", []):
                lines.append(f"{opt.get('label')}. {opt.get('name')}（{opt.get('count')}个结果）")
            return "\n".join([x for x in lines if x])

    stub_search = StubSearch()
    stub_llm = StubLLM()
    stub_question = StubQuestion()

    monkeypatch.setattr(chat_api, "get_search_service", lambda: stub_search)
    monkeypatch.setattr(chat_api, "get_llm_service", lambda: stub_llm)
    monkeypatch.setattr(chat_api, "get_question_service", lambda: stub_question)

    cm = get_conversation_manager()
    cm.clear_conversation("reg1")

    # --- turn 1: initial query triggers first question ---
    req1 = chat_api.ChatRequest(message="重汽TX电路图", session_id="reg1")
    out1 = asyncio.run(chat_api.chat(req1))
    assert out1.needs_choice is True
    assert out1.options and out1.options[0]["label"] == "A"

    st = cm.get_or_create_state("reg1")
    assert st.state == ConversationStateEnum.NEEDS_CHOICE
    assert st.current_query == "重汽TX电路图"
    assert len(st.search_results or []) == 10

    # --- turn 2: user picks A; should NOT rerun search(), should continue with filtered_results ---
    req2 = chat_api.ChatRequest(message="A", session_id="reg1")
    out2 = asyncio.run(chat_api.chat(req2))
    assert out2.needs_choice is True
    assert calls["search"] == 1  # still only the first-turn search

    st2 = cm.get_or_create_state("reg1")
    # critical: do not overwrite current_query with "A"
    assert st2.current_query == "重汽TX电路图"
    # and candidate set should be the bucket ids (7 results)
    assert len(st2.search_results or []) == 7


def test_search_does_not_inject_inferred_brand_when_not_explicit():
    """
    回归：意图里带 brand，但用户原文未显式出现时，不应把 brand 注入为硬关键词。
    这能避免“JH6空调线路图”被强行加上“解放”导致 AND 失败。
    """
    from backend.app.services.search_service import SearchService
    from backend.app.models.intent import IntentResult

    class StubLoader:
        def get_all(self):
            # Only contains JH6 + 空调 + 线路图, but NOT "解放"
            from backend.app.models.circuit_diagram import CircuitDiagram

            return [
                CircuitDiagram(
                    id=1,
                    hierarchy_path=["电路图", "线路图", "商用车", "其他", "JH6"],
                    file_name="JH6 空调 线路图",
                )
            ]

    svc = SearchService(data_loader=StubLoader())
    intent = IntentResult(brand="解放", model="JH6", diagram_type=None, vehicle_category=None, keywords=["空调", "线路图"], original_query="JH6空调线路图", confidence=0.7)

    # If brand were injected as hard AND term, this would fail. With fix, it should succeed.
    results = svc.search(query=intent.get_search_query(), logic="AND", max_results=10, use_fuzzy=True, intent_result=intent)
    assert len(results) == 1


def test_option_count_matches_ids_and_never_increases(monkeypatch):
    """
    回归：选择题每个选项的 count 必须等于 ids 长度；
    用户选择某个选项后，筛选结果数不得增加（只能 <= 之前）。
    """
    import asyncio
    from backend.app.api import chat as chat_api
    from backend.app.models.conversation import get_conversation_manager, ConversationStateEnum

    def _mk(diagram_id: int, diagram_type: str, brand: str = "中国重汽", model: str = "豪瀚"):
        from backend.app.models.circuit_diagram import CircuitDiagram
        from backend.app.models.types import ScoredResult

        d = CircuitDiagram(
            id=diagram_id,
            hierarchy_path=["电路图", diagram_type, "商用车", brand, model],
            file_name=f"{brand}_{model}_{diagram_type}_{diagram_id}.PDF",
        )
        return ScoredResult(diagram=d, score=1.0)

    class StubLLM:
        def parse_intent(self, q):
            return None

    class StubSearch:
        def __init__(self):
            self._all = []
            # total 38: 33 豪瀚天然气 + 5 CAN总线图
            for i in range(1, 34):
                self._all.append(_mk(i, "豪瀚天然气"))
            for i in range(34, 39):
                self._all.append(_mk(i, "CAN总线图"))

        def search(self, *args, **kwargs):
            return list(self._all)

        def deduplicate_results(self, results):
            return results

        def strict_filename_and_stats(self, *args, **kwargs):
            return {"and_count": 1, "term_counts": {}}

        def filter_by_hierarchy(self, results, brand=None, model=None, diagram_type=None, vehicle_category=None):
            # Should never be needed if ids are used, but keep a safe fallback
            out = list(results)
            if diagram_type:
                out = [r for r in out if (r.diagram.diagram_type == diagram_type)]
            return out

    stub_search = StubSearch()
    monkeypatch.setattr(chat_api, "get_search_service", lambda: stub_search)
    monkeypatch.setattr(chat_api, "get_llm_service", lambda: StubLLM())
    # use real question_service to exercise ids generation
    monkeypatch.setattr(chat_api, "get_question_service", chat_api.get_question_service)

    sid = "reg-ids"
    cm = get_conversation_manager()
    cm.clear_conversation(sid)

    out1 = asyncio.run(chat_api.chat(chat_api.ChatRequest(message="豪瀚玻璃升降电路图", session_id=sid)))
    assert out1.needs_choice is True
    assert out1.options
    # All options should have ids and count == len(ids)
    for opt in out1.options:
        assert isinstance(opt.get("ids"), list) and opt["ids"], f"missing ids for opt {opt}"
        assert int(opt.get("count") or 0) == len(opt["ids"])

    st = cm.get_or_create_state(sid)
    assert st.state == ConversationStateEnum.NEEDS_CHOICE
    pre_n = len(st.search_results or [])
    assert pre_n == 38

    # pick first option (likely 豪瀚天然气)
    pick_label = out1.options[0]["label"]
    out2 = asyncio.run(chat_api.chat(chat_api.ChatRequest(message=pick_label, session_id=sid)))
    st2 = cm.get_or_create_state(sid)
    post_n = len(st2.search_results or [])
    assert post_n <= pre_n


def test_single_option_choice_is_bypassed_and_expands_to_file_list(monkeypatch):
    """
    回归：当选择题只生成 1 个选项时（无信息增量），不应要求用户再点一次；
    /api/chat 应直接展开到“文件级列表”供用户选择。
    """
    from backend.app.api import chat as chat_api
    from backend.app.models.conversation import get_conversation_manager

    class StubLLM:
        def parse_intent(self, q):
            return None

        def generate_question_text(self, *args, **kwargs):
            return "请选择："

    class StubSearch:
        def __init__(self):
            self._all = [_mk_result(i, file_name=f"江淮_康铃{i}_保险盒定义_{i}.DOCX") for i in range(1, 15)]

        def search(self, *args, **kwargs):
            return list(self._all)

        def deduplicate_results(self, results):
            return results

        def strict_filename_and_stats(self, *args, **kwargs):
            return {"and_count": 1, "term_counts": {}}

        def filter_by_hierarchy(self, results, brand=None, model=None, diagram_type=None, vehicle_category=None):
            return list(results)

    class StubQuestion:
        @staticmethod
        def _make_option_labels(n: int):
            import string

            letters = string.ascii_uppercase
            out = []
            for i in range(n):
                out.append(letters[i] if i < 26 else f"A{letters[i - 26]}")
            return out

        def generate_question(self, results, *args, **kwargs):
            # 故意返回“只有一个桶”的选择题（覆盖全部 ids）
            return {
                "question": "明白了。请问您需要的是哪一份资料：",
                "option_type": "filename_prefix",
                "options": [
                    {
                        "label": "A",
                        "name": "江淮_康铃1_保险盒定义",
                        "type": "filename_prefix",
                        "count": len(results),
                        "ids": [r.diagram.id for r in results],
                    }
                ],
            }

        def format_question_message(self, question_data):
            lines = [question_data.get("question", "").strip()]
            for opt in question_data.get("options", []):
                lines.append(f"{opt.get('label')}. {opt.get('name')}（{opt.get('count')}个结果）")
            return "\n".join([x for x in lines if x])

    monkeypatch.setattr(chat_api, "get_search_service", lambda: StubSearch())
    monkeypatch.setattr(chat_api, "get_llm_service", lambda: StubLLM())
    monkeypatch.setattr(chat_api, "get_question_service", lambda: StubQuestion())

    cm = get_conversation_manager()
    sid = "reg-single-opt"
    cm.clear_conversation(sid)

    out = asyncio.run(chat_api.chat(chat_api.ChatRequest(message="庆铃保险盒盒图", session_id=sid, max_results=5)))
    assert out.needs_choice is True
    assert out.options is not None
    # should have expanded to multiple file-level options (not a single one)
    assert len(out.options) >= 2
    assert all(o.get("type") == "result" for o in out.options)


