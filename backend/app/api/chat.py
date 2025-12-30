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

from backend.app.utils.data_loader import get_data_loader

router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    """聊天响应"""
    message: str
    results: Optional[List[dict]] = None  # 搜索结果（如果有）


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    
    目前是基础版本，后续会集成LLM和多轮对话
    """
    # 获取数据加载器
    data_loader = get_data_loader()
    
    # 简单的关键词搜索（临时实现）
    keyword = request.message.strip()
    if not keyword:
        return ChatResponse(
            message="请输入您要查找的电路图关键词，例如：东风天龙仪表图"
        )
    
    # 搜索
    results = data_loader.search_by_keyword(keyword)
    
    if not results:
        return ChatResponse(
            message=f"抱歉，没有找到与「{keyword}」相关的电路图。请尝试其他关键词。"
        )
    
    # 限制返回结果数量
    max_results = 5
    limited_results = results[:max_results]
    
    # 格式化结果
    formatted_results = [
        {
            "id": diagram.id,
            "file_name": diagram.file_name,
            "hierarchy_path": " -> ".join(diagram.hierarchy_path)
        }
        for diagram in limited_results
    ]
    
    if len(results) > max_results:
        message = f"找到了 {len(results)} 个相关结果，显示前 {max_results} 个：\n\n"
    else:
        message = f"找到了 {len(results)} 个相关结果：\n\n"
    
    for i, result in enumerate(formatted_results, 1):
        message += f"{i}. [ID: {result['id']}] {result['file_name']}\n"
        message += f"   路径: {result['hierarchy_path']}\n\n"
    
    return ChatResponse(
        message=message,
        results=formatted_results
    )

