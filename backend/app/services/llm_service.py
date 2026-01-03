"""
LLM服务模块
提供通义千问API调用和意图理解功能
"""
import json
import re
from typing import Optional, Dict, Any, List
import dashscope
from dashscope import Generation
from config import Config
from backend.app.models.intent import IntentResult
from backend.app.utils.hierarchy_util import HierarchyUtil


class LLMService:
    """LLM服务"""
    
    def __init__(self):
        """初始化LLM服务"""
        self.api_key = Config.ALI_QWEN_API_KEY
        self.model = Config.ALI_QWEN_MODEL
        self.max_tokens = Config.MAX_TOKENS
        self.temperature = Config.TEMPERATURE
        self.enabled = bool(self.api_key and str(self.api_key).strip())
        
        # 设置API Key（未配置时允许降级为“无 LLM”模式）
        if self.enabled:
            dashscope.api_key = self.api_key
        else:
            print("⚠️  未配置 ALI_QWEN_API_KEY：将以无 LLM 模式运行（意图理解/问题生成会降级）")
        
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
        if not self.enabled:
            raise Exception("ALI_QWEN_API_KEY 未设置，LLM 功能不可用")
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
   **重要**：如果用户说"东风天龙"、"东风天龙XXX"，brand字段应该设置为"东风天龙"（完整品牌），而不是"东风"
   **重要**：如果用户说"天龙"，应该理解为"东风天龙"品牌
   **重要**：复合品牌（如"东风天龙"、"一汽解放"）应该作为完整的brand返回，不要拆分

2. **型号**：如天龙KL、JH6、杰狮、豪瀚、欧曼ETX、乘龙H7等
   **注意**：如果用户说"东风天龙"，这是品牌，不是型号

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
- **关键规则**：如果用户查询包含"东风天龙"，brand必须设置为"东风天龙"，不能只设置为"东风"
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

            # --- Guardrail: sanitize/validate diagram_type extracted by LLM ---
            # Some LLM responses mistakenly put the whole query into diagram_type
            # (e.g. "VGT线路图"). This later triggers hierarchy filtering and
            # can incorrectly drop valid matches.
            keywords_from_llm = intent_dict.get("keywords", []) or []
            diagram_type, keywords_from_type = self._sanitize_diagram_type(diagram_type, user_query.strip())
            # merge back to keywords
            merged_keywords = []
            for x in list(keywords_from_llm) + list(keywords_from_type):
                s = (str(x) or "").strip()
                if not s:
                    continue
                merged_keywords.append(s)
            
            # 构建IntentResult
            intent_result = IntentResult(
                brand=brand if brand and brand.lower() != "null" else None,
                model=intent_dict.get("model") if intent_dict.get("model") and intent_dict.get("model").lower() != "null" else None,
                diagram_type=diagram_type if diagram_type and diagram_type.lower() != "null" else None,
                vehicle_category=intent_dict.get("vehicle_category") if intent_dict.get("vehicle_category") and intent_dict.get("vehicle_category").lower() != "null" else None,
                keywords=merged_keywords,
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

    @staticmethod
    def _sanitize_diagram_type(diagram_type: Optional[str], user_query: str) -> tuple[Optional[str], List[str]]:
        """
        Validate/normalize diagram_type.

        - Only accept known diagram types (or a known type substring within the extracted value).
        - If the extracted value contains extra tokens (e.g. "VGT线路图"), extract the known type
          and return the remaining tokens as extra keywords.
        """
        if not diagram_type:
            return None, []

        dt_raw = str(diagram_type).strip()
        if not dt_raw:
            return None, []

        # Known types (include synonym-family roots; keep longest-first matching)
        candidates = list(dict.fromkeys(HierarchyUtil.COMMON_DIAGRAM_TYPES))
        candidates.sort(key=len, reverse=True)

        # If LLM returns the whole query or an overly long string, try to extract a known type.
        extra_keywords: List[str] = []
        best = None
        for c in candidates:
            if c and c in dt_raw:
                best = c
                break
        if best is None:
            # also try in user query (sometimes dt_raw is garbage encoding)
            for c in candidates:
                if c and c in (user_query or ""):
                    best = c
                    break

        if best is not None:
            # Anything besides the best type is treated as keyword
            rest = dt_raw.replace(best, " ").strip()
            # Extract short uppercase/number codes like VGT/KL/C81 from the remaining string
            for m in re.findall(r"[A-Z]{2,5}\d{0,4}", (rest or "").upper()):
                if m and m not in extra_keywords:
                    extra_keywords.append(m)
            return best, extra_keywords

        # If it's not a known type, drop it. (Avoid later hierarchy filtering.)
        return None, []
    
    def build_question_prompt(
        self,
        option_type: str,
        options: list,
        total_count: int,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建问题生成的Prompt
        
        Args:
            option_type: 选项类型（"brand", "model", "type", "category"）
            options: 选项列表，格式：[{"name": "选项名", "count": 数量}, ...]
            total_count: 总结果数
            context: 对话上下文（可选）
            
        Returns:
            完整的Prompt文本
        """
        # 选项类型名称映射
        type_mapping = {
            "brand": "品牌",
            "model": "型号",
            "type": "电路图类型",
            "category": "车辆类别",
            "brand_model": "系列"
        }
        option_type_name = type_mapping.get(option_type, "选项")
        
        # 格式化选项列表
        options_text = ""
        for i, option in enumerate(options, 1):
            options_text += f"{i}. {option['name']} ({option['count']}个结果)\n"
        
        # 构建上下文信息
        context_info = ""
        if context:
            if context.get("filter_history"):
                filters = context["filter_history"]
                if filters:
                    filter_texts = []
                    for f in filters[-2:]:  # 只显示最近2个筛选条件
                        filter_type = f.get("type", "")
                        filter_value = f.get("value", "")
                        filter_type_name = type_mapping.get(filter_type, filter_type)
                        filter_texts.append(f"{filter_type_name}: {filter_value}")
                    if filter_texts:
                        context_info = f"用户已选择：{', '.join(filter_texts)}\n"
        
        prompt = f"""你是一个智能车辆电路图资料导航助手。请根据以下信息生成一个自然、简洁的选择题问题。

**当前情况**：
- 找到了 {total_count} 个相关结果
- 需要用户选择{option_type_name}来缩小范围

**可选选项**：
{options_text}

**对话上下文**：
{context_info if context_info else "这是第一次提问"}

**重要要求**：
1. 问题必须简洁明确，不超过30字
2. 严格按照以下示例风格生成问题：
   - **第一次提问（品牌或品牌+型号）**：必须使用格式："我找到了[品牌/关键词]相关的电路图。请问您需要的是："
     示例："我找到了东风天龙相关的电路图。请问您需要的是："
   - **第二次提问（型号）**：必须使用格式："明白了。请问您需要的是哪种型号："
   - **第二次提问（类型）**：必须使用格式："明白了。请问您需要的是哪种类型的仪表电路图："
3. 不要包含选项列表（选项会单独显示）
4. 不要包含结果数量信息（如"找到了9个结果"）
5. 不要包含选项字母（A/B/C/D）
6. 问题应该引导用户从选项中选择
7. 如果这是第一次提问且选项类型是brand_model，从当前查询中提取品牌信息，使用格式："我找到了[品牌]相关的电路图。请问您需要的是："
8. 如果这是后续提问，使用格式："明白了。请问您需要的是..."

**示例**：
- 第一次提问（brand_model）："我找到了东风相关的电路图。请问您需要的是："
- 第二次提问（type）："明白了。请问您需要的是哪种类型的仪表电路图："

只返回问题文本，不要包含其他内容。"""
        return prompt
    
    def generate_question_text(
        self,
        option_type: str,
        options: list,
        total_count: int,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        使用LLM生成问题文本
        
        Args:
            option_type: 选项类型（"brand", "model", "type", "category"）
            options: 选项列表，格式：[{"name": "选项名", "count": 数量}, ...]
            total_count: 总结果数
            context: 对话上下文（可选）
            
        Returns:
            生成的问题文本
            
        Raises:
            Exception: LLM调用失败时抛出异常
        """
        if not options:
            return "请选择您需要的选项："
        
        try:
            # 构建Prompt
            prompt = self.build_question_prompt(option_type, options, total_count, context)
            
            # 调用LLM（使用较低的温度，确保生成的问题稳定）
            response_text = self.call_llm(prompt, max_tokens=100, temperature=0.5)
            
            # 清理响应文本（移除可能的引号、换行等）
            question_text = response_text.strip()
            # 移除可能的引号
            if question_text.startswith('"') and question_text.endswith('"'):
                question_text = question_text[1:-1]
            if question_text.startswith("'") and question_text.endswith("'"):
                question_text = question_text[1:-1]
            
            return question_text
        
        except Exception as e:
            # 如果LLM调用失败，使用默认模板
            print(f"⚠️ 问题生成失败: {str(e)}，使用默认模板")
            type_mapping = {
                "brand": "品牌",
                "model": "型号",
                "type": "电路图类型",
                "category": "车辆类别"
            }
            type_name = type_mapping.get(option_type, "选项")
            return f"找到了 {total_count} 个相关结果。请选择您需要的{type_name}："


# 全局LLM服务实例（单例模式）
_llm_service_instance = None


def get_llm_service() -> LLMService:
    """获取LLM服务实例（单例）"""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
