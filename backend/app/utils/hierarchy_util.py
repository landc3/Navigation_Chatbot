"""
层级工具模块

为 CircuitDiagram 提供：
- 品牌/型号/类型/车辆类别筛选
- 从结果中提取选择题选项
- 从结果中汇总所有层级字段（用于fallback）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set

from backend.app.models.circuit_diagram import CircuitDiagram
import re
import unicodedata


class HierarchyUtil:
    """
    层级与字段提取工具类（静态方法集合）。
    注意：该类被多个服务直接 import 使用，属于启动链路关键依赖。
    """

    # 复合品牌列表（需要优先匹配）
    COMPOUND_BRANDS: List[str] = [
        "东风天龙",
        "东风乘龙",
        "一汽解放",
        "中国重汽",
        "上汽大通",
        "福田欧曼",
        "红岩杰狮",
        "重汽豪瀚",
        "重汽豪汉",
    ]

    # 常见品牌列表（用于验证/解析）
    COMMON_BRANDS: List[str] = [
        "三一",
        "徐工",
        "斗山",
        "杰西博",
        "久保田",
        "卡特彼勒",
        "凯斯",
        "龙工",
        "柳工",
        "雷沃",
        "日立",
        "山东临工",
        "山重建机",
        "山河智能",
        "神钢",
        "沃尔沃",
        "小松",
        "东风",
        "解放",
        "重汽",
        "福田",
        "乘龙",
        "红岩",
        "豪瀚",
        "欧曼",
        "上汽大通",
        "五十铃",
        "康明斯",
        "玉柴",
    ]

    # 常见类型列表（用于意图验证/解析）
    COMMON_DIAGRAM_TYPES: List[str] = [
        "仪表电路图",
        "ECU电路图",
        "整车电路图",
        "电路图",
        "仪表图",
        "ECU图",
        "整车图",
        "线路图",
        "接线图",
        "针脚图",
        "仪表模块",
    ]

    # 常见车辆类别（用于意图验证/解析）
    COMMON_VEHICLE_CATEGORIES: List[str] = [
        "工程机械",
        "商用车",
        "乘用车",
    ]

    @staticmethod
    def _norm(s: Optional[str]) -> str:
        if not s:
            return ""
        # 统一规范化：全半角、大小写、去分隔符（下划线/空格/括号等）
        s2 = unicodedata.normalize("NFKC", str(s))
        s2 = s2.replace("*", "")
        s2 = s2.lower()
        s2 = re.sub(r"[\s_\-·•.。/\\()（）\[\]【】{}<>《》“”\"'’`~!@#$%^&*+=|:;，,；：?？]+", "", s2)
        return s2.strip()

    @staticmethod
    def _any_contains(haystacks: Iterable[str], needle: str) -> bool:
        needle_n = HierarchyUtil._norm(needle)
        if not needle_n:
            return False
        for h in haystacks:
            h_n = HierarchyUtil._norm(h)
            if not h_n:
                continue
            if needle_n in h_n or h_n in needle_n:
                return True
        return False

    @staticmethod
    def _diagram_text_fields(diagram: CircuitDiagram) -> List[str]:
        fields: List[str] = []
        fields.append(diagram.file_name or "")
        fields.extend(diagram.hierarchy_path or [])
        if diagram.brand:
            fields.append(diagram.brand)
        if diagram.model:
            fields.append(diagram.model)
        if diagram.diagram_type:
            fields.append(diagram.diagram_type)
        if diagram.vehicle_category:
            fields.append(diagram.vehicle_category)
        return fields

    @staticmethod
    def filter_by_brand(diagrams: Sequence[CircuitDiagram], brand: str) -> List[CircuitDiagram]:
        """按品牌筛选（支持复合品牌与包含关系匹配）。"""
        brand_n = HierarchyUtil._norm(brand)
        if not brand_n:
            return list(diagrams)

        filtered: List[CircuitDiagram] = []
        for d in diagrams:
            # 优先使用解析字段
            if d.brand and (brand_n in HierarchyUtil._norm(d.brand) or HierarchyUtil._norm(d.brand) in brand_n):
                filtered.append(d)
                continue
            # 回退：在层级路径/文件名中做包含匹配
            if HierarchyUtil._any_contains(HierarchyUtil._diagram_text_fields(d), brand):
                filtered.append(d)
        return filtered

    @staticmethod
    def filter_by_model(diagrams: Sequence[CircuitDiagram], model: str) -> List[CircuitDiagram]:
        """按型号筛选（包含匹配；兼容“系列”等后缀）。"""
        model_n = HierarchyUtil._norm(model)
        if not model_n:
            return list(diagrams)

        # 简单清理常见后缀，提升命中率
        model_variants = {model_n}
        for suf in ("系列", "系列图", "系列电路图"):
            if model_n.endswith(suf):
                model_variants.add(model_n[: -len(suf)].strip())

        def _any_contains_strict(haystacks: Iterable[str], needle: str) -> bool:
            """
            Strict containment: only accept "needle in haystack".
            Rationale: the previous bidirectional check (haystack in needle) can cause
            over-matching when hierarchy contains generic short tokens like "天龙",
            making "天龙" match "天龙KL_6x4牵引车" across unrelated variants.
            """
            needle_n = HierarchyUtil._norm(needle)
            if not needle_n:
                return False
            for h in haystacks:
                h_n = HierarchyUtil._norm(h)
                if not h_n:
                    continue
                if needle_n in h_n:
                    return True
            return False

        filtered: List[CircuitDiagram] = []
        for d in diagrams:
            # 优先使用解析字段
            # IMPORTANT: Only accept "user_model in parsed_model".
            # The reverse ("parsed_model in user_model") makes generic parsed values like "天龙"
            # incorrectly match a specific selection like "天龙KL_6x4牵引车".
            if d.model and any(v and (v in HierarchyUtil._norm(d.model)) for v in model_variants):
                filtered.append(d)
                continue
            # 回退：在层级路径/文件名中搜索
            fields = HierarchyUtil._diagram_text_fields(d)
            if any(_any_contains_strict(fields, v) for v in model_variants):
                filtered.append(d)
        return filtered

    @staticmethod
    def filter_by_diagram_type(diagrams: Sequence[CircuitDiagram], diagram_type: str) -> List[CircuitDiagram]:
        """按电路图类型筛选（包含匹配）。"""
        t_n = HierarchyUtil._norm(diagram_type)
        if not t_n:
            return list(diagrams)

        filtered: List[CircuitDiagram] = []
        for d in diagrams:
            if d.diagram_type and (t_n in HierarchyUtil._norm(d.diagram_type) or HierarchyUtil._norm(d.diagram_type) in t_n):
                filtered.append(d)
                continue
            if HierarchyUtil._any_contains(HierarchyUtil._diagram_text_fields(d), diagram_type):
                filtered.append(d)
        return filtered

    @staticmethod
    def filter_by_vehicle_category(diagrams: Sequence[CircuitDiagram], vehicle_category: str) -> List[CircuitDiagram]:
        """按车辆类别筛选（包含匹配）。"""
        c_n = HierarchyUtil._norm(vehicle_category)
        if not c_n:
            return list(diagrams)

        filtered: List[CircuitDiagram] = []
        for d in diagrams:
            if d.vehicle_category and (c_n in HierarchyUtil._norm(d.vehicle_category) or HierarchyUtil._norm(d.vehicle_category) in c_n):
                filtered.append(d)
                continue
            if HierarchyUtil._any_contains(HierarchyUtil._diagram_text_fields(d), vehicle_category):
                filtered.append(d)
        return filtered

    @staticmethod
    def get_all_levels(diagrams: Sequence[CircuitDiagram]) -> Dict[str, Set[str]]:
        """
        汇总所有可用层级字段集合（用于fallback问题生成）。

        Returns:
            {
              "brands": set(...),
              "models": set(...),
              "types": set(...),
              "categories": set(...),
            }
        """
        brands: Set[str] = set()
        models: Set[str] = set()
        types: Set[str] = set()
        categories: Set[str] = set()

        for d in diagrams:
            if d.brand:
                brands.add(d.brand.strip())
            if d.model:
                models.add(d.model.strip())
            if d.diagram_type:
                types.add(d.diagram_type.strip())
            if d.vehicle_category:
                categories.add(d.vehicle_category.strip())

        # 兜底：如果解析字段缺失，尝试从层级路径中补一点信息
        if not brands or not models or not types or not categories:
            for d in diagrams:
                for level in d.hierarchy_path or []:
                    lv = (level or "").replace("*", "").strip()
                    if not lv:
                        continue
                    # 类型/类别/品牌的极简启发式
                    if any(k in lv for k in ("电路图", "仪表", "ECU", "整车", "线路", "接线", "针脚")):
                        types.add(lv)
                    if lv in HierarchyUtil.COMMON_VEHICLE_CATEGORIES:
                        categories.add(lv)
                    if lv in HierarchyUtil.COMMON_BRANDS or any(cb in lv for cb in HierarchyUtil.COMPOUND_BRANDS):
                        brands.add(lv)

        return {"brands": brands, "models": models, "types": types, "categories": categories}

    @staticmethod
    def extract_options(
        diagrams: Sequence[CircuitDiagram],
        option_type: str,
        max_options: int = 5,
    ) -> List[Dict]:
        """
        从电路图列表中提取选项（用于选择题）。

        option_type 支持：
        - brand / model / type / category / brand_model

        Returns:
            [{"name": str, "count": int}, ...]
        """
        opt = (option_type or "").strip().lower()
        if max_options <= 0:
            return []

        counts: Dict[str, int] = {}

        def add(name: Optional[str]):
            n = (name or "").replace("*", "").strip()
            if not n:
                return
            counts[n] = counts.get(n, 0) + 1

        for d in diagrams:
            if opt == "brand":
                add(d.brand)
            elif opt == "model":
                add(d.model)
            elif opt in ("type", "diagram_type"):
                add(d.diagram_type)
            elif opt in ("category", "vehicle_category"):
                add(d.vehicle_category)
            elif opt in ("brand_model", "brand+model"):
                b = (d.brand or "").strip()
                m = (d.model or "").strip()
                if b and m:
                    add(f"{b} {m}")
                elif b:
                    add(b)
                elif m:
                    add(m)
            else:
                # 未知类型：返回空，交由上层 fallback 处理
                return []

        options = [{"name": name, "count": count} for name, count in counts.items() if name]
        options.sort(key=lambda x: (-x["count"], x["name"]))
        return options[:max_options]

