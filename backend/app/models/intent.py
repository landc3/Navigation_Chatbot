"""
意图理解结果模型
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    """意图理解结果"""
    brand: Optional[str] = Field(None, description="品牌名称，如：三一、徐工、东风、解放、重汽等")
    model: Optional[str] = Field(None, description="型号名称，如：天龙KL、JH6、杰狮等")
    diagram_type: Optional[str] = Field(None, description="电路图类型，如：仪表图、ECU电路图、整车电路图等")
    vehicle_category: Optional[str] = Field(None, description="车辆类别，如：工程机械、商用车等")
    keywords: List[str] = Field(default_factory=list, description="其他关键词列表")
    original_query: str = Field(..., description="原始用户查询")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度，0-1之间")
    
    def has_brand(self) -> bool:
        """是否包含品牌信息"""
        return self.brand is not None and self.brand.strip() != ""
    
    def has_model(self) -> bool:
        """是否包含型号信息"""
        return self.model is not None and self.model.strip() != ""
    
    def has_diagram_type(self) -> bool:
        """是否包含电路图类型信息"""
        return self.diagram_type is not None and self.diagram_type.strip() != ""
    
    def has_keywords(self) -> bool:
        """是否有关键词"""
        return len(self.keywords) > 0
    
    def get_search_query(self) -> str:
        """获取用于搜索的查询字符串"""
        parts = []
        if self.brand:
            parts.append(self.brand)
        if self.model:
            parts.append(self.model)
        if self.diagram_type:
            parts.append(self.diagram_type)
        if self.keywords:
            parts.extend(self.keywords)
        
        # 如果没有提取到任何信息，返回原始查询
        if not parts:
            return self.original_query
        
        return " ".join(parts)




