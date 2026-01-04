"""
Option merge utility

Goal:
- When option count is large (> threshold), merge highly similar options to reduce obvious duplicates.
- Similarity rule: merge only when similarity >= 0.5 (roughly "50%+ characters are the same").
- Keep behavior safe: merged options carry `ids` (or can be built from `id`) so downstream filtering remains precise.
"""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re
from typing import Any, Dict, List, Optional, Tuple


_EXT_RE = re.compile(r"\.(docx|doc|pdf|pptx|ppt|xlsx|xls)$", flags=re.IGNORECASE)


def _strip_ext(s: str) -> str:
    return _EXT_RE.sub("", s or "").strip()


def _norm_for_similarity(s: str) -> str:
    """
    Normalize for similarity computation (not display):
    - remove extension
    - remove all whitespace
    - collapse repeated punctuation noise
    """
    s = _strip_ext(str(s or ""))
    s = re.sub(r"\s+", "", s)
    return s


def _char_overlap_ratio(a: str, b: str) -> float:
    """
    Character multiset overlap ratio:
      intersection_chars / max(len(a), len(b))
    This matches the intuitive "50%+ characters are the same" requirement better than pure edit distance.
    """
    if not a or not b:
        return 0.0
    ca = Counter(a)
    cb = Counter(b)
    inter = sum((ca & cb).values())
    denom = max(len(a), len(b))
    return float(inter) / float(denom) if denom else 0.0


def name_similarity(a: str, b: str) -> float:
    """
    Similarity score in [0,1]. Uses max of:
    - difflib.SequenceMatcher ratio (order-aware)
    - character multiset overlap ratio (order-insensitive)
    """
    na = _norm_for_similarity(a)
    nb = _norm_for_similarity(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ov = _char_overlap_ratio(na, nb)
    return max(seq, ov)


def _display_base_name(s: str) -> str:
    """
    Build a compact display name for a merged group.
    Heuristic:
    - strip extension
    - if string begins with a bracket tag like "【推荐】", keep it, then cut before the *next* "【...".
      This matches cases like: "【推荐】解放动力...【VGT/VNT_...】..." -> "【推荐】解放动力..."
    - otherwise keep the full stripped string
    """
    raw = _strip_ext(str(s or "")).strip()
    if not raw:
        return ""
    # remove duplicated spaces for display only
    raw = re.sub(r"\s+", " ", raw).strip()
    if "】" in raw:
        end_tag = raw.find("】") + 1
        nxt = raw.find("【", end_tag)
        if nxt != -1:
            return raw[:nxt].strip()
    return raw


def _longest_common_prefix(strings: List[str]) -> str:
    if not strings:
        return ""
    s0 = strings[0]
    for i in range(len(s0)):
        ch = s0[i]
        for s in strings[1:]:
            if i >= len(s) or s[i] != ch:
                return s0[:i]
    return s0


def _choose_group_name(names: List[str]) -> str:
    """
    Choose a stable merged display name for a group.
    Prefer common base names; if they differ, use a conservative common prefix (>=3 chars),
    otherwise fall back to the first base name.
    """
    bases = [b for b in (_display_base_name(n) for n in names) if b]
    if not bases:
        return ""
    # If all bases equal (after removing spaces), use it
    bases_norm = [re.sub(r"\s+", "", b) for b in bases]
    if len(set(bases_norm)) == 1:
        return bases[0]
    # Prefer a base that is a common substring of all others (avoid overly-short prefixes like “东风天”)
    # Choose the longest such base (more informative).
    candidates = []
    for b in bases_norm:
        if len(b) < 4:
            continue
        ok = True
        for other in bases_norm:
            if b not in other:
                ok = False
                break
        if ok:
            candidates.append(b)
    if candidates:
        return max(candidates, key=len)

    # Fallback: keep the first base name (stable), do NOT use very short LCP which can destroy meaning.
    return bases[0]


def merge_similar_options(
    options: List[Dict[str, Any]],
    *,
    enabled_min_len: int = 6,
    similarity_threshold: float = 0.5,
    name_key: str = "name",
) -> List[Dict[str, Any]]:
    """
    Merge similar options when option count is large.

    - Only runs when len(options) >= enabled_min_len.
    - Two options are considered similar when name_similarity(nameA, nameB) >= similarity_threshold.
    - Merged option:
      - keeps `type` (if present) from the first member
      - sets `name` to a compact group name
      - sets `ids` to union of member ids (from `ids` list and/or `id`)
      - does NOT set single `id` to avoid overriding ids-based filtering in chat selection
      - `count` defaults to len(ids)

    Returns a new list preserving the first-occurrence order of groups.
    """
    if not options or len(options) < enabled_min_len:
        return options or []

    n = len(options)
    names = [str((o or {}).get(name_key, "") or "") for o in options]

    # Union-Find for clustering
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        ni = names[i]
        if not ni:
            continue
        for j in range(i + 1, n):
            nj = names[j]
            if not nj:
                continue
            if name_similarity(ni, nj) >= similarity_threshold:
                union(i, j)

    # Build groups by root in first-occurrence order
    groups: Dict[int, List[int]] = {}
    order: List[int] = []
    for idx in range(n):
        r = find(idx)
        if r not in groups:
            groups[r] = []
            order.append(r)
        groups[r].append(idx)

    merged_out: List[Dict[str, Any]] = []
    for r in order:
        members = groups[r]
        if not members:
            continue

        if len(members) == 1:
            # Keep original option untouched
            merged_out.append(options[members[0]])
            continue

        # Merge ids from `ids` or `id`
        id_set = set()
        for m in members:
            o = options[m] or {}
            ids = o.get("ids")
            if isinstance(ids, list):
                id_set.update(ids)
            oid = o.get("id")
            if oid is not None:
                id_set.add(oid)

        # If we cannot produce ids, do not merge (safety: keep original disambiguation)
        if not id_set:
            for m in members:
                merged_out.append(options[m])
            continue

        first = options[members[0]] or {}
        group_names = [names[m] for m in members]
        group_name = _choose_group_name(group_names) or _strip_ext(group_names[0])

        merged_item: Dict[str, Any] = {}
        # carry through type if present
        if "type" in first:
            merged_item["type"] = first.get("type")
        merged_item[name_key] = group_name
        merged_item["ids"] = sorted(id_set)
        merged_item["count"] = len(id_set)
        merged_out.append(merged_item)

    return merged_out


