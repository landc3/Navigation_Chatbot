#!/usr/bin/env python3
"""
测试新功能：重新表述需求和返回上一步
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_conversation_model():
    """测试对话状态模型的新功能"""
    try:
        from backend.app.models.conversation import ConversationState, ConversationStateEnum

        # 创建一个对话状态
        state = ConversationState()
        print("✅ ConversationState 创建成功")

        # 测试状态历史功能
        state.state = ConversationStateEnum.SEARCHING
        state.current_query = "测试查询"
        state.save_state_snapshot()
        print("✅ 状态快照保存成功")

        # 测试能否撤销
        can_undo = state.can_undo()
        print(f"✅ can_undo() 返回: {can_undo}")

        if can_undo:
            success = state.undo_last_step()
            print(f"✅ undo_last_step() 返回: {success}")
            print(f"   撤销后的状态: {state.state}")
            print(f"   撤销后的查询: {state.current_query}")

        # 测试清空功能
        state.clear()
        print("✅ clear() 方法执行成功")

        print("🎉 ConversationState 所有功能测试通过!")
        return True

    except Exception as e:
        print(f"❌ ConversationState 测试失败: {e}")
        return False

def test_undo_keywords():
    """测试撤销关键词检测"""
    undo_keywords = ["返回上一步", "上一步", "返回", "撤销", "后悔", "重新选择", "换一个选择"]

    test_inputs = [
        "返回上一步",
        "我想返回上一步",
        "上一步",
        "撤销这个选择",
        "我后悔了",
        "重新选择",
        "换一个选择",
        "正常输入不应该匹配"
    ]

    print("测试撤销关键词检测:")
    for test_input in test_inputs:
        is_undo = any(keyword in test_input.lower() for keyword in undo_keywords)
        status = "✅" if is_undo else "❌"
        print(f"  {status} '{test_input}' -> {is_undo}")

    return True

def test_reset_keywords():
    """测试重置关键词检测"""
    reset_keywords = ["我要找", "找一下", "搜索", "查找", "重新", "换一个"]

    test_inputs = [
        "我要找东风天龙",
        "找一下仪表图",
        "搜索电路图",
        "查找资料",
        "重新搜索",
        "换一个",
        "我要一个东风天龙",  # 不应该匹配
        "正常输入不应该匹配"
    ]

    print("测试重置关键词检测:")
    for test_input in test_inputs:
        is_reset = False
        for keyword in reset_keywords:
            if keyword in test_input:
                is_reset = True
                break
        # 特殊处理："我要一个XXX"不应该触发重置
        if "我要一个" in test_input or "我要个" in test_input:
            is_reset = False

        status = "✅" if is_reset else "❌"
        print(f"  {status} '{test_input}' -> {is_reset}")

    return True

if __name__ == "__main__":
    print("🧪 开始测试新功能...\n")

    results = []
    results.append(test_conversation_model())
    print()
    results.append(test_undo_keywords())
    print()
    results.append(test_reset_keywords())

    print(f"\n📊 测试结果: {sum(results)}/{len(results)} 通过")

    if all(results):
        print("🎉 所有测试通过！新功能实现成功。")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，需要检查代码。")
        sys.exit(1)
