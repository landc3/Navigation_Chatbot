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

#### 方法1：一键启动（推荐）⭐

使用 `run.py` 脚本一键启动前后端并自动打开浏览器：

```bash
python run.py
```

**功能特点**：
- ✅ 自动检查并安装依赖
- ✅ 同时启动前后端服务
- ✅ 自动打开浏览器访问前端
- ✅ 优雅处理服务停止

#### 方法2：手动启动

##### 启动后端（终端1）
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端将在 `http://localhost:8000` 启动

##### 启动前端（终端2）
```bash
cd frontend
npm run dev
```

前端将在 `http://localhost:3500` 启动（Vite）

### 访问应用

- **前端**: http://localhost:3500
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

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

### 使用 keywords.txt 做回归检查（推荐）
```bash
python scripts/e2e_keywords_check.py
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

## 🚢 部署（生产环境）

### 🌐 阿里云服务器部署

#### 前置准备
1. **购买阿里云ECS服务器**（推荐配置：2核4G）
2. **配置安全组规则**：
   - 端口 80：HTTP前端访问
   - 端口 8000：后端API
   - 端口 22：SSH远程管理（建议只开放你的IP）

#### 快速部署（使用GitHub仓库）

**GitHub仓库地址**: https://github.com/landc3/Navigation_Chatbot.git

**完整部署步骤**：查看 [远程服务器部署指南.md](远程服务器部署指南.md)

**快速命令（Windows Server）：**
```powershell
# 1. 远程连接到服务器（使用RDP）
mstsc /v:101.37.89.207

# 2. 在服务器上克隆仓库
cd C:\
git clone https://github.com/landc3/Navigation_Chatbot.git
cd Navigation_Chatbot

# 3. 配置环境变量
Copy-Item env.example .env
notepad .env  # 编辑并填入你的API密钥

# 4. 启动Docker容器
docker compose up --build -d

# 5. 验证部署
docker ps
```

#### 详细部署指南
- **Windows Server 2022（推荐）**：查看 [远程服务器部署指南.md](远程服务器部署指南.md)
- **Ubuntu Linux**：查看 [部署指南_Ubuntu_Linux.md](部署指南_Ubuntu_Linux.md)

#### 部署完成后的访问地址
- **前端应用**：`http://<你的公网IP>`
- **后端API**：`http://<你的公网IP>:8000`
- **API文档**：`http://<你的公网IP>:8000/docs`

---

### 本地Docker部署

#### 方案A：Docker 一键部署（推荐）

- **前置**：安装 Docker / Docker Compose
- **配置**：在宿主机环境变量或 `.env` 中设置 `ALI_QWEN_API_KEY`
- **启动**：

```bash
docker compose up --build -d
```

- **访问**：
  - **前端**：`http://localhost`（Nginx 静态托管 + `/api` 反代）
  - **后端**：`http://localhost:8000`

#### 方案B：本地生产构建

- **Windows PowerShell**：

```powershell
.\scripts\start_prod.ps1
```

- **macOS/Linux**：

```bash
bash scripts/start_prod.sh
```

