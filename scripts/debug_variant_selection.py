import re
import sys
from pathlib import Path

# Ensure project root on sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.search_service import get_search_service


def variant_key(file_name: str):
    """Replicate current variant_key logic used in QuestionService/chat.py."""
    if not file_name:
        return None
    base = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", file_name).strip()
    parts = [p for p in base.split("_") if p]
    if not parts:
        return None
    p0 = parts[0]
    if len(parts) == 1:
        return p0
    p1 = parts[1]

    role_keywords = ["牵引车", "载货车", "自卸车", "环卫车", "专用车", "搅拌车"]
    is_role_variant = any(w in p1 for w in role_keywords) or bool(re.match(r"^\d+x\d+", p1, flags=re.IGNORECASE))
    if is_role_variant:
        if len(parts) >= 3 and re.match(r"^D\d{2,3}[._]", parts[2]):
            return f"{p0}_{p1}"
        return None

    if re.fullmatch(r"D\d{2,3}", p1):
        return f"{p0}_{p1}"
    return p0


def simulate_select(results, option_name: str):
    base = (option_name or "").strip()
    for suf in (" 系列", "系列"):
        if base.endswith(suf):
            base = base[: -len(suf)].strip()
            break
    picked = []
    for r in results:
        k = variant_key(r.diagram.file_name or "")
        if k and k == base:
            picked.append(r)
    return base, picked


def main():
    ss = get_search_service()
    q = "天龙KL电路图"
    rs = ss.search(q, logic="AND", max_results=100000, use_fuzzy=True)
    print("query:", q)
    print("total:", len(rs))

    # show keys
    key_counts = {}
    for r in rs:
        fn = r.diagram.file_name or ""
        k = variant_key(fn)
        key_counts[k] = key_counts.get(k, 0) + 1
        print("---")
        print("key:", repr(k))
        print("fn :", fn)

    print("\nunique keys/counts:")
    for k, c in sorted(key_counts.items(), key=lambda x: (-(x[1]), str(x[0]))):
        print(repr(k), "=>", c)

    # simulate the 5 options we expect
    option_names = [
        "东风天龙KL_6x4环卫车 系列",
        "东风天龙KL 系列",
        "东风天龙KL_6x4牵引车 系列",
        "东风新天龙KL 系列",
        "东风新天龙KL_D320 系列",
    ]
    print("\nSimulate selection:")
    for opt in option_names:
        base, picked = simulate_select(rs, opt)
        print(opt, "-> base", repr(base), "picked", len(picked))
        if picked:
            print("  first:", picked[0].diagram.file_name)


if __name__ == "__main__":
    main()


