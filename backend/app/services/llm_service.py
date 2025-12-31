"""
LLM服务模块
提供通义千问API调用和意图理解功能
"""
import json
import re
from typing import Optional, Dict, Any
import dashscope
from dashscope import Generation
from config import Config
from backend.app.models.intent import IntentResult


class LLMService:
    """LLM服务"""
    
    def __init__(self):
        """初始化LLM服务"""
        self.api_key = Config.ALI_QWEN_API_KEY
        self.model = Config.ALI_QWEN_MODEL
        self.max_tokens = Config.MAX_TOKENS
        self.temperature = Config.TEMPERATURE
        
        # 设置API Key
        dashscope.api_key = self.api_key
        
        # 近义词映射表
        self.synonyms = {
            "仪表图": ["仪表电路图", "仪表针脚图", "仪表线路图"],
            "ECU图": ["ECU电路图", "电脑版电路图", "ECU针脚图"],
            "整车图": ["整车电路图", "整车线路图"],
            "保险丝图": ["保险盒图", "保险丝盒图"],
            "接线图": ["接线盒图", "接线定义图"],
        }
        
        # 品牌补全映射
        self.brand_completion = {
            "天龙": "东风天龙",
            "JH6": "解放JH6",
            "杰狮": "红岩杰狮",
            "豪瀚": "重汽豪瀚",
            "豪汉": "重汽豪汉",
            "欧曼": "福田欧曼",
            "乘龙": "东风乘龙",
        }
    
    def call_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
            model: 模型名称（默认使用配置的模型）
            max_tokens: 最大输出token数（默认使用配置值）
            temperature: 温度参数（默认使用配置值）
            
        Returns:
            LLM返回的文本
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            response = Generation.call(
                model=model or self.model,
                prompt=prompt,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                raise Exception(f"LLM API调用失败: {response.message}")
        
        except Exception as e:
            raise Exception(f"LLM调用异常: {str(e)}")
    
    def build_intent_prompt(self, user_query: str) -> str:
        """
        构建意图理解的Prompt
        
        Args:
            user_query: 用户查询
            
        Returns:
            完整的Prompt文本
        """
        prompt = f"""你是一个智能车辆电路图资料导航助手。请分析用户的查询，提取以下信息：

1. **品牌**：如三一、徐工、东风、解放、重汽、福田、红岩等
2. **型号**：如天龙KL、JH6、杰狮、豪瀚、欧曼ETX、乘龙H7等
3. **电路图类型**：如仪表图、ECU电路图、整车电路图、保险丝图等
4. **车辆类别**：如工程机械、商用车等
5. **其他关键词**：查询中的其他重要信息

用户查询：{user_query}

请以JSON格式返回结果，格式如下：
{{
    "brand": "品牌名称或null",
    "model": "型号名称或null",
    "diagram_type": "电路图类型或null",
    "vehicle_category": "车辆类别或null",
    "keywords": ["关键词1", "关键词2"],
    "confidence": 0.0-1.0之间的数字
}}

注意：
- 如果信息不明确，返回null
- 处理近义词（如"仪表图" = "仪表电路图"）
- 处理模糊表达（如"天龙" = "东风天龙"）
- keywords包含除品牌、型号、类型外的其他重要信息
- 只返回JSON，不要有其他文字说明
"""
        return prompt
    
    def parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        从文本中提取JSON
        
        Args:
            text: 包含JSON的文本
            
        Returns:
            解析后的JSON字典
            
        Raises:
            ValueError: JSON解析失败
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取JSON部分（使用正则表达式）
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            # 尝试解析最长的匹配
            for match in sorted(matches, key=len, reverse=True):
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        raise ValueError(f"无法从文本中提取有效的JSON: {text[:200]}")
    
    def apply_synonyms(self, text: str) -> str:
        """
        应用近义词映射
        
        Args:
            text: 原始文本
            
        Returns:
            应用近义词后的文本
        """
        result = text
        for key, synonyms in self.synonyms.items():
            if key in result:
                # 如果找到关键词，可以替换为第一个同义词，或者保持原样
                # 这里保持原样，因为搜索时会处理同义词
                pass
        return result
    
    def complete_brand(self, brand: Optional[str]) -> Optional[str]:
        """
        补全品牌名称
        
        Args:
            brand: 品牌名称（可能不完整）
            
        Returns:
            补全后的品牌名称
        """
        if not brand:
            return None
        
        # 检查是否需要补全
        for short_name, full_name in self.brand_completion.items():
            if short_name in brand:
                return full_name
        
        return brand
    
    def parse_intent(self, user_query: str) -> IntentResult:
        """
        解析用户意图
        
        Args:
            user_query: 用户查询
            
        Returns:
            意图理解结果
            
        Raises:
            Exception: 解析失败时抛出异常
        """
        if not user_query or not user_query.strip():
            return IntentResult(
                original_query=user_query or "",
                keywords=[user_query] if user_query else []
            )
        
        try:
            # 构建Prompt
            prompt = self.build_intent_prompt(user_query.strip())
            
            # 调用LLM
            response_text = self.call_llm(prompt, max_tokens=500, temperature=0.3)
            
            # 解析JSON
            intent_dict = self.parse_json_from_text(response_text)
            
            # 应用品牌补全
            brand = intent_dict.get("brand")
            if brand:
                brand = self.complete_brand(brand)
            
            # 应用近义词处理
            diagram_type = intent_dict.get("diagram_type")
            if diagram_type:
                diagram_type = self.apply_synonyms(diagram_type)
            
            # 构建IntentResult
            intent_result = IntentResult(
                brand=brand if brand and brand.lower() != "null" else None,
                model=intent_dict.get("model") if intent_dict.get("model") and intent_dict.get("model").lower() != "null" else None,
                diagram_type=diagram_type if diagram_type and diagram_type.lower() != "null" else None,
                vehicle_category=intent_dict.get("vehicle_category") if intent_dict.get("vehicle_category") and intent_dict.get("vehicle_category").lower() != "null" else None,
                keywords=intent_dict.get("keywords", []),
                original_query=user_query.strip(),
                confidence=float(intent_dict.get("confidence", 0.5))
            )
            
            return intent_result
        
        except Exception as e:
            # 如果LLM调用失败，返回基础结果（使用原始查询）
            print(f"⚠️ 意图理解失败: {str(e)}，使用原始查询作为关键词")
            return IntentResult(
                original_query=user_query.strip(),
                keywords=[user_query.strip()],
                confidence=0.0
            )


# 全局LLM服务实例（单例模式）
_llm_service_instance = None


def get_llm_service() -> LLMService:
    """获取LLM服务实例（单例）"""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
