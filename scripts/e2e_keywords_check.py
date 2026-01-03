"""
E2E（无服务）关键词回归检查

- 读取项目根目录的 keywords.txt
- 对每个关键词跑一次检索（不依赖 LLM）
- 输出命中数量，发现 0 命中会给出非 0 退出码

用法：
  python scripts/e2e_keywords_check.py
"""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from backend.app.services.search_service import get_search_service

    keywords_path = project_root / "keywords.txt"
    if not keywords_path.exists():
        print(f"ERROR: keywords.txt not found at: {keywords_path}")
        return 2

    lines = [ln.strip() for ln in keywords_path.read_text(encoding="utf-8").splitlines()]
    queries = [ln for ln in lines if ln and not ln.startswith("#")]
    if not queries:
        print("ERROR: No keywords found in keywords.txt")
        return 2

    svc = get_search_service()

    failed = []
    print(f"Running keyword checks: {len(queries)} queries")
    for q in queries:
        try:
            results = svc.search(query=q, logic="AND", max_results=200, use_fuzzy=True)
            n = len(results or [])
            if n == 0:
                # 模拟真实对话策略：AND 无结果时，走“逐步放宽关键词”兜底
                relaxed, _meta = svc.search_and_relax(query=q, max_results=200, use_fuzzy=True, intent_result=None)
                rn = len(relaxed or [])
                top = relaxed[0].diagram.file_name if rn else "-"
                print(f"- {q} -> AND:0 | relaxed:{rn} | top: {top}")
                if rn == 0:
                    failed.append(q)
            else:
                top = results[0].diagram.file_name if n else "-"
                print(f"- {q} -> AND:{n} | top: {top}")
        except Exception as e:
            print(f"- {q} -> ERROR: {e}")
            failed.append(q)

    if failed:
        print("\nFAILED queries (0 hits or error):")
        for q in failed:
            print(f"  - {q}")
        return 1

    print("\nAll keyword checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


