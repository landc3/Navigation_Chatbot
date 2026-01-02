"""
搜索服务模块
提供增强的搜索功能，包括模糊匹配、多关键词搜索、相关性评分等
"""
from typing import List, Dict, Optional, Tuple, Iterable
import jieba
import re
import unicodedata
import json
from pathlib import Path
from backend.app.models.circuit_diagram import CircuitDiagram
from backend.app.models.intent import IntentResult
from backend.app.models.types import ScoredResult, rebuild_scored_result_model
from backend.app.utils.data_loader import get_data_loader
from backend.app.utils.hierarchy_util import HierarchyUtil
from config import config as app_config

# 确保 ScoredResult 模型已重建（解决前向引用问题）
rebuild_scored_result_model()


class SearchService:
    """搜索服务"""
    
    # 同义/包含词族（可按需扩展；匹配时会做规范化，支持下划线/空格等变体）
    # 设计：用户输入上位词（如“仪表图”）时，此处的下位词都可视为“命中该词族”
    DEFAULT_SYNONYM_FAMILIES: Dict[str, List[str]] = {
        "仪表图": ["仪表图", "仪表电路图", "仪表线路图", "仪表接线图", "仪表针脚图"],
        "ECU图": ["ECU图", "ECU电路图", "电脑版电路图", "ECU针脚图"],
        "整车图": ["整车图", "整车电路图", "整车线路图"],
        "线路图": ["线路图", "电路图"],
        "接线图": ["接线图", "接线定义图", "接线盒定义图", "电路图"],
        # “针脚图”应当更严格：不要自动把“针脚定义/针脚”都算作“针脚图”的命中（否则会误判首轮 AND 命中）
        "针脚图": ["针脚图", "针角图"],
        # allow splitting keyword like “针脚” / typo “针角”
        "针脚": ["针脚", "针角", "针脚图", "针角图", "针脚定义图", "针脚定义", "ECU针脚图"],
    }

    # 常见符号/分隔符：匹配时会被移除，确保 “仪表_电路图”≈“仪表电路图”
    _NORMALIZE_SEP_RE = re.compile(r"[\s_\-·•.。/\\()（）\[\]【】{}<>《》“”\"'’`~!@#$%^&*+=|:;，,；：?？]+")

    def __init__(self, data_loader=None):
        """初始化搜索服务"""
        self.data_loader = data_loader or get_data_loader()
        self.synonym_families: Dict[str, List[str]] = dict(self.DEFAULT_SYNONYM_FAMILIES)

        # 可配置同义/包含词族：默认读取项目根目录的 synonyms.json（可用环境变量覆盖）
        try:
            project_root = Path(__file__).parent.parent.parent.parent
            families_path = getattr(app_config, "SYNONYM_FAMILIES_PATH", "synonyms.json")
            synonym_file = (project_root / families_path).resolve()
            if synonym_file.exists():
                with open(synonym_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # 允许覆盖或新增 key
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, list):
                            self.synonym_families[k] = [str(x) for x in v if str(x).strip()]
        except Exception as e:
            # 配置文件加载失败不应影响服务启动
            print(f"⚠️ 同义词配置加载失败，将使用内置默认表: {e}")
        # 初始化jieba分词
        jieba.initialize()
        # 添加自定义词典，确保复合品牌和类型关键词不被拆分
        custom_words = [
            "东风天龙", "东风乘龙", "一汽解放", "中国重汽", "上汽大通",
            "福田欧曼", "红岩杰狮", "重汽豪瀚", "重汽豪汉",
            "重汽豪沃", "豪沃",
            "仪表图", "仪表电路图", "ECU图", "ECU电路图",
            "整车图", "整车电路图", "线路图", "接线图", "针脚图", "针角图",
            "国一", "国二", "国三", "国四", "国五", "国六", "国七", "国八",
        ]
        for word in custom_words:
            jieba.add_word(word, freq=1000)  # 设置高频率，确保优先匹配
        # 词族快速索引：把“任何族成员”映射回该词族，避免用“包含匹配”造成过度扩展
        self._synonym_member_lookup: Dict[str, List[str]] = {}
        self._rebuild_synonym_lookup()

    def _rebuild_synonym_lookup(self) -> None:
        lookup: Dict[str, List[str]] = {}
        for _, fam in (self.synonym_families or {}).items():
            if not isinstance(fam, list):
                continue
            fam_list = [str(x) for x in fam if str(x).strip()]
            for member in fam_list:
                mn = self._norm_text(member)
                if not mn:
                    continue
                # If a member appears in multiple families, keep the first (more specific) one.
                # This prevents broad families like “针脚” from overriding the stricter “针脚图” family.
                if mn not in lookup:
                    lookup[mn] = fam_list
        self._synonym_member_lookup = lookup

    @classmethod
    def _norm_text(cls, s: str) -> str:
        """统一规范化：全半角、大小写、去分隔符（下划线/空格/括号等）。"""
        if not s:
            return ""
        s = unicodedata.normalize("NFKC", str(s))
        s = s.lower()
        s = cls._NORMALIZE_SEP_RE.sub("", s)
        return s.strip()

    @classmethod
    def _diagram_blob(cls, diagram: CircuitDiagram) -> str:
        """拼接可检索文本（并规范化）"""
        parts: List[str] = []
        parts.append(diagram.file_name or "")
        parts.extend(diagram.hierarchy_path or [])
        if diagram.brand:
            parts.append(diagram.brand)
        if diagram.model:
            parts.append(diagram.model)
        if diagram.diagram_type:
            parts.append(diagram.diagram_type)
        if diagram.vehicle_category:
            parts.append(diagram.vehicle_category)
        return cls._norm_text(" ".join([p for p in parts if p]))

    def _expand_term_variants(self, term: str) -> List[str]:
        """对上位词做词族扩展；默认返回 [term]。"""
        if not term:
            return []
        tn = self._norm_text(term)
        variants = self._synonym_member_lookup.get(tn)
        if not variants:
            variants = [term]
        # 去重保持顺序
        seen = set()
        out: List[str] = []
        for v in variants:
            vn = self._norm_text(v)
            if not vn or vn in seen:
                continue
            seen.add(vn)
            out.append(v)
        return out
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        从查询中提取关键词
        
        Args:
            query: 用户查询字符串
            
        Returns:
            关键词列表
        """
        # 轻度纠错（不影响原文展示，仅用于匹配）
        query = (query or "").replace("上气大通", "上汽大通")

        # 定义复合品牌列表（需要作为整体保留）
        compound_brands = [
            "东风天龙", "东风乘龙", "一汽解放", "中国重汽", "上汽大通",
            "福田欧曼", "红岩杰狮", "重汽豪瀚", "重汽豪汉", "重汽豪沃"
        ]
        
        # 定义类型关键词（需要作为整体保留）
        type_keywords = [
            "仪表图", "仪表电路图", "ECU图", "ECU电路图", 
            "整车图", "整车电路图", "线路图", "接线图", "针脚图", "针角图"
        ]
        
        # 停用词列表（需要过滤的词）
        stop_words = ['的', '了', '是', '在', '和', '与', '或', '一个', '我要', '要', '我', '有', '个']
        
        # 先做轻度规范化（仅用于检测复合词；不影响最终返回的关键词文本）
        query_for_detect = unicodedata.normalize("NFKC", query or "")
        # 把 “国六/国5/国Ⅵ”等作为可拆分关键词，避免被粘连到前一个词
        # 例：豪沃国六 -> 豪沃 国六
        # 注意：这里必须用 \d（不要写成 \\d），否则会匹配字面量“\d”导致国6/国12无法拆分。
        query_for_detect = re.sub(
            r"(国[一二三四五六七八九十]|国\d{1,2}|国[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)",
            r" \1 ",
            query_for_detect,
        )
        # 将常见分隔符替换为空格，避免“东风_天龙”检测失败
        query_for_detect = self._NORMALIZE_SEP_RE.sub(" ", query_for_detect)

        # 先提取复合品牌和类型关键词，避免被jieba拆分
        extracted_keywords = []
        remaining_query = query_for_detect
        
        # 提取复合品牌（按长度从长到短排序，优先匹配更长的品牌）
        sorted_brands = sorted(compound_brands, key=len, reverse=True)
        for brand in sorted_brands:
            if brand in remaining_query:
                # “重汽豪沃”在业务上更希望拆成两个可独立组合的关键词：重汽 + 豪沃
                if brand == "重汽豪沃":
                    extracted_keywords.append("重汽")
                    extracted_keywords.append("豪沃")
                else:
                    extracted_keywords.append(brand)
                remaining_query = remaining_query.replace(brand, " ", 1)
        
        # 提取类型关键词（按长度从长到短排序，优先匹配更长的类型）
        sorted_type_keywords = sorted(type_keywords, key=len, reverse=True)
        for type_keyword in sorted_type_keywords:
            if type_keyword in remaining_query:
                extracted_keywords.append(type_keyword)
                remaining_query = remaining_query.replace(type_keyword, " ", 1)

        # 特殊：把“仪表针脚图/仪表针角图”拆成两个可组合关键词：仪表 + 针脚
        if ("仪表" in query_for_detect) and ("针脚" in query_for_detect or "针角" in query_for_detect):
            # 若用户显式说“针脚图/针角图”，优先保留更强约束的“针脚图”（否则首轮 AND 往往会误召回“针脚定义”类资料）
            has_pin_diagram = ("针脚图" in query_for_detect) or ("针角图" in query_for_detect)
            pin_term = "针脚图" if has_pin_diagram else "针脚"
            if not any("仪表" in k for k in extracted_keywords):
                extracted_keywords.append("仪表")
            # 只加入一个 pin_term，避免出现 “针脚 + 针脚图” 同时作为 AND 组导致过严
            if pin_term not in extracted_keywords and not any(("针脚" in k or "针角" in k) for k in extracted_keywords):
                extracted_keywords.append(pin_term)
            # 避免剩余 query 再切出重复词
            remaining_query = remaining_query.replace("仪表", " ")
            remaining_query = remaining_query.replace("针脚", " ")
            remaining_query = remaining_query.replace("针角", " ")
            remaining_query = remaining_query.replace("针脚图", " ")
            remaining_query = remaining_query.replace("针角图", " ")
        
        # 对剩余部分使用jieba分词
        words = jieba.cut(remaining_query)
        # 过滤掉停用词和单字符
        additional_keywords = [
            word.strip() 
            for word in words 
            if len(word.strip()) > 1 and word.strip() not in stop_words
        ]
        
        # 合并关键词，去重
        all_keywords = extracted_keywords + additional_keywords
        # 去重但保持顺序
        seen = set()
        keywords = []
        for kw in all_keywords:
            kw_clean = kw.strip()
            if kw_clean and kw_clean not in seen:
                seen.add(kw_clean)
                # 轻度归一：针角 -> 针脚
                if kw_clean == "针角":
                    kw_clean = "针脚"
                if kw_clean == "针角图":
                    kw_clean = "针脚图"
                keywords.append(kw_clean)
        
        # 如果提取到了关键词，返回；否则返回原始查询
        result = keywords if keywords else [query.strip()]
        # NOTE: Avoid emojis in logs; on Windows GBK console they can trigger UnicodeEncodeError.
        print(f"[DEBUG] _extract_keywords input: '{query}' -> output: {result}")
        return result

    def search_and_relax(
        self,
        query: str,
        max_results: int = 5,
        use_fuzzy: bool = True,
        intent_result: Optional[IntentResult] = None,
        force_remove_terms: Optional[List[str]] = None,
    ) -> tuple[List[ScoredResult], Dict[str, object]]:
        """
        AND 搜索兜底策略（按业务规则“逐步放宽”）：
        - 先剔除命中数为 0 的关键词
        - 若仍无结果：
          - 当关键词数 > 3：优先剔除“与其他关键词可组合数最少”的关键词（0 优先）
          - 否则：从末尾关键词开始依次剔除
        返回 (results, meta)，meta 用于上层生成更友好的提示/确认话术。
        """
        if not query or not query.strip():
            return [], {"original_keywords": [], "used_keywords": [], "removed_keywords": []}

        original_query = query.strip()
        if intent_result:
            search_query = intent_result.get_search_query()
            if search_query and search_query.strip():
                query = search_query.strip()
            if intent_result.original_query:
                original_query = intent_result.original_query.strip()

        # 关键词提取：优先用原始查询
        keywords = self._extract_keywords(original_query) or self._extract_keywords(query.strip())

        # 去重（按规范化后）
        seen_kw = set()
        unique_keywords: List[str] = []
        for kw in keywords:
            n = self._norm_text(kw)
            if not n or n in seen_kw:
                continue
            seen_kw.add(n)
            unique_keywords.append(kw.strip())
        keywords = unique_keywords

        # 品牌兜底注入（与 search() 一致）
        if intent_result and intent_result.brand:
            brand_keyword = intent_result.brand
            brand_norm = self._norm_text(brand_keyword)
            if brand_norm and all(brand_norm not in self._norm_text(k) and self._norm_text(k) not in brand_norm for k in keywords):
                keywords.insert(0, brand_keyword)

        # 类型兜底注入（比 search() 更保守：ECU 不在原文里就不注入）
        if intent_result and intent_result.diagram_type:
            raw_q = original_query or ""
            type_keyword = intent_result.diagram_type
            # ECU 类型：必须显式出现 ECU 才允许注入
            if "ECU" in (type_keyword or "").upper() and "ECU" not in raw_q.upper():
                pass
            else:
                type_norm = self._norm_text(type_keyword)
                has_type_keyword = any(type_norm and (type_norm in self._norm_text(k) or self._norm_text(k) in type_norm) for k in keywords)
                if not has_type_keyword:
                    # 仪表类：注入上位词“仪表图”，避免过细类型导致 AND 过严
                    if "仪表" in (type_keyword or ""):
                        keywords.append("仪表图")
                    else:
                        keywords.append(type_keyword)

        if not keywords:
            return [], {"original_keywords": [], "used_keywords": [], "removed_keywords": []}

        all_diagrams = self.data_loader.get_all()
        id_to_diagram = {d.id: d for d in all_diagrams}

        # term_groups（每个 term 是一个 AND 组；组内 variants 视为 OR）
        term_groups: List[Dict[str, List[str]]] = []
        for kw in keywords:
            term_groups.append({"term": kw, "variants": self._expand_term_variants(kw)})

        # 预计算：term -> matched ids；以及每个 diagram 对每个 term 的 best_score（用于快速重算子集 AND 分数）
        term_to_ids: Dict[str, set] = {g["term"]: set() for g in term_groups}
        diagram_term_best: Dict[int, Dict[str, float]] = {}

        for diagram in all_diagrams:
            did = diagram.id
            for group in term_groups:
                term = group["term"]
                best_score = 0.0
                matched_any = False
                for v in group["variants"]:
                    matched, score = self._match_keyword(diagram, v, use_fuzzy)
                    if matched:
                        matched_any = True
                        if score > best_score:
                            best_score = score
                if matched_any:
                    term_to_ids[term].add(did)
                    diagram_term_best.setdefault(did, {})[term] = best_score

        def _ensure_term_computed(term: str) -> None:
            """
            When we introduce a new term during relaxation (e.g. replace 针脚图 -> 针脚),
            we must compute its matched-id set and best-scores, otherwise intersections will be empty
            and the term will be incorrectly dropped later.
            """
            if not term or term in term_to_ids:
                return
            term_to_ids[term] = set()
            variants = self._expand_term_variants(term)
            for diagram in all_diagrams:
                did = diagram.id
                best_score = 0.0
                matched_any = False
                for v in variants:
                    matched, score = self._match_keyword(diagram, v, use_fuzzy)
                    if matched:
                        matched_any = True
                        if score > best_score:
                            best_score = score
                if matched_any:
                    term_to_ids[term].add(did)
                    diagram_term_best.setdefault(did, {})[term] = best_score

        def intersect_ids(terms: List[str]) -> set:
            if not terms:
                return set()
            s = None
            for t in terms:
                ids = term_to_ids.get(t, set())
                s = ids if s is None else (s & ids)
                if not s:
                    return set()
            return s or set()

        original_terms = [g["term"] for g in term_groups]
        remaining = list(original_terms)
        removed: List[str] = []

        # 1) 剔除 0 命中关键词（带“智能替换”：针脚图/针角图 0 命中时，用更宽的“针脚”替换）
        replaced: Dict[str, str] = {}
        zero_terms = [t for t in remaining if len(term_to_ids.get(t, set())) == 0]
        # Also allow caller to force-remove certain terms (e.g. strict filename AND says a term never appears in file_name)
        if force_remove_terms:
            for t in force_remove_terms:
                if t and t in remaining and t not in zero_terms:
                    zero_terms.append(t)
        if zero_terms:
            new_remaining: List[str] = []
            for t in remaining:
                if t not in zero_terms:
                    new_remaining.append(t)
                    continue
                # record removal
                removed.append(t)
                # smart replace
                if t in ("针脚图", "针角图"):
                    repl = "针脚"
                    _ensure_term_computed(repl)
                    if repl not in new_remaining:
                        new_remaining.append(repl)
                    replaced[t] = repl
            remaining = new_remaining

        hit_ids = intersect_ids(remaining)

        # 2) 逐步放宽直到有命中或只剩 1 个关键词
        while not hit_ids and len(remaining) > 1:
            # --- term importance / protection ---
            # Protect brand/model-like terms from being dropped too early; drop generic terms first.
            brand_hints = [
                "东风", "解放", "重汽", "中国重汽", "上汽", "上汽大通", "大通", "福田", "欧曼", "红岩", "杰狮",
                "乘龙", "天龙", "豪沃", "豪瀚", "豪汉",
            ]
            generic_terms = {
                "电路图", "线路图", "接线图", "整车图", "整车电路图", "仪表图", "仪表电路图", "ECU图", "ECU电路图",
                "针脚图", "针角图",
            }
            def is_model_like(t: str) -> bool:
                tt = (t or "").strip()
                # model/codes are typically uppercase alphanum like H7/V80/JH6/EDC17C81...
                # Avoid protecting generic test tokens like "term1" by requiring at least one uppercase letter.
                if not tt or not re.search(r"\d", tt) or not re.search(r"[A-Za-z]", tt):
                    return False
                if not re.search(r"[A-Z]", tt):
                    return False
                return bool(re.fullmatch(r"[A-Z]{1,6}\d{1,4}[A-Z0-9]{0,6}", tt))

            def is_series_code(t: str) -> bool:
                """
                保护类似 “KL/KC/VGT” 这种短大写系列码，避免在 AND 放宽时被错误剔除。
                """
                tt = (t or "").strip()
                if not tt:
                    return False
                up = tt.upper()
                # 常见系统缩写不保护（否则会误导放宽策略）
                excluded_acronyms = {
                    "ECU", "VEC", "VECU", "BCM", "ABS", "ESP", "TCS", "EBD",
                    "DOC", "DCI", "DCM", "EDC", "LNG", "UDS", "OBD", "CAN", "LIN",
                }
                if up in excluded_acronyms:
                    return False
                if tt in generic_terms:
                    return False
                return bool(re.fullmatch(r"[A-Z]{2,5}", up))

            protected = set()
            for t in remaining:
                if any(h in t for h in brand_hints) or is_model_like(t) or is_series_code(t):
                    protected.add(t)

            def pick_from_tail_prefer_generic() -> str | None:
                # 先剔除 generic（如“线路图/电路图”），更符合用户心智：型号/系列码通常是核心信息
                for t in reversed(remaining):
                    if t in generic_terms and t not in protected:
                        return t
                for t in reversed(remaining):
                    if t not in protected:
                        return t
                return None

            def pick_from_tail_non_protected() -> str | None:
                for t in reversed(remaining):
                    if t not in protected and t not in generic_terms:
                        return t
                for t in reversed(remaining):
                    if t not in protected:
                        return t
                return None

            if len(remaining) > 3:
                # 计算“可组合度”：能与多少个其他关键词组成非空交集
                combo_counts: Dict[str, int] = {}
                for i, ti in enumerate(remaining):
                    c = 0
                    ids_i = term_to_ids.get(ti, set())
                    for j, tj in enumerate(remaining):
                        if i == j:
                            continue
                        if ids_i and (ids_i & term_to_ids.get(tj, set())):
                            c += 1
                    combo_counts[ti] = c
                # 选 combo 最小的剔除；并列则从末尾开始剔除
                min_combo = min(combo_counts.values()) if combo_counts else 0
                candidates = [t for t in remaining if combo_counts.get(t, 0) == min_combo]
                # 优先剔除 generic，再剔除非 protected
                generic_candidates = [t for t in candidates if t in generic_terms]
                non_protected_candidates = [t for t in candidates if t not in protected]
                if generic_candidates:
                    drop = next((t for t in reversed(remaining) if t in set(generic_candidates)), generic_candidates[-1])
                elif non_protected_candidates:
                    drop = next((t for t in reversed(remaining) if t in set(non_protected_candidates)), non_protected_candidates[-1])
                else:
                    # all protected: fallback to tail
                    drop = remaining[-1]
            else:
                # <=3：从末尾开始剔除
                drop = pick_from_tail_prefer_generic() or remaining[-1]

            remaining = [t for t in remaining if t != drop]
            removed.append(drop)
            hit_ids = intersect_ids(remaining)

        # 组装结果
        results: List[ScoredResult] = []
        if hit_ids:
            for did in hit_ids:
                d = id_to_diagram.get(did)
                if not d:
                    continue
                score = 0.0
                bests = diagram_term_best.get(did, {})
                for t in remaining:
                    score += float(bests.get(t, 0.0))
                results.append(ScoredResult(diagram=d, score=score))
            if intent_result:
                results = self._adjust_scores_by_intent(results, intent_result)
            results.sort(key=lambda x: x.score, reverse=True)
            if max_results < len(results):
                results = results[:max_results]

        meta: Dict[str, object] = {
            "original_keywords": original_terms,
            "used_keywords": remaining,
            "removed_keywords": removed,
            "zero_hit_keywords": zero_terms,
            "replaced_keywords": replaced,
        }
        return results, meta

    def strict_filename_and_stats(
        self,
        query: str,
        intent_result: Optional[IntentResult] = None,
    ) -> Dict[str, object]:
        """
        Strict AND definition (per user requirement A):
        - A term-group is considered matched ONLY if it matches within diagram.file_name (normalized).
        - AND means all term-groups must match in file_name.

        Returns:
            {
              "terms": [...],
              "term_counts": {term: count_of_diagrams_matching_term_in_filename},
              "and_count": count_of_diagrams_matching_all_terms_in_filename,
              "and_ids": [...],
            }
        """
        if not query or not query.strip():
            return {"terms": [], "term_counts": {}, "and_count": 0, "and_ids": []}

        # IMPORTANT: strict gating should use user-visible query only; do NOT inject extra terms from intent_result
        original_query = query.strip()
        keywords = self._extract_keywords(original_query)

        # dedupe
        seen = set()
        unique: List[str] = []
        for kw in keywords:
            n = self._norm_text(kw)
            if not n or n in seen:
                continue
            seen.add(n)
            unique.append(kw.strip())
        keywords = unique

        if not keywords:
            return {"terms": [], "term_counts": {}, "and_count": 0, "and_ids": []}

        term_groups = [{"term": kw, "variants": self._expand_term_variants(kw)} for kw in keywords]
        terms = [g["term"] for g in term_groups]
        term_counts: Dict[str, int] = {t: 0 for t in terms}
        and_ids: List[int] = []

        all_diagrams = self.data_loader.get_all()
        for d in all_diagrams:
            fn_norm = self._norm_text(d.file_name or "")
            if not fn_norm:
                continue
            ok_all = True
            for g in term_groups:
                term = g["term"]
                matched = False
                for v in g["variants"]:
                    vn = self._norm_text(v)
                    if vn and vn in fn_norm:
                        matched = True
                        break
                if matched:
                    term_counts[term] = term_counts.get(term, 0) + 1
                else:
                    ok_all = False
            if ok_all:
                and_ids.append(d.id)

        return {
            "terms": terms,
            "term_counts": term_counts,
            "and_count": len(and_ids),
            "and_ids": and_ids,
        }
    
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

        # --- Special handling for short uppercase "series codes" like KL/KC/VL ---
        # Problem: our normalized matching removes separators (e.g. "TK.L0" -> "tkl0"),
        # which can make "KL" accidentally match across punctuation ("K.L").
        # For 2-3 letter uppercase codes, require a *contiguous* match in the original text.
        # Also exclude common non-series acronyms to avoid over-restricting.
        kw_raw = (keyword or "").strip()
        kw_up = kw_raw.upper()
        excluded_acronyms = {
            "ECU", "VEC", "VECU", "BCM", "ABS", "ESP", "TCS", "EBD",
            "DOC", "DCI", "DCM", "EDC", "LNG", "UDS", "OBD", "CAN", "LIN",
        }
        if re.fullmatch(r"[A-Z]{2,3}", kw_up) and kw_up not in excluded_acronyms:
            hay = " ".join(
                [diagram.file_name or ""]
                + (diagram.hierarchy_path or [])
                + [diagram.brand or "", diagram.model or "", diagram.diagram_type or ""]
            ).upper()
            # "word boundary" for ASCII codes: do not allow adjacent A-Z/0-9
            pat = re.compile(rf"(?<![A-Z0-9]){re.escape(kw_up)}(?![A-Z0-9])")
            if pat.search(hay):
                score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                return True, score
            return False, 0.0

        # --- Special handling for the generic keyword “电路图” ---
        # Many records have hierarchy_path[0] == "电路图", which would make “电路图” match almost everything.
        # For user queries like “C81电路图”, we want “电路图” to mean the *document type in the filename*
        # (e.g., 整车电路图/仪表电路图/电路图概述...), not the root category label.
        if self._norm_text(keyword) == self._norm_text("电路图"):
            fn_norm = self._norm_text(diagram.file_name or "")
            if self._norm_text("电路图") in fn_norm:
                score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                return True, score
            return False, 0.0

        # 规范化 blob（用于“下划线/空格变体”匹配）
        blob = self._diagram_blob(diagram)
        keyword_norm = self._norm_text(keyword)
        
        # 定义复合品牌及其变体匹配规则
        compound_brand_patterns = {
            "东风天龙": ["东风天龙", "天龙"],
            "东风乘龙": ["东风乘龙", "乘龙"],
            "一汽解放": ["一汽解放", "解放"],
            "中国重汽": ["中国重汽", "重汽"],
            "上汽大通": ["上汽大通", "大通"],
            "福田欧曼": ["福田欧曼", "欧曼"],
            "红岩杰狮": ["红岩杰狮", "杰狮"],
            "重汽豪瀚": ["重汽豪瀚", "豪瀚"],
            "重汽豪汉": ["重汽豪汉", "豪汉"],
            "重汽豪沃": ["重汽豪沃", "豪沃"],
        }
        
        # 检查是否是复合品牌关键词
        brand_patterns = None
        for compound_brand, patterns in compound_brand_patterns.items():
            if compound_brand in keyword or any(pattern in keyword for pattern in patterns):
                brand_patterns = patterns
                break
        
        # 规范化后的“完全包含”快速路径（覆盖：仪表_电路图 vs 仪表电路图）
        if keyword_norm and keyword_norm in blob:
            score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
            return True, score

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
            # 对于复合品牌关键词（如"东风天龙"），需要特殊处理
            if brand_patterns:
                # 检查文件名称中是否包含品牌模式
                file_name_lower = diagram.file_name.lower()
                hierarchy_path_lower = " ".join([level.lower() for level in diagram.hierarchy_path])
                brand_lower = diagram.brand.lower() if diagram.brand else ""
                model_lower = diagram.model.lower() if diagram.model else ""
                
                # 检查是否匹配品牌模式（支持变体，如"东风天龙D310"、"东风天龙KL"等）
                matched = False
                for pattern in brand_patterns:
                    pattern_lower = pattern.lower()
                    # 在文件名称中搜索（支持"东风天龙D310"、"东风天龙KL"等变体）
                    if pattern_lower in file_name_lower:
                        matched = True
                        break
                    # 在层级路径中搜索（支持所有层级）
                    if pattern_lower in hierarchy_path_lower:
                        matched = True
                        break
                    # 在品牌字段中搜索
                    if brand_lower and pattern_lower in brand_lower:
                        matched = True
                        break
                    # 在型号字段中搜索（支持"天龙KL"、"天龙D310"等）
                    if model_lower and pattern_lower in model_lower:
                        matched = True
                        break
                
                # 如果还没有匹配，尝试更灵活的匹配方式
                # 对于"东风天龙"，只要文件名或层级路径中包含"东风"和"天龙"（不一定连续），也算匹配
                if not matched and "东风天龙" in keyword:
                    # 检查文件名中是否同时包含"东风"和"天龙"（支持变体）
                    if "东风" in file_name_lower and ("天龙" in file_name_lower or "tianlong" in file_name_lower):
                        matched = True
                    # 检查层级路径中是否同时包含"东风"和"天龙"
                    elif "东风" in hierarchy_path_lower and ("天龙" in hierarchy_path_lower or "tianlong" in hierarchy_path_lower):
                        matched = True
                    # 检查品牌和型号字段
                    elif "东风" in brand_lower and ("天龙" in brand_lower or "天龙" in model_lower or "tianlong" in model_lower):
                        matched = True
                
                if matched:
                    score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                    return True, score
            
            # 对于类型关键词（如"仪表图"、"仪表电路图"），进行模糊匹配
            # 检查是否包含类型关键词
            if "仪表" in keyword or ("图" in keyword and ("仪表" in keyword or "电路" in keyword)):
                # 如果关键词是"仪表图"，进行词族/包含匹配：能命中“仪表电路图/线路图/接线图/针脚图”等
                if "仪表图" in keyword:
                    variants = self._expand_term_variants("仪表图")
                    for v in variants:
                        vn = self._norm_text(v)
                        if vn and vn in blob:
                            score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                            return True, score
                    
                    # 如果层级路径中包含"仪表模块"或"仪表"，也认为匹配（因为"仪表模块"通常包含仪表图）
                    if self._norm_text("仪表模块") in blob or (self._norm_text("仪表") in blob and self._norm_text("模块") in blob):
                        score = self._calculate_match_score(diagram, keyword, is_exact_match=False) * 0.8  # 降低分数
                        return True, score
                    
                    # 如果类型字段是"仪表模块"，也认为匹配
                    if diagram.diagram_type and "仪表模块" in diagram.diagram_type.lower():
                        score = self._calculate_match_score(diagram, keyword, is_exact_match=False) * 0.8  # 降低分数
                        return True, score
                
                # 对于其他类型关键词，使用变体匹配
                else:
                    # 构建类型关键词的变体列表（用于匹配）
                    type_variants = []
                    if "仪表电路图" in keyword:
                        # 如果关键词是"仪表电路图"，也要匹配"仪表图"
                        type_variants = ["仪表电路图", "仪表图", "仪表线路图", "仪表针脚图"]
                    elif "仪表" in keyword:
                        type_variants = ["仪表", "仪表图", "仪表电路图", "仪表线路图", "仪表针脚图"]
                    else:
                        type_variants = [keyword]
                    
                    # 检查文件名称中是否包含类型变体
                    file_name_lower = diagram.file_name.lower()
                    for variant in type_variants:
                        if variant.lower() in file_name_lower:
                            score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                            return True, score
                    
                    # 在层级路径中搜索
                    hierarchy_path_lower = " ".join([level.lower() for level in diagram.hierarchy_path])
                    for variant in type_variants:
                        if variant.lower() in hierarchy_path_lower:
                            score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                            return True, score
                    
                    # 在类型字段中搜索
                    if diagram.diagram_type:
                        diagram_type_lower = diagram.diagram_type.lower()
                        for variant in type_variants:
                            if variant.lower() in diagram_type_lower:
                                score = self._calculate_match_score(diagram, keyword, is_exact_match=False)
                                return True, score
            
            # 通用模糊匹配（对于其他关键词）
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
        
        # 保存原始查询（用于关键词提取）
        original_query = query.strip()
        
        # 如果提供了意图理解结果，优先使用意图理解的信息
        if intent_result:
            # 使用意图理解结果构建搜索查询
            search_query = intent_result.get_search_query()
            if search_query and search_query.strip():
                query = search_query.strip()
            # 同时保留原始查询，用于提取关键词
            if intent_result.original_query:
                original_query = intent_result.original_query.strip()
        
        # 提取关键词：优先使用原始查询提取，确保提取到用户实际输入的关键词
        keywords = self._extract_keywords(original_query)
        
        # 如果从原始查询中提取不到关键词，使用当前查询
        if not keywords:
            keywords = self._extract_keywords(query.strip())
        
        # 调试信息：打印提取的关键词
        print(f"[DEBUG] original_query: {original_query}")
        print(f"[DEBUG] query: {query}")
        print(f"[DEBUG] extracted keywords (pre-dedupe): {keywords}")
        
        # 去重关键词列表（按规范化后去重，保持顺序；避免复杂“包含替换”导致不稳定）
        seen_kw = set()
        unique_keywords: List[str] = []
        for kw in keywords:
            n = self._norm_text(kw)
            if not n or n in seen_kw:
                continue
            seen_kw.add(n)
            unique_keywords.append(kw.strip())
        keywords = unique_keywords
        print(f"[DEBUG] deduped keywords: {keywords}")
        
        # 如果意图理解返回了类型信息，谨慎注入类型关键词：
        # 仅当用户在原始查询里显式提到类型（如 ECU/仪表/整车/针脚图 等）才注入，
        # 避免像“电脑版针角图”被错误塞入“ECU电路图”导致 AND 过严。
        if intent_result and intent_result.diagram_type:
            raw_q = original_query or ""
            explicit_type = any(
                t in raw_q
                for t in (
                    "ECU", "ECU图", "ECU电路图",
                    "仪表", "仪表图", "仪表电路图",
                    "整车图", "整车电路图",
                    "针脚图", "针角图", "针脚",
                    "接线图", "线路图",
                )
            )
            if explicit_type:
                type_keyword = intent_result.diagram_type
                # ECU 类型：必须在原始查询里显式出现 ECU 才允许注入（避免“电脑版/针角”被误判成 ECU）
                if "ECU" in (type_keyword or "").upper() and "ECU" not in raw_q.upper():
                    type_keyword = None
                has_type_keyword = False
                if type_keyword:
                    for kw in keywords:
                        kw_lower = kw.lower()
                        if "仪表图" in kw_lower or type_keyword.lower() in kw_lower or kw_lower in type_keyword.lower():
                            has_type_keyword = True
                            break
                    if not has_type_keyword:
                        if "仪表电路图" in type_keyword or "仪表" in type_keyword:
                            keywords.append("仪表图")
                        else:
                            keywords.append(type_keyword)
        
        # 如果意图理解返回了品牌信息，确保包含品牌关键词
        if intent_result and intent_result.brand:
            brand_keyword = intent_result.brand
            # 检查是否已经包含品牌关键词
            has_brand_keyword = False
            for kw in keywords:
                kw_lower = kw.lower()
                brand_lower = brand_keyword.lower()
                # 如果关键词中包含品牌，或者品牌包含在关键词中，认为已经匹配
                if brand_lower in kw_lower or kw_lower in brand_lower:
                    has_brand_keyword = True
                    break
            
            if not has_brand_keyword:
                keywords.insert(0, brand_keyword)  # 插入到开头
        
        if not keywords:
            return []
        
        # 获取所有数据
        all_diagrams = self.data_loader.get_all()
        print(f"[DEBUG] total diagrams: {len(all_diagrams)}")
        
        # 将关键词转换为“AND 组”：每个关键词可扩展为多个可接受变体（同义/包含）
        term_groups: List[Dict[str, List[str]]] = []
        for kw in keywords:
            variants = self._expand_term_variants(kw)
            term_groups.append({"term": kw, "variants": variants})

        # 存储每个电路图的匹配信息
        diagram_scores = {}  # {diagram_id: {"diagram": diagram, "matched_terms": [], "matched_groups": int, "total_score": float}}
        
        # 统计匹配情况（按原始 term）
        match_stats = {g["term"]: 0 for g in term_groups}
        
        for diagram in all_diagrams:
            matched_terms: List[str] = []
            total_score = 0.0
            matched_groups = 0

            for group in term_groups:
                term = group["term"]
                variants = group["variants"]
                best_score = 0.0
                group_matched = False
                for v in variants:
                    matched, score = self._match_keyword(diagram, v, use_fuzzy)
                    if matched:
                        group_matched = True
                        best_score = max(best_score, score)
                if group_matched:
                    matched_groups += 1
                    matched_terms.append(term)
                    total_score += best_score
                    match_stats[term] = match_stats.get(term, 0) + 1
            
            # 根据逻辑运算符决定是否包含此结果
            if logic.upper() == "AND":
                # AND逻辑：所有“关键词组”都必须匹配（支持同义/包含词族）
                if matched_groups == len(term_groups):
                    diagram_scores[diagram.id] = {
                        "diagram": diagram,
                        "matches": matched_terms,
                        "matched_groups": matched_groups,
                        "total_score": total_score
                    }
            else:
                # OR逻辑：至少一个关键词匹配
                if matched_groups > 0:
                    if diagram.id in diagram_scores:
                        # 如果已存在，更新分数（取最大值）
                        diagram_scores[diagram.id]["total_score"] = max(
                            diagram_scores[diagram.id]["total_score"],
                            total_score
                        )
                    else:
                        diagram_scores[diagram.id] = {
                            "diagram": diagram,
                            "matches": matched_terms,
                            "matched_groups": matched_groups,
                            "total_score": total_score
                        }
        
        print(f"[DEBUG] match_stats: {match_stats}")
        print(f"[DEBUG] {logic.upper()} matched: {len(diagram_scores)}")
        
        # 转换为ScoredResult列表并排序（OR 时加入“命中组数”加权，避免只命中部分硬条件的结果排前）
        results: List[ScoredResult] = []
        for item in diagram_scores.values():
            base = float(item["total_score"])
            if logic.upper() != "AND":
                base += float(item.get("matched_groups", 0)) * 2.0
            results.append(ScoredResult(diagram=item["diagram"], score=base))
        
        # 如果提供了意图理解结果，调整评分权重
        if intent_result:
            results = self._adjust_scores_by_intent(results, intent_result)
        
        # 按评分降序排序
        results.sort(key=lambda x: x.score, reverse=True)

        # --- Post filter for "series code + diagram" queries ---
        # When users ask like "天龙KL 电路图", we want KL to behave like a *series code*,
        # and avoid returning "role variants" that are missing a concrete configuration segment.
        # This also aligns the first-step option grouping with the expectation of "车型变体" buckets.
        try:
            if logic.upper() == "AND" and keywords:
                has_series_code = any(
                    isinstance(k, str)
                    and re.fullmatch(r"[A-Z]{2,3}", k.strip().upper() or "")
                    and (k.strip().upper() or "") not in {"ECU", "VEC", "VECU", "BCM", "ABS", "ESP", "DOC", "DCI", "DCM", "EDC", "LNG"}
                    for k in keywords
                )
                has_diagram_word = any(isinstance(k, str) and ("图" in k or "电路" in k) for k in keywords)
                if has_series_code and has_diagram_word:
                    role_keywords = ["牵引车", "载货车", "自卸车", "环卫车", "专用车", "搅拌车"]
                    config_pat = re.compile(r"_D\d{2,3}[._]")
                    filtered = []
                    for r in results:
                        fn = r.diagram.file_name or ""
                        if any(w in fn for w in role_keywords):
                            # If it's a role/usage variant but doesn't carry a concrete "Dxxx" config segment, drop it.
                            if not config_pat.search(fn):
                                continue
                        filtered.append(r)
                    results = filtered
        except Exception as e:
            # Never fail the search pipeline because of a heuristic post-filter.
            print(f"[WARN] post-filter skipped due to error: {e}")
        
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

    def filter_results(
        self,
        results: List[ScoredResult],
        brand: Optional[str] = None,
        model: Optional[str] = None,
        diagram_type: Optional[str] = None,
        vehicle_category: Optional[str] = None
    ) -> List[ScoredResult]:
        """
        兼容旧调用的筛选方法，内部调用层级筛选。
        """
        return self.filter_by_hierarchy(
            results,
            brand=brand,
            model=model,
            diagram_type=diagram_type,
            vehicle_category=vehicle_category,
        )
    
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
    
    def _parse_brand_model(self, option_value: str) -> tuple:
        """
        解析品牌+型号组合选项值
        
        Args:
            option_value: 选项值（如"东风 天龙KL"、"东风天龙 KL"、"东风 DOC"、"东风 DOCX 系列"等）
            
        Returns:
            (brand, model) 元组，如果无法解析则返回(None, None)
        """
        if not option_value:
            return None, None
        
        # 去除常见的后缀（如"系列"、"系列图"等）
        option_value = option_value.strip()
        suffixes = ['系列', '系列图', '系列电路图', '系列图', ' 系列']
        for suffix in suffixes:
            if option_value.endswith(suffix):
                option_value = option_value[:-len(suffix)].strip()
                break
        
        # 常见品牌列表
        common_brands = [
            '三一', '徐工', '斗山', '杰西博', '久保田', '卡特彼勒', '凯斯',
            '龙工', '柳工', '雷沃', '日立', '山东临工', '山重建机', '山河智能',
            '神钢', '沃尔沃', '小松', '东风', '解放', '重汽', '福田', '乘龙',
            '红岩', '豪瀚', '欧曼', '上汽大通', '五十铃', '康明斯', '玉柴'
        ]
        
        # 如果包含空格，尝试分割（如"东风 DOC"、"东风 DOCX"）
        if ' ' in option_value:
            parts = option_value.split(' ', 1)
            if len(parts) == 2:
                brand_part = parts[0].strip()
                model_part = parts[1].strip()
                
                # 去除型号部分的后缀
                for suffix in suffixes:
                    if model_part.endswith(suffix):
                        model_part = model_part[:-len(suffix)].strip()
                        break
                
                # 验证品牌部分是否是有效品牌
                brand = None
                for b in common_brands:
                    if b == brand_part or b in brand_part or brand_part in b:
                        brand = b
                        break
                
                if brand and model_part:
                    return brand, model_part
        
        # 尝试匹配品牌（不包含空格的情况）
        brand = None
        for b in common_brands:
            if b in option_value:
                brand = b
                break
        
        if not brand:
            return None, None
        
        # 提取品牌后面的部分作为型号
        brand_pos = option_value.find(brand)
        if brand_pos != -1:
            model_part = option_value[brand_pos + len(brand):].strip()
            # 去除常见的分隔符和后缀
            model_part = model_part.strip('_-. ')
            # 去除后缀
            for suffix in suffixes:
                if model_part.endswith(suffix):
                    model_part = model_part[:-len(suffix)].strip()
                    break
            if model_part:
                return brand, model_part
        
        return brand, None


# 全局搜索服务实例（单例模式）
_search_service_instance = None


def get_search_service() -> SearchService:
    """获取搜索服务实例（单例）"""
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SearchService()
    return _search_service_instance

