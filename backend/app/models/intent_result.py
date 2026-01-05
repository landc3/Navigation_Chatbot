"""
意图结果数据模型
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class IntentResult:
    """用户意图解析结果"""
    # 提取的信息
    brand: Optional[str] = None  # 品牌（如：三一、徐工、东风）
    model: Optional[str] = None  # 型号（如：天龙KL、JH6）
    diagram_type: Optional[str] = None  # 电路图类型（如：仪表图、ECU电路图）
    vehicle_category: Optional[str] = None  # 车辆类别（如：工程机械、商用车）
    keywords: List[str] = None  # 其他关键词列表
    
    # 元数据
    confidence: float = 0.0  # 置信度（0-1）
    raw_query: str = ""  # 原始查询
    normalized_query: str = ""  # 标准化后的查询
    
    def __post_init__(self):
        """初始化后处理"""
        if self.keywords is None:
            self.keywords = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "brand": self.brand,
            "model": self.model,
            "diagram_type": self.diagram_type,
            "vehicle_category": self.vehicle_category,
            "keywords": self.keywords,
            "confidence": self.confidence,
            "raw_query": self.raw_query,
            "normalized_query": self.normalized_query
        }
    
    def has_brand(self) -> bool:
        """是否有品牌信息"""
        return self.brand is not None and self.brand.strip() != ""
    
    def has_model(self) -> bool:
        """是否有型号信息"""
        return self.model is not None and self.model.strip() != ""
    
    def has_type(self) -> bool:
        """是否有类型信息"""
        return self.diagram_type is not None and self.diagram_type.strip() != ""
    
    def has_category(self) -> bool:
        """是否有类别信息"""
        return self.vehicle_category is not None and self.vehicle_category.strip() != ""
    
    def is_empty(self) -> bool:
        """是否为空（没有任何提取的信息）"""
        return not (self.has_brand() or self.has_model() or 
                   self.has_type() or self.has_category() or 
                   (self.keywords and len(self.keywords) > 0))






