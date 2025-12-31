"""
问题生成服务模块
根据搜索结果生成选择题，引导用户缩小范围
"""
from typing import List, Dict, Optional
from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.types import ScoredResult, rebuild_scored_result_model
from backend.app.services.search_service import get_search_service

# 确保 ScoredResult 模型已重建（解决前向引用问题）
rebuild_scored_result_model()


class QuestionService:
    """问题生成服务"""
    
    def __init__(self):
        """初始化问题生成服务"""
        self.search_service = get_search_service()
    
    def generate_question(
        self,
        results: List[ScoredResult],
        min_options: int = 2,
        max_options: int = 5,
        excluded_types: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        根据搜索结果生成选择题
        
        Args:
            results: 搜索结果列表
            min_options: 最少选项数
            max_options: 最多选项数
            excluded_types: 要排除的选项类型列表（如：["brand", "model"]），用于跳过已经选择的类型
            
        Returns:
            问题字典，包含问题文本和选项列表，如果无法生成则返回None
            格式: {
                "question": "问题文本",
                "options": [
                    {"label": "A", "name": "选项名", "count": 数量, "type": "brand"},
                    ...
                ],
                "option_type": "brand"  # 选项类型
            }
        """
        if not results or len(results) < min_options:
            return None
        
        # 按优先级尝试生成问题：品牌 -> 型号 -> 类型 -> 类别
        option_types = ["brand", "model", "type", "category"]
        
        # 如果指定了要排除的类型，跳过它们
        if excluded_types:
            original_option_types = option_types.copy()
            option_types = [opt_type for opt_type in option_types if opt_type not in excluded_types]
            # 调试信息：确保排除的类型不在 option_types 中
            print(f"[DEBUG] 排除的类型: {excluded_types}, 原始类型: {original_option_types}, 可用类型: {option_types}")
        
        # 如果所有类型都被排除了，返回 None
        if not option_types:
            print(f"[DEBUG] 所有类型都被排除，无法生成问题")
            return None
        
        for option_type in option_types:
            # 双重检查：确保当前类型不在排除列表中
            if excluded_types and option_type in excluded_types:
                print(f"[DEBUG] 警告：类型 {option_type} 在排除列表中，跳过")
                continue
                
            options = self.search_service.extract_options(
                results,
                option_type,
                max_options=max_options
            )
            
            # 检查选项数量是否足够
            if options and len(options) >= min_options:
                question_text = self._generate_question_text(option_type, len(results))
                option_labels = ['A', 'B', 'C', 'D', 'E']
                
                formatted_options = []
                for i, option in enumerate(options[:max_options]):
                    formatted_options.append({
                        "label": option_labels[i],
                        "name": option['name'],
                        "count": option['count'],
                        "type": option_type
                    })
                
                # 最终检查：确保生成的问题类型不在排除列表中
                if excluded_types and option_type in excluded_types:
                    print(f"[DEBUG] 错误：生成的问题类型 {option_type} 在排除列表中，返回 None")
                    continue
                
                return {
                    "question": question_text,
                    "options": formatted_options,
                    "option_type": option_type
                }
        
        # 如果无法生成问题，返回None
        return None
    
    def _generate_question_text(self, option_type: str, total_count: int) -> str:
        """
        生成问题文本
        
        Args:
            option_type: 选项类型
            total_count: 总结果数
            
        Returns:
            问题文本
        """
        type_mapping = {
            "brand": "品牌",
            "model": "型号",
            "type": "电路图类型",
            "category": "车辆类别"
        }
        
        type_name = type_mapping.get(option_type, "选项")
        
        return f"找到了 {total_count} 个相关结果。请选择您需要的{type_name}："
    
    def format_question_message(self, question_data: Dict) -> str:
        """
        格式化问题消息（用于显示给用户）
        
        Args:
            question_data: 问题数据（由generate_question返回）
            
        Returns:
            格式化的消息文本
        """
        message = f"{question_data['question']}\n\n"
        
        for option in question_data['options']:
            message += f"{option['label']}. {option['name']} ({option['count']}个结果)\n"
        
        message += "\n请回复选项字母（如：A）或直接输入选项名称。"
        
        return message
    
    def parse_user_choice(
        self,
        user_input: str,
        question_data: Dict
    ) -> Optional[str]:
        """
        解析用户选择
        
        Args:
            user_input: 用户输入（可能是选项字母或选项名称）
            question_data: 问题数据
            
        Returns:
            选中的选项名称，如果无法解析则返回None
        """
        user_input = user_input.strip().upper()
        
        # 检查是否是选项字母（A/B/C/D/E）
        if len(user_input) == 1 and user_input in ['A', 'B', 'C', 'D', 'E']:
            # 找到对应的选项
            for option in question_data['options']:
                if option['label'] == user_input:
                    return option['name']
        
        # 检查是否是选项名称（完全匹配或部分匹配）
        user_input_lower = user_input.lower()
        for option in question_data['options']:
            option_name_lower = option['name'].lower()
            if user_input_lower == option_name_lower or user_input_lower in option_name_lower:
                return option['name']
        
        return None


# 全局问题生成服务实例（单例模式）
_question_service_instance = None


def get_question_service() -> QuestionService:
    """获取问题生成服务实例（单例）"""
    global _question_service_instance
    if _question_service_instance is None:
        _question_service_instance = QuestionService()
    return _question_service_instance

