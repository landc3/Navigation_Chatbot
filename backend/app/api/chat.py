"""
聊天API
集成意图理解和对话管理
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional
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
                
                # 更新对话状态
                conv_state.search_results = filtered_results
                conv_state.current_options = []
                conv_state.option_type = None
                
                # 继续处理筛选后的结果
                query = option_value  # 使用选项值作为新的查询
            else:
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
            
            conv_state.search_results = filtered_results
            conv_state.current_options = []
            conv_state.option_type = None
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
    
    # 执行搜索
    logic = request.logic or "AND"
    max_results = request.max_results or 5
    
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
    if not scored_results and logic.upper() == "AND":
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
    
    # 更新对话状态中的搜索结果
    conv_state.search_results = scored_results
    
    if not scored_results:
        conv_state.update_state(ConversationStateEnum.COMPLETED)
        conv_state.add_message("assistant", f"抱歉，没有找到与「{query}」相关的电路图。请尝试其他关键词。")
        return ChatResponse(
            message=f"抱歉，没有找到与「{query}」相关的电路图。请尝试其他关键词。",
            session_id=session_id
        )
    
    total_found = len(scored_results)
    
    # 如果结果超过5个，尝试生成选择题引导用户缩小范围
    if total_found > max_results:
        # 获取已筛选的类型（避免重复提问）
        excluded_types = [f.get('type') for f in conv_state.filter_history]
        
        # 生成选择题
        question_data = question_service.generate_question(
            scored_results,
            min_options=2,
            max_options=5,
            excluded_types=excluded_types if excluded_types else None
        )
        
        if question_data:
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
            # 无法生成选择题，返回所有结果（限制数量）
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
            
            message = f"找到了 {total_found} 个相关结果（显示前{max_results}个，按相关性排序）：\n\n"
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
    else:
        # 结果≤5个，直接返回所有结果
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
