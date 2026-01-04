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
    state_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="状态历史记录，用于支持返回上一步功能",
        exclude=True,  # 不序列化给前端
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
        self.relax_meta = None
        self.state_history = []

    def save_state_snapshot(self):
        """保存当前状态的快照，用于返回上一步功能"""
        # 只在有意义的状态下保存快照（避免保存初始状态或错误状态）
        if self.state not in [ConversationStateEnum.INITIAL, ConversationStateEnum.COMPLETED]:
            snapshot = {
                "state": self.state,
                "current_query": self.current_query,
                "search_results": self.search_results.copy() if self.search_results else [],
                "current_options": self.current_options.copy() if self.current_options else [],
                "option_type": self.option_type,
                "filter_history": self.filter_history.copy() if self.filter_history else [],
                "message_history": self.message_history.copy() if self.message_history else [],
                "intent_result": self.intent_result,
                "relax_meta": self.relax_meta.copy() if self.relax_meta else None,
                "timestamp": __import__("time").time()
            }
            # 限制历史记录数量，避免内存占用过多
            if len(self.state_history) >= 10:
                self.state_history.pop(0)
            self.state_history.append(snapshot)

    def can_undo(self) -> bool:
        """检查是否可以返回上一步"""
        return len(self.state_history) > 0

    def undo_last_step(self):
        """返回上一步的状态"""
        if not self.can_undo():
            return False

        # 恢复上一个状态
        last_snapshot = self.state_history.pop()
        self.state = last_snapshot["state"]
        self.current_query = last_snapshot["current_query"]
        self.search_results = last_snapshot["search_results"]
        self.current_options = last_snapshot["current_options"]
        self.option_type = last_snapshot["option_type"]
        self.filter_history = last_snapshot["filter_history"]
        self.message_history = last_snapshot["message_history"]
        self.intent_result = last_snapshot["intent_result"]
        self.relax_meta = last_snapshot["relax_meta"]

        return True
    
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

