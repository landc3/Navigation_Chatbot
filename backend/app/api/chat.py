"""
聊天API
集成意图理解和对话管理
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional
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
    
    # 添加用户消息到历史
    conv_state.add_message("user", query)
    
    # 检查是否是选择题答案（A/B/C/D/E 或单个字母）
    user_input_upper = query.upper().strip()
    is_option_selection = len(user_input_upper) == 1 and user_input_upper in ['A', 'B', 'C', 'D', 'E']
    
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
                # 添加筛选条件到历史
                conv_state.add_filter(
                    selected_option.get('type', 'unknown'),
                    selected_option.get('name', '')
                )
                
                # 基于选择筛选结果
                option_type = selected_option.get('type')
                option_value = selected_option.get('name')
                
                pre_filter_total = len(conv_state.search_results or [])
                filtered_results = conv_state.search_results
                if option_type == "brand":
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, brand=option_value
                    )
                elif option_type == "model":
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, model=option_value
                    )
                elif option_type == "type":
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, diagram_type=option_value
                    )
                elif option_type == "variant":
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
                        filtered_results = search_service.filter_by_hierarchy(
                            filtered_results, brand=brand
                        )
                
                # 更新对话状态
                conv_state.search_results = filtered_results
                conv_state.current_options = []
                conv_state.option_type = None
                # 支持配置/轴型筛选（如 6x4 牵引车）
                if option_type == "config":
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
                            preface = f"明白了。查看包含电路图的数据，发现{pre_filter_total}条数据中图纸类型只有“{only_type}”，我直接把结果列出来：\n\n"
                    except Exception:
                        preface = ""

                    message = preface + f"已为您找到以下电路图：\n\n"
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
                # 继续到下面的逻辑处理
                query = option_value  # 使用选项值作为新的查询
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
            conv_state.add_filter(
                matched_option.get('type', 'unknown'),
                matched_option.get('name', '')
            )
            
            option_type = matched_option.get('type')
            option_value = matched_option.get('name')
            
            filtered_results = conv_state.search_results
            if option_type == "brand":
                filtered_results = search_service.filter_by_hierarchy(
                    filtered_results, brand=option_value
                )
            elif option_type == "model":
                filtered_results = search_service.filter_by_hierarchy(
                    filtered_results, model=option_value
                )
            elif option_type == "type":
                filtered_results = search_service.filter_by_hierarchy(
                    filtered_results, diagram_type=option_value
                )
            elif option_type == "variant":
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
                    filtered_results = search_service.filter_by_hierarchy(
                        filtered_results, brand=brand
                    )
            
            conv_state.search_results = filtered_results
            conv_state.current_options = []
            conv_state.option_type = None
            # 支持配置/轴型筛选（如 6x4 牵引车）
            if option_type == "config":
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
                        preface = f"明白了。查看包含电路图的数据，发现{len(conv_state.search_results or [])}条数据中图纸类型只有“{only_type}”，我直接把结果列出来：\n\n"
                except Exception:
                    preface = ""

                message = preface + f"已为您找到以下电路图：\n\n"
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
            query = option_value
    
    # 执行意图理解
    intent_result = None
    try:
        intent_result = llm_service.parse_intent(query)
        conv_state.intent_result = intent_result
    except Exception as e:
        print(f"⚠️ 意图理解失败: {str(e)}，使用关键词搜索")
        # 意图理解失败时，继续使用关键词搜索
    
    # 更新对话状态
    conv_state.update_state(ConversationStateEnum.SEARCHING)
    conv_state.current_query = query
    
    # 记录用户已指定的品牌/类型，用于后续过滤和避免重复提问
    brand_already_specified = intent_result.has_brand() if intent_result else False
    type_already_specified = intent_result.has_diagram_type() if intent_result else False
    brand_tokens = []
    if brand_already_specified and intent_result.brand:
        brand_tokens.append(intent_result.brand)
        base_brand_hints = ["东风", "解放", "重汽", "欧曼", "乘龙", "杰狮", "豪瀚", "豪汉", "大通"]
        for hint in base_brand_hints:
            if hint in intent_result.brand:
                brand_tokens.append(hint)

    # 执行搜索
    logic = request.logic or "AND"
    max_results = request.max_results or 5
    max_options = max_results  # 用于限制选择题选项数量
    
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
    
    # 如果AND逻辑无结果，尝试OR逻辑
    # 重要：当用户输入中包含多个核心关键词时，不应自动降级为OR（会导致“只命中部分关键词”的结果混入）
    # 仅当“核心关键词<=1”（例如只输入一个词）时，才允许AND->OR的兜底。
    if not scored_results and logic.upper() == "AND":
        extracted_keywords = search_service._extract_keywords(query)
        core_kw_count = len([k for k in extracted_keywords if k and len(k.strip()) > 0])
        allow_or_fallback = core_kw_count <= 1

        if not allow_or_fallback:
            conv_state.update_state(ConversationStateEnum.COMPLETED)
            error_message = f"抱歉，没有找到**同时匹配**您关键词的结果（AND）。\n\n建议：\n- 检查关键词是否过于具体（如针脚图/版本号）\n- 尝试补充或替换关键词（例如：仪表图/仪表电路图）\n- 或者减少一个限定词再试"
            conv_state.add_message("assistant", error_message)
            return ChatResponse(
                message=error_message,
                session_id=session_id
            )

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

    # 如果用户已经明确品牌/类型，先进行强过滤，避免出现无关选项
    if intent_result and (brand_already_specified or type_already_specified):
        filtered_results = search_service.filter_by_hierarchy(
            scored_results,
            brand=intent_result.brand if brand_already_specified else None,
            diagram_type=intent_result.diagram_type if type_already_specified else None
        )
        if filtered_results:
            scored_results = filtered_results
        else:
            conv_state.update_state(ConversationStateEnum.COMPLETED)
            error_message = f"抱歉，没有找到同时匹配「{intent_result.brand or ''}」和「{intent_result.diagram_type or ''}」的电路图。请确认关键词或提供更多信息。"
            conv_state.add_message("assistant", error_message)
            return ChatResponse(
                message=error_message,
                session_id=session_id
            )
    
    # 更新对话状态中的搜索结果
    conv_state.search_results = scored_results
    
    if not scored_results:
        conv_state.update_state(ConversationStateEnum.COMPLETED)
        error_message = f"抱歉，没有找到与「{query}」相关的电路图。\n\n建议：\n1. 尝试使用其他关键词\n2. 检查拼写是否正确\n3. 尝试使用更通用的关键词（如品牌名称）"
        conv_state.add_message("assistant", error_message)
        return ChatResponse(
            message=error_message,
            session_id=session_id
        )
    
    total_found = len(scored_results)
    
    print(f"🔍 搜索结果: {total_found} 个，max_results: {max_results}")
    
    # 如果结果超过5个，尝试生成选择题引导用户缩小范围
    # 重要：当结果>5个时，必须生成选择题，不能直接返回结果
    if total_found > max_results:
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
                            # 转换为选项格式
                            options = [{"name": name, "count": sum(1 for r in scored_results 
                                                                   if (opt_type == "brand" and r.diagram.brand == name) or
                                                                      (opt_type == "model" and r.diagram.model == name) or
                                                                      (opt_type == "type" and r.diagram.diagram_type == name) or
                                                                      (opt_type == "category" and r.diagram.vehicle_category == name))}
                                      for name in list(level_set)[:max_options]]
                            options.sort(key=lambda x: x["count"], reverse=True)
                            print(f"⚠️ 类型 {opt_type} 生成选项数: {len(options)}")
                            if len(options) >= 2:
                                best_option_type = opt_type
                                best_options = options[:max_options]
                                break
            
            if best_option_type and best_options:
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
                
                option_labels = ['A', 'B', 'C', 'D', 'E']
                formatted_options = []
                for i, option in enumerate(best_options[:max_options]):
                    formatted_options.append({
                        "label": option_labels[i],
                        "name": option['name'],
                        "count": option['count'],
                        "type": best_option_type
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
                    hierarchy_options = {}
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
                                    hierarchy_options[option_name] = hierarchy_options.get(option_name, 0) + 1
                            else:
                                # 如果没有找到品牌，尝试提取层级路径中的其他层级
                                for i, level in enumerate(diagram.hierarchy_path):
                                    if i > 0 and level and level != "电路图" and len(level) > 1:
                                        # 跳过第一个层级（通常是"电路图"）
                                        hierarchy_options[level] = hierarchy_options.get(level, 0) + 1
                                        break
                    
                    print(f"⚠️ 从层级路径提取到 {len(hierarchy_options)} 个选项")
                    
                    if len(hierarchy_options) >= 2:
                        # 转换为选项格式
                        options = [
                            {"name": name, "count": count}
                            for name, count in sorted(hierarchy_options.items(), key=lambda x: x[1], reverse=True)[:max_options]
                        ]
                        
                        question_text = question_service._generate_question_text(
                            "brand_model", total_found, context
                        )
                        
                        option_labels = ['A', 'B', 'C', 'D', 'E']
                        formatted_options = []
                        for i, option in enumerate(options):
                            formatted_options.append({
                                "label": option_labels[i],
                                "name": option['name'],
                                "count": option['count'],
                                "type": "brand_model"
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
                    hierarchy_options = {}
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
                                        hierarchy_options[level_clean] = hierarchy_options.get(level_clean, 0) + 1
                    
                    # 如果提取到选项，使用它们
                    if len(hierarchy_options) >= 2 and not type_already_specified:
                        options = [
                            {"name": name, "count": count}
                            for name, count in sorted(hierarchy_options.items(), key=lambda x: x[1], reverse=True)[:max_options]
                        ]
                        
                        question_text = question_service._generate_question_text(
                            "type", total_found, context
                        )
                        
                        option_labels = ['A', 'B', 'C', 'D', 'E']
                        formatted_options = []
                        for i, option in enumerate(options):
                            formatted_options.append({
                                "label": option_labels[i],
                                "name": option['name'],
                                "count": option['count'],
                                "type": "type"
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
                            {"name": name, "count": count}
                            for name, count in sorted(hierarchy_options.items(), key=lambda x: x[1], reverse=True)[:max_options]
                        ]

                        question_text = question_service._generate_question_text(
                            "brand_model", total_found, context
                        )

                        option_labels = ['A', 'B', 'C', 'D', 'E']
                        formatted_options = []
                        for i, option in enumerate(options):
                            formatted_options.append({
                                "label": option_labels[i],
                                "name": option['name'],
                                "count": option['count'],
                                "type": "brand_model"
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
                        file_name_options = {}
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
                                        file_name_options[key_part] = file_name_options.get(key_part, 0) + 1
                            
                            # 或者直接使用文件名的一部分
                            if not file_name_options:
                                # 提取文件名中的关键词（去除扩展名）
                                name_part = file_name.split('.')[0]
                                if len(name_part) > 5:
                                    # 取文件名的一部分作为选项
                                    key_part = name_part[:15]
                                    file_name_options[key_part] = file_name_options.get(key_part, 0) + 1
                        
                        if len(file_name_options) >= 2:
                            options = [
                                {"name": name, "count": count}
                                for name, count in sorted(file_name_options.items(), key=lambda x: x[1], reverse=True)[:max_options]
                            ]
                            
                            question_text = f"找到了 {total_found} 个相关结果。请选择您需要的类型："
                            
                            option_labels = ['A', 'B', 'C', 'D', 'E']
                            formatted_options = []
                            for i, option in enumerate(options):
                                formatted_options.append({
                                    "label": option_labels[i],
                                    "name": option['name'],
                                    "count": option['count'],
                                    "type": "type"
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
                    
                    option_labels = ['A', 'B', 'C', 'D', 'E']
                    formatted_options = []
                    for i, group in enumerate(groups[:max_options]):
                        formatted_options.append({
                            "label": option_labels[i],
                            "name": group['name'],
                            "count": group['count'],
                            "type": "group"
                        })
                    
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
