"""
电路图数据模型
"""
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class CircuitDiagram:
    """电路图数据模型"""
    id: int
    hierarchy_path: List[str]  # 层级路径列表
    file_name: str  # 文件名称
    
    # 解析后的字段（可选）
    diagram_type: Optional[str] = None  # 电路图类型（如：ECU电路图、整车电路图）
    vehicle_category: Optional[str] = None  # 车辆类别（如：工程机械、商用车）
    brand: Optional[str] = None  # 品牌（如：三一、徐工、东风）
    model: Optional[str] = None  # 型号（如：SY60、天龙KL）
    other_attrs: Optional[Dict] = None  # 其他属性
    
    def __post_init__(self):
        """初始化后处理，解析层级路径"""
        if self.other_attrs is None:
            self.other_attrs = {}
        
        # 解析层级路径
        self._parse_hierarchy()
    
    def _parse_hierarchy(self):
        """解析层级路径，提取关键信息"""
        if not self.hierarchy_path:
            return
        
        # 常见的层级位置模式（根据实际数据调整）
        # 通常格式：电路图 -> 类型 -> 类别 -> 品牌 -> 型号/其他
        
        # 第一层通常是"电路图"
        if len(self.hierarchy_path) > 1:
            self.diagram_type = self.hierarchy_path[1]  # 第二层通常是类型
        
        # 查找车辆类别（通常在第三层）
        if len(self.hierarchy_path) > 2:
            self.vehicle_category = self.hierarchy_path[2]
        
        # 查找品牌（通常在第四层，但可能变化）
        # 常见的品牌列表
        brands = ['三一', '徐工', '斗山', '杰西博', '久保田', '卡特彼勒', '凯斯', 
                  '龙工', '柳工', '雷沃', '日立', '山东临工', '山重建机', '山河智能',
                  '神钢', '沃尔沃', '小松', '东风', '解放', '重汽', '福田', '乘龙',
                  '红岩', '豪瀚', '欧曼', '上汽大通', '五十铃', '康明斯', '玉柴']
        
        for i, level in enumerate(self.hierarchy_path):
            if level in brands:
                self.brand = level
                # 品牌后面通常是型号
                if i + 1 < len(self.hierarchy_path):
                    self.model = self.hierarchy_path[i + 1]
                break
        
        # 如果没有找到品牌，尝试其他位置
        if not self.brand and len(self.hierarchy_path) > 3:
            self.brand = self.hierarchy_path[3]
            if len(self.hierarchy_path) > 4:
                self.model = self.hierarchy_path[4]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'hierarchy_path': self.hierarchy_path,
            'file_name': self.file_name,
            'diagram_type': self.diagram_type,
            'vehicle_category': self.vehicle_category,
            'brand': self.brand,
            'model': self.model,
            'other_attrs': self.other_attrs
        }
    
    def matches_keyword(self, keyword: str) -> bool:
        """检查是否匹配关键词（简单匹配）"""
        keyword_lower = keyword.lower()
        # 在文件名称中搜索
        if keyword_lower in self.file_name.lower():
            return True
        # 在层级路径中搜索
        for level in self.hierarchy_path:
            if keyword_lower in level.lower():
                return True
        return False

