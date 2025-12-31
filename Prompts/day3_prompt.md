# 第3天开发任务 Prompt

## 📅 第3天：意图理解与智能检索

### 任务目标
集成大语言模型（通义千问），实现用户意图理解功能，优化智能检索，并搭建多轮对话基础框架。

---

## 上午任务（4小时）

### 1. 大语言模型集成

#### 当前状态
- ✅ 已配置通义千问API（config.py中）
- ✅ 已安装dashscope SDK（requirements.txt）
- ⚠️ 需要实现：LLM调用封装函数、意图理解Prompt模板

#### 任务清单

##### 1.1 LLM调用封装
- [ ] 创建 `backend/app/services/llm_service.py`
- [ ] 实现 `LLMService` 类
- [ ] 封装通义千问API调用
  - 使用 `dashscope.Generation.call()` 方法
  - 从 `config.py` 读取API配置
  - 实现错误处理和重试机制
  - 支持流式输出（可选）
- [ ] 实现基础调用方法 `call_llm(prompt, **kwargs)`
- [ ] 测试LLM调用是否正常

##### 1.2 意图理解Prompt模板设计
- [ ] 设计意图理解Prompt模板
  - 输入：用户自然语言查询
  - 输出：结构化的JSON格式（品牌、型号、类型、关键词等）
- [ ] 实现Prompt构建函数 `build_intent_prompt(user_query)`
- [ ] 定义意图理解结果的数据结构（`IntentResult` 类）
- [ ] 实现JSON解析和验证

#### 实现位置
- 创建 `backend/app/services/llm_service.py`
- 创建 `backend/app/models/intent.py`（意图理解结果模型）

---

### 2. 意图理解功能开发

#### 任务清单

##### 2.1 用户意图解析
- [ ] 实现 `IntentService` 类（在 `llm_service.py` 中或单独文件）
- [ ] 实现意图理解方法 `parse_intent(user_query: str) -> IntentResult`
- [ ] 提取信息：
  - **品牌**：三一、徐工、东风、解放、重汽等
  - **型号**：天龙KL、JH6、杰狮等
  - **类型**：仪表图、ECU电路图、整车电路图等
  - **关键词**：其他重要信息
- [ ] 处理模糊表达（如"天龙" → "东风天龙"）
- [ ] 处理近义词（如"仪表图" = "仪表电路图"）

##### 2.2 近义词识别
- [ ] 创建近义词词典（可选，或让LLM处理）
- [ ] 实现近义词映射函数
- [ ] 常见映射：
  - "仪表图" → "仪表电路图"、"仪表针脚图"
  - "ECU图" → "ECU电路图"、"电脑版电路图"
  - "整车图" → "整车电路图"

##### 2.3 模糊表达处理
- [ ] 实现品牌补全（如"天龙" → "东风天龙"）
- [ ] 实现型号补全（如"KL" → "天龙KL"）
- [ ] 使用LLM或规则引擎处理

#### 实现位置
- `backend/app/services/llm_service.py` 或 `backend/app/services/intent_service.py`
- `backend/app/models/intent.py`

---

## 下午任务（4小时）

### 3. 智能检索优化

#### 当前状态
- ✅ 已实现基础搜索功能（SearchService）
- ✅ 支持关键词搜索、模糊匹配、层级筛选
- ⚠️ 需要优化：结合意图理解结果优化搜索

#### 任务清单

##### 3.1 结合意图理解优化搜索
- [ ] 修改 `SearchService.search()` 方法，支持意图理解结果作为输入
- [ ] 实现 `search_with_intent(intent_result: IntentResult)` 方法
- [ ] 优化搜索策略：
  - 优先使用意图理解提取的品牌、型号、类型
  - 结合关键词进行多维度搜索
  - 提高匹配精度
- [ ] 当意图理解失败时，降级为关键词搜索

##### 3.2 语义搜索（可选）
- [ ] 如果时间允许，考虑实现向量数据库集成
- [ ] 使用向量相似度搜索（可选，第3天不强制）

##### 3.3 改进相关性评分
- [ ] 结合意图理解结果调整评分权重
- [ ] 意图匹配的结果权重更高
- [ ] 更新 `_calculate_match_score` 方法

##### 3.4 处理无结果情况
- [ ] 当搜索无结果时，使用LLM生成友好提示
- [ ] 建议用户修改查询或提供相关关键词

#### 实现位置
- `backend/app/services/search_service.py`（扩展）
- `backend/app/api/chat.py`（集成意图理解）

---

### 4. 多轮对话基础框架

#### 任务清单

##### 4.1 对话状态管理
- [ ] 创建 `ConversationState` 类（`backend/app/models/conversation.py`）
- [ ] 定义对话状态：
  - `INITIAL`：初始状态
  - `SEARCHING`：搜索中
  - `NEEDS_CHOICE`：等待用户选择
  - `FILTERING`：筛选中
  - `COMPLETED`：已完成
- [ ] 实现状态转换逻辑

##### 4.2 对话历史记录
- [ ] 创建 `ConversationHistory` 类
- [ ] 存储对话消息列表
- [ ] 存储当前搜索上下文（查询、结果、选项等）
- [ ] 实现历史记录管理方法：
  - `add_message(role, content)`
  - `get_recent_messages(n)`
  - `clear()`

##### 4.3 问题生成逻辑框架
- [ ] 创建 `QuestionService` 类（`backend/app/services/question_service.py`）
- [ ] 实现问题生成方法框架：
  - `generate_question(results, context)` - 生成问题
  - `format_options(options)` - 格式化选项
- [ ] 使用LLM生成自然的问题文本（可选，第3天先实现框架）

##### 4.4 对话流程控制
- [ ] 在 `chat.py` 中集成对话状态管理
- [ ] 实现对话流程：
  1. 接收用户输入
  2. 意图理解
  3. 执行搜索
  4. 判断是否需要选择题
  5. 生成响应
- [ ] 处理用户选择（A/B/C/D或文本）

#### 实现位置
- `backend/app/models/conversation.py`（新增）
- `backend/app/services/question_service.py`（扩展或新增）
- `backend/app/api/chat.py`（集成）

---

## 代码结构设计

### 新增文件
```
backend/app/
├── services/
│   ├── llm_service.py          # LLM服务（新增）
│   ├── intent_service.py        # 意图理解服务（可选，可合并到llm_service）
│   └── question_service.py      # 问题生成服务（扩展）
├── models/
│   ├── intent.py                # 意图理解结果模型（新增）
│   └── conversation.py         # 对话状态模型（新增）
└── api/
    └── chat.py                  # 需要更新，集成意图理解和对话管理
```

### LLM服务接口设计

```python
class LLMService:
    """LLM服务"""
    
    def call_llm(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1500,
        temperature: float = 0.7
    ) -> str:
        """调用LLM API"""
        pass
    
    def parse_intent(self, user_query: str) -> IntentResult:
        """解析用户意图"""
        pass
```

### 意图理解结果模型

```python
class IntentResult:
    """意图理解结果"""
    brand: Optional[str] = None      # 品牌
    model: Optional[str] = None      # 型号
    diagram_type: Optional[str] = None  # 电路图类型
    vehicle_category: Optional[str] = None  # 车辆类别
    keywords: List[str] = []         # 其他关键词
    original_query: str              # 原始查询
    confidence: float = 0.0          # 置信度（可选）
```

### 对话状态模型

```python
class ConversationState:
    """对话状态"""
    state: str                       # 当前状态
    current_query: str               # 当前查询
    search_results: List[ScoredResult]  # 搜索结果
    current_options: List[Dict]      # 当前选项
    filter_history: List[Dict]       # 筛选历史
    message_history: List[ChatMessage]  # 消息历史
```

---

## Prompt模板设计

### 意图理解Prompt模板

```
你是一个智能车辆电路图资料导航助手。请分析用户的查询，提取以下信息：

1. **品牌**：如三一、徐工、东风、解放、重汽等
2. **型号**：如天龙KL、JH6、杰狮等
3. **电路图类型**：如仪表图、ECU电路图、整车电路图等
4. **车辆类别**：如工程机械、商用车等
5. **其他关键词**：查询中的其他重要信息

用户查询：{user_query}

请以JSON格式返回结果：
{{
    "brand": "品牌名称或null",
    "model": "型号名称或null",
    "diagram_type": "电路图类型或null",
    "vehicle_category": "车辆类别或null",
    "keywords": ["关键词1", "关键词2"],
    "confidence": 0.0-1.0
}}

注意：
- 如果信息不明确，返回null
- 处理近义词（如"仪表图" = "仪表电路图"）
- 处理模糊表达（如"天龙" = "东风天龙"）
- keywords包含除品牌、型号、类型外的其他重要信息
```

---

## 交付物检查清单

### 必须完成
- [ ] LLM调用封装完成，可以正常调用通义千问API
- [ ] 意图理解功能可用，能够提取品牌、型号、类型等信息
- [ ] 近义词识别功能实现
- [ ] 模糊表达处理功能实现
- [ ] 搜索功能结合意图理解结果优化
- [ ] 对话状态管理实现
- [ ] 对话历史记录功能实现
- [ ] 问题生成逻辑框架搭建完成
- [ ] API接口集成意图理解和对话管理

### 代码质量要求
- 代码结构清晰，职责分离
- 注释完整，函数有文档字符串
- 错误处理完善（LLM调用失败、JSON解析失败等）
- 遵循Python最佳实践
- 单元测试覆盖主要功能

---

## 开发注意事项

1. **LLM调用成本**：注意控制API调用次数和token数量
2. **错误处理**：LLM调用可能失败，要有降级方案（使用关键词搜索）
3. **响应时间**：LLM调用较慢，考虑异步处理或超时设置
4. **JSON解析**：LLM返回的JSON可能格式不正确，要有容错处理
5. **向后兼容**：保持现有API接口兼容

---

## 测试建议

### 测试用例
1. **意图理解测试**：
   - "我要一个东风天龙的仪表图"
   - "找一下JH6的ECU电路图"
   - "三一工程机械的电路图"
   
2. **近义词测试**：
   - "仪表图" → 应识别为"仪表电路图"
   - "ECU图" → 应识别为"ECU电路图"
   
3. **模糊表达测试**：
   - "天龙" → 应补全为"东风天龙"
   - "KL" → 应识别为"天龙KL"（需要上下文）

4. **搜索优化测试**：
   - 使用意图理解结果搜索，验证结果更精准
   - 对比使用和不使用意图理解的搜索结果

5. **对话流程测试**：
   - 测试多轮对话状态转换
   - 测试对话历史记录
   - 测试用户选择处理

---

## 下一步准备

完成第3天后，为第4天做准备：
- 对话状态管理要为选择题生成做准备
- 问题生成框架要为第4天的选择题生成逻辑做准备
- API接口要考虑多轮对话的完整流程

---

**开始开发！** 🚀
