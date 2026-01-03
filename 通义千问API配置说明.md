# 通义千问 API 配置说明

## 一、API 获取方式

### 1. 注册/登录阿里云账号
- 访问：https://www.aliyun.com/
- 如果没有账号，先注册一个

### 2. 开通 DashScope 服务
- 访问 DashScope 控制台：https://dashscope.console.aliyun.com/overview
- 点击"开通服务" → "去开通"
- 阅读并同意服务协议后，点击"立即开通"

### 3. 创建 API Key
- 在 DashScope 控制台，导航至"API-KEY 管理"页面
- 点击"创建新的 API-KEY"
- 系统会生成一个新的 API Key（格式：`sk-xxxxxxxxxxxxx`）
- **重要**：请妥善保存，API Key 只显示一次

## 二、价格说明

通义千问提供多个模型版本，价格不同：

| 模型版本 | 输入价格 | 输出价格 | 适用场景 | 特殊功能 |
|---------|---------|---------|---------|---------|
| **Qwen-Turbo** | 0.001元/1K tokens | 0.003元/1K tokens | 简单任务，快速响应 | - |
| **Qwen-Plus-2025-07-28** | 阶梯计费 | 阶梯计费 | 标准任务，性能平衡（推荐）⭐ | 支持1M上下文，深度思考模式 |
| **Qwen-Max** | 0.12元/1K tokens | 0.12元/1K tokens | 复杂任务，最强性能 | - |

**本项目推荐使用 Qwen-Plus-2025-07-28（最新版本）**：
- ✅ 最新版本（2025年7月28日快照）
- ✅ 支持1M上下文长度（适合长对话）
- ✅ 阶梯计费（根据上下文长度）
- ✅ 支持深度思考和文本生成模式切换
- ✅ 在中英文能力、工具调用上进行了增强
- ✅ 适合意图理解和选择题生成

## 三、环境变量配置

### Windows 系统

#### 方法1：使用 .env 文件（推荐）
1. 在项目根目录创建 `.env` 文件
2. 复制 `.env.example` 的内容
3. 修改 API Key：
   ```
   ALI_QWEN_API_KEY=sk-your-api-key-here
   ```

#### 方法2：系统环境变量
1. 右键"此电脑" → "属性"
2. 点击"高级系统设置"
3. 点击"环境变量"
4. 在"用户变量"中新建：
   - 变量名：`ALI_QWEN_API_KEY`
   - 变量值：`sk-your-api-key-here`

#### 方法3：PowerShell 临时设置（仅当前会话）
```powershell
$env:ALI_QWEN_API_KEY="sk-your-api-key-here"
```

### Linux/Mac 系统

#### 方法1：使用 .env 文件（推荐）
```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
nano .env
```

#### 方法2：系统环境变量
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export ALI_QWEN_API_KEY="sk-your-api-key-here"

# 重新加载配置
source ~/.bashrc  # 或 source ~/.zshrc
```

## 四、Python 代码中使用

### 安装 SDK
```bash
pip install dashscope
```

### 使用示例
```python
import os
from dashscope import Generation

# 从环境变量读取 API Key
api_key = os.getenv('ALI_QWEN_API_KEY', 'sk-your-api-key-here')

# 调用 API
def call_qwen(prompt, model='qwen-plus'):
    response = Generation.call(
        model=model,
        api_key=api_key,
        prompt=prompt,
        max_tokens=1500,
        temperature=0.7
    )
    return response.output.text

# 使用示例
result = call_qwen("你好，请介绍一下你自己")
print(result)
```

## 五、API 调用限制

- **免费额度**：新用户通常有免费额度（具体查看 DashScope 控制台）
- **QPS限制**：不同模型有不同的 QPS（每秒查询数）限制
- **Token限制**：单次请求的最大 token 数有限制

## 六、安全建议

1. **不要将 API Key 提交到 Git**
   - 确保 `.env` 文件在 `.gitignore` 中
   - 不要将 API Key 硬编码在代码中

2. **定期更换 API Key**
   - 如果怀疑泄露，立即在 DashScope 控制台删除并重新创建

3. **使用环境变量**
   - 生产环境使用环境变量或密钥管理服务

## 七、测试 API 连接

创建测试脚本 `test_api.py`：

```python
import os
from dashscope import Generation

def test_qwen_api():
    api_key = os.getenv('ALI_QWEN_API_KEY')
    
    if not api_key:
        print("❌ 错误：未找到 ALI_QWEN_API_KEY 环境变量")
        return False
    
    try:
        response = Generation.call(
            model='qwen-plus',
            api_key=api_key,
            prompt='你好，请回复"API连接成功"',
            max_tokens=50
        )
        
        if response.status_code == 200:
            print("✅ API 连接成功！")
            print(f"回复：{response.output.text}")
            return True
        else:
            print(f"❌ API 调用失败：{response.message}")
            return False
    except Exception as e:
        print(f"❌ 错误：{e}")
        return False

if __name__ == '__main__':
    test_qwen_api()
```

运行测试：
```bash
python test_api.py
```

## 八、常见问题

### Q1: API Key 格式是什么？
A: 格式为 `sk-` 开头的字符串，例如：`sk-your-api-key-here`

### Q2: 如何查看 API 使用量和费用？
A: 登录 DashScope 控制台 → 费用中心，可以查看使用量和费用

### Q3: API 调用失败怎么办？
A: 
1. 检查 API Key 是否正确
2. 检查网络连接
3. 查看 DashScope 控制台的错误日志
4. 确认账户余额是否充足

### Q4: 支持哪些编程语言？
A: 官方提供 Python SDK，其他语言可以通过 HTTP API 调用

---

**你的 API Key 已配置：** `sk-your-api-key-here`

现在可以开始开发了！🚀

