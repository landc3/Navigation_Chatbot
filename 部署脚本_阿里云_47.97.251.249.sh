#!/bin/bash
# 阿里云服务器一键部署脚本
# 服务器IP: 47.97.251.249
# 项目地址: https://github.com/landc3/Navigation_Chatbot.git

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🚀 Navigation_Chatbot 部署脚本"
echo "服务器IP: 47.97.251.249"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 检查系统环境...${NC}"

# 更新系统
echo -e "${YELLOW}📦 更新系统包...${NC}"
apt update && apt upgrade -y

# 安装必要工具
echo -e "${YELLOW}📦 安装必要工具...${NC}"
apt install -y git curl wget unzip

# 检查并安装Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}🐳 安装Docker...${NC}"
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    echo -e "${GREEN}✅ Docker安装完成${NC}"
else
    echo -e "${GREEN}✅ Docker已安装: $(docker --version)${NC}"
fi

# 检查并安装Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${YELLOW}🐳 安装Docker Compose...${NC}"
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✅ Docker Compose安装完成${NC}"
else
    echo -e "${GREEN}✅ Docker Compose已安装${NC}"
fi

# 创建项目目录
PROJECT_DIR="/root/Navigation_Chatbot"
echo -e "${YELLOW}📁 准备项目目录...${NC}"

if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}⚠️  项目目录已存在，备份后重新克隆...${NC}"
    mv "$PROJECT_DIR" "${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
fi

# 克隆项目
echo -e "${YELLOW}📥 从GitHub克隆项目...${NC}"
cd /root
git clone https://github.com/landc3/Navigation_Chatbot.git
cd "$PROJECT_DIR"

# 配置环境变量
echo -e "${YELLOW}⚙️  配置环境变量...${NC}"
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        cp env.example .env
        echo -e "${YELLOW}⚠️  请编辑 .env 文件，设置 ALI_QWEN_API_KEY${NC}"
        echo -e "${YELLOW}   使用命令: nano $PROJECT_DIR/.env${NC}"
        echo ""
        read -p "是否现在编辑 .env 文件? (y/n): " edit_now
        if [ "$edit_now" = "y" ] || [ "$edit_now" = "Y" ]; then
            nano .env
        else
            echo -e "${RED}❌ 请稍后手动编辑 .env 文件后再运行部署${NC}"
            echo -e "${YELLOW}   文件路径: $PROJECT_DIR/.env${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ 未找到 env.example 文件${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env 文件已存在${NC}"
fi

# 检查API密钥是否配置
if grep -q "sk-your-api-key-here" .env 2>/dev/null || ! grep -q "ALI_QWEN_API_KEY=sk-" .env 2>/dev/null; then
    echo -e "${RED}❌ 请先配置 ALI_QWEN_API_KEY 在 .env 文件中${NC}"
    echo -e "${YELLOW}   使用命令: nano $PROJECT_DIR/.env${NC}"
    exit 1
fi

# 构建并启动容器
echo -e "${YELLOW}🏗️  构建Docker镜像...${NC}"
docker compose build

echo -e "${YELLOW}🚀 启动容器...${NC}"
docker compose up -d

# 等待服务启动
echo -e "${YELLOW}⏳ 等待服务启动（10秒）...${NC}"
sleep 10

# 检查容器状态
echo -e "${GREEN}📊 检查容器状态...${NC}"
docker ps

# 检查服务健康
echo -e "${YELLOW}🏥 检查服务健康状态...${NC}"
sleep 5

if curl -f http://localhost:8000/api/health &> /dev/null; then
    echo -e "${GREEN}✅ 后端服务运行正常${NC}"
else
    echo -e "${YELLOW}⚠️  后端服务可能还在启动中，请稍后检查${NC}"
fi

# 显示访问信息
echo ""
echo "=========================================="
echo -e "${GREEN}✅ 部署完成！${NC}"
echo "=========================================="
echo ""
echo "📱 访问地址："
echo -e "   ${GREEN}前端应用: http://47.97.251.249${NC}"
echo -e "   ${GREEN}后端API:  http://47.97.251.249:8000${NC}"
echo -e "   ${GREEN}API文档:  http://47.97.251.249:8000/docs${NC}"
echo ""
echo "🔧 常用命令："
echo "   查看日志: docker compose logs -f"
echo "   重启服务: docker compose restart"
echo "   停止服务: docker compose down"
echo "   更新代码: cd $PROJECT_DIR && git pull && docker compose up --build -d"
echo ""
echo "🛡️  安全组检查："
echo "   确保已开放端口: 80 (HTTP), 8000 (后端API), 22 (SSH)"
echo ""

