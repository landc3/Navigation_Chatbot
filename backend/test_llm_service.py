"""
测试LLM服务和意图理解功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.llm_service import get_llm_service
from backend.app.services.intent_service import get_intent_service


def test_llm_connection():
    """测试LLM连接"""
    print("=" * 60)
    print("测试LLM连接...")
    print("=" * 60)
    
    llm_service = get_llm_service()
    
    try:
        success = llm_service.test_connection()
        if success:
            print("[OK] LLM连接成功！")
        else:
            print("[FAIL] LLM连接失败")
        return success
    except Exception as e:
        print(f"[FAIL] LLM连接测试失败：{e}")
        return False


def test_llm_call():
    """测试LLM调用"""
    print("\n" + "=" * 60)
    print("测试LLM调用...")
    print("=" * 60)
    
    llm_service = get_llm_service()
    
    try:
        response = llm_service.call_qwen(
            prompt="你好，请介绍一下你自己",
            max_tokens=100,
            temperature=0.7
        )
        print(f"[OK] LLM调用成功！")
        print(f"回复：{response[:200]}...")
        return True
    except Exception as e:
        print(f"[FAIL] LLM调用失败：{e}")
        return False


def test_intent_parsing():
    """测试意图理解"""
    print("\n" + "=" * 60)
    print("测试意图理解...")
    print("=" * 60)
    
    intent_service = get_intent_service()
    
    test_queries = [
        "我要一个东风天龙的仪表图",
        "三一SY60的ECU电路图",
        "红岩杰狮保险丝图纸",
        "天龙KL电路图",
        "仪表针脚图"
    ]
    
    for query in test_queries:
        print(f"\n查询：{query}")
        try:
            intent_result = intent_service.parse_intent(query, use_llm=True)
            print(f"  品牌：{intent_result.brand}")
            print(f"  型号：{intent_result.model}")
            print(f"  类型：{intent_result.diagram_type}")
            print(f"  类别：{intent_result.vehicle_category}")
            print(f"  关键词：{intent_result.keywords}")
            print(f"  置信度：{intent_result.confidence:.2f}")
            print(f"  标准化查询：{intent_result.normalized_query}")
        except Exception as e:
            print(f"  [FAIL] 解析失败：{e}")
            # 尝试规则匹配
            try:
                intent_result = intent_service.parse_intent(query, use_llm=False)
                print(f"  [规则匹配] 品牌：{intent_result.brand}, 类型：{intent_result.diagram_type}")
            except Exception as e2:
                print(f"  [FAIL] 规则匹配也失败：{e2}")


def test_intent_with_llm():
    """测试使用LLM的意图理解"""
    print("\n" + "=" * 60)
    print("测试使用LLM的意图理解...")
    print("=" * 60)
    
    intent_service = get_intent_service()
    
    query = "我要一个东风天龙的仪表针脚图"
    print(f"查询：{query}")
    
    try:
        intent_result = intent_service.parse_intent(query, use_llm=True)
        print(f"\n解析结果：")
        print(f"  品牌：{intent_result.brand}")
        print(f"  型号：{intent_result.model}")
        print(f"  类型：{intent_result.diagram_type}")
        print(f"  类别：{intent_result.vehicle_category}")
        print(f"  关键词：{intent_result.keywords}")
        print(f"  置信度：{intent_result.confidence:.2f}")
        print(f"  标准化查询：{intent_result.normalized_query}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 意图理解失败：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("开始测试LLM服务和意图理解功能...\n")
    
    # 测试LLM连接
    connection_ok = test_llm_connection()
    
    if connection_ok:
        # 测试LLM调用
        test_llm_call()
        
        # 测试意图理解（使用LLM）
        test_intent_with_llm()
    else:
        print("\n[WARN] LLM连接失败，跳过LLM相关测试")
        print("将使用规则匹配进行测试...")
    
    # 测试意图理解（规则匹配）
    print("\n" + "=" * 60)
    print("测试规则匹配的意图理解...")
    print("=" * 60)
    intent_service = get_intent_service()
    query = "东风天龙仪表图"
    intent_result = intent_service.parse_intent(query, use_llm=False)
    print(f"查询：{query}")
    print(f"品牌：{intent_result.brand}")
    print(f"类型：{intent_result.diagram_type}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

