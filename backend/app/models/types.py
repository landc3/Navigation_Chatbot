"""
类型定义模块
用于定义共享的数据类型，避免循环导入
"""
from typing import TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from backend.app.models.circuit_diagram import CircuitDiagram


class ScoredResult(BaseModel):
    """带评分的搜索结果"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    diagram: 'CircuitDiagram' = Field(..., description="电路图对象")
    score: float = Field(..., description="评分")
    
    def __repr__(self):
        return f"ScoredResult(id={self.diagram.id}, score={self.score:.2f})"


# 延迟重建模型，解决前向引用问题
# 当 CircuitDiagram 被导入后，需要调用此函数重建模型
def rebuild_scored_result_model():
    """重建 ScoredResult 模型以解决前向引用"""
    try:
        ScoredResult.model_rebuild()
    except Exception:
        # 如果重建失败，忽略错误（可能 CircuitDiagram 还未定义）
        pass


# 尝试立即重建（如果 CircuitDiagram 已经导入）
try:
    import backend.app.models.circuit_diagram  # noqa: F401
    rebuild_scored_result_model()
except ImportError:
    pass

