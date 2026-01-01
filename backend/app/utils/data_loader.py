"""
数据加载模块
负责读取CSV文件并转换为数据结构
"""
import pandas as pd
from typing import List, Dict
from pathlib import Path
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.app.models.circuit_diagram import CircuitDiagram
    from config import config
except ImportError:
    # 如果直接运行，尝试相对导入
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    from backend.app.models.circuit_diagram import CircuitDiagram
    from config import config


class DataLoader:
    """数据加载器"""
    
    def __init__(self, csv_path: str = None):
        """
        初始化数据加载器
        
        Args:
            csv_path: CSV文件路径，默认使用config中的路径
        """
        if csv_path:
            self.csv_path = csv_path
        else:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent.parent
            csv_file = project_root / config.DATA_CSV_PATH
            self.csv_path = str(csv_file)
        self.data: List[CircuitDiagram] = []
        self.encoding_used = None
        self._load_data()
    
    def _load_data(self):
        """加载CSV数据"""
        try:
            # 读取CSV文件，支持常见中文编码回退
            encodings_to_try = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']
            last_error = None
            df = None
            for enc in encodings_to_try:
                try:
                    df = pd.read_csv(self.csv_path, encoding=enc)
                    self.encoding_used = enc
                    break
                except UnicodeDecodeError as e:
                    last_error = e
                    continue
            
            if df is None:
                raise Exception(f"无法读取CSV文件，尝试的编码: {encodings_to_try}，原始错误: {last_error}")
            
            if self.encoding_used != 'utf-8':
                print(f"[WARN] 读取CSV使用编码 {self.encoding_used}，建议统一为UTF-8以避免问题")
            
            # 验证必要的列是否存在
            required_columns = ['ID', '层级路径', '关联文件名称']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"CSV文件缺少必要的列: {missing_columns}")
            
            # 转换为CircuitDiagram对象列表
            self.data = []
            for _, row in df.iterrows():
                # 解析层级路径（用->分割）
                hierarchy_str = str(row['层级路径'])
                hierarchy_path = [level.strip() for level in hierarchy_str.split('->')]
                
                # 创建CircuitDiagram对象
                diagram = CircuitDiagram(
                    id=int(row['ID']),
                    hierarchy_path=hierarchy_path,
                    file_name=str(row['关联文件名称'])
                )
                self.data.append(diagram)
            
            print(f"[OK] 成功加载 {len(self.data)} 条电路图数据")
            
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到数据文件: {self.csv_path}")
        except Exception as e:
            raise Exception(f"加载数据时出错: {str(e)}")
    
    def get_all(self) -> List[CircuitDiagram]:
        """获取所有数据"""
        return self.data
    
    def get_by_id(self, diagram_id: int) -> CircuitDiagram:
        """根据ID获取电路图"""
        for diagram in self.data:
            if diagram.id == diagram_id:
                return diagram
        return None
    
    def get_statistics(self) -> Dict:
        """获取数据统计信息"""
        stats = {
            'total_count': len(self.data),
            'diagram_types': {},
            'vehicle_categories': {},
            'brands': {},
            'models': {}
        }
        
        for diagram in self.data:
            # 统计电路图类型
            if diagram.diagram_type:
                stats['diagram_types'][diagram.diagram_type] = \
                    stats['diagram_types'].get(diagram.diagram_type, 0) + 1
            
            # 统计车辆类别
            if diagram.vehicle_category:
                stats['vehicle_categories'][diagram.vehicle_category] = \
                    stats['vehicle_categories'].get(diagram.vehicle_category, 0) + 1
            
            # 统计品牌
            if diagram.brand:
                stats['brands'][diagram.brand] = \
                    stats['brands'].get(diagram.brand, 0) + 1
            
            # 统计型号
            if diagram.model:
                stats['models'][diagram.model] = \
                    stats['models'].get(diagram.model, 0) + 1
        
        return stats
    
    def search_by_keyword(self, keyword: str) -> List[CircuitDiagram]:
        """
        根据关键词搜索（简单匹配）
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的电路图列表
        """
        results = []
        keyword_lower = keyword.lower()
        
        for diagram in self.data:
            # 在文件名称中搜索
            if keyword_lower in diagram.file_name.lower():
                results.append(diagram)
                continue
            
            # 在层级路径中搜索
            for level in diagram.hierarchy_path:
                if keyword_lower in level.lower():
                    results.append(diagram)
                    break
        
        return results


# 全局数据加载器实例（单例模式）
_data_loader_instance = None


def get_data_loader() -> DataLoader:
    """获取数据加载器实例（单例）"""
    global _data_loader_instance
    if _data_loader_instance is None:
        _data_loader_instance = DataLoader()
    return _data_loader_instance

