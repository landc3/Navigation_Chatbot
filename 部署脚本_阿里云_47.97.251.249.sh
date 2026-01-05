#!/bin/bash
# 阿里云服务器一键部署脚本
# 服务器IP: 47.97.251.249
# 项目地址: https://github.com/landc3/Navigation_Chatbot.git

# 不立即退出，允许错误处理
set +e

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

# 自动检测系统类型和包管理器
detect_package_manager() {
    if command -v apt &> /dev/null; then
        PKG_MANAGER="apt"
        UPDATE_CMD="apt update"
        UPGRADE_CMD="apt upgrade -y"
        INSTALL_CMD="apt install -y"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
        UPDATE_CMD="yum update -y"
        UPGRADE_CMD="yum upgrade -y"
        INSTALL_CMD="yum install -y"
    elif command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
        UPDATE_CMD="dnf update -y"
        UPGRADE_CMD="dnf upgrade -y"
        INSTALL_CMD="dnf install -y"
    else
        echo -e "${RED}❌ 无法检测包管理器，请手动安装依赖${NC}"
        exit 1
    fi
    
    # 显示检测到的系统信息
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo -e "${GREEN}✅ 检测到系统: $PRETTY_NAME${NC}"
    fi
    echo -e "${GREEN}✅ 使用包管理器: $PKG_MANAGER${NC}"
}

# 检测包管理器
detect_package_manager

# 更新系统
echo -e "${YELLOW}📦 更新系统包...${NC}"
$UPDATE_CMD
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  系统更新失败，继续执行...${NC}"
fi

# 安装必要工具
echo -e "${YELLOW}📦 安装必要工具...${NC}"
$INSTALL_CMD git curl wget unzip nano
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 安装必要工具失败${NC}"
    exit 1
fi

# 重新启用错误退出
set -e

# 检查并安装Docker
install_docker() {
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✅ Docker已安装: $(docker --version)${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}🐳 安装Docker...${NC}"
    
    # 方法1：使用yum/dnf直接安装（推荐，适用于阿里云服务器）
    if [ "$PKG_MANAGER" = "yum" ] || [ "$PKG_MANAGER" = "dnf" ]; then
        echo -e "${YELLOW}   尝试使用 $PKG_MANAGER 安装Docker...${NC}"
        
        # 安装Docker依赖
        $INSTALL_CMD yum-utils device-mapper-persistent-data lvm2
        
        # 添加Docker官方yum源（如果网络允许）
        if curl -fsSL https://download.docker.com/linux/centos/docker-ce.repo -o /etc/yum.repos.d/docker-ce.repo 2>/dev/null; then
            $INSTALL_CMD docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            if [ $? -eq 0 ]; then
                systemctl enable docker
                systemctl start docker
                echo -e "${GREEN}✅ Docker安装完成（使用官方源）${NC}"
                return 0
            fi
        fi
        
        # 如果官方源失败，尝试使用阿里云镜像源
        echo -e "${YELLOW}   尝试使用阿里云镜像源安装Docker...${NC}"
        
        # 配置阿里云Docker镜像源
        cat > /etc/yum.repos.d/docker-ce.repo << 'EOF'
[docker-ce-stable]
name=Docker CE Stable - $basearch
baseurl=https://mirrors.aliyun.com/docker-ce/linux/centos/$releasever/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=https://mirrors.aliyun.com/docker-ce/linux/centos/gpg
EOF
        
        # 清理缓存并安装
        $PKG_MANAGER clean all
        $INSTALL_CMD docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        if [ $? -eq 0 ]; then
            systemctl enable docker
            systemctl start docker
            echo -e "${GREEN}✅ Docker安装完成（使用阿里云镜像源）${NC}"
            return 0
        fi
    fi
    
    # 方法2：使用get.docker.com脚本（备选方案）
    echo -e "${YELLOW}   尝试使用官方安装脚本...${NC}"
    
    # 设置不验证SSL（仅用于安装脚本）
    export DOCKER_OPTS="--insecure-registry"
    
    # 尝试使用get.docker.com，如果失败则使用阿里云镜像
    if curl -fsSL https://get.docker.com -o /tmp/get-docker.sh 2>/dev/null; then
        bash /tmp/get-docker.sh --mirror Aliyun
    else
        # 如果curl失败，尝试使用wget
        if command -v wget &> /dev/null; then
            wget -O /tmp/get-docker.sh https://get.docker.com --no-check-certificate 2>/dev/null
            if [ $? -eq 0 ]; then
                bash /tmp/get-docker.sh --mirror Aliyun
            else
                echo -e "${RED}❌ 无法下载Docker安装脚本${NC}"
                return 1
            fi
        else
            echo -e "${RED}❌ 无法下载Docker安装脚本（curl和wget都不可用）${NC}"
            return 1
        fi
    fi
    
    if [ $? -eq 0 ]; then
        systemctl enable docker
        systemctl start docker
        echo -e "${GREEN}✅ Docker安装完成${NC}"
        return 0
    else
        echo -e "${RED}❌ Docker安装失败${NC}"
        echo -e "${YELLOW}   请手动安装Docker，参考: https://docs.docker.com/engine/install/${NC}"
        return 1
    fi
}

# 执行Docker安装
install_docker

# 验证Docker安装
if command -v docker &> /dev/null; then
    docker --version
else
    echo -e "${RED}❌ Docker安装失败，请检查错误信息${NC}"
    exit 1
fi

# 检查并安装Docker Compose
install_docker_compose() {
    # 检查是否已安装（新版本Docker包含compose插件）
    if docker compose version &> /dev/null; then
        echo -e "${GREEN}✅ Docker Compose已安装（作为Docker插件）: $(docker compose version)${NC}"
        return 0
    fi
    
    # 检查旧版本docker-compose命令
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✅ Docker Compose已安装: $(docker-compose --version)${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}🐳 安装Docker Compose...${NC}"
    
    # 方法1：使用curl下载（优先）
    COMPOSE_URL="https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)"
    
    if curl -L "$COMPOSE_URL" -o /usr/local/bin/docker-compose 2>/dev/null; then
        chmod +x /usr/local/bin/docker-compose
        if docker-compose --version &> /dev/null; then
            echo -e "${GREEN}✅ Docker Compose安装完成${NC}"
            return 0
        fi
    fi
    
    # 方法2：使用wget下载（备选）
    if command -v wget &> /dev/null; then
        echo -e "${YELLOW}   尝试使用wget下载...${NC}"
        if wget "$COMPOSE_URL" -O /usr/local/bin/docker-compose --no-check-certificate 2>/dev/null; then
            chmod +x /usr/local/bin/docker-compose
            if docker-compose --version &> /dev/null; then
                echo -e "${GREEN}✅ Docker Compose安装完成${NC}"
                return 0
            fi
        fi
    fi
    
    # 方法3：使用pip安装（最后备选）
    echo -e "${YELLOW}   尝试使用pip安装...${NC}"
    if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
        PIP_CMD=$(command -v pip3 || command -v pip)
        $PIP_CMD install docker-compose 2>/dev/null
        if docker-compose --version &> /dev/null; then
            echo -e "${GREEN}✅ Docker Compose安装完成（使用pip）${NC}"
            return 0
        fi
    fi
    
    echo -e "${YELLOW}⚠️  Docker Compose安装失败，但Docker已包含compose插件，可以继续使用${NC}"
    echo -e "${YELLOW}   使用 'docker compose' 命令代替 'docker-compose'${NC}"
    return 0
}

# 执行Docker Compose安装
install_docker_compose

# 验证Docker Compose
if docker compose version &> /dev/null || docker-compose --version &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose可用${NC}"
else
    echo -e "${YELLOW}⚠️  Docker Compose未安装，但可以使用 'docker compose' 命令${NC}"
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

# 查找可用的文本编辑器
find_editor() {
    if command -v nano &> /dev/null; then
        echo "nano"
    elif command -v vim &> /dev/null; then
        echo "vim"
    elif command -v vi &> /dev/null; then
        echo "vi"
    else
        echo ""
    fi
}

# 配置环境变量
echo -e "${YELLOW}⚙️  配置环境变量...${NC}"
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        cp env.example .env
        echo -e "${YELLOW}⚠️  请编辑 .env 文件，设置 ALI_QWEN_API_KEY${NC}"
        
        EDITOR=$(find_editor)
        if [ -z "$EDITOR" ]; then
            echo -e "${RED}❌ 未找到文本编辑器（nano/vim/vi），请手动安装${NC}"
            echo -e "${YELLOW}   安装nano: $INSTALL_CMD nano${NC}"
            echo -e "${YELLOW}   然后手动编辑: $PROJECT_DIR/.env${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}   使用编辑器: $EDITOR${NC}"
        echo -e "${YELLOW}   文件路径: $PROJECT_DIR/.env${NC}"
        echo ""
        read -p "是否现在编辑 .env 文件? (y/n): " edit_now
        if [ "$edit_now" = "y" ] || [ "$edit_now" = "Y" ]; then
            $EDITOR .env
            if [ $? -ne 0 ]; then
                echo -e "${YELLOW}⚠️  编辑器退出，请检查是否已保存${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  请稍后手动编辑 .env 文件${NC}"
            echo -e "${YELLOW}   使用命令: $EDITOR $PROJECT_DIR/.env${NC}"
            echo -e "${YELLOW}   或使用: cat > $PROJECT_DIR/.env << 'EOF'${NC}"
            echo -e "${YELLOW}   ALI_QWEN_API_KEY=sk-你的密钥${NC}"
            echo -e "${YELLOW}   EOF${NC}"
            echo ""
            read -p "按Enter继续（确保已配置API密钥）..." dummy
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
    EDITOR=$(find_editor)
    if [ -n "$EDITOR" ]; then
        echo -e "${YELLOW}   使用命令: $EDITOR $PROJECT_DIR/.env${NC}"
    else
        echo -e "${YELLOW}   文件路径: $PROJECT_DIR/.env${NC}"
        echo -e "${YELLOW}   使用以下命令设置API密钥:${NC}"
        echo -e "${YELLOW}   echo 'ALI_QWEN_API_KEY=sk-你的密钥' > $PROJECT_DIR/.env${NC}"
    fi
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

