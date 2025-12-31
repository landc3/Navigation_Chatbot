"""
层级路径工具模块
提供层级路径解析、筛选和选项提取功能
"""
from typing import List, Dict, Optional, Set
from backend.app.models.circuit_diagram import CircuitDiagram


class HierarchyUtil:
    """层级路径工具类"""
    
    # 常见品牌列表
    COMMON_BRANDS = [
        '三一', '徐工', '斗山', '杰西博', '久保田', '卡特彼勒', '凯斯',
        '龙工', '柳工', '雷沃', '日立', '山东临工', '山重建机', '山河智能',
        '神钢', '沃尔沃', '小松', '东风', '解放', '重汽', '福田', '乘龙',
        '红岩', '豪瀚', '欧曼', '上汽大通', '五十铃', '康明斯', '玉柴'
    ]
    
    # 常见电路图类型
    COMMON_DIAGRAM_TYPES = [
        'ECU电路图', '整车电路图', '仪表电路图', '仪表图', 'ECU图',
        '线路图', '电路图', '针脚图', '接线图'
    ]
    
    # 常见车辆类别
    COMMON_VEHICLE_CATEGORIES = [
        '工程机械', '商用车', '乘用车', '客车', '货车'
    ]
    
    @staticmethod
    def extract_brand(hierarchy_path: List[str]) -> Optional[str]:
        """
        从层级路径中提取品牌
        
        Args:
            hierarchy_path: 层级路径列表
            
        Returns:
            品牌名称，如果未找到则返回None
        """
        for level in hierarchy_path:
            if level in HierarchyUtil.COMMON_BRANDS:
                return level
        
        # 模糊匹配品牌（包含关系）
        for level in hierarchy_path:
            for brand in HierarchyUtil.COMMON_BRANDS:
                if brand in level or level in brand:
                    return brand
        
        return None
    
    @staticmethod
    def extract_diagram_type(hierarchy_path: List[str]) -> Optional[str]:
        """
        从层级路径中提取电路图类型
        
        Args:
            hierarchy_path: 层级路径列表
            
        Returns:
            电路图类型，如果未找到则返回None
        """
        for level in hierarchy_path:
            for diagram_type in HierarchyUtil.COMMON_DIAGRAM_TYPES:
                if diagram_type in level:
                    return diagram_type
        
        # 如果第二层存在，通常就是类型
        if len(hierarchy_path) > 1:
            return hierarchy_path[1]
        
        return None
    
    @staticmethod
    def extract_vehicle_category(hierarchy_path: List[str]) -> Optional[str]:
        """
        从层级路径中提取车辆类别
        
        Args:
            hierarchy_path: 层级路径列表
            
        Returns:
            车辆类别，如果未找到则返回None
        """
        for level in hierarchy_path:
            if level in HierarchyUtil.COMMON_VEHICLE_CATEGORIES:
                return level
        
        # 如果第三层存在，通常就是类别
        if len(hierarchy_path) > 2:
            return hierarchy_path[2]
        
        return None
    
    @staticmethod
    def extract_model(hierarchy_path: List[str], brand: Optional[str] = None) -> Optional[str]:
        """
        从层级路径中提取型号
        
        Args:
            hierarchy_path: 层级路径列表
            brand: 品牌名称（如果已知，可以提高准确性）
            
        Returns:
            型号名称，如果未找到则返回None
        """
        # 如果已知品牌，在品牌后面查找
        if brand:
            for i, level in enumerate(hierarchy_path):
                if level == brand or brand in level:
                    if i + 1 < len(hierarchy_path):
                        return hierarchy_path[i + 1]
        
        # 否则，尝试在品牌位置后面查找
        brand_pos = None
        for i, level in enumerate(hierarchy_path):
            if level in HierarchyUtil.COMMON_BRANDS:
                brand_pos = i
                break
        
        if brand_pos is not None and brand_pos + 1 < len(hierarchy_path):
            return hierarchy_path[brand_pos + 1]
        
        # 如果层级路径长度足够，通常型号在品牌后面
        if len(hierarchy_path) > 4:
            return hierarchy_path[4]
        
        return None
    
    @staticmethod
    def filter_by_brand(
        diagrams: List[CircuitDiagram],
        brand: str
    ) -> List[CircuitDiagram]:
        """
        按品牌筛选电路图
        
        Args:
            diagrams: 电路图列表
            brand: 品牌名称
            
        Returns:
            筛选后的电路图列表
        """
        results = []
        brand_lower = brand.lower()
        
        for diagram in diagrams:
            # 检查品牌字段
            if diagram.brand and brand_lower in diagram.brand.lower():
                results.append(diagram)
                continue
            
            # 检查层级路径
            for level in diagram.hierarchy_path:
                if brand_lower in level.lower():
                    results.append(diagram)
                    break
        
        return results
    
    @staticmethod
    def filter_by_model(
        diagrams: List[CircuitDiagram],
        model: str
    ) -> List[CircuitDiagram]:
        """
        按型号筛选电路图
        
        Args:
            diagrams: 电路图列表
            model: 型号名称
            
        Returns:
            筛选后的电路图列表
        """
        results = []
        model_lower = model.lower()
        
        for diagram in diagrams:
            # 检查型号字段
            if diagram.model and model_lower in diagram.model.lower():
                results.append(diagram)
                continue
            
            # 检查文件名称
            if model_lower in diagram.file_name.lower():
                results.append(diagram)
                continue
            
            # 检查层级路径
            for level in diagram.hierarchy_path:
                if model_lower in level.lower():
                    results.append(diagram)
                    break
        
        return results
    
    @staticmethod
    def filter_by_diagram_type(
        diagrams: List[CircuitDiagram],
        diagram_type: str
    ) -> List[CircuitDiagram]:
        """
        按电路图类型筛选
        
        Args:
            diagrams: 电路图列表
            diagram_type: 电路图类型
            
        Returns:
            筛选后的电路图列表
        """
        results = []
        type_lower = diagram_type.lower()
        
        for diagram in diagrams:
            # 检查类型字段
            if diagram.diagram_type and type_lower in diagram.diagram_type.lower():
                results.append(diagram)
                continue
            
            # 检查层级路径
            for level in diagram.hierarchy_path:
                if type_lower in level.lower():
                    results.append(diagram)
                    break
            
            # 检查文件名称
            if type_lower in diagram.file_name.lower():
                results.append(diagram)
        
        return results
    
    @staticmethod
    def filter_by_vehicle_category(
        diagrams: List[CircuitDiagram],
        category: str
    ) -> List[CircuitDiagram]:
        """
        按车辆类别筛选
        
        Args:
            diagrams: 电路图列表
            category: 车辆类别
            
        Returns:
            筛选后的电路图列表
        """
        results = []
        category_lower = category.lower()
        
        for diagram in diagrams:
            # 检查类别字段
            if diagram.vehicle_category and category_lower in diagram.vehicle_category.lower():
                results.append(diagram)
                continue
            
            # 检查层级路径
            for level in diagram.hierarchy_path:
                if category_lower in level.lower():
                    results.append(diagram)
                    break
        
        return results
    
    @staticmethod
    def extract_options(
        diagrams: List[CircuitDiagram],
        option_type: str,
        max_options: int = 5
    ) -> List[Dict]:
        """
        从电路图列表中提取选项（用于选择题）
        
        Args:
            diagrams: 电路图列表
            option_type: 选项类型（"brand", "model", "type", "category"）
            max_options: 最大选项数量
            
        Returns:
            选项列表，每个选项包含名称和数量
            格式: [{"name": "选项名", "count": 数量}, ...]
        """
        option_counts = {}
        
        for diagram in diagrams:
            value = None
            
            if option_type == "brand":
                value = diagram.brand
            elif option_type == "model":
                value = diagram.model
            elif option_type == "type":
                value = diagram.diagram_type
            elif option_type == "category":
                value = diagram.vehicle_category
            
            if value:
                option_counts[value] = option_counts.get(value, 0) + 1
        
        # 转换为列表并按数量排序
        options = [
            {"name": name, "count": count}
            for name, count in option_counts.items()
        ]
        options.sort(key=lambda x: x["count"], reverse=True)
        
        # 限制选项数量
        return options[:max_options]
    
    @staticmethod
    def get_all_levels(diagrams: List[CircuitDiagram]) -> Dict[str, Set[str]]:
        """
        获取所有层级的唯一值
        
        Args:
            diagrams: 电路图列表
            
        Returns:
            字典，包含各层级的唯一值集合
            格式: {
                "brands": {"三一", "东风", ...},
                "models": {"天龙KL", "JH6", ...},
                "types": {"ECU电路图", ...},
                "categories": {"工程机械", ...}
            }
        """
        result = {
            "brands": set(),
            "models": set(),
            "types": set(),
            "categories": set()
        }
        
        for diagram in diagrams:
            if diagram.brand:
                result["brands"].add(diagram.brand)
            if diagram.model:
                result["models"].add(diagram.model)
            if diagram.diagram_type:
                result["types"].add(diagram.diagram_type)
            if diagram.vehicle_category:
                result["categories"].add(diagram.vehicle_category)
        
        return result


