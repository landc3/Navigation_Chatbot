#!/bin/bash
# 终极修复方案：尝试多个镜像源，找到可用的

set +e  # 允许错误继续

echo "=========================================="
echo "🔧 终极修复方案：测试多个镜像源"
echo "=========================================="

cd /root/Navigation_Chatbot

# 测试镜像源函数
test_mirror() {
    local mirror=$1
    local image=$2
    echo "测试镜像源: $mirror"
    if docker pull "${mirror}/${image}" 2>&1 | grep -q "Error\|denied\|failed"; then
        return 1
    else
        return 0
    fi
}

# 可用的镜像源列表（按优先级）
MIRRORS=(
    "dockerhub.azk8s.cn"
    "docker.m.daocloud.io"
    "dockerproxy.com"
    "docker.nju.edu.cn"
)

# 测试Python镜像
echo ""
echo "📥 测试Python镜像源..."
PYTHON_MIRROR=""
for mirror in "${MIRRORS[@]}"; do
    echo "尝试: $mirror/library/python:3.11-slim"
    if docker pull "${mirror}/library/python:3.11-slim" 2>/dev/null; then
        PYTHON_MIRROR="$mirror"
        echo "✅ Python镜像拉取成功: $mirror"
        break
    else
        echo "❌ $mirror 失败，尝试下一个..."
    fi
done

# 测试Node镜像
echo ""
echo "📥 测试Node镜像源..."
NODE_MIRROR=""
for mirror in "${MIRRORS[@]}"; do
    echo "尝试: $mirror/library/node:18-alpine"
    if docker pull "${mirror}/library/node:18-alpine" 2>/dev/null; then
        NODE_MIRROR="$mirror"
        echo "✅ Node镜像拉取成功: $mirror"
        break
    else
        echo "❌ $mirror 失败，尝试下一个..."
    fi
done

# 测试Nginx镜像
echo ""
echo "📥 测试Nginx镜像源..."
NGINX_MIRROR=""
for mirror in "${MIRRORS[@]}"; do
    echo "尝试: $mirror/library/nginx:alpine"
    if docker pull "${mirror}/library/nginx:alpine" 2>/dev/null; then
        NGINX_MIRROR="$mirror"
        echo "✅ Nginx镜像拉取成功: $mirror"
        break
    else
        echo "❌ $mirror 失败，尝试下一个..."
    fi
done

# 如果都失败了，使用Docker Hub直接拉取（可能需要时间）
if [ -z "$PYTHON_MIRROR" ] || [ -z "$NODE_MIRROR" ] || [ -z "$NGINX_MIRROR" ]; then
    echo ""
    echo "⚠️  所有镜像源测试失败，尝试直接使用Docker Hub（可能需要较长时间）..."
    echo "   如果Docker Hub也无法访问，请检查网络连接或配置代理"
    echo ""
    
    # 使用默认Docker Hub
    PYTHON_MIRROR=""
    NODE_MIRROR=""
    NGINX_MIRROR=""
fi

# 修改Dockerfile
echo ""
echo "📝 修改Dockerfile..."

# 修改后端Dockerfile
if [ -n "$PYTHON_MIRROR" ]; then
    sed -i "1s|.*|FROM ${PYTHON_MIRROR}/library/python:3.11-slim|" backend/Dockerfile
    echo "✅ backend/Dockerfile 使用: ${PYTHON_MIRROR}/library/python:3.11-slim"
else
    sed -i "1s|.*|FROM python:3.11-slim|" backend/Dockerfile
    echo "✅ backend/Dockerfile 使用: python:3.11-slim (Docker Hub)"
fi

# 修改前端Dockerfile
if [ -n "$NODE_MIRROR" ]; then
    sed -i "1s|.*|FROM ${NODE_MIRROR}/library/node:18-alpine AS build|" frontend/Dockerfile
    echo "✅ frontend/Dockerfile Node使用: ${NODE_MIRROR}/library/node:18-alpine"
else
    sed -i "1s|.*|FROM node:18-alpine AS build|" frontend/Dockerfile
    echo "✅ frontend/Dockerfile Node使用: node:18-alpine (Docker Hub)"
fi

if [ -n "$NGINX_MIRROR" ]; then
    sed -i '/^FROM nginx:alpine/s|.*|FROM '"${NGINX_MIRROR}"'/library/nginx:alpine|' frontend/Dockerfile
    echo "✅ frontend/Dockerfile Nginx使用: ${NGINX_MIRROR}/library/nginx:alpine"
else
    sed -i '/^FROM nginx:alpine/s|.*|FROM nginx:alpine|' frontend/Dockerfile
    echo "✅ frontend/Dockerfile Nginx使用: nginx:alpine (Docker Hub)"
fi

echo ""
echo "=========================================="
echo "✅ Dockerfile修改完成"
echo "=========================================="
echo ""
echo "现在可以运行: docker compose up --build -d"
echo ""

