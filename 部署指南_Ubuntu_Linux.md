# Ubuntu Linux 部署指南（推荐）

## 📋 为什么选择Linux？
- ✅ Docker在Linux上原生支持，性能更好
- ✅ 资源占用更少（适合小型服务器）
- ✅ 更适合生产环境部署
- ✅ 社区支持更完善

---

## 🔄 第1步：重装系统为Ubuntu

### 在阿里云控制台操作：

1. **停止服务器**
   - 进入ECS控制台
   - 找到你的实例（101.37.89.207）
   - 点击"停止" → 等待停止完成

2. **更换系统盘**
   - 点击"更多" → "云盘和镜像" → "更换操作系统"
   - 选择镜像：**Ubuntu 22.04 64位**（推荐）
   - 设置root密码（记住这个密码！）
   - 点击"确认更换"
   - 等待5-10分钟完成

3. **启动服务器**
   - 系统更换完成后，点击"启动"
   - 等待1-2分钟启动完成

---

## 🔌 第2步：SSH连接到服务器

**Windows PowerShell：**
```powershell
ssh root@101.37.89.207
```

**首次连接会提示，输入 `yes`**

**输入root密码**（刚才设置的密码）

---

## 🐳 第3步：安装Docker和Docker Compose

```bash
# 更新系统
apt update && apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com | bash

# 启动Docker服务
systemctl enable docker
systemctl start docker

# 验证Docker安装
docker --version

# 安装Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 验证Docker Compose安装
docker compose version
```

---

## 📦 第4步：上传项目代码

**方法1：使用Git（推荐）**
```bash
# 安装Git
apt install git -y

# 克隆项目（如果有Git仓库）
cd /root
git clone <你的Git仓库地址>
cd Navigation_Chatbot
```

**方法2：使用SCP上传（从本地电脑）**

在**本地电脑的PowerShell**中执行：
```powershell
# 打包项目
Compress-Archive -Path .\Navigation_Chatbot\* -DestinationPath .\navigation_chatbot.zip

# 使用WinSCP或FileZilla上传到服务器 /root/ 目录
# 或者使用scp命令（需要安装OpenSSH客户端）
scp navigation_chatbot.zip root@101.37.89.207:/root/
```

然后在**服务器上**执行：
```bash
# 安装unzip
apt install unzip -y

# 解压文件
cd /root
unzip navigation_chatbot.zip -d Navigation_Chatbot
cd Navigation_Chatbot
```

---

## ⚙️ 第5步：配置环境变量

```bash
# 复制环境变量模板
cp env.example .env

# 编辑环境变量
nano .env
```

**编辑内容：**
```
ALI_QWEN_API_KEY=你的API密钥
ALI_QWEN_MODEL=qwen-plus-2025-07-28
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

**保存：** 按 `Ctrl + X`，然后 `Y`，然后 `Enter`

---

## 🚀 第6步：启动应用

```bash
# 构建并启动容器（后台运行）
docker compose up --build -d

# 查看容器状态
docker ps

# 查看日志（如果有问题）
docker compose logs -f
```

---

## ✅ 第7步：验证部署

1. **检查容器状态**
   ```bash
   docker ps
   ```
   应该看到两个容器：
   - `navigation_chatbot-backend-1`
   - `navigation_chatbot-frontend-1`

2. **测试访问**
   - 打开浏览器访问：http://101.37.89.207
   - 应该能看到导航聊天机器人界面

3. **测试API**
   ```bash
   curl http://localhost:8000/api/health
   ```

---

## 🔧 常用命令

```bash
# 查看容器日志
docker compose logs backend
docker compose logs frontend

# 重启容器
docker compose restart

# 停止容器
docker compose down

# 更新代码后重新部署
docker compose up --build -d

# 查看资源使用
docker stats
```

---

## 🛡️ 安全建议

1. **修改SSH端口**（可选）
2. **禁用root登录，创建新用户**（可选）
3. **配置自动备份**
4. **设置监控告警**

---

## 📞 遇到问题？

1. **容器无法启动**：查看日志 `docker compose logs`
2. **端口被占用**：检查 `netstat -tulpn | grep :80`
3. **无法访问**：检查防火墙 `ufw status`
4. **内存不足**：升级服务器配置


