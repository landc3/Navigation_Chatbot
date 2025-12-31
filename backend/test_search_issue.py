"""
测试搜索问题：为什么集成第三天代码后无法找到"东风天龙仪表针脚图"
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.search_service import get_search_service
from backend.app.services.intent_service import get_intent_service
from backend.app.models.intent_result import IntentResult

def test_search_without_intent():
    """测试不使用意图理解的搜索"""
    print("=" * 60)
    print("测试1: 不使用意图理解的搜索")
    print("=" * 60)
    
    search_service = get_search_service()
    query = "东风天龙仪表针脚图"
    
    results = search_service.search(
        query=query,
        logic="AND",
        max_results=10,
        use_fuzzy=True,
        intent_result=None  # 不使用意图理解
    )
    
    print(f"查询: {query}")
    print(f"找到 {len(results)} 个结果:")
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. [ID: {result.diagram.id}] {result.diagram.file_name}")
        print(f"   品牌: {result.diagram.brand}, 型号: {result.diagram.model}, 类型: {result.diagram.diagram_type}")
        print(f"   评分: {result.score:.2f}")
        print()
    
    return results

def test_intent_parsing():
    """测试意图理解"""
    print("=" * 60)
    print("测试2: 意图理解结果")
    print("=" * 60)
    
    intent_service = get_intent_service()
    query = "东风天龙仪表针脚图"
    
    # 测试LLM解析
    try:
        intent_result = intent_service.parse_intent(query, use_llm=True)
        print(f"查询: {query}")
        print(f"品牌: {intent_result.brand}")
        print(f"型号: {intent_result.model}")
        print(f"类型: {intent_result.diagram_type}")
        print(f"类别: {intent_result.vehicle_category}")
        print(f"关键词: {intent_result.keywords}")
        print(f"标准化查询: {intent_result.normalized_query}")
        print(f"置信度: {intent_result.confidence}")
        print(f"是否为空: {intent_result.is_empty()}")
        print()
        return intent_result
    except Exception as e:
        print(f"LLM解析失败: {e}")
        # 降级为规则匹配
        intent_result = intent_service.parse_intent(query, use_llm=False)
        print(f"规则匹配结果:")
        print(f"品牌: {intent_result.brand}")
        print(f"型号: {intent_result.model}")
        print(f"类型: {intent_result.diagram_type}")
        print(f"关键词: {intent_result.keywords}")
        print()
        return intent_result

def test_search_with_intent():
    """测试使用意图理解的搜索"""
    print("=" * 60)
    print("测试3: 使用意图理解的搜索")
    print("=" * 60)
    
    search_service = get_search_service()
    intent_service = get_intent_service()
    query = "东风天龙仪表针脚图"
    
    # 解析意图
    try:
        intent_result = intent_service.parse_intent(query, use_llm=True)
    except Exception as e:
        print(f"LLM解析失败，使用规则匹配: {e}")
        intent_result = intent_service.parse_intent(query, use_llm=False)
    
    print(f"意图理解结果:")
    print(f"  品牌: {intent_result.brand}")
    print(f"  型号: {intent_result.model}")
    print(f"  类型: {intent_result.diagram_type}")
    print(f"  关键词: {intent_result.keywords}")
    print()
    
    # 使用意图理解搜索
    results = search_service.search(
        query=query,
        logic="AND",
        max_results=10,
        use_fuzzy=True,
        intent_result=intent_result
    )
    
    print(f"查询: {query}")
    print(f"找到 {len(results)} 个结果:")
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. [ID: {result.diagram.id}] {result.diagram.file_name}")
        print(f"   品牌: {result.diagram.brand}, 型号: {result.diagram.model}, 类型: {result.diagram.diagram_type}")
        print(f"   评分: {result.score:.2f}")
        print()
    
    return results

def test_search_with_intent_or_logic():
    """测试使用意图理解和OR逻辑的搜索"""
    print("=" * 60)
    print("测试4: 使用意图理解和OR逻辑的搜索")
    print("=" * 60)
    
    search_service = get_search_service()
    intent_service = get_intent_service()
    query = "东风天龙仪表针脚图"
    
    # 解析意图
    try:
        intent_result = intent_service.parse_intent(query, use_llm=True)
    except Exception as e:
        print(f"LLM解析失败，使用规则匹配: {e}")
        intent_result = intent_service.parse_intent(query, use_llm=False)
    
    # 使用OR逻辑搜索
    results = search_service.search(
        query=query,
        logic="OR",
        max_results=10,
        use_fuzzy=True,
        intent_result=intent_result
    )
    
    print(f"查询: {query}")
    print(f"找到 {len(results)} 个结果:")
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. [ID: {result.diagram.id}] {result.diagram.file_name}")
        print(f"   品牌: {result.diagram.brand}, 型号: {result.diagram.model}, 类型: {result.diagram.diagram_type}")
        print(f"   评分: {result.score:.2f}")
        print()
    
    return results

if __name__ == "__main__":
    print("\n开始测试搜索问题...\n")
    
    # 测试1: 不使用意图理解
    results1 = test_search_without_intent()
    
    # 测试2: 意图理解
    intent_result = test_intent_parsing()
    
    # 测试3: 使用意图理解 + AND逻辑
    results3 = test_search_with_intent()
    
    # 测试4: 使用意图理解 + OR逻辑
    results4 = test_search_with_intent_or_logic()
    
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"不使用意图理解: {len(results1)} 个结果")
    print(f"使用意图理解 + AND逻辑: {len(results3)} 个结果")
    print(f"使用意图理解 + OR逻辑: {len(results4)} 个结果")
    print()
    
    if len(results1) > 0 and len(results3) == 0:
        print("❌ 问题确认: 使用意图理解后无法找到结果！")
        print("   原因分析:")
        print("   1. 意图理解可能提取了不准确的关键词")
        print("   2. AND逻辑要求所有关键词都必须匹配")
        print("   3. 筛选条件可能过于严格")
    elif len(results1) > 0 and len(results3) > 0:
        print("✅ 使用意图理解也能找到结果")
    elif len(results1) == 0:
        print("⚠️  即使不使用意图理解也无法找到结果，可能是数据问题")


