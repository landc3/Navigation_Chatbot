# 阿里云Workbench部署指南

## 📋 当前状态
- ✅ 已通过Workbench登录到服务器
- ✅ 服务器：Windows Server 2022
- ✅ 服务器IP：101.37.89.207
- ✅ GitHub仓库：https://github.com/landc3/Navigation_Chatbot.git

---

## 🚀 在Workbench中部署项目

### 第1步：打开PowerShell

在Workbench中：

1. **方法1：从开始菜单打开**
   - 点击左下角"开始"按钮
   - 搜索"PowerShell"
   - 右键点击"Windows PowerShell" → "以管理员身份运行"（推荐）


---

### 第2步：检查并安装必要工具

#### 2.1 检查Git是否安装

```powershell
git --version
```

**如果未安装Git：**

```powershell
# 使用winget安装（推荐）
winget install --id Git.Git -e --source winget

# 或者下载安装包
# 访问：https://git-scm.com/download/win
# 下载并安装后，重启PowerShell
```

#### 2.2 检查Docker是否安装

```powershell
docker --version
```

**如果未安装Docker Desktop：**

1. 在Workbench中打开浏览器（Microsoft Edge）
2. 访问：https://www.docker.com/products/docker-desktop/
3. 下载"Docker Desktop for Windows"
4. 运行安装程序
5. 安装完成后重启服务器
6. 启动Docker Desktop（等待右下角图标变绿）

**验证Docker运行：**
```powershell
docker info
```

---

### 第3步：克隆GitHub仓库

在PowerShell中执行：

```powershell
# 进入C盘根目录
cd C:\

# 克隆项目
git clone https://github.com/landc3/Navigation_Chatbot.git

# 进入项目目录
cd Navigation_Chatbot

# 查看项目文件
dir
```

---

### 第4步：配置环境变量

```powershell
# 确保在项目目录中
cd C:\Navigation_Chatbot

# 复制环境变量模板
Copy-Item env.example .env

# 编辑.env文件
notepad .env
```

**在打开的记事本中，编辑内容：**

```
ALI_QWEN_API_KEY=你的阿里云API密钥
ALI_QWEN_MODEL=qwen-plus-2025-07-28
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

**重要：**
- 将 `你的阿里云API密钥` 替换为你的真实API密钥
- 保存文件（Ctrl+S）
- 关闭记事本

---

### 第5步：配置Windows防火墙

在PowerShell中（以管理员身份运行）：

```powershell
# 允许端口80（HTTP）
New-NetFirewallRule -DisplayName "Navigation_Chatbot_HTTP_80" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow

# 允许端口8000（后端API）
New-NetFirewallRule -DisplayName "Navigation_Chatbot_API_8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# 验证规则已添加
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*Navigation_Chatbot*"}
```

---

### 第6步：启动Docker容器

```powershell
# 确保在项目目录中
cd C:\Navigation_Chatbot

# 确保Docker Desktop正在运行
# 检查Docker状态
docker info

# 构建并启动容器（后台运行）
docker compose up --build -d

# 查看容器状态
docker ps
```

**应该看到两个容器：**
- `navigation_chatbot-backend-1` (状态: Up)
- `navigation_chatbot-frontend-1` (状态: Up)

---

### 第7步：查看日志验证启动

```powershell
# 查看所有容器日志
docker compose logs

# 查看后端日志
docker compose logs backend

# 查看前端日志
docker compose logs frontend

# 实时查看日志（按Ctrl+C退出）
docker compose logs -f
```

---

### 第8步：验证部署成功

#### 在Workbench中测试（本地访问）

```powershell
# 测试后端健康检查
Invoke-WebRequest -Uri http://localhost:8000/api/health

# 或者使用curl（如果已安装）
curl http://localhost:8000/api/health
```

#### 在本地电脑浏览器中访问

- **前端应用**: http://101.37.89.207
- **后端API**: http://101.37.89.207:8000/api/health
- **API文档**: http://101.37.89.207:8000/docs

---

## ⚡ 快速部署（使用脚本）

如果你已经安装了Git和Docker，可以使用一键部署脚本：

```powershell
# 进入项目目录
cd C:\Navigation_Chatbot

# 进入scripts目录
cd scripts

# 以管理员身份运行部署脚本
.\deploy_remote.ps1
```

脚本会自动完成所有步骤！

---

## 🔧 常用管理命令

### 查看容器状态
```powershell
docker ps
```

### 停止容器
```powershell
cd C:\Navigation_Chatbot
docker compose down
```

### 重启容器
```powershell
cd C:\Navigation_Chatbot
docker compose restart
```

### 更新代码后重新部署
```powershell
cd C:\Navigation_Chatbot
# 拉取最新代码
git pull

# 重新构建并启动
docker compose up --build -d
```

### 查看容器资源使用
```powershell
docker stats
```

---

## ⚠️ 故障排查

### 问题1：容器无法启动

**检查日志：**
```powershell
docker compose logs backend
docker compose logs frontend
```

**常见原因：**
- API密钥未配置或错误
- 端口被占用
- Docker Desktop未启动

### 问题2：端口被占用

**检查端口占用：**
```powershell
netstat -ano | findstr :80
netstat -ano | findstr :8000
```

**停止占用端口的进程：**
```powershell
# 找到占用端口的进程ID（PID），然后停止
taskkill /PID <进程ID> /F
```

### 问题3：无法从外网访问

**检查清单：**
1. ✅ 安全组规则已配置（阿里云控制台）
2. ✅ Windows防火墙已开放端口
3. ✅ Docker容器正在运行：`docker ps`
4. ✅ 服务器可以本地访问：`Invoke-WebRequest http://localhost:8000/api/health`

### 问题4：Git克隆失败

**如果网络问题：**
```powershell
# 检查网络连接
ping github.com

# 如果无法访问GitHub，可以：
# 1. 使用代理
# 2. 或者下载ZIP文件手动上传
```

---

## 📝 部署完成检查清单

- [ ] Git已安装
- [ ] Docker Desktop已安装并运行
- [ ] 项目代码已克隆到服务器
- [ ] `.env` 文件已配置API密钥
- [ ] Windows防火墙已开放端口80和8000
- [ ] Docker容器已成功启动
- [ ] 可以在浏览器访问 http://101.37.89.207
- [ ] 可以在浏览器访问 http://101.37.89.207:8000/docs

---

## 🎉 部署成功！

部署完成后，你的导航聊天机器人可以通过以下地址访问：

- **前端应用**: http://101.37.89.207
- **后端API**: http://101.37.89.207:8000
- **API文档**: http://101.37.89.207:8000/docs

**恭喜！你的应用已经成功部署到公网了！** 🚀


