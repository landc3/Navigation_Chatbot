"""
问题生成服务模块
根据搜索结果生成选择题，引导用户缩小范围
"""
from typing import List, Dict, Optional, Any
import re
import string
from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.types import ScoredResult, rebuild_scored_result_model
from backend.app.services.search_service import get_search_service
from backend.app.services.llm_service import get_llm_service

# 确保 ScoredResult 模型已重建（解决前向引用问题）
rebuild_scored_result_model()


class QuestionService:
    """问题生成服务"""
    
    def __init__(self):
        """初始化问题生成服务"""
        self.search_service = get_search_service()
        self.llm_service = get_llm_service()

    @staticmethod
    def _make_option_labels(n: int) -> List[str]:
        """
        生成足够数量的选项标签：A..Z, AA..AZ, BA..BZ...
        """
        if n <= 0:
            return []
        letters = string.ascii_uppercase

        def idx_to_label(idx: int) -> str:
            # Excel-style column naming (0-based)
            out = ""
            x = idx
            while True:
                x, rem = divmod(x, 26)
                out = letters[rem] + out
                if x == 0:
                    break
                x -= 1
            return out

        return [idx_to_label(i) for i in range(n)]
    
    def generate_question(
        self,
        results: List[ScoredResult],
        min_options: int = 2,
        max_options: int = 5,
        excluded_types: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        use_llm: bool = True
    ) -> Optional[Dict]:
        """
        根据搜索结果生成选择题
        
        Args:
            results: 搜索结果列表
            min_options: 最少选项数
            max_options: 最多选项数
            excluded_types: 要排除的选项类型列表（如：["brand", "model"]），用于跳过已经选择的类型
            context: 对话上下文（可选），包含filter_history等信息
            use_llm: 是否使用LLM生成问题文本（默认True）
            
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
        
        # 按优先级尝试生成问题：车型变体(variant) -> 品牌+型号组合 -> 品牌 -> 配置 -> 型号 -> 类型 -> 类别
        # 如果用户已经选择了品牌，尝试使用品牌+型号组合
        option_types = []
        
        # 检查是否已经选择了品牌和类型
        has_brand_filter = False
        has_type_filter = False
        if excluded_types:
            has_brand_filter = "brand" in excluded_types
            has_type_filter = "type" in excluded_types
        
        # 若用户输入形如“天龙KL电路图”，首轮优先按“车型变体前缀”分组（更符合业务期望）
        current_query = (context or {}).get("current_query") or ""
        has_diagram_kw = ("电路图" in current_query) or ("电路" in current_query and "图" in current_query)
        # series code: KL/KC/VL... ; ecu/code: C81 / EDC17C81 ...
        has_ecu_code = bool(re.search(r"[A-Za-z]{1,6}\d{1,3}", current_query))
        has_series_code = bool(re.search(r"[A-Z]{2,3}", current_query)) and not has_ecu_code

        # 如果已经选择了品牌和类型，优先询问系列（品牌后面的层级），其次询问配置/轴型
        force_hierarchy_extraction = False
        if has_brand_filter and has_type_filter:
            # 用户已经指定了品牌和类型，必须询问系列（如KL、KC等）
            # 只尝试brand_model类型，不允许fallback到其他类型
            option_types = ["brand_model", "config"]
            # 强制使用层级路径提取，不允许使用标准方法
            force_hierarchy_extraction = True
        elif has_brand_filter:
            # 用户已经选择了品牌，优先询问系列，然后才是类型
            option_types = ["brand_model", "config", "model", "type", "category"]
        else:
            # 否则，先尝试单一维度，如果单一维度选项不足，再尝试组合维度
            # 优先尝试品牌+型号组合，因为这样可以从层级路径中提取更精确的选项
            option_types = ["brand_model", "brand", "config", "model", "type", "category"]

        # “代号/系列码 + 电路图”场景：把 variant 放到最前面（并避免被 excluded_types 过滤）
        if has_diagram_kw and (has_series_code or has_ecu_code):
            if not excluded_types or "variant" not in excluded_types:
                option_types = ["variant"] + [t for t in option_types if t != "variant"]
        
        # 如果指定了要排除的类型，跳过它们
        if excluded_types:
            option_types = [opt_type for opt_type in option_types if opt_type not in excluded_types]

        # 类型直返规则（关键）：如果候选的“diagram_type”只有一种，就不要再问类型，直接问下一维度
        # 这能避免“明明都只有整车电路图，却还在问你要哪种类型”的低效澄清。
        if "type" in option_types:
            unique_types = {r.diagram.diagram_type for r in results if getattr(r.diagram, "diagram_type", None)}
            if len(unique_types) <= 1:
                option_types = [t for t in option_types if t != "type"]
        
        # 如果所有类型都被排除了，返回 None
        if not option_types:
            return None
        
        for option_type in option_types:
            # 双重检查：确保当前类型不在排除列表中
            if excluded_types and option_type in excluded_types:
                continue
            
            # 特殊处理：variant/brand_model/config 需要特殊提取逻辑
            if option_type == "variant":
                options = self._extract_variant_options(results, max_options=max_options, context=context)
            elif option_type == "brand_model":
                # 优先从层级路径中提取品牌+系列组合
                options = self._extract_options_from_hierarchy(results, max_options, context)
                print(f"🔍 _extract_options_from_hierarchy返回选项数: {len(options) if options else 0}")
                # 如果提取失败，且不是强制层级提取，使用标准方法
                if not options or len(options) < min_options:
                    if not force_hierarchy_extraction:
                        print(f"⚠️ 层级提取失败，尝试标准方法")
                        options = self._extract_brand_model_options(results, max_options)
                        print(f"🔍 _extract_brand_model_options返回选项数: {len(options) if options else 0}")
                    else:
                        # 强制层级提取时，如果失败，尝试更激进的提取策略
                        print(f"⚠️ 强制层级提取失败，尝试更激进的提取策略")
                        # 尝试从所有层级路径中提取系列代码，不限制位置
                        options = self._extract_series_codes_aggressive(results, max_options, context)
                        print(f"🔍 激进提取返回选项数: {len(options) if options else 0}")
                        # 如果激进提取也失败，至少尝试从文件名中提取
                        if not options or len(options) < min_options:
                            print(f"⚠️ 激进提取也失败，尝试从文件名提取系列代码")
                            options = self._extract_series_from_filenames(results, max_options, context)
                            print(f"🔍 文件名提取返回选项数: {len(options) if options else 0}")
            elif option_type == "type":
                # 关键修复：
                # - “type” 必须按当前候选集的 diagram_type 进行**分桶**（每条数据只属于一个桶），
                #   否则会出现“选项显示4条，但点进去变33条”的严重不一致。
                options = self._extract_disjoint_type_options(results, max_options=max_options)
            elif option_type == "config":
                options = self._extract_config_variants(results, max_options=max_options, context=context)
            else:
                options = self.search_service.extract_options(
                    results,
                    option_type,
                    max_options=max_options
                )
            
            # 如果选项数量不足，尝试从层级路径中提取选项
            if not options or len(options) < min_options:
                if option_type == "variant":
                    # variant 没有更好的回退策略，交给后续 option_type 继续尝试
                    pass
                elif option_type == "brand_model":
                    # 尝试从层级路径中提取品牌+层级组合
                    options = self._extract_options_from_hierarchy(results, max_options, context)
                elif option_type == "type":
                    # 对于类型，尝试提取类型变体
                    options = self._extract_type_variants(results, max_options, context)
                elif option_type in ["brand", "model", "category"]:
                    # 对于其他类型，也尝试从层级路径中提取
                    try:
                        hierarchy_options = self._extract_options_from_hierarchy(results, max_options, context)
                        if hierarchy_options and len(hierarchy_options) >= min_options:
                            # 如果层级提取成功，使用层级选项
                            options = hierarchy_options
                            option_type = "brand_model"  # 更新选项类型
                    except:
                        pass
            
            # 优化选项（去重、排序）
            # IMPORTANT: options may already carry exact ids. When ids are present,
            # we must keep count == len(ids) and ensure “其他”闭合。
            options = self._finalize_options_with_ids(
                option_type=option_type,
                options=options,
                results=results,
                max_options=max_options,
                context=context,
            )
            
            # 检查选项数量是否足够
            if options and len(options) >= min_options:
                # 使用LLM生成问题文本（如果启用）
                if use_llm:
                    try:
                        question_text = self.llm_service.generate_question_text(
                            option_type=option_type,
                            options=options,
                            total_count=len(results),
                            context=context
                        )
                    except Exception as e:
                        print(f"⚠️ LLM生成问题失败: {str(e)}，使用默认模板")
                        question_text = self._generate_question_text(option_type, len(results), context)
                else:
                    question_text = self._generate_question_text(option_type, len(results), context)
                
                option_labels = self._make_option_labels(min(max_options, len(options)))
                formatted_options = []
                for i, option in enumerate(options[:max_options]):
                    formatted_options.append({
                        "label": option_labels[i],
                        "name": option['name'],
                        "count": int(option.get("count") or 0),
                        "type": option_type,
                        # Optional: exact ids for this bucket (used for precise filtering)
                        "ids": option.get("ids") if isinstance(option, dict) else None,
                    })
                
                return {
                    "question": question_text,
                    "options": formatted_options,
                    "option_type": option_type
                }
        
        # 如果无法生成问题，尝试最后的fallback：从层级路径中提取任意有区分度的选项
        if not results or len(results) < min_options:
            return None
        
        # 最后的fallback：从层级路径中提取品牌+型号组合
        try:
            fallback_options = self._extract_options_from_hierarchy(results, max_options, context)
            if fallback_options and len(fallback_options) >= min_options:
                # 使用默认模板生成问题
                question_text = self._generate_question_text("brand_model", len(results), context)
                
                option_labels = self._make_option_labels(min(max_options, len(fallback_options)))
                formatted_options = []
                for i, option in enumerate(fallback_options[:max_options]):
                    formatted_options.append({
                        "label": option_labels[i],
                        "name": option['name'],
                        "count": option['count'],
                        "type": "brand_model"
                    })
                
                return {
                    "question": question_text,
                    "options": formatted_options,
                    "option_type": "brand_model"
                }
        except Exception as e:
            print(f"⚠️ Fallback选项提取失败: {str(e)}")
        
        # 如果所有方法都失败，返回None
        return None

    def _extract_disjoint_type_options(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
    ) -> List[Dict]:
        """
        Disjoint type buckets based on diagram.diagram_type.
        Each diagram belongs to at most one bucket.
        """
        type_to_ids: Dict[str, set] = {}
        for r in results:
            d = r.diagram
            t = (getattr(d, "diagram_type", None) or "").replace("*", "").strip()
            if not t:
                t = "其他（未标注类型）"
            type_to_ids.setdefault(t, set()).add(d.id)
        options = [{"name": k, "count": len(v), "ids": sorted(v)} for k, v in type_to_ids.items()]
        options.sort(key=lambda x: (-x["count"], x["name"]))
        return options[: max(1, max_options * 5)]

    def _finalize_options_with_ids(
        self,
        option_type: str,
        options: List[Dict],
        results: List[ScoredResult],
        max_options: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """
        Normalize/merge options and ensure:
        - each option has ids
        - count == len(ids)
        - append “其他（未分类/更多）” to close coverage when truncated
        """
        if not options:
            return []

        # Build mapping name -> ids (prefer provided ids; otherwise compute via disjoint field buckets)
        all_ids = {r.diagram.id for r in results}

        def norm_name(s: str) -> str:
            if not s:
                return ""
            s = str(s).replace("*", "").strip()
            s = re.sub(r"\s+", " ", s)
            s = re.sub(r"(系列)\s*(系列)+", r"\1", s)
            return s.strip()

        merged: Dict[str, set] = {}

        # Fast paths: if options already have ids, just merge by normalized name
        has_any_ids = any(isinstance(o, dict) and isinstance(o.get("ids"), list) for o in options)
        if has_any_ids:
            for o in options:
                name = norm_name(o.get("name"))
                ids = o.get("ids") or []
                if not name:
                    continue
                merged.setdefault(name, set()).update(ids)
        else:
            # Fallback: compute ids from parsed fields for disjoint types where possible
            # brand/model/category/brand_model use parsed fields => disjoint buckets, stable counts
            opt = (option_type or "").strip().lower()
            if opt in ("brand", "model", "category", "vehicle_category", "brand_model", "brand+model"):
                for r in results:
                    d = r.diagram
                    if opt == "brand":
                        key = (d.brand or "").strip() or "其他（未标注品牌）"
                    elif opt == "model":
                        key = (d.model or "").strip() or "其他（未标注型号/系列）"
                    elif opt in ("category", "vehicle_category"):
                        key = (getattr(d, "vehicle_category", None) or "").strip() or "其他（未标注类别）"
                    else:
                        b = (d.brand or "").strip()
                        m = (d.model or "").strip()
                        if b and m:
                            key = f"{b} {m}"
                        elif b:
                            key = b
                        elif m:
                            key = m
                        else:
                            key = "其他（未标注品牌/型号）"
                    key = norm_name(key)
                    merged.setdefault(key, set()).add(d.id)
            elif opt == "type":
                for r in results:
                    d = r.diagram
                    key = (getattr(d, "diagram_type", None) or "").strip() or "其他（未标注类型）"
                    key = norm_name(key)
                    merged.setdefault(key, set()).add(d.id)
            else:
                # Unknown: keep original counts, but without ids we cannot guarantee consistency
                # (still better to return as-is)
                return self.optimize_options(options, max_options)

        # Convert to list with ids
        items = [{"name": k, "ids": sorted(v), "count": len(v)} for k, v in merged.items() if k]
        items.sort(key=lambda x: (-x["count"], x["name"]))

        # Remove non-discriminating buckets: options that cover the entire candidate set
        # These lead to "23 → 23" no-op selections and can trap users in non-converging loops.
        if all_ids:
            items = [it for it in items if set(it.get("ids") or []) != all_ids]

        # Apply truncation with “其他” closure (only when there are more than max_options buckets)
        if max_options <= 0:
            return []

        if len(items) <= max_options:
            return items

        head_limit = max_options - 1 if max_options >= 3 else max_options
        head = items[:head_limit]
        used = set()
        for it in head:
            used |= set(it["ids"])
        rest = all_ids - used
        if rest and head_limit < max_options:
            head.append({"name": "其他（未分类/更多）", "ids": sorted(rest), "count": len(rest)})
        head.sort(key=lambda x: (-x["count"], x["name"]))
        return head[:max_options]

    def _extract_config_variants(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        提取“配置/轴型/用途”等选项（如 4x2/6x2/6x4 + 牵引车/载货车/自卸车/环卫车 等）
        用于第二层澄清。
        """
        import re
        from backend.app.services.search_service import SearchService

        def norm(s: str) -> str:
            return SearchService._norm_text(s)

        role_keywords = ["牵引车", "载货车", "自卸车", "环卫车", "搅拌车", "专用车", "厢式", "工程车", "冷藏车"]
        options: Dict[str, int] = {}

        for r in results:
            d = r.diagram
            text = " ".join([d.file_name or ""] + (d.hierarchy_path or []))
            t = norm(text)
            if not t:
                continue

            # 轴型/驱动：4x2 / 6x2 / 6x4 / 8x4 等
            axle = None
            m = re.search(r"(\d)\s*[xX]\s*(\d)", text)
            if m:
                axle = f"{m.group(1)}x{m.group(2)}"
            else:
                # 兼容 “6X4”写法（大小写）
                m2 = re.search(r"(\d)\s*[Xx]\s*(\d)", text)
                if m2:
                    axle = f"{m2.group(1)}x{m2.group(2)}"

            role = None
            for kw in role_keywords:
                if norm(kw) in t:
                    role = kw
                    break

            if axle and role:
                name = f"{axle} {role}"
            elif axle:
                name = axle
            elif role:
                name = role
            else:
                continue

            options[name] = options.get(name, 0) + 1

        out = [{"name": k, "count": v} for k, v in options.items()]
        out.sort(key=lambda x: (-x["count"], x["name"]))
        return out[:max_options]
    
    def _extract_brand_model_options(
        self,
        results: List[ScoredResult],
        max_options: int = 5
    ) -> List[Dict]:
        """
        提取品牌+型号组合选项
        
        Args:
            results: 搜索结果列表
            max_options: 最大选项数量
            
        Returns:
            选项列表
        """
        from backend.app.utils.hierarchy_util import HierarchyUtil
        
        diagrams = [result.diagram for result in results]
        return HierarchyUtil.extract_options(diagrams, "brand_model", max_options)
    
    def _extract_options_from_hierarchy(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        从层级路径中提取选项（用于生成选择题）
        优先提取品牌后面的系列信息（如KL、KC等）
        
        Args:
            results: 搜索结果列表
            max_options: 最大选项数量
            
        Returns:
            选项列表
        """
        from backend.app.utils.hierarchy_util import HierarchyUtil
        
        diagrams = [result.diagram for result in results]
        option_counts: Dict[str, int] = {}
        option_ids: Dict[str, set] = {}
        
        # 从上下文中获取用户意图的品牌（可能是复合品牌）
        user_brand = None
        if context and context.get("intent_result"):
            user_brand = context["intent_result"].get("brand")
        elif context and context.get("filter_history"):
            for filter_item in context["filter_history"]:
                if filter_item.get("type") == "brand":
                    user_brand = filter_item.get("value")
                    break
        
        for diagram in diagrams:
            # 查找品牌在层级路径中的位置（支持复合品牌）
            brand_pos = -1
            series_pos = -1
            
            # 首先尝试使用用户意图的品牌（可能是复合品牌）
            if user_brand:
                # 如果用户品牌是复合品牌（如"东风天龙"），尝试匹配层级路径
                if user_brand in HierarchyUtil.COMPOUND_BRANDS:
                    # 提取基础品牌（如"东风"）
                    base_brand = None
                    series_keyword = None
                    if "东风" in user_brand:
                        base_brand = "东风"
                        if "天龙" in user_brand:
                            series_keyword = "天龙"
                    elif "解放" in user_brand:
                        base_brand = "解放"
                    elif "重汽" in user_brand:
                        base_brand = "重汽"
                    elif "福田" in user_brand:
                        base_brand = "福田"
                    elif "红岩" in user_brand:
                        base_brand = "红岩"
                    
                    # 在层级路径中查找基础品牌
                    if base_brand:
                        for i, level in enumerate(diagram.hierarchy_path):
                            if base_brand in level or level == base_brand:
                                brand_pos = i
                                # 如果找到了基础品牌，查找包含系列关键词的层级
                                if series_keyword:
                                    for j in range(i + 1, len(diagram.hierarchy_path)):
                                        if series_keyword in diagram.hierarchy_path[j]:
                                            series_pos = j
                                            break
                                break
                else:
                    # 如果不是复合品牌，直接匹配
                    for i, level in enumerate(diagram.hierarchy_path):
                        if user_brand in level or level == user_brand:
                            brand_pos = i
                            break
            
            # 如果没有找到，使用diagram.brand（可能是从层级路径解析出来的）
            if brand_pos == -1 and diagram.brand:
                for i, level in enumerate(diagram.hierarchy_path):
                    if diagram.brand in level or level == diagram.brand:
                        brand_pos = i
                        break
            
            # 确定要提取的层级位置
            # 层级路径结构：电路图 -> 类型 -> 品牌 -> 系列层级 -> 具体系列（如天龙KL） -> ...
            extract_pos = -1
            if brand_pos != -1:
                # 查找品牌后面的层级，优先查找包含系列代码的层级
                # 先查找"系列"相关的层级（如"天龙*系列"或"天龙KL系列"）
                for i in range(brand_pos + 1, len(diagram.hierarchy_path)):
                    level = diagram.hierarchy_path[i]
                    level_clean = level.replace('*', '').strip()
                    
                    # 如果层级包含"系列"关键词，优先使用
                    if "系列" in level_clean:
                        # 检查当前层级是否包含系列代码（如"天龙KL系列"）
                        series_match = re.search(r'([A-Z]{2,3})', level_clean)
                        if series_match:
                            potential_code = series_match.group(1)
                            if potential_code not in ['ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 'DOCX', 'VECU', 'BCM']:
                                extract_pos = i
                                break
                        # 如果当前层级不包含系列代码，检查下一层
                        if i + 1 < len(diagram.hierarchy_path):
                            next_level = diagram.hierarchy_path[i + 1]
                            next_level_clean = next_level.replace('*', '').strip()
                            # 如果下一层包含系列代码（如KL、KC等），使用下一层
                            series_match = re.search(r'([A-Z]{2,3})', next_level_clean)
                            if series_match:
                                potential_code = series_match.group(1)
                                if potential_code not in ['ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 'DOCX', 'VECU', 'BCM']:
                                    extract_pos = i + 1
                                    break
                        # 否则使用当前层级
                        if extract_pos == -1:
                            extract_pos = i
                        break
                    
                    # 如果层级包含"天龙"且包含系列代码（如"天龙KL"）
                    if user_brand and "天龙" in user_brand and "天龙" in level_clean:
                        series_match = re.search(r'([A-Z]{2,3})', level_clean)
                        if series_match:
                            potential_code = series_match.group(1)
                            if potential_code not in ['ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 'DOCX', 'VECU', 'BCM']:
                                extract_pos = i
                                break
                
                # 如果没有找到系列层级，查找品牌后面第一个包含系列代码的层级
                if extract_pos == -1:
                    for i in range(brand_pos + 1, len(diagram.hierarchy_path)):
                        level = diagram.hierarchy_path[i]
                        level_clean = level.replace('*', '').strip()
                        # 跳过类型相关的层级
                        type_keywords = ['电路图', '仪表', 'ECU', '整车', '线路', '针脚', '模块']
                        if any(keyword in level_clean for keyword in type_keywords):
                            continue
                        # 检查是否包含系列代码
                        series_match = re.search(r'([A-Z]{2,3})', level_clean)
                        if series_match:
                            potential_code = series_match.group(1)
                            if potential_code not in ['ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 'DOCX', 'VECU', 'BCM']:
                                extract_pos = i
                                break
                
                # 如果仍然没有找到，使用品牌后面的第一个非类型层级
                if extract_pos == -1 and brand_pos + 1 < len(diagram.hierarchy_path):
                    for i in range(brand_pos + 1, len(diagram.hierarchy_path)):
                        level = diagram.hierarchy_path[i]
                        level_clean = level.replace('*', '').strip()
                        # 跳过类型相关的层级
                        type_keywords = ['电路图', '仪表', 'ECU', '整车', '线路', '针脚', '模块']
                        if not any(keyword in level_clean for keyword in type_keywords):
                            extract_pos = i
                            break
            
            # 提取系列信息
            if extract_pos != -1 and extract_pos < len(diagram.hierarchy_path):
                level_value = diagram.hierarchy_path[extract_pos]
                # 清理层级值（去除特殊字符）
                level_value_clean = level_value.replace('*', '').strip()
                
                # 跳过类型相关的层级
                type_keywords = ['电路图', '仪表', 'ECU', '整车', '线路', '针脚', '模块']
                if any(keyword in level_value_clean for keyword in type_keywords):
                    # 如果层级值包含类型关键词，尝试提取更后面的层级
                    if extract_pos + 1 < len(diagram.hierarchy_path):
                        level_value = diagram.hierarchy_path[extract_pos + 1]
                        level_value_clean = level_value.replace('*', '').strip()
                
                # 提取系列代码（如KL、KC、VL等）
                # 尝试从多个来源提取系列信息
                series_code = None
                
                # 定义需要排除的非系列代码关键词（文件扩展名、ECU类型等）
                excluded_codes = [
                    'ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 
                    'DOCX', 'VECU', 'BCM', 'PDF', 'XLS', 'XLSX', 'PPT', 'PPTX',
                    'D31', 'D32', 'D53', 'D56', 'ABS', 'ESP', 'TCS', 'EBD',
                    'CAN', 'LIN', 'MOST', 'FLEX', 'KWP', 'UDS', 'OBD'
                ]
                
                # 1. 优先从层级值中提取系列代码（如"天龙KL" -> "KL"）
                if level_value_clean:
                    # 如果层级值包含品牌名称（如"天龙"），提取后面的系列代码
                    if user_brand and "天龙" in user_brand:
                        # 查找"天龙"后面的系列代码
                        if "天龙" in level_value_clean:
                            after_tianlong = level_value_clean.split("天龙", 1)[1] if "天龙" in level_value_clean else level_value_clean
                            # 提取系列代码（优先匹配2-3个大写字母，如KL、KC、VL）
                            series_match = re.search(r'([A-Z]{2,3})', after_tianlong)
                            if series_match:
                                potential_code = series_match.group(1)
                                if potential_code not in excluded_codes:
                                    series_code = potential_code
                    
                    # 直接查找2-3个大写字母（系列代码，如KL、KC、VL）
                    if not series_code:
                        # 优先匹配2-3个大写字母（系列代码通常是2-3个字母）
                        series_match = re.search(r'([A-Z]{2,3})', level_value_clean)
                        if series_match:
                            potential_code = series_match.group(1)
                            # 排除常见的非系列代码
                            if potential_code not in excluded_codes:
                                series_code = potential_code
                    
                    # 如果层级值包含"系列"关键词，尝试提取系列名称
                    if "系列" in level_value_clean and not series_code:
                        # 提取"系列"前面的部分作为系列名称
                        series_part = level_value_clean.split("系列")[0].strip()
                        if series_part and len(series_part) <= 10:
                            # 检查是否是系列代码格式（2-3个大写字母）
                            series_match = re.search(r'([A-Z]{2,3})', series_part)
                            if series_match:
                                potential_code = series_match.group(1)
                                if potential_code not in excluded_codes:
                                    series_code = potential_code
                            else:
                                # 如果不是系列代码格式，使用整个部分
                                series_code = series_part
                
                # 2. 如果从层级路径中提取不到，尝试从文件名中提取（但要排除文件扩展名）
                if not series_code and diagram.file_name:
                    file_name = diagram.file_name
                    # 去除文件扩展名（.DOCX、.PDF等）
                    file_name_without_ext = re.sub(r'\.[A-Z]{2,5}$', '', file_name, flags=re.IGNORECASE)
                    
                    # 查找文件名中的系列代码（如"东风天龙KL..." -> "KL"）
                    # 先查找品牌后面的部分
                    if user_brand:
                        brand_in_file = user_brand
                    elif diagram.brand:
                        brand_in_file = diagram.brand
                    else:
                        brand_in_file = "东风"
                    
                    if brand_in_file in file_name_without_ext:
                        after_brand = file_name_without_ext.split(brand_in_file, 1)[1] if brand_in_file in file_name_without_ext else file_name_without_ext
                        # 提取2-3个大写字母（系列代码）
                        # 只检查品牌后面的前30个字符，避免提取到文件扩展名或ECU类型
                        series_match = re.search(r'([A-Z]{2,3})', after_brand[:30])
                        if series_match:
                            potential_code = series_match.group(1)
                            # 排除文件扩展名和ECU类型
                            if potential_code not in excluded_codes:
                                series_code = potential_code
                
                # 3. 如果提取到了系列代码，生成选项
                if series_code:
                    display_brand = user_brand if user_brand else (diagram.brand or "东风")
                    option_name = f"{display_brand} {series_code} 系列"
                    option_counts[option_name] = option_counts.get(option_name, 0) + 1
                    option_ids.setdefault(option_name, set()).add(diagram.id)
                elif level_value_clean and level_value_clean != diagram.brand and len(level_value_clean) <= 15:
                    # 如果没有提取到系列代码，但层级值有意义，使用层级值
                    # 跳过类型相关的层级
                    type_keywords = ['电路图', '仪表', 'ECU', '整车', '线路', '针脚', '模块']
                    if not any(keyword in level_value_clean for keyword in type_keywords):
                        display_brand = user_brand if user_brand else (diagram.brand or "东风")
                        option_name = f"{display_brand} {level_value_clean}"
                        option_counts[option_name] = option_counts.get(option_name, 0) + 1
                        option_ids.setdefault(option_name, set()).add(diagram.id)
        
        # 关键修复：
        # - 为每个选项携带精确 ids，后续筛选直接按 ids 过滤，避免 “选NT却混入MT/N” 的不精确问题
        # - 加入 “其他/未分类” 桶，让选项 count 能覆盖上一轮总数（即使被 max_options 截断）

        # 先按 count 排序
        sorted_names = [n for n, _ in sorted(option_counts.items(), key=lambda x: x[1], reverse=True)]
        total_ids = {d.id for d in diagrams}

        # 预留一个槽位给 “其他”，保证 sums 闭合
        head_limit = max_options
        reserve_other = True
        if reserve_other and head_limit >= 3:
            head_limit = max_options - 1

        chosen_names = sorted_names[:head_limit]
        chosen: List[Dict] = []
        used_ids = set()
        for name in chosen_names:
            ids = set(option_ids.get(name, set()))
            if not ids:
                # fallback：没有 ids 记录时使用计数（但尽量不发生）
                continue
            used_ids |= ids
            chosen.append({"name": name, "count": len(ids), "ids": sorted(ids)})

        remaining_ids = total_ids - used_ids
        if reserve_other and remaining_ids:
            chosen.append({"name": "其他（未分类/更多）", "count": len(remaining_ids), "ids": sorted(remaining_ids)})

        chosen.sort(key=lambda x: x["count"], reverse=True)
        return chosen[:max_options]

    def _extract_variant_options(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """
        车型变体选项：按文件名前缀（车型/用途/轴型/配置等）分组。
        典型场景：用户输入“天龙KL电路图”，希望先在 5 个变体中选一个，再直接给结果。
        """
        from backend.app.utils.variant_util import variant_key_for_query

        diagrams = [r.diagram for r in results]
        current_query = (context or {}).get("current_query") or ""

        counts: Dict[str, int] = {}
        for d in diagrams:
            k = variant_key_for_query(d.file_name or "", current_query)
            if not k:
                continue
            counts[k] = counts.get(k, 0) + 1

        options = [{"name": f"{k} 系列", "count": c} for k, c in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
        return options[:max_options]
    
    def _extract_series_codes_aggressive(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        更激进地从层级路径和文件名中提取系列代码
        不限制位置，从所有可能的层级中提取
        
        Args:
            results: 搜索结果列表
            max_options: 最大选项数量
            context: 对话上下文（可选）
            
        Returns:
            选项列表
        """
        from backend.app.utils.hierarchy_util import HierarchyUtil
        
        diagrams = [result.diagram for result in results]
        option_counts = {}
        
        # 从上下文中获取用户意图的品牌
        user_brand = None
        if context and context.get("intent_result"):
            user_brand = context["intent_result"].get("brand")
        elif context and context.get("filter_history"):
            for filter_item in context["filter_history"]:
                if filter_item.get("type") == "brand":
                    user_brand = filter_item.get("value")
                    break
        
        # 定义需要排除的非系列代码关键词
        excluded_codes = [
            'ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 
            'DOCX', 'VECU', 'BCM', 'PDF', 'XLS', 'XLSX', 'PPT', 'PPTX',
            'D31', 'D32', 'D53', 'D56', 'ABS', 'ESP', 'TCS', 'EBD',
            'CAN', 'LIN', 'MOST', 'FLEX', 'KWP', 'UDS', 'OBD'
        ]
        
        # 从所有层级路径中提取系列代码
        for diagram in diagrams:
            # 遍历所有层级路径，查找系列代码
            for level in diagram.hierarchy_path:
                level_clean = level.replace('*', '').strip()
                
                # 跳过类型相关的层级
                type_keywords = ['电路图', '仪表', 'ECU', '整车', '线路', '针脚', '模块']
                if any(keyword in level_clean for keyword in type_keywords):
                    continue
                
                # 查找系列代码（2-3个大写字母）
                series_match = re.search(r'([A-Z]{2,3})', level_clean)
                if series_match:
                    potential_code = series_match.group(1)
                    if potential_code not in excluded_codes:
                        display_brand = user_brand if user_brand else (diagram.brand or "东风")
                        option_name = f"{display_brand} {potential_code} 系列"
                        option_counts[option_name] = option_counts.get(option_name, 0) + 1
                        break  # 找到一个就停止，避免重复
        
        # 转换为列表并按数量排序
        options = [
            {"name": name, "count": count}
            for name, count in sorted(option_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return options[:max_options]
    
    def _extract_series_from_filenames(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        从文件名中提取系列代码（最后的fallback）
        
        Args:
            results: 搜索结果列表
            max_options: 最大选项数量
            context: 对话上下文（可选）
            
        Returns:
            选项列表
        """
        option_counts = {}
        
        # 从上下文中获取用户意图的品牌
        user_brand = None
        if context and context.get("intent_result"):
            user_brand = context["intent_result"].get("brand")
        elif context and context.get("filter_history"):
            for filter_item in context["filter_history"]:
                if filter_item.get("type") == "brand":
                    user_brand = filter_item.get("value")
                    break
        
        # 定义需要排除的非系列代码关键词
        excluded_codes = [
            'ECU', 'DCI', 'LNG', 'EDC', 'VEC', 'DOC', 'DCM', 
            'DOCX', 'VECU', 'BCM', 'PDF', 'XLS', 'XLSX', 'PPT', 'PPTX',
            'D31', 'D32', 'D53', 'D56', 'ABS', 'ESP', 'TCS', 'EBD',
            'CAN', 'LIN', 'MOST', 'FLEX', 'KWP', 'UDS', 'OBD'
        ]
        
        for result in results:
            diagram = result.diagram
            file_name = diagram.file_name
            
            # 去除文件扩展名
            file_name_without_ext = re.sub(r'\.[A-Z]{2,5}$', '', file_name, flags=re.IGNORECASE)
            
            # 确定品牌
            brand_in_file = user_brand if user_brand else (diagram.brand or "东风")
            
            # 从文件名中提取系列代码
            if brand_in_file in file_name_without_ext:
                after_brand = file_name_without_ext.split(brand_in_file, 1)[1] if brand_in_file in file_name_without_ext else file_name_without_ext
                # 提取2-3个大写字母（系列代码）
                series_match = re.search(r'([A-Z]{2,3})', after_brand[:30])
                if series_match:
                    potential_code = series_match.group(1)
                    if potential_code not in excluded_codes:
                        display_brand = user_brand if user_brand else (diagram.brand or "东风")
                        option_name = f"{display_brand} {potential_code} 系列"
                        option_counts[option_name] = option_counts.get(option_name, 0) + 1
        
        # 转换为列表并按数量排序
        options = [
            {"name": name, "count": count}
            for name, count in sorted(option_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return options[:max_options]
    
    def _extract_type_variants(
        self,
        results: List[ScoredResult],
        max_options: int = 5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        提取类型变体选项（用于当用户已经指定了类型时）
        例如：如果用户已经指定了"仪表图"，提取"ECU仪表针脚图"、"整车仪表线路图"等
        
        Args:
            results: 搜索结果列表
            max_options: 最大选项数量
            context: 对话上下文（可选）
            
        Returns:
            选项列表
        """
        from backend.app.utils.hierarchy_util import HierarchyUtil
        
        diagrams = [result.diagram for result in results]
        option_counts = {}
        
        # 从上下文中获取用户已指定的类型关键词
        type_keywords = []
        if context and context.get("filter_history"):
            for filter_item in context["filter_history"]:
                if filter_item.get("type") == "type":
                    type_keywords.append(filter_item.get("value", ""))
        
        # 如果没有从筛选历史中获取，尝试从当前查询中提取
        if not type_keywords and context and context.get("current_query"):
            query = context["current_query"]
            # 检查是否包含类型关键词
            type_patterns = ["仪表", "ECU", "整车", "线路", "针脚"]
            for pattern in type_patterns:
                if pattern in query:
                    type_keywords.append(pattern)
                    break
        
        # 从层级路径和文件名称中提取包含类型关键词的具体类型变体
        for diagram in diagrams:
            # 检查层级路径中的类型信息
            for level in diagram.hierarchy_path:
                level_lower = level.lower()
                # 如果层级包含类型关键词，且不是简单的类型名称，提取作为选项
                if any(keyword in level_lower for keyword in type_keywords) if type_keywords else True:
                    # 检查是否是具体的类型变体（包含多个关键词或更详细的描述）
                    if len(level) > 5:  # 避免提取太短的层级
                        # 清理层级值
                        level_clean = level.replace('*', '').strip()
                        if level_clean and level_clean not in ["电路图", "仪表图", "ECU图"]:
                            option_counts[level_clean] = option_counts.get(level_clean, 0) + 1
            
            # 检查文件名称中的类型信息
            file_name = diagram.file_name
            if any(keyword in file_name.lower() for keyword in type_keywords) if type_keywords else True:
                # 尝试从文件名称中提取类型相关信息
                # 这里可以进一步优化，提取文件名称中包含类型关键词的部分
                pass
        
        # 转换为列表并按数量排序
        options = [
            {"name": name, "count": count}
            for name, count in option_counts.items()
        ]
        options.sort(key=lambda x: x["count"], reverse=True)
        
        return options[:max_options]
    
    def optimize_options(
        self,
        options: List[Dict],
        max_options: int = 5
    ) -> List[Dict]:
        """
        优化选项列表（去重、排序）
        
        Args:
            options: 选项列表，格式：[{"name": "选项名", "count": 数量}, ...]
            max_options: 最大选项数量
            
        Returns:
            优化后的选项列表
        """
        if not options:
            return []
        
        # 去重：合并相似选项（先做轻度规范化，避免因为空格/重复“系列”导致 A/B 看起来一样）
        def norm_name(s: str) -> str:
            if not s:
                return ""
            s = str(s).strip()
            s = re.sub(r"\s+", " ", s)
            s = s.replace("  ", " ")
            # collapse duplicated “系列”
            s = re.sub(r"(系列)\s*(系列)+", r"\1", s)
            return s.strip()

        merged_options = {}
        for option in options:
            name = norm_name(option['name'])
            count = option['count']
            
            # 检查是否有相似的选项（包含关系）
            merged = False
            for existing_name in list(merged_options.keys()):
                # 如果新选项包含现有选项，合并（保留更具体的）
                if name in existing_name:
                    # 新选项是现有选项的一部分，不合并
                    pass
                elif existing_name in name:
                    # 现有选项是新选项的一部分，用新选项替换
                    merged_options[name] = merged_options.pop(existing_name) + count
                    merged = True
                    break
            
            if not merged:
                if name in merged_options:
                    merged_options[name] += count
                else:
                    merged_options[name] = count
        
        # 转换为列表并按数量排序
        optimized = [
            {"name": name, "count": count}
            for name, count in merged_options.items()
        ]
        optimized.sort(key=lambda x: x["count"], reverse=True)
        
        # 限制选项数量
        return optimized[:max_options]
    
    def _generate_question_text(
        self,
        option_type: str,
        total_count: int,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成问题文本（默认模板）
        
        按照项目文档示例格式：
        - 第一次提问："我找到了XX相关的电路图。请问您需要的是："
        - 第二次提问："明白了。请问您需要的是哪种类型的仪表电路图："
        
        Args:
            option_type: 选项类型
            total_count: 总结果数
            context: 对话上下文（可选）
            
        Returns:
            问题文本
        """
        # 检查是否有筛选历史
        has_filter_history = context and context.get("filter_history")
        current_query = context.get("current_query", "") if context else ""
        
        # 如果是第一次提问（没有筛选历史）
        if not has_filter_history:
            # 从当前查询中提取品牌信息
            if option_type in ("variant", "brand_model"):
                # 尝试从查询中提取品牌
                brand_keywords = ["东风", "解放", "重汽", "三一", "徐工", "福田", "红岩"]
                brand = None
                for keyword in brand_keywords:
                    if keyword in current_query:
                        brand = keyword
                        break
                
                if brand:
                    return f"我找到了{brand}相关的电路图。请问您需要的是："
                else:
                    return f"我找到了相关电路图。请问您需要的是："
            elif option_type == "brand":
                return f"我找到了相关电路图。请问您需要的是："
            else:
                return f"我找到了相关电路图。请问您需要的是："
        
        # 如果有筛选历史，说明是后续提问
        filters = context.get("filter_history", [])
        if filters:
            last_filter = filters[-1]
            filter_value = last_filter.get("value", "")
            
            if option_type in ("variant", "brand_model"):
                return f"我找到了{filter_value}相关的电路图。请问您需要的是："
            elif option_type == "model":
                return f"明白了。请问您需要的是哪种型号："
            elif option_type == "type":
                return f"明白了。请问您需要的是哪种类型的仪表电路图："
            else:
                return f"明白了。请选择您需要的选项："
        
        return f"我找到了相关电路图。请问您需要的是："
    
    def format_question_message(self, question_data: Dict) -> str:
        """
        格式化问题消息（用于显示给用户）
        
        按照项目文档示例格式：
        - 选项格式：A. 东风天龙 KL 系列（而不是 A. 东风 DOC (4个结果)）
        
        Args:
            question_data: 问题数据（由generate_question返回）
            
        Returns:
            格式化的消息文本
        """
        message = f"{question_data['question']}\n"
        
        for option in question_data['options']:
            # 格式化选项名称，添加"系列"后缀（如果是品牌+型号组合）
            option_name = option['name']
            option_type = question_data.get('option_type', '')
            
            # 如果是品牌+型号组合，添加"系列"后缀
            if option_type == "brand_model" and "系列" not in option_name:
                option_name = f"{option_name} 系列"
            # 如果是类型选择，保持原样或添加描述
            elif option_type == "type":
                # 保持原样，LLM应该已经生成了合适的描述
                pass
            
            message += f"{option['label']}. {option_name}\n"
        
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

