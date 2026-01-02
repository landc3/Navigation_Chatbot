"""
对话状态和对话历史模型
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from backend.app.models.types import ScoredResult


class ConversationStateEnum(str, Enum):
    """对话状态枚举"""
    INITIAL = "initial"           # 初始状态
    SEARCHING = "searching"       # 搜索中
    NEEDS_CHOICE = "needs_choice"  # 等待用户选择
    NEEDS_CONFIRM = "needs_confirm"  # 需要用户确认（例如：已放宽关键词找到近似结果）
    FILTERING = "filtering"       # 筛选中
    COMPLETED = "completed"       # 已完成


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色：user 或 assistant")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[float] = Field(None, description="时间戳")


class ConversationState(BaseModel):
    """对话状态"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # 排除 search_results 和 intent_result 字段的序列化
        # 这些字段包含复杂对象，不需要在 API 响应中序列化
    )
    
    state: ConversationStateEnum = Field(
        ConversationStateEnum.INITIAL,
        description="当前对话状态"
    )
    current_query: str = Field("", description="当前查询")
    # 使用 Any 类型避免前向引用问题
    # 这个字段不参与序列化，只在内部使用
    search_results: List[Any] = Field(
        default_factory=list,
        description="当前搜索结果",
        exclude=True  # 排除序列化
    )
    current_options: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="当前选择题选项"
    )
    option_type: Optional[str] = Field(None, description="当前选项类型（brand/model/type）")
    filter_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="筛选历史记录"
    )
    message_history: List[ChatMessage] = Field(
        default_factory=list,
        description="消息历史记录"
    )
    intent_result: Optional[Any] = Field(
        None, 
        description="意图理解结果",
        exclude=True  # 排除序列化
    )
    relax_meta: Optional[Dict[str, Any]] = Field(
        None,
        description="放宽搜索元信息（用于确认/调试）",
        exclude=True,
    )
    
    def add_message(self, role: str, content: str):
        """添加消息到历史记录"""
        import time
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=time.time()
        )
        self.message_history.append(message)
    
    def get_recent_messages(self, n: int = 10) -> List[ChatMessage]:
        """获取最近N条消息"""
        return self.message_history[-n:] if n > 0 else self.message_history
    
    def clear(self):
        """清空对话状态"""
        self.state = ConversationStateEnum.INITIAL
        self.current_query = ""
        self.search_results = []
        self.current_options = []
        self.option_type = None
        self.filter_history = []
        self.message_history = []
        self.intent_result = None
    
    def update_state(self, new_state: ConversationStateEnum):
        """更新对话状态"""
        self.state = new_state
    
    def add_filter(self, filter_type: str, filter_value: str):
        """添加筛选条件到历史"""
        self.filter_history.append({
            "type": filter_type,
            "value": filter_value,
            "timestamp": __import__("time").time()
        })


class ConversationManager:
    """对话管理器（单例模式）"""
    
    def __init__(self):
        """初始化对话管理器"""
        # 使用字典存储不同会话的状态（key: session_id）
        self.conversations: Dict[str, ConversationState] = {}
    
    def get_or_create_state(self, session_id: str = "default") -> ConversationState:
        """
        获取或创建对话状态
        
        Args:
            session_id: 会话ID（默认使用"default"）
            
        Returns:
            对话状态对象
        """
        if session_id not in self.conversations:
            self.conversations[session_id] = ConversationState()
        return self.conversations[session_id]
    
    def clear_conversation(self, session_id: str = "default"):
        """清空指定会话的对话状态"""
        if session_id in self.conversations:
            self.conversations[session_id].clear()
    
    def remove_conversation(self, session_id: str):
        """删除指定会话"""
        if session_id in self.conversations:
            del self.conversations[session_id]


# 全局对话管理器实例（单例）
_conversation_manager_instance = None


def get_conversation_manager() -> ConversationManager:
    """获取对话管理器实例（单例）"""
    global _conversation_manager_instance
    if _conversation_manager_instance is None:
        _conversation_manager_instance = ConversationManager()
    return _conversation_manager_instance

