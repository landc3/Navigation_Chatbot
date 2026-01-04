"""
聊天API
集成意图理解和对话管理
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import re
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.search_service import get_search_service
from backend.app.services.llm_service import get_llm_service
from backend.app.services.question_service import get_question_service
from backend.app.models.conversation import (
    get_conversation_manager,
    ConversationStateEnum
)
from backend.app.utils.hierarchy_util import HierarchyUtil
from backend.app.utils.variant_util import variant_key_for_query

router = APIRouter()

def _filter_conditions_text(filter_history: List[Dict[str, Any]]) -> str:
    """
    将 filter_history 归一成可读的“当前筛选条件”文本。
    规则：同一 type 只保留最后一次的 value，并按固定顺序输出。
    """
    label_map = {
        "brand": "品牌",
        "model": "型号/系列",
        "type": "图纸类型",
        "variant": "车型变体",
        "brand_model": "品牌+系列",
        "config": "配置/用途",
        "result": "资料",
    }
    last_by_type: Dict[str, str] = {}
    for f in (filter_history or []):
        try:
            t = str(f.get("type") or "").strip()
            v = str(f.get("value") or "").strip()
        except Exception:
            continue
        if t and v:
            last_by_type[t] = v
    if not last_by_type:
        return ""
    # 若 brand + model 都已存在，则不再额外展示 brand_model（避免重复/噪音）
    if "brand" in last_by_type and "model" in last_by_type and "brand_model" in last_by_type:
        last_by_type.pop("brand_model", None)

    order = ["brand", "model", "type", "variant", "config", "result", "brand_model"]
    parts: List[str] = []
    for t in order:
        if t in last_by_type:
            parts.append(f"{label_map.get(t, t)}={last_by_type[t]}")
    for t, v in last_by_type.items():
        if t not in order:
            parts.append(f"{label_map.get(t, t)}={v}")
    return "，".join(parts)


def _build_selection_summary(
    option_value: str,
    pre_total: int,
    post_total: int,
    filter_history: List[Dict[str, Any]],
) -> str:
    ov = (option_value or "").strip()
    cond_txt = _filter_conditions_text(filter_history)
    if cond_txt:
        return (
            f"明白了，已根据您选择的“{ov}”进一步筛选：{pre_total} → {post_total} 条。\n"
            f"当前筛选条件：{cond_txt}"
        )
    return f"明白了，已根据您选择的“{ov}”进一步筛选：{pre_total} → {post_total} 条。"


def _prepend_selection_summary(message: str, selection_summary: Optional[str]) -> str:
    if selection_summary:
        return f"{selection_summary}\n\n{message}"
    return message


def _filter_out_noop_options(options: List[Dict[str, Any]], all_ids: set) -> List[Dict[str, Any]]:
    """
    Remove options that do not narrow the candidate set at all (ids == all_ids).
    This prevents "23 → 23" loops where the user keeps seeing (and selecting) no-op buckets.
    """
    if not options or not all_ids:
        return options or []
    out: List[Dict[str, Any]] = []
    for o in options:
        ids = o.get("ids")
        if isinstance(ids, list) and ids and set(ids) == all_ids:
            continue
        out.append(o)
    return out


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色：user 或 assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    history: Optional[List[ChatMessage]] = Field(default_factory=list)
    logic: Optional[str] = "AND"  # AND or OR
    max_results: Optional[int] = 5
    session_id: Optional[str] = "default"  # 会话ID，用于多轮对话


class ChatResponse(BaseModel):
    """聊天响应"""
    message: str
    results: Optional[List[dict]] = None  # 搜索结果（如果有）
    options: Optional[List[dict]] = None  # 选择题选项（如果有）
    needs_choice: Optional[bool] = False  # 是否需要用户选择
    session_id: Optional[str] = "default"  # 会话ID


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    
    集成意图理解和对话管理
    支持多轮对话和选择题引导
    """
    # 确保 re 模块可用（显式引用全局变量）
    _ = re
    
    # 获取服务实例
    search_service = get_search_service()
    llm_service = get_llm_service()
    question_service = get_question_service()
    conversation_manager = get_conversation_manager()
    
    # 获取或创建对话状态
    session_id = request.session_id or "default"
    conv_state = conversation_manager.get_or_create_state(session_id)
    
    # 获取用户查询
    query = request.message.strip()
    if not query:
        return ChatResponse(
            message="请输入您要查找的电路图关键词，例如：东风天龙仪表针脚图",
            session_id=session_id
        )
    
    # 检测用户是否想要重述需求（明确的重述需求请求）
    rephrase_keywords = ["我要重述需求", "重述需求", "重新表述需求", "重新表达需求", "重新说", "重新输入"]
    is_rephrase_request = False
    for keyword in rephrase_keywords:
        if keyword in query:
            is_rephrase_request = True
            break

    # 处理重述需求请求
    if is_rephrase_request:
        # 清空对话状态，准备重新开始
        conv_state.clear()
        # 添加用户消息到历史
        conv_state.add_message("user", query)
        # 返回友好的提示，引导用户重新输入
        friendly_message = "好的，我已经清空了之前的搜索条件。\n\n请重新输入您要查找的电路图关键词，例如：\n- 东风天龙仪表针脚图\n- 重汽豪沃整车电路图\n- 解放JH6 ECU图"
        conv_state.add_message("assistant", friendly_message)
        return ChatResponse(
            message=friendly_message,
            session_id=session_id
        )

    # 检测用户是否重新表达需求（如"我要找XXX"、"找一下XXX"等）
    # 注意：不要将"我要一个XXX"误判为重置关键词
    reset_keywords = ["我要找", "找一下", "搜索", "查找", "重新", "换一个"]
    # 检查是否是重置关键词（排除"我要一个"这种情况）
    is_new_query = False
    if conv_state.state != ConversationStateEnum.INITIAL:
        for keyword in reset_keywords:
            if keyword in query:
                is_new_query = True
                break
        # 特殊处理："我要一个XXX"不应该触发重置
        if "我要一个" in query or "我要个" in query:
            is_new_query = False

    # 检测用户是否想要返回上一步
    undo_keywords = ["返回上一步", "上一步", "返回", "撤销", "后悔", "重新选择", "换一个选择"]
    is_undo_request = False
    for keyword in undo_keywords:
        if keyword in query.lower():
            is_undo_request = True
            break

    # 处理返回上一步请求
    if is_undo_request:
        # 不添加用户消息到历史（因为这是操作命令，不是对话内容）
        if conv_state.can_undo():
            # 执行撤销操作（这会从历史中恢复上一个状态）
            success = conv_state.undo_last_step()
            if success:
                # 找到恢复状态后的最后一条助手消息
                last_assistant_msg = None
                for msg in reversed(conv_state.message_history):
                    if msg.role == "assistant":
                        last_assistant_msg = msg
                        break

                if last_assistant_msg:
                    # 直接返回恢复的状态，不添加额外的提示信息
                    return ChatResponse(
                        message=last_assistant_msg.content,
                        options=conv_state.current_options if conv_state.current_options else None,
                        needs_choice=conv_state.state == ConversationStateEnum.NEEDS_CHOICE,
                        session_id=session_id
                    )
                else:
                    return ChatResponse(
                        message="已返回上一步，但无法恢复之前的界面。请重新输入您的需求。",
                        session_id=session_id
                    )
            else:
                return ChatResponse(
                    message="无法返回上一步，没有可用的历史状态。",
                    session_id=session_id
                )
        else:
            return ChatResponse(
                message="无法返回上一步，这是对话的开始状态。",
                session_id=session_id
            )

    # 如果用户重新表达需求，重置对话状态
    if is_new_query:
        conv_state.clear()
        # 提取新的查询（移除重置关键词）
        for keyword in reset_keywords:
            query = query.replace(keyword, "").strip()
        if not query:
            return ChatResponse(
                message="请输入您要查找的电路图关键词，例如：东风天龙仪表针脚图",
                session_id=session_id
            )
    
    # 在处理用户输入前保存当前状态（用于返回上一步功能）
    # 在添加用户消息之前保存，这样返回上一步时不会包含用户消息
    # 但不保存初始状态或已完成状态
    if conv_state.state not in [ConversationStateEnum.INITIAL, ConversationStateEnum.COMPLETED]:
        conv_state.save_state_snapshot()

    # 添加用户消息到历史
    conv_state.add_message("user", query)

    # 如果上一轮是“放宽关键词后找到近似结果”的确认态，这一轮优先处理“需要/不需要”
    if conv_state.state == ConversationStateEnum.NEEDS_CONFIRM:
        user_confirm = (query or "").strip()
        yes_set = {"需要", "要", "好的", "好", "是", "可以", "行", "ok", "OK"}
        no_set = {"不需要", "不要", "不用", "否", "不", "算了"}

        if user_confirm in yes_set:
            # 关键修复：
            # 用户回复“需要”时，必须沿用“放宽后得到的结果集”，绝不能再次跑意图识别/重新搜索
            # 否则会把“乘龙H7电路图”扩大成“东风柳汽一堆系列”的无关集合。

            # 重要：不要把 current_query 覆盖成“需要”
            query = (conv_state.current_query or "").strip() or query

            # 直接复用上一轮的放宽结果（本身就是 used_keywords 的 AND 交集）
            scored_results = search_service.deduplicate_results(conv_state.search_results or [])
            conv_state.search_results = scored_results

            # 复用上一轮的意图（若存在），用于生成更合理的选择题上下文
            intent_result = conv_state.intent_result

            meta = conv_state.relax_meta or {}
            used = meta.get("used_keywords") or []
            try:
                print(f"[DEBUG] confirm=YES, relaxed used_keywords: {used}")
            except Exception:
                pass

            # 关键修复：
            # 进入“放宽后继续”的后续选择题时，current_query 必须改成 used_keywords，
            # 否则问题文本/后续分组会继续引用被剔除的关键词（例如：庆龄=0 但 UI 仍说“庆龄相关”）。
            relaxed_query = " ".join([str(x).strip() for x in used if str(x).strip()])
            if relaxed_query:
                query = relaxed_query
                conv_state.current_query = relaxed_query

            # 标记：后续不要再做意图解析/搜索，只做选择题/展示
            skip_search = True
            force_choose = True
            conv_state.update_state(ConversationStateEnum.SEARCHING)
        elif user_confirm in no_set:
            conv_state.update_state(ConversationStateEnum.COMPLETED)
            msg = "好的。如需继续，请直接输入新的关键词重新搜索。"
            conv_state.add_message("assistant", msg)
            return ChatResponse(message=msg, session_id=session_id)
        else:
            msg = "我可以基于已找到的相关资料继续为您筛选。请回复“需要”继续，或回复“不需要”重新搜索。"
            conv_state.add_message("assistant", msg)
            return ChatResponse(message=msg, session_id=session_id)
    
    # 检测用户是否在回答“选项标签”（支持 A..Z, AA.. 等动态扩展标签）
    user_input_upper = (query or "").upper().strip()
    is_option_selection = False
    if conv_state.state == ConversationStateEnum.NEEDS_CHOICE and conv_state.current_options:
        labels = {str(o.get("label", "")).upper().strip() for o in conv_state.current_options if o.get("label")}
        if user_input_upper in labels:
            is_option_selection = True
    
    # 如果当前状态是等待选择，且用户输入是选项，处理选择
    if conv_state.state == ConversationStateEnum.NEEDS_CHOICE and is_option_selection:
        # 解析用户选择
        if conv_state.current_options:
            # 找到对应的选项
            selected_option = None
            for option in conv_state.current_options:
                if option.get('label') == user_input_upper:
                    selected_option = option
                    break
            
            if selected_option:
                # 基于选择筛选结果
                option_type = selected_option.get('type')
                option_value = selected_option.get('name')
                
                pre_filter_total = len(conv_state.search_results or [])
                filtered_results = conv_state.search_results
                # 关键修复：如果选项自带 ids，优先按 ids 精确过滤（避免“选NT却混入MT/N”等问题）
                opt_ids = selected_option.get("ids")
                if isinstance(opt_ids, list) and opt_ids:
                    try:
                        id_set = {int(x) for x in opt_ids}
                    except Exception:
                        id_set = {x for x in opt_ids}
                    filtered_results = [r for r in (filtered_results or []) if r.diagram.id in id_set]
                if option_type == "brand":
                    conv_state.add_filter("brand", option_value or "")
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, brand=option_value
                    )
                elif option_type == "model":
                    conv_state.add_filter("model", option_value or "")
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, model=option_value
                    )
                elif option_type == "type":
                    conv_state.add_filter("type", option_value or "")
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, diagram_type=option_value
                    )
                elif option_type == "variant":
                    conv_state.add_filter("variant", option_value or "")
                    # 车型变体：按文件名前缀精确分组（例如 “东风天龙KL_6x4环卫车”）
                    base = (option_value or "").strip()
                    for suf in (" 系列", "系列"):
                        if base.endswith(suf):
                            base = base[: -len(suf)].strip()
                            break
                    next_filtered = []
                    for r in filtered_results:
                        k = variant_key_for_query(r.diagram.file_name or "", conv_state.current_query or "")
                        if k and k == base:
                            next_filtered.append(r)
                    filtered_results = next_filtered
                elif option_type == "brand_model":
                    # 品牌+型号组合：解析选项值（如"东风 天龙KL"、"东风 DOC"、"东风 VEC"等）
                    brand, model = search_service._parse_brand_model(option_value)
                    if brand and model:
                        conv_state.add_filter("brand", brand)
                        conv_state.add_filter("model", model)
                        # 先按品牌筛选
                        filtered_results = search_service.filter_by_hierarchy(
                            filtered_results, brand=brand
                        )
                        # 再按型号筛选（支持层级路径匹配）
                        if filtered_results:
                            filtered_diagrams = HierarchyUtil.filter_by_model(
                                [r.diagram for r in filtered_results], model
                            )
                            filtered_ids = {d.id for d in filtered_diagrams}
                            filtered_results = [r for r in filtered_results if r.diagram.id in filtered_ids]
                    elif brand:
                        conv_state.add_filter("brand", brand)
                        filtered_results = search_service.filter_by_hierarchy(
                            filtered_results, brand=brand
                        )
                elif option_type == "result":
                    conv_state.add_filter("result", option_value or user_input_upper)
                    # 直接选择某一份资料（文件）
                    target_id = selected_option.get("id")
                    if target_id is not None:
                        filtered_results = [r for r in (filtered_results or []) if r.diagram.id == target_id]
                elif option_type == "document_category":
                    # 文档主题分类：如果选项有 ids，直接按 ids 过滤；否则按类别名称匹配文件名
                    conv_state.add_filter("document_category", option_value or "")
                    # 如果 ids 过滤没有结果（或没有 ids），尝试按名称匹配
                    if not filtered_results or not opt_ids:
                        from backend.app.services.search_service import SearchService
                        category_name = SearchService._norm_text(option_value or "")
                        if category_name:
                            next_filtered = []
                            for r in (conv_state.search_results or []):
                                d = r.diagram
                                file_name_norm = SearchService._norm_text(d.file_name or "")
                                # 检查文件名是否包含类别名称的关键部分
                                if category_name in file_name_norm:
                                    next_filtered.append(r)
                            filtered_results = next_filtered
                elif option_type == "filename_prefix":
                    # 文件名前缀合并：如果选项有 ids，直接按 ids 过滤；否则按前缀名称匹配文件名
                    conv_state.add_filter("filename_prefix", option_value or "")
                    # 如果 ids 过滤没有结果（或没有 ids），尝试按前缀名称匹配
                    if not filtered_results or not opt_ids:
                        from backend.app.services.search_service import SearchService
                        prefix_name = option_value or ""
                        # 去除"系列"后缀
                        prefix_name = re.sub(r'系列$', '', prefix_name).strip()
                        prefix_norm = SearchService._norm_text(prefix_name)
                        if prefix_norm:
                            next_filtered = []
                            for r in (conv_state.search_results or []):
                                d = r.diagram
                                file_name_norm = SearchService._norm_text(d.file_name or "")
                                # 检查文件名是否以该前缀开头
                                if file_name_norm.startswith(prefix_norm):
                                    next_filtered.append(r)
                            filtered_results = next_filtered
                
                # 更新对话状态
                conv_state.search_results = filtered_results
                conv_state.current_options = []
                conv_state.option_type = None
                # 支持配置/轴型筛选（如 6x4 牵引车）
                if option_type == "config":
                    conv_state.add_filter("config", option_value or "")
                    # 基于规范化文本包含匹配
                    from backend.app.services.search_service import SearchService
                    target = SearchService._norm_text(option_value)
                    if target:
                        next_filtered = []
                        for r in filtered_results:
                            d = r.diagram
                            blob = SearchService._diagram_blob(d)
                            if target in blob:
                                next_filtered.append(r)
                        filtered_results = next_filtered
                        conv_state.search_results = filtered_results
                
                # 检查筛选后的结果数量
                if not filtered_results:
                    conv_state.update_state(ConversationStateEnum.COMPLETED)
                    conv_state.add_message("assistant", f"抱歉，没有找到与「{option_value}」相关的电路图。请尝试其他选项或重新搜索。")
                    return ChatResponse(
                        message=f"抱歉，没有找到与「{option_value}」相关的电路图。请尝试其他选项或重新搜索。",
                        session_id=session_id
                    )
                
                # 统一的筛选摘要：无论继续提问还是直接出结果，都先写清“条数变化 + 当前筛选条件”
                selection_summary = _build_selection_summary(
                    option_value=option_value or user_input_upper,
                    pre_total=pre_filter_total,
                    post_total=len(filtered_results),
                    filter_history=conv_state.filter_history,
                )
                # 关键保护：筛选后结果不能比筛选前更多（否则说明选项count/ids或筛选逻辑不一致）
                if len(filtered_results) > pre_filter_total:
                    print(f"[WARN] selection increased results: {pre_filter_total} -> {len(filtered_results)}; option={option_type}:{option_value}")
                
                # 如果筛选后结果≤5个，直接返回结果
                max_results = request.max_results or 5
                if len(filtered_results) <= max_results:
                    formatted_results = []
                    for result in filtered_results:
                        formatted_results.append({
                            "id": result.diagram.id,
                            "file_name": result.diagram.file_name,
                            "hierarchy_path": " -> ".join(result.diagram.hierarchy_path),
                            "score": round(result.score, 2),
                            "brand": result.diagram.brand,
                            "model": result.diagram.model,
                            "diagram_type": result.diagram.diagram_type
                        })
                    
                    # 若用户查询包含“电路图”，且筛选后只剩单一图纸类型，则加一段确认话术（更贴近业务期望）
                    preface = ""
                    try:
                        q0 = (conv_state.current_query or "")
                        unique_types = {r.diagram.diagram_type for r in filtered_results if getattr(r.diagram, "diagram_type", None)}
                        if ("电路图" in q0) and len(unique_types) == 1:
                            only_type = next(iter(unique_types))
                            preface = f"补充说明：查看包含电路图的数据，发现{pre_filter_total}条数据中图纸类型只有“{only_type}”，我直接把结果列出来：\n\n"
                    except Exception:
                        preface = ""

                    message = _prepend_selection_summary(preface + f"已为您找到以下电路图：\n\n", selection_summary)
                    for i, result in enumerate(formatted_results, 1):
                        message += f"{i}. [ID: {result['id']}] {result['file_name']}\n"
                        message += f"   路径: {result['hierarchy_path']}\n"
                        if result['brand'] or result['model']:
                            attrs = []
                            if result['brand']:
                                attrs.append(f"品牌: {result['brand']}")
                            if result['model']:
                                attrs.append(f"型号: {result['model']}")
                            if result['diagram_type']:
                                attrs.append(f"类型: {result['diagram_type']}")
                            if attrs:
                                message += f"   {', '.join(attrs)}\n"
                        message += "\n"
                    
                    conv_state.update_state(ConversationStateEnum.COMPLETED)
                    conv_state.add_message("assistant", message)
                    
                    return ChatResponse(
                        message=message,
                        results=formatted_results,
                        needs_choice=False,
                        session_id=session_id
                    )
                
                # 如果筛选后结果仍然>5个，继续生成选择题
                # 关键修复：
                # 已经有 filtered_results（候选集）了，这里绝不能把 query 改成选项文本再去跑一次全量 AND 搜索，
                # 否则会出现“上一轮显示 7 条/33 条，下一轮却只剩 1 条甚至 0 条”的深度搜索错乱。
                scored_results = filtered_results
                skip_search = True
                force_choose = True
                # 同时避免把 current_query 覆盖成用户输入的“选项标签(A/B/AA...)”
                query = (conv_state.current_query or "").strip() or (option_value or "").strip() or query
            else:
                conv_state.add_message("assistant", "抱歉，无法识别您的选择。请重新选择或输入选项名称。")
                return ChatResponse(
                    message="抱歉，无法识别您的选择。请重新选择或输入选项名称。",
                    session_id=session_id
                )
        else:
            # 没有选项数据，重新搜索
            pass
    
    # 如果用户输入是文本选项名称，也尝试匹配
    elif conv_state.state == ConversationStateEnum.NEEDS_CHOICE and conv_state.current_options:
        # 尝试匹配选项名称
        matched_option = None
        for option in conv_state.current_options:
            if query.lower() in option.get('name', '').lower() or \
               option.get('name', '').lower() in query.lower():
                matched_option = option
                break
        
        if matched_option:
            # 处理匹配的选项
            option_type = matched_option.get('type')
            option_value = matched_option.get('name')
            
            filtered_results = conv_state.search_results
            # 关键修复：如果选项自带 ids，优先按 ids 精确过滤
            opt_ids = matched_option.get("ids")
            if isinstance(opt_ids, list) and opt_ids:
                try:
                    id_set = {int(x) for x in opt_ids}
                except Exception:
                    id_set = {x for x in opt_ids}
                filtered_results = [r for r in (filtered_results or []) if r.diagram.id in id_set]
            pre_filter_total = len(conv_state.search_results or [])
            if option_type == "brand":
                conv_state.add_filter("brand", option_value or "")
                filtered_results = search_service.filter_by_hierarchy(
                    filtered_results, brand=option_value
                )
            elif option_type == "model":
                conv_state.add_filter("model", option_value or "")
                filtered_results = search_service.filter_by_hierarchy(
                    filtered_results, model=option_value
                )
            elif option_type == "type":
                conv_state.add_filter("type", option_value or "")
                filtered_results = search_service.filter_by_hierarchy(
                    filtered_results, diagram_type=option_value
                )
            elif option_type == "variant":
                conv_state.add_filter("variant", option_value or "")
                # 车型变体：按文件名前缀精确分组（例如 “东风天龙KL_6x4环卫车”）
                base = (option_value or "").strip()
                for suf in (" 系列", "系列"):
                    if base.endswith(suf):
                        base = base[: -len(suf)].strip()
                        break
                next_filtered = []
                for r in filtered_results:
                    k = variant_key_for_query(r.diagram.file_name or "", conv_state.current_query or "")
                    if k and k == base:
                        next_filtered.append(r)
                filtered_results = next_filtered
            elif option_type == "brand_model":
                # 品牌+型号组合：解析选项值（如"东风 DOC"、"东风 VEC"等）
                brand, model = search_service._parse_brand_model(option_value)
                if brand and model:
                    conv_state.add_filter("brand", brand)
                    conv_state.add_filter("model", model)
                    # 先按品牌筛选
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, brand=brand
                    )
                    # 再按型号筛选（支持层级路径匹配）
                    if filtered_results:
                        filtered_diagrams = HierarchyUtil.filter_by_model(
                            [r.diagram for r in filtered_results], model
                        )
                        filtered_ids = {d.id for d in filtered_diagrams}
                        filtered_results = [r for r in filtered_results if r.diagram.id in filtered_ids]
                elif brand:
                    conv_state.add_filter("brand", brand)
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, brand=brand
                    )
            elif option_type == "result":
                conv_state.add_filter("result", option_value or query)
                target_id = matched_option.get("id")
                if target_id is not None:
                    filtered_results = [r for r in (filtered_results or []) if r.diagram.id == target_id]
            elif option_type == "document_category":
                # 文档主题分类：如果选项有 ids，直接按 ids 过滤；否则按类别名称匹配文件名
                conv_state.add_filter("document_category", option_value or "")
                opt_ids = matched_option.get("ids")
                # 如果 ids 过滤没有结果（或没有 ids），尝试按名称匹配
                if not filtered_results or not opt_ids:
                    from backend.app.services.search_service import SearchService
                    category_name = SearchService._norm_text(option_value or "")
                    if category_name:
                        next_filtered = []
                        for r in (conv_state.search_results or []):
                            d = r.diagram
                            file_name_norm = SearchService._norm_text(d.file_name or "")
                            # 检查文件名是否包含类别名称的关键部分
                            if category_name in file_name_norm:
                                next_filtered.append(r)
                        filtered_results = next_filtered
            elif option_type == "filename_prefix":
                # 文件名前缀合并：如果选项有 ids，直接按 ids 过滤；否则按前缀名称匹配文件名
                conv_state.add_filter("filename_prefix", option_value or "")
                opt_ids = matched_option.get("ids")
                # 如果 ids 过滤没有结果（或没有 ids），尝试按前缀名称匹配
                if not filtered_results or not opt_ids:
                    from backend.app.services.search_service import SearchService
                    prefix_name = option_value or ""
                    # 去除"系列"后缀
                    prefix_name = re.sub(r'系列$', '', prefix_name).strip()
                    prefix_norm = SearchService._norm_text(prefix_name)
                    if prefix_norm:
                        next_filtered = []
                        for r in (conv_state.search_results or []):
                            d = r.diagram
                            file_name_norm = SearchService._norm_text(d.file_name or "")
                            # 检查文件名是否以该前缀开头
                            if file_name_norm.startswith(prefix_norm):
                                next_filtered.append(r)
                        filtered_results = next_filtered
            
            conv_state.search_results = filtered_results
            conv_state.current_options = []
            conv_state.option_type = None
            # 支持配置/轴型筛选（如 6x4 牵引车）
            if option_type == "config":
                conv_state.add_filter("config", option_value or "")
                from backend.app.services.search_service import SearchService
                target = SearchService._norm_text(option_value)
                if target:
                    next_filtered = []
                    for r in filtered_results:
                        d = r.diagram
                        blob = SearchService._diagram_blob(d)
                        if target in blob:
                            next_filtered.append(r)
                    filtered_results = next_filtered
                    conv_state.search_results = filtered_results
            
            # 检查筛选后的结果数量
            if not filtered_results:
                conv_state.update_state(ConversationStateEnum.COMPLETED)
                conv_state.add_message("assistant", f"抱歉，没有找到与「{option_value}」相关的电路图。请尝试其他选项或重新搜索。")
                return ChatResponse(
                    message=f"抱歉，没有找到与「{option_value}」相关的电路图。请尝试其他选项或重新搜索。",
                    session_id=session_id
                )
            
            # 统一的筛选摘要：无论继续提问还是直接出结果，都先写清“条数变化 + 当前筛选条件”
            selection_summary = _build_selection_summary(
                option_value=option_value or query,
                pre_total=pre_filter_total,
                post_total=len(filtered_results),
                filter_history=conv_state.filter_history,
            )
            
            # 如果筛选后结果≤5个，直接返回结果
            max_results = request.max_results or 5
            if len(filtered_results) <= max_results:
                formatted_results = []
                for result in filtered_results:
                    formatted_results.append({
                        "id": result.diagram.id,
                        "file_name": result.diagram.file_name,
                        "hierarchy_path": " -> ".join(result.diagram.hierarchy_path),
                        "score": round(result.score, 2),
                        "brand": result.diagram.brand,
                        "model": result.diagram.model,
                        "diagram_type": result.diagram.diagram_type
                    })
                
                # 若用户查询包含“电路图”，且筛选后只剩单一图纸类型，则加一段确认话术（更贴近业务期望）
                preface = ""
                try:
                    q0 = (conv_state.current_query or "")
                    unique_types = {r.diagram.diagram_type for r in filtered_results if getattr(r.diagram, "diagram_type", None)}
                    if ("电路图" in q0) and len(unique_types) == 1:
                        only_type = next(iter(unique_types))
                        # 注意：这里的 pre_filter_total 在“文本命中选项”分支也应取筛选前的总数
                        preface = f"补充说明：查看包含电路图的数据，发现{pre_filter_total}条数据中图纸类型只有“{only_type}”，我直接把结果列出来：\n\n"
                except Exception:
                    preface = ""

                message = _prepend_selection_summary(preface + f"已为您找到以下电路图：\n\n", selection_summary)
                for i, result in enumerate(formatted_results, 1):
                    message += f"{i}. [ID: {result['id']}] {result['file_name']}\n"
                    message += f"   路径: {result['hierarchy_path']}\n"
                    if result['brand'] or result['model']:
                        attrs = []
                        if result['brand']:
                            attrs.append(f"品牌: {result['brand']}")
                        if result['model']:
                            attrs.append(f"型号: {result['model']}")
                        if result['diagram_type']:
                            attrs.append(f"类型: {result['diagram_type']}")
                        if attrs:
                            message += f"   {', '.join(attrs)}\n"
                    message += "\n"
                
                conv_state.update_state(ConversationStateEnum.COMPLETED)
                conv_state.add_message("assistant", message)
                
                return ChatResponse(
                    message=message,
                    results=formatted_results,
                    needs_choice=False,
                    session_id=session_id
                )
            
            # 如果筛选后结果仍然>5个，继续生成选择题
            scored_results = filtered_results
            skip_search = True
            force_choose = True
            query = (conv_state.current_query or "").strip() or (option_value or "").strip() or query

            if len(filtered_results) > pre_filter_total:
                print(f"[WARN] selection increased results(text-match): {pre_filter_total} -> {len(filtered_results)}; option={option_type}:{option_value}")
    
    # 执行意图理解（确认态“需要”会跳过）
    if "skip_search" not in locals():
        skip_search = False
    if "intent_result" not in locals():
        intent_result = None
    if not skip_search:
        try:
            intent_result = llm_service.parse_intent(query)
            conv_state.intent_result = intent_result
        except Exception as e:
            print(f"⚠️ 意图理解失败: {str(e)}，使用关键词搜索")
            # 意图理解失败时，继续使用关键词搜索

    # 关键修复：
    # LLM 可能会“推断”品牌/类型（例如 JH6 -> 解放），但若用户原文未出现该品牌/类型，
    # 就不应把它当作硬条件参与检索/过滤，也不应在回复里强行展示该词。
    def _is_explicit_brand(brand: str, raw_q: str) -> bool:
        if not brand or not raw_q:
            return False
        if brand in raw_q:
            return True
        # 若用户只写了简称，也视为显式（例如 “重汽” 命中 “中国重汽/重汽豪瀚”）
        raw = raw_q
        hints = ["东风", "解放", "重汽", "中国重汽", "一汽", "上汽", "大通", "欧曼", "乘龙", "红岩", "杰狮", "豪瀚", "豪汉", "豪沃", "福田"]
        for h in hints:
            if h in brand and h in raw:
                return True
        return False

    def _is_explicit_type(diagram_type: str, raw_q: str) -> bool:
        if not diagram_type or not raw_q:
            return False
        # 只要用户原文提到了该类型或其常见上位词，就算显式
        type_hints = ["ECU", "仪表", "整车", "针脚", "针角", "接线", "线路", "电路图", "线路图", "接线图", "针脚图", "针角图", "整车电路图", "仪表图", "ECU图"]
        return any(t in raw_q for t in type_hints)

    if intent_result:
        raw_q = (query or "")
        if intent_result.brand and not _is_explicit_brand(intent_result.brand, raw_q):
            intent_result.brand = None
        if intent_result.diagram_type and not _is_explicit_type(intent_result.diagram_type, raw_q):
            intent_result.diagram_type = None
    
    # 更新对话状态
    conv_state.update_state(ConversationStateEnum.SEARCHING)
    conv_state.current_query = query
    
    # 记录用户已指定的品牌/类型，用于后续过滤和避免重复提问
    brand_already_specified = (intent_result.has_brand() and _is_explicit_brand(intent_result.brand, conv_state.current_query or "")) if intent_result else False
    type_already_specified = (intent_result.has_diagram_type() and _is_explicit_type(intent_result.diagram_type, conv_state.current_query or "")) if intent_result else False
    brand_tokens = []
    if brand_already_specified and intent_result.brand:
        brand_tokens.append(intent_result.brand)
        base_brand_hints = ["东风", "解放", "重汽", "欧曼", "乘龙", "杰狮", "豪瀚", "豪汉", "大通"]
        for hint in base_brand_hints:
            if hint in intent_result.brand:
                brand_tokens.append(hint)

    # 执行搜索（确认态“需要”会跳过这里，因为 scored_results 已经存在且 skip_search=True）
    logic = request.logic or "AND"
    max_results = request.max_results or 5
    # 选项数量不要硬绑定 max_results：用户要求“东风天龙”这类大结果集要展示更多分类供选择
    max_options = max(5, min(15, max_results * 3))
    if "force_choose" not in locals():
        force_choose = False
    
    if (not skip_search) and ("scored_results" not in locals()):
        # 使用意图理解结果进行搜索
        if intent_result:
            scored_results = search_service.search_with_intent(
                intent_result=intent_result,
                logic=logic,
                max_results=1000,  # 获取足够多的结果用于分析
                use_fuzzy=True
            )
        else:
            # 降级为关键词搜索
            scored_results = search_service.search(
                query=query,
                logic=logic,
                max_results=1000,
                use_fuzzy=True
            )

    # 确认态“需要”会跳过搜索：这里确保 scored_results 一定存在，避免后续逻辑跑偏
    if skip_search and ("scored_results" not in locals()):
        scored_results = conv_state.search_results or []
    
    # 严格 AND（用户要求A）：必须在“文件名”中同时命中所有关键词组
    strict_filename_failed = False
    strict_removed_terms: List[str] = []
    if logic.upper() == "AND" and scored_results and not skip_search:
        strict_stats = search_service.strict_filename_and_stats(query=query, intent_result=intent_result)
        if (strict_stats.get("and_count") or 0) <= 0:
            strict_filename_failed = True
            term_counts = strict_stats.get("term_counts") or {}
            strict_removed_terms = [t for t, c in term_counts.items() if int(c) <= 0]

    # 如果 AND 无结果（或严格文件名AND失败）：按业务规则做“逐步放宽关键词”的兜底；仅在核心关键词很少时再允许 AND->OR
    if (not scored_results or strict_filename_failed) and logic.upper() == "AND" and not skip_search:
        extracted_keywords = search_service._extract_keywords(query)
        core_kw_count = len([k for k in extracted_keywords if k and len(k.strip()) > 0])

        # 核心词 > 1：不直接 OR，先尝试“剔除 0 命中/不可组合关键词”的 AND 放宽策略
        if core_kw_count > 1:
            relaxed, meta = search_service.search_and_relax(
                query=query,
                max_results=1000,
                use_fuzzy=True,
                intent_result=intent_result,
                force_remove_terms=strict_removed_terms if strict_filename_failed else None,
            )
            relaxed = search_service.deduplicate_results(relaxed)

            if relaxed:
                used = meta.get("used_keywords") or []
                removed = meta.get("removed_keywords") or []
                # 优先展示“严格文件名AND未命中”的关键词（更符合用户心智）
                if strict_filename_failed and strict_removed_terms:
                    removed = strict_removed_terms
                # 只有“确实放宽过”才进入确认态
                if removed:
                    removed_txt = "、".join([str(x) for x in removed if str(x).strip()])
                    # phrase：按用户要求A展示为 “东风天龙”“针脚” 这种格式，并尽量去掉过于泛的词
                    generic = {"电路图", "线路图", "接线图"}
                    phrase_terms = [str(x) for x in used if str(x).strip() and str(x) not in generic]
                    # 如果只剩下泛词（如“线路图”），也要展示出来；否则会变成“相关”，用户会觉得很怪
                    shown_terms = phrase_terms if phrase_terms else [str(x) for x in used if str(x).strip()]
                    phrase = "".join([f"“{t}”" for t in shown_terms]) if shown_terms else "“相关”"
                    msg = (
                        "抱歉，没有找到**同时匹配**您关键词的结果（AND）。\n\n"
                        "建议：\n"
                        "- 检查关键词是否过于具体（如针脚图/版本号）\n"
                        "- 尝试补充或替换关键词（例如：仪表图/仪表电路图）\n"
                        "- 或者减少一个限定词再试\n\n"
                        f"同时已为您扩大范围（去掉不匹配关键字{removed_txt}），"
                        f"已为您找到“{phrase}”相关数据，是否需要？\n"
                        "回复需要就可以进行选择逻辑"
                    )
                    conv_state.search_results = relaxed
                    conv_state.relax_meta = meta
                    conv_state.update_state(ConversationStateEnum.NEEDS_CONFIRM)
                    conv_state.add_message("assistant", msg)
                    return ChatResponse(message=msg, needs_choice=False, session_id=session_id)

                scored_results = relaxed
            else:
                conv_state.update_state(ConversationStateEnum.COMPLETED)
                error_message = (
                    "抱歉，没有找到**同时匹配**您关键词的结果（AND）。\n\n"
                    "建议：\n"
                    "- 检查关键词是否过于具体（如针脚图/版本号）\n"
                    "- 尝试补充或替换关键词（例如：仪表图/仪表电路图）\n"
                    "- 或者减少一个限定词再试"
                )
                conv_state.add_message("assistant", error_message)
                return ChatResponse(message=error_message, session_id=session_id)

        # 核心词很少（<=1）：允许 AND->OR 兜底
        if not scored_results:
            if intent_result:
                scored_results = search_service.search_with_intent(
                    intent_result=intent_result,
                    logic="OR",
                    max_results=1000,
                    use_fuzzy=True
                )
            else:
                scored_results = search_service.search(
                    query=query,
                    logic="OR",
                    max_results=1000,
                    use_fuzzy=True
                )
    
    # 去重
    scored_results = search_service.deduplicate_results(scored_results)

    # 如果用户已经明确品牌/类型，优先过滤，但过滤为空时不要直接报错（避免“其实搜到了但被字段过滤清空”）
    if intent_result and (brand_already_specified or type_already_specified):
        filtered_results = search_service.filter_by_hierarchy(
            scored_results,
            brand=intent_result.brand if brand_already_specified else None,
            diagram_type=intent_result.diagram_type if type_already_specified else None
        )
        if filtered_results:
            scored_results = filtered_results
        else:
            # 退一步：品牌/类型分别尝试，能保留多少保留多少
            alt = []
            if brand_already_specified and intent_result.brand:
                alt = search_service.filter_by_hierarchy(scored_results, brand=intent_result.brand)
            if not alt and type_already_specified and intent_result.diagram_type:
                alt = search_service.filter_by_hierarchy(scored_results, diagram_type=intent_result.diagram_type)
            if alt:
                scored_results = alt
    
    # 更新对话状态中的搜索结果
    conv_state.search_results = scored_results
    
    if not scored_results:
        conv_state.update_state(ConversationStateEnum.COMPLETED)
        error_message = (
            "抱歉，没有找到**同时匹配**您关键词的结果（AND）。\n\n"
            "建议：\n"
            "- 检查关键词是否过于具体（如针脚图/版本号）\n"
            "- 尝试补充或替换关键词（例如：仪表图/仪表电路图）\n"
            "- 或者减少一个限定词再试"
        )
        conv_state.add_message("assistant", error_message)
        return ChatResponse(message=error_message, session_id=session_id)
    
    total_found = len(scored_results)
    
    print(f"🔍 搜索结果: {total_found} 个，max_results: {max_results}")
    
    # 对“针脚/针角”这类查询，即使结果较少，也强制走选择题（避免直接吐 5 条）
    if (not force_choose) and re.search(r"(针脚|针角)", conv_state.current_query or "") and total_found >= 2:
        force_choose = True

    # 如果结果超过5个，或强制选择，尝试生成选择题引导用户缩小范围
    # 重要：当结果>5个时，必须生成选择题，不能直接返回结果
    if force_choose or total_found > max_results:
        print(f"✅ 结果数({total_found}) > max_results({max_results})，进入选择题生成逻辑")
        
        # 如果意图理解识别到了品牌和类型，将它们添加到筛选历史（用于指导选择题生成）
        # 注意：这里不实际筛选结果，只是记录用户意图，以便生成合适的选择题
        temp_filter_history = list(conv_state.filter_history)  # 复制一份，避免修改原始历史
        if intent_result:
            # 如果识别到了品牌，添加到临时筛选历史
            if intent_result.has_brand() and not any(f.get('type') == 'brand' for f in temp_filter_history):
                temp_filter_history.append({
                    "type": "brand",
                    "value": intent_result.brand
                })
            # 如果识别到了类型，添加到临时筛选历史
            if intent_result.has_diagram_type() and not any(f.get('type') == 'type' for f in temp_filter_history):
                temp_filter_history.append({
                    "type": "type",
                    "value": intent_result.diagram_type
                })
        
        # 获取已筛选的类型（避免重复提问）
        excluded_types = [f.get('type') for f in temp_filter_history]
        
        # 构建上下文信息（使用临时筛选历史）
        context = {
            "filter_history": temp_filter_history,
            "current_query": conv_state.current_query,
            "total_results": total_found,
            "intent_result": {
                "brand": intent_result.brand if intent_result else None,
                "model": intent_result.model if intent_result else None,
                "diagram_type": intent_result.diagram_type if intent_result else None
            } if intent_result else None
        }
        
        # 若结果数不大：直接让用户“按文件名精确选择”（比按品牌/型号分组更精确）
        question_data = None
        choose_file_threshold = max(max_results, 15)
        if force_choose and total_found <= choose_file_threshold:
            # 选项标签按需扩展，避免 max_results > 5 时越界
            option_labels = question_service._make_option_labels(min(choose_file_threshold, len(scored_results)))
            formatted_options = []
            for i, r in enumerate(scored_results[:choose_file_threshold]):
                formatted_options.append({
                    "label": option_labels[i],
                    "name": r.diagram.file_name,
                    "count": 1,
                    "type": "result",
                    "id": r.diagram.id,
                })
            question_data = {
                "question": "明白了。请问您需要的是哪一份资料：",
                "options": formatted_options,
                "option_type": "result",
            }
        else:
            # 生成选择题（使用LLM生成自然的问题文本）
            question_data = question_service.generate_question(
                scored_results,
                min_options=2,
                max_options=max_options,
                excluded_types=excluded_types if excluded_types else None,
                context=context,
                use_llm=True
            )
        
        print(f"🔍 question_data: {question_data is not None}")
        
        if question_data:
            print(f"✅ 成功生成选择题，选项数: {len(question_data.get('options', []))}")
            # 更新对话状态
            conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
            conv_state.current_options = question_data['options']
            conv_state.option_type = question_data['option_type']
            
            # 格式化消息
            message = question_service.format_question_message(question_data)
            message = _prepend_selection_summary(message, locals().get("selection_summary"))
            
            conv_state.add_message("assistant", message)
            
            return ChatResponse(
                message=message,
                results=None,
                options=question_data['options'],
                needs_choice=True,
                session_id=session_id
            )
        else:
            # 无法生成选择题，尝试从层级路径中提取更细粒度的选项
            # 尝试提取层级路径中的不同层级作为选项
            print(f"⚠️ generate_question返回None，尝试fallback逻辑，结果数: {total_found}")
            
            # 尝试提取不同层级的选项
            all_levels = HierarchyUtil.get_all_levels([r.diagram for r in scored_results])
            
            # 尝试找到有多个选项的层级
            best_option_type = None
            best_options = []
            
            # 按优先级检查：品牌+型号组合 -> 品牌 -> 型号 -> 类型 -> 类别
            # 优先尝试从层级路径中提取品牌+型号组合
            try:
                brand_model_options = question_service._extract_options_from_hierarchy(
                    scored_results, max_options
                )
                print(f"⚠️ 从层级路径提取品牌+型号组合: {len(brand_model_options) if brand_model_options else 0} 个选项")
                if brand_model_options and len(brand_model_options) >= 2:
                    best_option_type = "brand_model"
                    best_options = brand_model_options
            except Exception as e:
                print(f"⚠️ 提取品牌+型号组合失败: {str(e)}")
            
            # 如果品牌+型号组合失败，尝试其他类型
            if not best_options:
                print(f"⚠️ 尝试其他类型选项，已排除类型: {excluded_types}")
                for opt_type, level_set in [("brand", all_levels.get("brands", set())),
                                            ("model", all_levels.get("models", set())),
                                            ("type", all_levels.get("types", set())),
                                            ("category", all_levels.get("categories", set()))]:
                    if opt_type not in (excluded_types or []):
                        print(f"⚠️ 检查类型 {opt_type}，选项数: {len(level_set)}")
                        if len(level_set) >= 2:
                            # 转换为选项格式（携带精确 ids，后续筛选才能严格收敛）
                            options = []
                            for name in list(level_set)[:max_options]:
                                ids = [
                                    r.diagram.id
                                    for r in scored_results
                                    if (
                                        (opt_type == "brand" and r.diagram.brand == name)
                                        or (opt_type == "model" and r.diagram.model == name)
                                        or (opt_type == "type" and r.diagram.diagram_type == name)
                                        or (opt_type == "category" and r.diagram.vehicle_category == name)
                                    )
                                ]
                                options.append({"name": name, "count": len(ids), "ids": ids})
                            # drop no-op buckets (ids == all_ids)
                            options = _filter_out_noop_options(options, {r.diagram.id for r in scored_results})
                            options.sort(key=lambda x: x["count"], reverse=True)
                            print(f"⚠️ 类型 {opt_type} 生成选项数: {len(options)}")
                            if len(options) >= 2:
                                best_option_type = opt_type
                                best_options = options[:max_options]
                                break
            
            if best_option_type and best_options:
                # 过滤掉“全量不收敛”的选项，避免用户选了也不缩小范围
                best_options = _filter_out_noop_options(best_options, {r.diagram.id for r in scored_results})
                if len(best_options) < 2:
                    best_option_type = None
                    best_options = []
                else:
                    # 生成问题（使用LLM或默认模板）
                    try:
                        # 使用已经在文件顶部导入的 llm_service
                        question_text = llm_service.generate_question_text(
                            option_type=best_option_type,
                            options=best_options,
                            total_count=total_found,
                            context=context
                        )
                    except Exception as e:
                        print(f"⚠️ LLM生成问题失败: {str(e)}，使用默认模板")
                        question_text = question_service._generate_question_text(
                            best_option_type, total_found, context
                        )
                    
                    sliced_options = best_options[:max_options]
                    option_labels = question_service._make_option_labels(len(sliced_options))
                    formatted_options = []
                    for i, option in enumerate(sliced_options):
                        opt_ids = option.get("ids") if isinstance(option, dict) else None
                        if isinstance(opt_ids, list) and opt_ids:
                            cnt = len(opt_ids)
                        else:
                            cnt = option.get("count", 0)
                        formatted_options.append({
                            "label": option_labels[i],
                            "name": option['name'],
                            "count": cnt,
                            "type": best_option_type,
                            "ids": opt_ids if isinstance(opt_ids, list) else None,
                        })
                    
                    question_data = {
                        "question": question_text,
                        "options": formatted_options,
                        "option_type": best_option_type
                    }
                    
                    # 更新对话状态
                    conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
                    conv_state.current_options = formatted_options
                    conv_state.option_type = best_option_type
                    
                    # 格式化消息
                    message = question_service.format_question_message(question_data)
                    message = _prepend_selection_summary(message, locals().get("selection_summary"))
                    
                    conv_state.add_message("assistant", message)
                    
                    return ChatResponse(
                        message=message,
                        results=None,
                        options=formatted_options,
                        needs_choice=True,
                        session_id=session_id
                    )
            
            # 如果仍然无法生成选择题，强制尝试从层级路径中提取选项
            # 这是最后的fallback，必须生成选择题
            if not best_options:
                print(f"⚠️ 尝试最后的fallback：从层级路径中提取任意有区分度的选项")
                try:
                    # 尝试从层级路径中提取任意有区分度的选项
                    hierarchy_options: Dict[str, set] = {}
                    for result in scored_results:
                        diagram = result.diagram
                        if diagram.hierarchy_path and len(diagram.hierarchy_path) > 2:
                            # 尝试提取品牌后面的层级
                            brand_pos = -1
                            if diagram.brand:
                                for i, level in enumerate(diagram.hierarchy_path):
                                    if diagram.brand in level or level == diagram.brand:
                                        brand_pos = i
                                        break
                            
                            if brand_pos != -1 and brand_pos + 1 < len(diagram.hierarchy_path):
                                level_value = diagram.hierarchy_path[brand_pos + 1]
                                level_value_clean = level_value.replace('*', '').strip()
                                if level_value_clean and level_value_clean != diagram.brand:
                                    option_name = f"{diagram.brand} {level_value_clean}"
                                    hierarchy_options.setdefault(option_name, set()).add(diagram.id)
                            else:
                                # 如果没有找到品牌，尝试提取层级路径中的其他层级
                                for i, level in enumerate(diagram.hierarchy_path):
                                    if i > 0 and level and level != "电路图" and len(level) > 1:
                                        # 跳过第一个层级（通常是"电路图"）
                                        hierarchy_options.setdefault(level, set()).add(diagram.id)
                                        break
                    
                    print(f"⚠️ 从层级路径提取到 {len(hierarchy_options)} 个选项")
                    
                    if len(hierarchy_options) >= 2:
                        # 转换为选项格式
                        options = [
                            {"name": name, "count": len(ids), "ids": sorted(ids)}
                            for name, ids in sorted(hierarchy_options.items(), key=lambda x: len(x[1]), reverse=True)[:max_options]
                        ]
                        options = _filter_out_noop_options(options, {r.diagram.id for r in scored_results})
                        
                        question_text = question_service._generate_question_text(
                            "brand_model", total_found, context
                        )
                        
                        option_labels = question_service._make_option_labels(len(options))
                        formatted_options = []
                        for i, option in enumerate(options):
                            formatted_options.append({
                                "label": option_labels[i],
                                "name": option['name'],
                                "count": option['count'],
                                "type": "brand_model",
                                "ids": option.get("ids"),
                            })
                        
                        question_data = {
                            "question": question_text,
                            "options": formatted_options,
                            "option_type": "brand_model"
                        }
                        
                        # 更新对话状态
                        conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
                        conv_state.current_options = formatted_options
                        conv_state.option_type = "brand_model"
                        
                        # 格式化消息
                        message = question_service.format_question_message(question_data)
                        message = _prepend_selection_summary(message, locals().get("selection_summary"))
                        
                        conv_state.add_message("assistant", message)
                        
                        return ChatResponse(
                            message=message,
                            results=None,
                            options=formatted_options,
                            needs_choice=True,
                            session_id=session_id
                        )
                except Exception as e:
                    print(f"⚠️ Fallback选项生成失败: {str(e)}")
            
            # 如果所有方法都失败，强制生成选择题（即使选项不够理想）
            if not best_options:
                print(f"⚠️ 所有方法都失败，强制生成选择题")
                # 强制从层级路径中提取选项，即使只有部分区分度
                try:
                    hierarchy_options: Dict[str, set] = {}
                    for result in scored_results:
                        diagram = result.diagram
                        if diagram.hierarchy_path:
                            # 尝试提取层级路径中的不同层级作为选项
                            for i, level in enumerate(diagram.hierarchy_path):
                                if i > 0 and level and level != "电路图" and len(level.strip()) > 1:
                                    # 跳过第一个层级（通常是"电路图"）
                                    level_clean = level.replace('*', '').strip()
                                    if not level_clean:
                                        continue
                                    # 已知类型时跳过类型相关层级，避免再次询问类型
                                    type_keywords = ['电路图', '仪表', 'ECU', '整车', '线路', '针脚', '模块', '接线']
                                    if type_already_specified and any(k in level_clean for k in type_keywords):
                                        continue
                                    # 已知品牌时跳过品牌层级，避免把品牌当选项
                                    if brand_tokens and any(bt and (bt in level_clean or level_clean in bt) for bt in brand_tokens):
                                        continue
                                    if level_clean:
                                        hierarchy_options.setdefault(level_clean, set()).add(diagram.id)
                    
                    # 如果提取到选项，使用它们
                    if len(hierarchy_options) >= 2 and not type_already_specified:
                        options = [
                            {"name": name, "count": len(ids), "ids": sorted(ids)}
                            for name, ids in sorted(hierarchy_options.items(), key=lambda x: len(x[1]), reverse=True)[:max_options]
                        ]
                        options = _filter_out_noop_options(options, {r.diagram.id for r in scored_results})
                        if len(options) < 2:
                            options = []
                        
                        question_text = question_service._generate_question_text(
                            "type", total_found, context
                        )
                        
                        option_labels = question_service._make_option_labels(len(options))
                        formatted_options = []
                        for i, option in enumerate(options):
                            formatted_options.append({
                                "label": option_labels[i],
                                "name": option['name'],
                                "count": option['count'],
                                "type": "type",
                                "ids": option.get("ids"),
                            })
                        
                        question_data = {
                            "question": question_text,
                            "options": formatted_options,
                            "option_type": "type"
                        }
                        
                        conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
                        conv_state.current_options = formatted_options
                        conv_state.option_type = "type"
                        
                        message = question_service.format_question_message(question_data)
                        message = _prepend_selection_summary(message, locals().get("selection_summary"))
                        conv_state.add_message("assistant", message)
                        
                        return ChatResponse(
                            message=message,
                            results=None,
                            options=formatted_options,
                            needs_choice=True,
                            session_id=session_id
                        )
                    elif len(hierarchy_options) >= 2:
                        # 如果类型已知，则将层级选项视为系列/型号选项继续追问
                        options = [
                            {"name": name, "count": len(ids), "ids": sorted(ids)}
                            for name, ids in sorted(hierarchy_options.items(), key=lambda x: len(x[1]), reverse=True)[:max_options]
                        ]
                        options = _filter_out_noop_options(options, {r.diagram.id for r in scored_results})
                        if len(options) < 2:
                            options = []

                        question_text = question_service._generate_question_text(
                            "brand_model", total_found, context
                        )

                        option_labels = question_service._make_option_labels(len(options))
                        formatted_options = []
                        for i, option in enumerate(options):
                            formatted_options.append({
                                "label": option_labels[i],
                                "name": option['name'],
                                "count": option['count'],
                                "type": "brand_model",
                                "ids": option.get("ids"),
                            })

                        question_data = {
                            "question": question_text,
                            "options": formatted_options,
                            "option_type": "brand_model"
                        }

                        conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
                        conv_state.current_options = formatted_options
                        conv_state.option_type = "brand_model"

                        message = question_service.format_question_message(question_data)
                        message = _prepend_selection_summary(message, locals().get("selection_summary"))
                        conv_state.add_message("assistant", message)

                        return ChatResponse(
                            message=message,
                            results=None,
                            options=formatted_options,
                            needs_choice=True,
                            session_id=session_id
                        )
                    else:
                        # 如果连层级路径都提取不到足够的选项，至少基于文件名生成选项
                        print(f"⚠️ 层级路径提取失败，尝试基于文件名生成选项")
                        file_name_options: Dict[str, set] = {}
                        for result in scored_results[:max_results * 2]:  # 检查更多结果以找到区分度
                            diagram = result.diagram
                            # 从文件名中提取关键词（去除品牌和常见词）
                            file_name = diagram.file_name
                            # 尝试提取文件名中的关键部分
                            if diagram.brand and diagram.brand in file_name:
                                # 提取品牌后面的部分
                                parts = file_name.split(diagram.brand, 1)
                                if len(parts) > 1:
                                    key_part = parts[1].split('.')[0].strip('_-. ')[:20]  # 取前20个字符
                                    if key_part and len(key_part) > 1:
                                        file_name_options.setdefault(key_part, set()).add(diagram.id)
                            
                            # 或者直接使用文件名的一部分
                            if not file_name_options:
                                # 提取文件名中的关键词（去除扩展名）
                                name_part = file_name.split('.')[0]
                                if len(name_part) > 5:
                                    # 取文件名的一部分作为选项
                                    key_part = name_part[:15]
                                    file_name_options.setdefault(key_part, set()).add(diagram.id)
                        
                        if len(file_name_options) >= 2:
                            options = [
                                {"name": name, "count": len(ids), "ids": sorted(ids)}
                                for name, ids in sorted(file_name_options.items(), key=lambda x: len(x[1]), reverse=True)[:max_options]
                            ]
                            options = _filter_out_noop_options(options, {r.diagram.id for r in scored_results})
                            if len(options) < 2:
                                options = []
                            
                            question_text = f"找到了 {total_found} 个相关结果。请选择您需要的类型："
                            
                            option_labels = question_service._make_option_labels(len(options))
                            formatted_options = []
                            for i, option in enumerate(options):
                                formatted_options.append({
                                    "label": option_labels[i],
                                    "name": option['name'],
                                    "count": option['count'],
                                    "type": "type",
                                    "ids": option.get("ids"),
                                })
                            
                            question_data = {
                                "question": question_text,
                                "options": formatted_options,
                                "option_type": "type"
                            }
                            
                            conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
                            conv_state.current_options = formatted_options
                            conv_state.option_type = "type"
                            
                            message = question_service.format_question_message(question_data)
                            message = _prepend_selection_summary(message, locals().get("selection_summary"))
                            conv_state.add_message("assistant", message)
                            
                            return ChatResponse(
                                message=message,
                                results=None,
                                options=formatted_options,
                                needs_choice=True,
                                session_id=session_id
                            )
                except Exception as e:
                    print(f"⚠️ 强制生成选择题失败: {str(e)}")
                
                # 如果所有强制生成方法都失败，至少生成一个基于结果数量的选择题
                print(f"⚠️ 所有强制生成方法都失败，生成基于结果的分组选择题")
                # 将结果分成几组，让用户选择
                group_size = max(2, total_found // max_results)
                groups = []
                for i in range(0, min(total_found, max_results * 2), group_size):
                    group_results = scored_results[i:i+group_size]
                    if group_results:
                        # 提取这组结果的关键特征
                        group_name = f"第{i+1}-{min(i+group_size, total_found)}个结果"
                        if group_results[0].diagram.brand:
                            group_name = f"{group_results[0].diagram.brand}相关"
                        groups.append({
                            "name": group_name,
                            "count": len(group_results),
                            "results": group_results
                        })
                
                if len(groups) >= 2:
                    question_text = f"找到了 {total_found} 个相关结果。请选择您需要的范围："
                    
                    sliced_groups = groups[:max_options]
                    option_labels = question_service._make_option_labels(len(sliced_groups))
                    formatted_options = []
                    for i, group in enumerate(sliced_groups):
                        group_ids = [r.diagram.id for r in (group.get("results") or []) if getattr(r, "diagram", None)]
                        formatted_options.append({
                            "label": option_labels[i],
                            "name": group['name'],
                            "count": group['count'],
                            "type": "group",
                            "ids": group_ids,
                        })
                    # Drop no-op groups (ids == all_ids) and re-label
                    all_ids = {r.diagram.id for r in scored_results}
                    formatted_options = _filter_out_noop_options(formatted_options, all_ids)
                    option_labels = question_service._make_option_labels(len(formatted_options))
                    for i, o in enumerate(formatted_options):
                        o["label"] = option_labels[i]
                        o["count"] = len(o.get("ids") or [])
                    
                    question_data = {
                        "question": question_text,
                        "options": formatted_options,
                        "option_type": "group"
                    }
                    
                    conv_state.update_state(ConversationStateEnum.NEEDS_CHOICE)
                    conv_state.current_options = formatted_options
                    conv_state.option_type = "group"
                    # 保存分组结果以便后续使用
                    conv_state.grouped_results = groups
                    
                    message = question_service.format_question_message(question_data)
                    message = _prepend_selection_summary(message, locals().get("selection_summary"))
                    conv_state.add_message("assistant", message)
                    
                    return ChatResponse(
                        message=message,
                        results=None,
                        options=formatted_options,
                        needs_choice=True,
                        session_id=session_id
                    )
                
                # 如果连分组都失败，返回错误提示（这种情况应该很少见）
                error_message = f"找到了 {total_found} 个相关结果，但无法生成选择题。请尝试使用更具体的关键词重新搜索。"
                conv_state.update_state(ConversationStateEnum.COMPLETED)
                conv_state.add_message("assistant", error_message)
                return ChatResponse(
                    message=error_message,
                    session_id=session_id
                )
    else:
        # 结果≤5个，直接返回所有结果
        print(f"✅ 结果数({total_found}) <= max_results({max_results})，直接返回结果")
        formatted_results = []
        for result in scored_results[:max_results]:
            formatted_results.append({
                "id": result.diagram.id,
                "file_name": result.diagram.file_name,
                "hierarchy_path": " -> ".join(result.diagram.hierarchy_path),
                "score": round(result.score, 2),
                "brand": result.diagram.brand,
                "model": result.diagram.model,
                "diagram_type": result.diagram.diagram_type
            })
        
        message = f"找到了 {total_found} 个相关结果：\n\n"
        for i, result in enumerate(formatted_results, 1):
            message += f"{i}. [ID: {result['id']}] {result['file_name']}\n"
            message += f"   路径: {result['hierarchy_path']}\n"
            if result['brand'] or result['model']:
                attrs = []
                if result['brand']:
                    attrs.append(f"品牌: {result['brand']}")
                if result['model']:
                    attrs.append(f"型号: {result['model']}")
                if result['diagram_type']:
                    attrs.append(f"类型: {result['diagram_type']}")
                if attrs:
                    message += f"   {', '.join(attrs)}\n"
            message += "\n"
        
        conv_state.update_state(ConversationStateEnum.COMPLETED)
        conv_state.add_message("assistant", message)
        
        return ChatResponse(
            message=message,
            results=formatted_results,
            needs_choice=False,
            session_id=session_id
        )
