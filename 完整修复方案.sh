#!/bin/bash
# 完整修复方案：手动拉取镜像并修复Dockerfile

set -e

echo "=========================================="
echo "🔧 完整修复方案"
echo "=========================================="

cd /root/Navigation_Chatbot

# 步骤1：检查并修改Dockerfile
echo "📝 步骤1: 修改Dockerfile使用阿里云镜像源..."

# 修改后端Dockerfile
if grep -q "registry.cn-hangzhou.aliyuncs.com" backend/Dockerfile; then
    echo "✅ backend/Dockerfile 已修改"
else
    echo "🔧 修改 backend/Dockerfile..."
    sed -i '1s|^FROM python:3.11-slim|FROM registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim|' backend/Dockerfile
    echo "✅ backend/Dockerfile 已修改"
fi

# 修改前端Dockerfile
if grep -q "registry.cn-hangzhou.aliyuncs.com" frontend/Dockerfile; then
    echo "✅ frontend/Dockerfile 已修改"
else
    echo "🔧 修改 frontend/Dockerfile..."
    sed -i '1s|^FROM node:18-alpine|FROM registry.cn-hangzhou.aliyuncs.com/library/node:18-alpine|' frontend/Dockerfile
    sed -i '/^FROM nginx:alpine/s|^FROM nginx:alpine|FROM registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine|' frontend/Dockerfile
    echo "✅ frontend/Dockerfile 已修改"
fi

# 步骤2：手动拉取基础镜像
echo ""
echo "📥 步骤2: 手动拉取基础镜像..."

echo "拉取 Python 镜像..."
docker pull registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim || {
    echo "⚠️  阿里云镜像拉取失败，尝试中科大镜像..."
    docker pull docker.mirrors.ustc.edu.cn/library/python:3.11-slim
    docker tag docker.mirrors.ustc.edu.cn/library/python:3.11-slim registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim
}

echo "拉取 Node 镜像..."
docker pull registry.cn-hangzhou.aliyuncs.com/library/node:18-alpine || {
    echo "⚠️  阿里云镜像拉取失败，尝试中科大镜像..."
    docker pull docker.mirrors.ustc.edu.cn/library/node:18-alpine
    docker tag docker.mirrors.ustc.edu.cn/library/node:18-alpine registry.cn-hangzhou.aliyuncs.com/library/node:18-alpine
}

echo "拉取 Nginx 镜像..."
docker pull registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine || {
    echo "⚠️  阿里云镜像拉取失败，尝试中科大镜像..."
    docker pull docker.mirrors.ustc.edu.cn/library/nginx:alpine
    docker tag docker.mirrors.ustc.edu.cn/library/nginx:alpine registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine
}

echo ""
echo "✅ 所有基础镜像已拉取完成"
echo ""

# 步骤3：验证Dockerfile
echo "📋 步骤3: 验证Dockerfile修改..."
echo ""
echo "backend/Dockerfile 第一行:"
head -1 backend/Dockerfile
echo ""
echo "frontend/Dockerfile 第一行和nginx行:"
head -1 frontend/Dockerfile
grep "nginx" frontend/Dockerfile | head -1
echo ""

# 步骤4：清理并重新构建
echo "🧹 步骤4: 清理旧的构建缓存..."
docker compose down 2>/dev/null || true
docker system prune -f

echo ""
echo "=========================================="
echo "✅ 修复完成！现在可以运行:"
echo "   docker compose up --build -d"
echo "=========================================="

