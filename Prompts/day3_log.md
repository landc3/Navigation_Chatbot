# 第3天开发日志

## 📅 日期
第3天：意图理解与智能检索

---

## ✅ 今日进展

完成 LLM 集成：新增 `LLMService` 封装通义千问调用，支持参数配置与异常处理。
完成意图理解：Prompt 结构化 JSON 输出；新增 `IntentResult`；实现 JSON 解析/容错；补近义词与品牌补全规则。
完成检索优化：`SearchService.search_with_intent()` + 意图加权排序；意图失败自动降级关键词检索；无结果给出友好提示。
完成多轮对话：新增会话状态机与历史记录；`/api/chat` 支持选择题答案处理与多轮筛选。

---

## 🐛 遇到的问题

- LLM 调用延迟（约 1–3 秒），需要异步/缓存优化。
- JSON 输出不稳定：已容错，但复杂场景仍可能解析失败。
- 复杂意图准确率有限：当前用降级检索兜底，后续继续优化 Prompt/规则。

---

## 📋 明日计划

- 选择题生成：问题/选项文本与排序展示优化（可引入 LLM）。
- 对话流程：返回上一步、重述需求、提示文案优化。
- 性能：LLM 异步 + 缓存（意图/检索）。

---

## 📊 当前状态

- LLM 服务封装 ✅（`backend/app/services/llm_service.py`）
- 意图理解数据模型 ✅（`backend/app/models/intent.py`）
- 对话状态与多会话管理 ✅（`backend/app/models/conversation.py`）
- 智能检索增强 ✅（`backend/app/services/search_service.py`）
- Chat API 集成意图理解与多轮对话 ✅（`backend/app/api/chat.py`）

---

## 🎯 总结

打通“意图理解 → 意图驱动检索 → 多轮筛选对话”主链路，为第4天选择题与对话体验优化打基础。

---

**生成时间**：第3天开发完成后


