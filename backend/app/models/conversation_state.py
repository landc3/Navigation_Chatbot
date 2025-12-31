"""
对话状态管理模块
"""
from enum import Enum
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from backend.app.models.intent_result import IntentResult

# 避免循环导入
if TYPE_CHECKING:
    from backend.app.services.search_service import ScoredResult


class ConversationState(Enum):
    """对话状态枚举"""
    INITIAL_SEARCH = "initial_search"  # 初始搜索
    WAITING_CHOICE = "waiting_choice"  # 等待用户选择
    FILTERING = "filtering"  # 正在筛选
    COMPLETED = "completed"  # 已完成


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationSession:
    """对话会话"""
    session_id: str
    state: ConversationState = ConversationState.INITIAL_SEARCH
    history: List[ChatMessage] = field(default_factory=list)
    
    # 当前搜索条件
    search_conditions: Dict[str, Any] = field(default_factory=dict)
    
    # 当前搜索结果（使用字符串类型避免循环导入）
    current_results: List[Any] = field(default_factory=list)  # List[ScoredResult]
    
    # 当前选择题选项
    current_options: Optional[List[Dict]] = None
    current_option_type: Optional[str] = None  # "brand", "model", "type", "category"
    
    # 意图理解结果
    intent_result: Optional[IntentResult] = None
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str):
        """添加消息到历史记录"""
        self.history.append(ChatMessage(role=role, content=content))
        self.updated_at = datetime.now()
    
    def get_last_user_message(self) -> Optional[ChatMessage]:
        """获取最后一条用户消息"""
        for msg in reversed(self.history):
            if msg.role == "user":
                return msg
        return None
    
    def get_last_assistant_message(self) -> Optional[ChatMessage]:
        """获取最后一条助手消息"""
        for msg in reversed(self.history):
            if msg.role == "assistant":
                return msg
        return None
    
    def update_state(self, new_state: ConversationState):
        """更新对话状态"""
        self.state = new_state
        self.updated_at = datetime.now()
    
    def update_search_conditions(self, **kwargs):
        """更新搜索条件"""
        self.search_conditions.update(kwargs)
        self.updated_at = datetime.now()
    
    def clear_search_conditions(self):
        """清空搜索条件"""
        self.search_conditions.clear()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in self.history
            ],
            "search_conditions": self.search_conditions,
            "current_results_count": len(self.current_results),
            "current_options": self.current_options,
            "current_option_type": self.current_option_type,
            "intent_result": self.intent_result.to_dict() if self.intent_result else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# 全局会话存储（简单内存存储，生产环境应使用Redis等）
_sessions: Dict[str, ConversationSession] = {}


def create_session(session_id: Optional[str] = None) -> ConversationSession:
    """
    创建新的对话会话
    
    Args:
        session_id: 会话ID（如果为None，则自动生成）
        
    Returns:
        对话会话对象
    """
    if session_id is None:
        import uuid
        session_id = str(uuid.uuid4())
    
    session = ConversationSession(session_id=session_id)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Optional[ConversationSession]:
    """
    获取对话会话
    
    Args:
        session_id: 会话ID
        
    Returns:
        对话会话对象，如果不存在则返回None
    """
    return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    """
    删除对话会话
    
    Args:
        session_id: 会话ID
        
    Returns:
        是否删除成功
    """
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


def list_sessions() -> List[str]:
    """列出所有会话ID"""
    return list(_sessions.keys())

