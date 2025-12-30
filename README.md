# 智能车辆电路图资料导航 Chatbot

基于大语言模型的车辆电路图检索对话机器人，帮助用户通过自然语言对话快速定位所需的车辆电路图文档。

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Node.js 16+
- npm 或 yarn

### 安装依赖

#### 后端依赖
```bash
pip install -r requirements.txt
```

#### 前端依赖
```bash
cd frontend
npm install
```

### 配置环境变量

复制 `env.example` 为 `.env` 并配置：
```bash
cp env.example .env
```

编辑 `.env` 文件，设置你的API密钥：
```
ALI_QWEN_API_KEY=your_api_key_here
```

### 启动服务

#### 启动后端（终端1）
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端将在 `http://localhost:8000` 启动

#### 启动前端（终端2）
```bash
cd frontend
npm run dev
```

前端将在 `http://localhost:3000` 启动

### 访问应用

打开浏览器访问：`http://localhost:3000`

## 📁 项目结构

```
Navigation_Chatbot/
├── backend/              # 后端代码
│   ├── app/
│   │   ├── main.py       # FastAPI主应用
│   │   ├── models/       # 数据模型
│   │   ├── services/     # 业务逻辑
│   │   ├── api/          # API路由
│   │   └── utils/        # 工具函数
│   └── test_data_loader.py
├── frontend/             # 前端代码
│   ├── src/
│   │   ├── components/   # React组件
│   │   ├── pages/        # 页面
│   │   └── services/     # API调用
│   └── package.json
├── Prompts/              # 开发提示文档
├── config.py             # 配置文件
├── 资料清单.csv          # 数据文件（4235条记录）
└── keywords.txt          # 搜索关键词示例
```

## 🧪 测试

### 测试数据加载模块
```bash
python backend/test_data_loader.py
```

### 测试API接口
```bash
# 健康检查
curl http://localhost:8000/api/health

# 聊天接口
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "东风天龙仪表针脚图"}'
```

## 📚 开发文档

- [开发项目描述](开发项目描述.md)
- [5天开发计划](5天开发计划.md)
- [快速开始指南](快速开始.md)
- [第1天开发总结](Prompts/day1_summary.md)

## 🎯 功能特性

- ✅ 数据加载和预处理
- ✅ 基础关键词搜索
- ✅ 聊天界面
- ✅ RESTful API接口
- 🔄 智能意图理解（开发中）
- 🔄 多轮对话引导（开发中）

## 📝 开发进度

- [x] 第1天：项目搭建与数据准备 ✅
- [ ] 第2天：核心检索功能开发
- [ ] 第3天：意图理解与智能检索
- [ ] 第4天：多轮对话引导功能
- [ ] 第5天：界面优化与部署

## 📄 许可证

MIT License

