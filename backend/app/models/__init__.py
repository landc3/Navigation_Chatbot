"""数据模型模块"""
from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.intent import IntentResult
from backend.app.models.conversation import (
    ConversationState,
    ConversationStateEnum,
    ChatMessage,
    ConversationManager,
    get_conversation_manager
)
from backend.app.models.types import ScoredResult

# 重建模型以解决前向引用问题
# 必须在 CircuitDiagram 导入后，ScoredResult 导入后执行
ScoredResult.model_rebuild()

__all__ = [
    'CircuitDiagram',
    'IntentResult',
    'ConversationState',
    'ConversationStateEnum',
    'ChatMessage',
    'ConversationManager',
    'get_conversation_manager',
    'ScoredResult'
]
