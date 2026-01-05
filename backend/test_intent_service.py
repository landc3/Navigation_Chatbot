"""
测试意图理解服务
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.llm_service import get_llm_service
from backend.app.services.search_service import get_search_service


def test_intent_parsing():
    """测试意图理解功能"""
    print("=" * 60)
    print("测试意图理解功能")
    print("=" * 60)
    
    llm_service = get_llm_service()
    
    test_queries = [
        "我要一个东风天龙的仪表图",
        "找一下JH6的ECU电路图",
        "三一工程机械的电路图",
        "红岩杰狮保险丝图纸",
        "豪瀚玻璃升降电路图"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        try:
            intent_result = llm_service.parse_intent(query)
            print(f"  品牌: {intent_result.brand}")
            print(f"  型号: {intent_result.model}")
            print(f"  类型: {intent_result.diagram_type}")
            print(f"  类别: {intent_result.vehicle_category}")
            print(f"  关键词: {intent_result.keywords}")
            print(f"  置信度: {intent_result.confidence:.2f}")
            print(f"  搜索查询: {intent_result.get_search_query()}")
        except Exception as e:
            print(f"  ❌ 错误: {str(e)}")


def test_search_with_intent():
    """测试结合意图理解的搜索"""
    print("\n" + "=" * 60)
    print("测试结合意图理解的搜索")
    print("=" * 60)
    
    llm_service = get_llm_service()
    search_service = get_search_service()
    
    test_query = "东风天龙仪表图"
    
    print(f"\n查询: {test_query}")
    
    # 意图理解
    try:
        intent_result = llm_service.parse_intent(test_query)
        print(f"意图理解结果:")
        print(f"  品牌: {intent_result.brand}")
        print(f"  型号: {intent_result.model}")
        print(f"  类型: {intent_result.diagram_type}")
    except Exception as e:
        print(f"  ❌ 意图理解失败: {str(e)}")
        return
    
    # 使用意图理解结果搜索
    try:
        results = search_service.search_with_intent(
            intent_result=intent_result,
            logic="OR",
            max_results=5,
            use_fuzzy=True
        )
        
        print(f"\n搜索结果（共{len(results)}个）:")
        for i, result in enumerate(results, 1):
            print(f"{i}. [ID: {result.diagram.id}] {result.diagram.file_name}")
            print(f"   评分: {result.score:.2f}")
            if result.diagram.brand:
                print(f"   品牌: {result.diagram.brand}")
            if result.diagram.model:
                print(f"   型号: {result.diagram.model}")
    except Exception as e:
        print(f"  ❌ 搜索失败: {str(e)}")


if __name__ == "__main__":
    print("开始测试...")
    
    # 测试意图理解
    test_intent_parsing()
    
    # 测试搜索
    test_search_with_intent()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)






