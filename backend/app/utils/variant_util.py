"""
Variant grouping utilities.

We use this for "first-step grouping" and for applying user selection afterwards.
The key design goal: the grouping key computed during question generation must be
identical to the key computed when applying the selection.
"""

from __future__ import annotations

import re
from typing import Optional


_ROLE_KEYWORDS = ["牵引车", "载货车", "自卸车", "环卫车", "专用车", "搅拌车"]
_CN_GUO_RE = re.compile(r"^国[三四五六七]$")


def _strip_ext(file_name: str) -> str:
    return re.sub(r"\.[A-Za-z0-9]{2,5}$", "", file_name or "").strip()


def variant_key_for_query(file_name: str, query: str) -> Optional[str]:
    """
    Compute a stable grouping key from a filename, given the user query context.

    Two strategies:
    - Series-code queries (e.g. 天龙KL电路图): group by p0 / p0_p1 (role variant) / p0_Dxxx
    - ECU/code queries (e.g. C81电路图 / EDC17C81电路图): group by prefix parts:
        - p0_p1 (brand + model-ish)
        - include p2 if it is "国四/国五/..." (important discriminator)
        - or include p1 if it is numeric (e.g. 奥铃_493)
    """
    if not file_name:
        return None
    base = _strip_ext(file_name)
    parts = [p for p in base.split("_") if p]
    if not parts:
        return None

    q = query or ""
    has_ecu_code = bool(re.search(r"[A-Za-z]{1,6}\d{1,3}", q))
    has_series_code = bool(re.search(r"[A-Z]{2,3}", q)) and not has_ecu_code

    # Strategy A: series-code (KL/KC/VL...) queries
    if has_series_code:
        p0 = parts[0]
        if len(parts) == 1:
            return p0
        p1 = parts[1]

        is_role_variant = any(w in p1 for w in _ROLE_KEYWORDS) or bool(re.match(r"^\d+x\d+", p1, flags=re.IGNORECASE))
        if is_role_variant:
            # only keep role variants with a concrete Dxxx segment
            if len(parts) >= 3 and re.match(r"^D\d{2,3}[._]", parts[2]):
                return f"{p0}_{p1}"
            return None

        # model followed by Dxxx (e.g. 东风新天龙KL_D320_...)
        if re.fullmatch(r"D\d{2,3}", p1):
            return f"{p0}_{p1}"
        return p0

    # Strategy B: ECU/code queries (C81/EDC17C81...) and general "电路图 + code" searches
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}_{parts[1]}"

    p0, p1, p2 = parts[0], parts[1], parts[2]
    # If p2 is 国四/国五/... include it
    if _CN_GUO_RE.match(p2):
        return f"{p0}_{p1}_{p2}"
    # Otherwise, default to first two parts (this covers 福田_时代康瑞H1 / 江淮_瑞风M5)
    return f"{p0}_{p1}"


