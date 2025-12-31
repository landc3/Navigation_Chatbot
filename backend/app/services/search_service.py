"""
搜索服务模块
提供增强的搜索功能，包括模糊匹配、多关键词搜索、相关性评分等
"""
from typing import List, Dict, Optional, Tuple
import jieba
from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.intent import IntentResult
from backend.app.models.types import ScoredResult, rebuild_scored_result_model
from backend.app.utils.data_loader import get_data_loader
from backend.app.utils.hierarchy_util import HierarchyUtil

# 确保 ScoredResult 模型已重建（解决前向引用问题）
rebuild_scored_result_model()


class SearchService:
    """搜索服务"""
    
    def __init__(self):
        """初始化搜索服务"""
        self.data_loader = get_data_loader()
        # 初始化jieba分词
        jieba.initialize()
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        从查询中提取关键词
        
        Args:
            query: 用户查询字符串
            
        Returns:
            关键词列表
        """
        # 使用jieba分词
        words = jieba.cut(query)
        # 过滤掉停用词和单字符
        keywords = [
            word.strip() 
            for word in words 
            if len(word.strip()) > 1 and word.strip() not in ['的', '了', '是', '在', '和', '与', '或']
        ]
        return keywords if keywords else [query]
    
    def _calculate_match_score(
        self,
        diagram: CircuitDiagram,
        keyword: str,
        is_exact_match: bool = False
    ) -> float:
        """
        计算单个关键词的匹配分数
        
        Args:
            diagram: 电路图对象
            keyword: 关键词
            is_exact_match: 是否为完全匹配
            
        Returns:
            匹配分数
        """
        score = 0.0
        keyword_lower = keyword.lower()
        
        # 完全匹配权重更高
        match_weight = 1.0 if is_exact_match else 0.7
        
        # 1. 文件名称匹配（权重：1.0）
        if keyword_lower in diagram.file_name.lower():
            if keyword_lower == diagram.file_name.lower():
                # 完全匹配文件名称
                score += 1.0 * match_weight * 2.0
            else:
                score += 1.0 * match_weight
        
        # 2. 品牌匹配（权重：0.8）
        if diagram.brand and keyword_lower in diagram.brand.lower():
            if keyword_lower == diagram.brand.lower():
                score += 0.8 * match_weight * 1.5
            else:
                score += 0.8 * match_weight
        
        # 3. 型号匹配（权重：0.9）
        if diagram.model and keyword_lower in diagram.model.lower():
            if keyword_lower == diagram.model.lower():
                score += 0.9 * match_weight * 1.5
            else:
                score += 0.9 * match_weight
        
        # 4. 层级路径匹配（权重：0.5）
        for level in diagram.hierarchy_path:
            if keyword_lower in level.lower():
                if keyword_lower == level.lower():
                    score += 0.5 * match_weight * 1.2
                else:
                    score += 0.5 * match_weight
                break
        
        # 5. 类型匹配（权重：0.6）
        if diagram.diagram_type and keyword_lower in diagram.diagram_type.lower():
            score += 0.6 * match_weight
        
        return score
    
    def _match_keyword(
        self,
        diagram: CircuitDiagram,
        keyword: str,
        use_fuzzy: bool = True
    ) -> Tuple[bool, float]:
        """
        检查电路图是否匹配关键词
        
        Args:
            diagram: 电路图对象
            keyword: 关键词
            use_fuzzy: 是否使用模糊匹配
            
        Returns:
            (是否匹配, 匹配分数)
        """
        keyword_lower = keyword.lower()
        
        # 完全匹配检查
        exact_match = False
        
        # 检查文件名称完全匹配
        if keyword_lower == diagram.file_name.lower():
            exact_match = True
            score = self._calculate_match_score(diagram, keyword, is_exact_match=True)
            return True, score
        
        # 检查层级路径完全匹配
        for level in diagram.hierarchy_path:
            if keyword_lower == level.lower():
                exact_match = True
                score = self._calculate_match_score(diagram, keyword, is_exact_match=True)
                return True, score
        
        # 部分匹配检查
        if use_fuzzy:
            # 在文件名称中搜索
            if keyword_lower in diagram.file_name.lower():
                score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                return True, score
            
            # 在层级路径中搜索
            for level in diagram.hierarchy_path:
                if keyword_lower in level.lower():
                    score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                    return True, score
            
            # 在品牌、型号等字段中搜索
            if diagram.brand and keyword_lower in diagram.brand.lower():
                score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                return True, score
            
            if diagram.model and keyword_lower in diagram.model.lower():
                score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                return True, score
        
        return False, 0.0
    
    def search(
        self,
        query: str,
        logic: str = "AND",
        max_results: int = 5,
        use_fuzzy: bool = True,
        intent_result: Optional[IntentResult] = None
    ) -> List[ScoredResult]:
        """
        搜索电路图
        
        Args:
            query: 搜索查询（支持多关键词）
            logic: 逻辑运算符（"AND" 或 "OR"）
            max_results: 最大返回结果数
            use_fuzzy: 是否使用模糊匹配
            intent_result: 意图理解结果（可选，如果提供则优先使用）
            
        Returns:
            评分后的结果列表（按评分降序）
        """
        if not query or not query.strip():
            return []
        
        # 如果提供了意图理解结果，优先使用意图理解的信息
        if intent_result:
            # 使用意图理解结果构建搜索查询
            search_query = intent_result.get_search_query()
            if search_query and search_query.strip():
                query = search_query.strip()
        
        # 提取关键词
        keywords = self._extract_keywords(query.strip())
        if not keywords:
            return []
        
        # 获取所有数据
        all_diagrams = self.data_loader.get_all()
        
        # 存储每个电路图的匹配信息
        diagram_scores = {}  # {diagram_id: {"matches": [], "total_score": 0.0}}
        
        for diagram in all_diagrams:
            matches = []
            total_score = 0.0
            
            for keyword in keywords:
                matched, score = self._match_keyword(diagram, keyword, use_fuzzy)
                if matched:
                    matches.append(keyword)
                    total_score += score
            
            # 根据逻辑运算符决定是否包含此结果
            if logic.upper() == "AND":
                # AND逻辑：所有关键词都必须匹配
                if len(matches) == len(keywords):
                    diagram_scores[diagram.id] = {
                        "diagram": diagram,
                        "matches": matches,
                        "total_score": total_score
                    }
            else:
                # OR逻辑：至少一个关键词匹配
                if len(matches) > 0:
                    if diagram.id in diagram_scores:
                        # 如果已存在，更新分数（取最大值）
                        diagram_scores[diagram.id]["total_score"] = max(
                            diagram_scores[diagram.id]["total_score"],
                            total_score
                        )
                    else:
                        diagram_scores[diagram.id] = {
                            "diagram": diagram,
                            "matches": matches,
                            "total_score": total_score
                        }
        
        # 转换为ScoredResult列表并排序
        results = [
            ScoredResult(diagram=item["diagram"], score=item["total_score"])
            for item in diagram_scores.values()
        ]
        
        # 如果提供了意图理解结果，调整评分权重
        if intent_result:
            results = self._adjust_scores_by_intent(results, intent_result)
        
        # 按评分降序排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        # 限制结果数量（如果max_results很大，返回所有结果）
        if max_results >= len(results):
            return results
        return results[:max_results]
    
    def _adjust_scores_by_intent(
        self,
        results: List[ScoredResult],
        intent_result: IntentResult
    ) -> List[ScoredResult]:
        """
        根据意图理解结果调整评分
        
        Args:
            results: 搜索结果列表
            intent_result: 意图理解结果
            
        Returns:
            调整后的搜索结果列表
        """
        for result in results:
            diagram = result.diagram
            bonus = 0.0
            
            # 品牌匹配加分
            if intent_result.has_brand() and diagram.brand:
                if intent_result.brand.lower() in diagram.brand.lower() or \
                   diagram.brand.lower() in intent_result.brand.lower():
                    bonus += 0.5
            
            # 型号匹配加分
            if intent_result.has_model() and diagram.model:
                if intent_result.model.lower() in diagram.model.lower() or \
                   diagram.model.lower() in intent_result.model.lower():
                    bonus += 0.6
            
            # 类型匹配加分
            if intent_result.has_diagram_type() and diagram.diagram_type:
                if intent_result.diagram_type.lower() in diagram.diagram_type.lower() or \
                   diagram.diagram_type.lower() in intent_result.diagram_type.lower():
                    bonus += 0.4
            
            # 应用加分
            result.score += bonus
        
        return results
    
    def search_with_intent(
        self,
        intent_result: IntentResult,
        logic: str = "AND",
        max_results: int = 5,
        use_fuzzy: bool = True
    ) -> List[ScoredResult]:
        """
        使用意图理解结果进行搜索
        
        Args:
            intent_result: 意图理解结果
            logic: 逻辑运算符（"AND" 或 "OR"）
            max_results: 最大返回结果数
            use_fuzzy: 是否使用模糊匹配
            
        Returns:
            评分后的结果列表（按评分降序）
        """
        # 构建搜索查询
        query = intent_result.get_search_query()
        
        # 如果意图理解没有提取到信息，使用原始查询
        if not query or query.strip() == "":
            query = intent_result.original_query
        
        return self.search(
            query=query,
            logic=logic,
            max_results=max_results,
            use_fuzzy=use_fuzzy,
            intent_result=intent_result
        )
    
    def filter_by_hierarchy(
        self,
        results: List[ScoredResult],
        brand: Optional[str] = None,
        model: Optional[str] = None,
        diagram_type: Optional[str] = None,
        vehicle_category: Optional[str] = None
    ) -> List[ScoredResult]:
        """
        基于层级路径筛选结果
        
        Args:
            results: 搜索结果列表
            brand: 品牌筛选条件
            model: 型号筛选条件
            diagram_type: 电路图类型筛选条件
            vehicle_category: 车辆类别筛选条件
            
        Returns:
            筛选后的结果列表
        """
        filtered = results
        
        if brand:
            filtered_diagrams = HierarchyUtil.filter_by_brand(
                [r.diagram for r in filtered], brand
            )
            filtered_ids = {d.id for d in filtered_diagrams}
            filtered = [r for r in filtered if r.diagram.id in filtered_ids]
        
        if model:
            filtered_diagrams = HierarchyUtil.filter_by_model(
                [r.diagram for r in filtered], model
            )
            filtered_ids = {d.id for d in filtered_diagrams}
            filtered = [r for r in filtered if r.diagram.id in filtered_ids]
        
        if diagram_type:
            filtered_diagrams = HierarchyUtil.filter_by_diagram_type(
                [r.diagram for r in filtered], diagram_type
            )
            filtered_ids = {d.id for d in filtered_diagrams}
            filtered = [r for r in filtered if r.diagram.id in filtered_ids]
        
        if vehicle_category:
            filtered_diagrams = HierarchyUtil.filter_by_vehicle_category(
                [r.diagram for r in filtered], vehicle_category
            )
            filtered_ids = {d.id for d in filtered_diagrams}
            filtered = [r for r in filtered if r.diagram.id in filtered_ids]
        
        return filtered
    
    def extract_options(
        self,
        results: List[ScoredResult],
        option_type: str,
        max_options: int = 5
    ) -> List[Dict]:
        """
        从搜索结果中提取选项（用于选择题）
        
        Args:
            results: 搜索结果列表
            option_type: 选项类型（"brand", "model", "type", "category"）
            max_options: 最大选项数量
            
        Returns:
            选项列表
        """
        diagrams = [result.diagram for result in results]
        return HierarchyUtil.extract_options(diagrams, option_type, max_options)
    
    def deduplicate_results(self, results: List[ScoredResult]) -> List[ScoredResult]:
        """
        结果去重（基于ID）
        
        Args:
            results: 搜索结果列表
            
        Returns:
            去重后的结果列表（保留评分最高的）
        """
        seen_ids = {}
        
        for result in results:
            diagram_id = result.diagram.id
            if diagram_id not in seen_ids:
                seen_ids[diagram_id] = result
            else:
                # 保留评分更高的结果
                if result.score > seen_ids[diagram_id].score:
                    seen_ids[diagram_id] = result
        
        return list(seen_ids.values())


# 全局搜索服务实例（单例模式）
_search_service_instance = None


def get_search_service() -> SearchService:
    """获取搜索服务实例（单例）"""
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SearchService()
    return _search_service_instance

