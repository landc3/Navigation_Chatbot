"""
文档类别提取模式配置加载器
用于从配置文件加载和管理分类模式，避免硬编码
"""
import json
import os
import re
from typing import Dict, List, Optional, Any
from pathlib import Path


class CategoryPatternLoader:
    """类别模式配置加载器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径，如果为None，则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径（相对于项目根目录）
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "category_patterns.json"
        
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                # 如果配置文件不存在，使用默认配置
                print(f"⚠️ 配置文件不存在: {self.config_path}，使用默认配置")
                self.config = self._get_default_config()
        except Exception as e:
            print(f"⚠️ 加载配置文件失败: {str(e)}，使用默认配置")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置（作为fallback）"""
        return {
            "patterns": {
                "diagnostic_guide": {
                    "suffixes": ["_诊断指导"]
                },
                "product_intro": {
                    "keywords": ["产品介绍"],
                    "cleanup_patterns": ["【\\d+】", "[-_]"]
                },
                "recommended": {
                    "prefixes": ["【推荐】"],
                    "stop_markers": ["【", "."]
                },
                "component_keywords": {
                    "keywords": ["传感器", "执行器", "增压器"],
                    "max_length_after_keyword": 10
                },
                "brand_patterns": {
                    "brands": ["解放动力", "龙擎动力", "东风", "重汽", "柳汽", "乘龙"],
                    "patterns": []
                }
            },
            "fallback": {
                "max_length": 30,
                "separators": ["【", "(", "_", "-"],
                "cleanup_patterns": ["[-_]\\d+$", "[-_]诊断指导$"]
            },
            "validation": {
                "min_length": 2,
                "max_length": 50,
                "remove_spaces": True,
                "strip_chars": "【】()（）-_"
            }
        }
    
    def reload_config(self):
        """重新加载配置文件（用于运行时更新配置）"""
        self._load_config()
    
    def get_patterns(self) -> Dict[str, Any]:
        """获取所有模式配置"""
        return self.config.get("patterns", {})
    
    def get_fallback_config(self) -> Dict[str, Any]:
        """获取通用提取机制配置"""
        return self.config.get("fallback", {})
    
    def get_validation_config(self) -> Dict[str, Any]:
        """获取验证配置"""
        return self.config.get("validation", {})
    
    def get_diagnostic_suffixes(self) -> List[str]:
        """获取诊断指导类后缀列表"""
        pattern = self.get_patterns().get("diagnostic_guide", {})
        return pattern.get("suffixes", ["_诊断指导"])
    
    def get_product_intro_keywords(self) -> List[str]:
        """获取产品介绍关键词列表"""
        pattern = self.get_patterns().get("product_intro", {})
        return pattern.get("keywords", ["产品介绍"])
    
    def get_component_keywords(self) -> List[str]:
        """获取组件关键词列表"""
        pattern = self.get_patterns().get("component_keywords", {})
        return pattern.get("keywords", ["传感器", "执行器", "增压器"])
    
    def get_brand_list(self) -> List[str]:
        """获取品牌列表"""
        pattern = self.get_patterns().get("brand_patterns", {})
        return pattern.get("brands", [])
    
    def get_brand_patterns(self) -> List[Dict[str, Any]]:
        """获取品牌正则表达式模式列表"""
        pattern = self.get_patterns().get("brand_patterns", {})
        return pattern.get("patterns", [])
    
    def get_recommended_prefixes(self) -> List[str]:
        """获取推荐类前缀列表"""
        pattern = self.get_patterns().get("recommended", {})
        return pattern.get("prefixes", ["【推荐】"])
    
    def get_recommended_stop_markers(self) -> List[str]:
        """获取推荐类停止标记列表"""
        pattern = self.get_patterns().get("recommended", {})
        return pattern.get("stop_markers", ["【", "."])


# 全局配置加载器实例（单例模式）
_pattern_loader_instance: Optional[CategoryPatternLoader] = None


def get_pattern_loader() -> CategoryPatternLoader:
    """获取全局配置加载器实例"""
    global _pattern_loader_instance
    if _pattern_loader_instance is None:
        _pattern_loader_instance = CategoryPatternLoader()
    return _pattern_loader_instance



