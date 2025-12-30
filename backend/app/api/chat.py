"""
聊天API
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.search_service import get_search_service

router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    history: Optional[List[ChatMessage]] = []
    logic: Optional[str] = "AND"  # AND or OR
    max_results: Optional[int] = 5


class ChatResponse(BaseModel):
    """聊天响应"""
    message: str
    results: Optional[List[dict]] = None  # 搜索结果（如果有）
    options: Optional[List[dict]] = None  # 选择题选项（如果有）
    needs_choice: Optional[bool] = False  # 是否需要用户选择


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    
    使用增强的搜索服务进行检索
    支持多轮对话和选择题引导
    """
    # 获取搜索服务
    search_service = get_search_service()
    
    # 获取用户查询
    query = request.message.strip()
    if not query:
        return ChatResponse(
            message="请输入您要查找的电路图关键词，例如：东风天龙仪表针脚图"
        )
    
    # 检查是否是选择题答案（A/B/C/D/E 或单个字母）
    user_input_upper = query.upper().strip()
    is_option_selection = len(user_input_upper) == 1 and user_input_upper in ['A', 'B', 'C', 'D', 'E']
    
    # 如果用户选择了选项，需要从历史记录中获取之前的问题和结果
    # 这里简化处理：如果用户输入是单个字母，尝试从历史中找到最近的选择题
    # 实际应用中应该维护对话状态，这里先实现基础功能
    
    # 执行搜索 - 获取所有结果，不限制数量
    logic = request.logic or "AND"
    
    # 先尝试AND逻辑，如果无结果则尝试OR逻辑
    scored_results = search_service.search(
        query=query,
        logic=logic,
        max_results=1000,  # 获取足够多的结果用于分析
        use_fuzzy=True
    )
    
    # 如果AND逻辑无结果，尝试OR逻辑
    if not scored_results and logic.upper() == "AND":
        scored_results = search_service.search(
            query=query,
            logic="OR",
            max_results=1000,
            use_fuzzy=True
        )
    
    # 去重
    scored_results = search_service.deduplicate_results(scored_results)
    
    if not scored_results:
        return ChatResponse(
            message=f"抱歉，没有找到与「{query}」相关的电路图。请尝试其他关键词。"
        )
    
    total_found = len(scored_results)
    
    # 如果结果超过5个，尝试生成选择题引导用户缩小范围
    if total_found > 5:
        # 提取选项（优先按品牌，然后是型号，最后是类型）
        options = None
        option_type = None
        question_text = ""
        
        # 尝试提取品牌选项
        brand_options = search_service.extract_options(scored_results, "brand", max_options=5)
        if brand_options and len(brand_options) >= 2:
            options = brand_options
            option_type = "brand"
            question_text = "找到了多个相关结果。请选择您需要的品牌："
        else:
            # 尝试提取型号选项
            model_options = search_service.extract_options(scored_results, "model", max_options=5)
            if model_options and len(model_options) >= 2:
                options = model_options
                option_type = "model"
                question_text = "找到了多个相关结果。请选择您需要的型号："
            else:
                # 尝试提取类型选项
                type_options = search_service.extract_options(scored_results, "type", max_options=5)
                if type_options and len(type_options) >= 2:
                    options = type_options
                    option_type = "type"
                    question_text = "找到了多个相关结果。请选择您需要的电路图类型："
        
        if options:
            # 生成选择题格式
            message = f"{question_text}\n\n"
            option_labels = ['A', 'B', 'C', 'D', 'E']
            formatted_options = []
            
            for i, option in enumerate(options[:5]):
                label = option_labels[i]
                message += f"{label}. {option['name']} ({option['count']}个结果)\n"
                formatted_options.append({
                    "label": label,
                    "name": option['name'],
                    "count": option['count'],
                    "type": option_type
                })
            
            message += "\n请回复选项字母（如：A）或直接输入选项名称。"
            
            return ChatResponse(
                message=message,
                results=None,  # 不返回结果，等待用户选择
                options=formatted_options,
                needs_choice=True
            )
        else:
            # 如果无法生成选项，返回所有结果
            formatted_results = []
            for result in scored_results:
                formatted_results.append({
                    "id": result.diagram.id,
                    "file_name": result.diagram.file_name,
                    "hierarchy_path": " -> ".join(result.diagram.hierarchy_path),
                    "score": round(result.score, 2),
                    "brand": result.diagram.brand,
                    "model": result.diagram.model,
                    "diagram_type": result.diagram.diagram_type
                })
            
            message = f"找到了 {total_found} 个相关结果（按相关性排序）：\n\n"
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
            
            return ChatResponse(
                message=message,
                results=formatted_results,
                needs_choice=False
            )
    else:
        # 结果≤5个，直接返回所有结果
        formatted_results = []
        for result in scored_results:
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
        
        return ChatResponse(
            message=message,
            results=formatted_results,
            needs_choice=False
        )

