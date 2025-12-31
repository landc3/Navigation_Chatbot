"""
意图理解服务模块
使用LLM解析用户自然语言查询，提取品牌、型号、类型等信息
"""
import json
from typing import Optional, List, Dict, Any
from backend.app.services.llm_service import get_llm_service
from backend.app.models.intent_result import IntentResult
from backend.app.utils.hierarchy_util import HierarchyUtil


class IntentService:
    """意图理解服务"""
    
    # 近义词映射表
    SYNONYM_MAP = {
        # 品牌简称映射
        "天龙": "东风天龙",
        "解放": "一汽解放",
        "重汽": "中国重汽",
        "上汽": "上汽大通",
        "大通": "上汽大通",
        
        # 类型近义词映射
        "仪表图": "仪表电路图",
        "仪表": "仪表电路图",
        "ECU图": "ECU电路图",
        "ECU": "ECU电路图",
        "线路图": "电路图",
        "接线图": "电路图",
        "针脚图": "ECU电路图",
        "整车图": "整车电路图",
    }
    
    # 品牌列表（用于验证）
    VALID_BRANDS = HierarchyUtil.COMMON_BRANDS
    
    # 电路图类型列表（用于验证）
    VALID_DIAGRAM_TYPES = HierarchyUtil.COMMON_DIAGRAM_TYPES
    
    def __init__(self):
        """初始化意图理解服务"""
        self.llm_service = get_llm_service()
    
    def parse_intent(self, user_query: str, use_llm: bool = True) -> IntentResult:
        """
        解析用户意图
        
        Args:
            user_query: 用户查询字符串
            use_llm: 是否使用LLM（如果False，则使用规则匹配）
            
        Returns:
            意图结果对象
        """
        if not user_query or not user_query.strip():
            return IntentResult(raw_query="", normalized_query="")
        
        user_query = user_query.strip()
        
        # 如果启用LLM，使用LLM解析
        if use_llm:
            try:
                return self._parse_with_llm(user_query)
            except Exception as e:
                print(f"LLM解析失败，降级为规则匹配：{e}")
                # 降级为规则匹配
                return self._parse_with_rules(user_query)
        else:
            # 直接使用规则匹配
            return self._parse_with_rules(user_query)
    
    def _parse_with_llm(self, user_query: str) -> IntentResult:
        """
        使用LLM解析用户意图
        
        Args:
            user_query: 用户查询
            
        Returns:
            意图结果对象
        """
        # 构建Prompt
        prompt = self._build_intent_prompt(user_query)
        
        # 系统提示词
        system_prompt = """你是一个专业的车辆电路图资料导航助手。你的任务是分析用户的自然语言查询，提取出以下信息：
1. 品牌（如：三一、徐工、东风、解放、重汽等）
2. 型号（如：天龙KL、JH6、SY60等）
3. 电路图类型（如：仪表图、ECU电路图、整车电路图等）
4. 车辆类别（如：工程机械、商用车等）
5. 其他关键词

请以JSON格式返回结果，格式如下：
{
    "brand": "品牌名称或null",
    "model": "型号名称或null",
    "diagram_type": "电路图类型或null",
    "vehicle_category": "车辆类别或null",
    "keywords": ["关键词1", "关键词2"],
    "confidence": 0.8
}

注意：
- 如果某个字段无法确定，请设置为null
- keywords字段应包含查询中的其他重要关键词
- confidence表示你对解析结果的置信度（0-1之间）
- 如果用户说"天龙"，应该理解为"东风天龙"品牌
- 如果用户说"仪表图"、"仪表"，应该理解为"仪表电路图"
"""
        
        # 调用LLM
        try:
            result_dict = self.llm_service.call_qwen_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # 降低温度，提高准确性
                max_tokens=500
            )
            
            # 构建IntentResult对象
            intent_result = IntentResult(
                brand=result_dict.get("brand"),
                model=result_dict.get("model"),
                diagram_type=result_dict.get("diagram_type"),
                vehicle_category=result_dict.get("vehicle_category"),
                keywords=result_dict.get("keywords", []),
                confidence=result_dict.get("confidence", 0.5),
                raw_query=user_query,
                normalized_query=user_query
            )
            
            # 应用近义词映射和标准化
            self._normalize_intent(intent_result)
            
            return intent_result
            
        except Exception as e:
            raise Exception(f"LLM解析失败：{str(e)}")
    
    def _parse_with_rules(self, user_query: str) -> IntentResult:
        """
        使用规则匹配解析用户意图（降级方案）
        
        Args:
            user_query: 用户查询
            
        Returns:
            意图结果对象
        """
        intent_result = IntentResult(
            raw_query=user_query,
            normalized_query=user_query,
            keywords=[],
            confidence=0.3  # 规则匹配的置信度较低
        )
        
        query_lower = user_query.lower()
        
        # 提取品牌
        for brand in self.VALID_BRANDS:
            if brand in user_query:
                intent_result.brand = brand
                break
        
        # 提取类型
        for diagram_type in self.VALID_DIAGRAM_TYPES:
            if diagram_type in user_query:
                intent_result.diagram_type = diagram_type
                break
        
        # 提取车辆类别
        for category in HierarchyUtil.COMMON_VEHICLE_CATEGORIES:
            if category in user_query:
                intent_result.vehicle_category = category
                break
        
        # 应用近义词映射
        self._normalize_intent(intent_result)
        
        # 提取其他关键词（使用jieba分词）
        import jieba
        words = jieba.cut(user_query)
        keywords = [
            word.strip() 
            for word in words 
            if len(word.strip()) > 1 and word.strip() not in ['的', '了', '是', '在', '和', '与', '或']
        ]
        intent_result.keywords = keywords
        
        return intent_result
    
    def _build_intent_prompt(self, user_query: str) -> str:
        """
        构建意图解析的Prompt
        
        Args:
            user_query: 用户查询
            
        Returns:
            Prompt字符串
        """
        return f"""请分析以下用户查询，提取出品牌、型号、电路图类型、车辆类别等信息：

用户查询：{user_query}

请以JSON格式返回解析结果。"""
    
    def _normalize_intent(self, intent_result: IntentResult):
        """
        标准化意图结果（应用近义词映射、处理模糊表达）
        
        Args:
            intent_result: 意图结果对象（会被修改）
        """
        # 应用近义词映射
        if intent_result.brand:
            normalized_brand = self.SYNONYM_MAP.get(intent_result.brand, intent_result.brand)
            if normalized_brand != intent_result.brand:
                intent_result.brand = normalized_brand
        
        if intent_result.model:
            normalized_model = self.SYNONYM_MAP.get(intent_result.model, intent_result.model)
            if normalized_model != intent_result.model:
                intent_result.model = normalized_model
        
        if intent_result.diagram_type:
            normalized_type = self.SYNONYM_MAP.get(intent_result.diagram_type, intent_result.diagram_type)
            if normalized_type != intent_result.diagram_type:
                intent_result.diagram_type = normalized_type
        
        # 处理模糊表达：如果只有型号没有品牌，尝试推断品牌
        if intent_result.model and not intent_result.brand:
            # 检查型号中是否包含品牌信息
            for brand in self.VALID_BRANDS:
                if brand in intent_result.model:
                    intent_result.brand = brand
                    break
        
        # 构建标准化查询
        normalized_parts = []
        if intent_result.brand:
            normalized_parts.append(intent_result.brand)
        if intent_result.model:
            normalized_parts.append(intent_result.model)
        if intent_result.diagram_type:
            normalized_parts.append(intent_result.diagram_type)
        if intent_result.vehicle_category:
            normalized_parts.append(intent_result.vehicle_category)
        if intent_result.keywords:
            normalized_parts.extend(intent_result.keywords)
        
        intent_result.normalized_query = " ".join(normalized_parts) if normalized_parts else intent_result.raw_query


# 全局意图理解服务实例（单例模式）
_intent_service_instance = None


def get_intent_service() -> IntentService:
    """获取意图理解服务实例（单例）"""
    global _intent_service_instance
    if _intent_service_instance is None:
        _intent_service_instance = IntentService()
    return _intent_service_instance


