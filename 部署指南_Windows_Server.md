# Windows Server 2022 部署指南

## 📋 前置条件
- 服务器：Windows Server 2022
- 公网IP：101.37.89.207
- 安全组：已配置（端口80、8000、22）

---

## 🚀 部署步骤

### 第1步：远程连接到服务器

使用Windows自带的**远程桌面连接**（RDP）：
1. 按 `Win + R`，输入 `mstsc`
2. 输入服务器IP：`101.37.89.207`
3. 使用管理员账号登录

**或者使用PowerShell：**
```powershell
# 在本地电脑上执行
mstsc /v:101.37.89.207
```

---

### 第2步：安装Docker Desktop for Windows

1. **下载Docker Desktop**
   - 访问：https://www.docker.com/products/docker-desktop/
   - 下载 "Docker Desktop for Windows"
   - 注意：需要Windows 10/11或Windows Server 2019+

2. **安装Docker Desktop**
   - 运行安装程序
   - 安装完成后重启服务器
   - 启动Docker Desktop

3. **验证安装**
   ```powershell
   docker --version
   docker compose version
   ```

---

### 第3步：上传项目代码到服务器

**方法1：使用远程桌面直接复制**
1. 在远程桌面中，打开浏览器
2. 访问你的Git仓库（如果有）或使用文件共享
3. 下载项目代码到服务器

**方法2：使用Git克隆（推荐）**
```powershell
# 在服务器上打开PowerShell
cd C:\
git clone <你的Git仓库地址>
# 或者直接下载ZIP文件解压
```

**方法3：使用SCP上传（从本地电脑）**
```powershell
# 在本地电脑的PowerShell中执行
# 先打包项目
Compress-Archive -Path .\Navigation_Chatbot\* -DestinationPath .\navigation_chatbot.zip

# 使用WinSCP或其他工具上传到服务器
```

---

### 第4步：配置环境变量

1. **创建 `.env` 文件**
   ```powershell
   cd C:\Navigation_Chatbot  # 或你的项目路径
   Copy-Item env.example .env
   ```

2. **编辑 `.env` 文件**
   ```powershell
   notepad .env
   ```
   
   内容：
   ```
   ALI_QWEN_API_KEY=你的API密钥
   ALI_QWEN_MODEL=qwen-plus-2025-07-28
   BACKEND_HOST=0.0.0.0
   BACKEND_PORT=8000
   ```

---

### 第5步：启动Docker容器

```powershell
# 进入项目目录
cd C:\Navigation_Chatbot

# 构建并启动容器（后台运行）
docker compose up --build -d

# 查看容器状态
docker ps

# 查看日志（如果有问题）
docker compose logs
```

---

### 第6步：验证部署

1. **检查容器状态**
   ```powershell
   docker ps
   ```
   应该看到两个容器在运行：
   - `navigation_chatbot-backend-1`
   - `navigation_chatbot-frontend-1`

2. **测试访问**
   - 前端：http://101.37.89.207
   - 后端：http://101.37.89.207:8000/api/health
   - API文档：http://101.37.89.207:8000/docs

---

## ⚠️ 注意事项

1. **Windows防火墙**
   - 确保Windows防火墙允许端口80和8000
   - 或在防火墙中添加规则

2. **Docker Desktop资源**
   - 确保Docker Desktop分配了足够的CPU和内存
   - 建议至少2GB内存给Docker

3. **文件路径**
   - Windows路径使用反斜杠 `\`，但Docker内部使用正斜杠 `/`
   - 确保项目路径中没有空格和特殊字符

---

## 🔧 故障排查

### 如果容器无法启动：
```powershell
# 查看详细日志
docker compose logs backend
docker compose logs frontend

# 检查环境变量
docker compose config
```

### 如果端口被占用：
```powershell
# 查看端口占用
netstat -ano | findstr :80
netstat -ano | findstr :8000
```

### 如果无法访问：
1. 检查Windows防火墙
2. 检查Docker Desktop是否运行
3. 检查容器是否正常运行：`docker ps`


