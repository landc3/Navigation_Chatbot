"""
测试通义千问 API 连接
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

try:
    from dashscope import Generation
except ImportError:
    print("错误：未安装 dashscope 库")
    print("请运行：pip install dashscope")
    sys.exit(1)


def test_qwen_api():
    """测试通义千问 API 连接"""
    api_key = os.getenv('ALI_QWEN_API_KEY', 'sk-your-api-key-here')
    model = os.getenv('ALI_QWEN_MODEL', 'qwen-plus-2025-07-28')  # 最新版本
    
    if not api_key:
        print("错误：未找到 ALI_QWEN_API_KEY 环境变量")
        print("请在 .env 文件中设置 ALI_QWEN_API_KEY")
        return False
    
    if not api_key.startswith('sk-'):
        print("警告：API Key 格式可能不正确（应以 'sk-' 开头）")
    
    print(f"API Key: {api_key[:10]}...{api_key[-10:]}")
    print(f"模型: {model}")
    print("正在测试 API 连接...\n")
    
    try:
        response = Generation.call(
            model=model,
            api_key=api_key,
            prompt='你好，请回复"API连接成功"',
            max_tokens=50,
            temperature=0.7
        )
        
        if response.status_code == 200:
            print("API 连接成功！")
            print(f"回复：{response.output.text}")
            print(f"Token 使用：{response.usage}")
            return True
        else:
            print(f"API 调用失败")
            print(f"状态码：{response.status_code}")
            print(f"错误信息：{response.message}")
            if hasattr(response, 'request_id'):
                print(f"请求ID：{response.request_id}")
            return False
            
    except Exception as e:
        print(f"错误：{e}")
        print("\n可能的原因：")
        print("1. API Key 不正确")
        print("2. 网络连接问题")
        print("3. DashScope 服务未开通")
        print("4. 账户余额不足")
        return False


if __name__ == '__main__':
    success = test_qwen_api()
    sys.exit(0 if success else 1)

