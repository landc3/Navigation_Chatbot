#!/bin/bash
# 快速修复Dockerfile，使用阿里云镜像源

set -e

echo "=========================================="
echo "🔧 修复Dockerfile使用阿里云镜像源"
echo "=========================================="

cd /root/Navigation_Chatbot

# 备份原始文件
echo "📦 备份原始Dockerfile..."
cp backend/Dockerfile backend/Dockerfile.bak 2>/dev/null || true
cp frontend/Dockerfile frontend/Dockerfile.bak 2>/dev/null || true

# 修改后端Dockerfile
echo "🔧 修改 backend/Dockerfile..."
sed -i 's|^FROM python:3.11-slim|# 使用阿里云镜像源\nFROM registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim|' backend/Dockerfile

# 修改前端Dockerfile
echo "🔧 修改 frontend/Dockerfile..."
sed -i 's|^FROM node:18-alpine|# 使用阿里云镜像源\nFROM registry.cn-hangzhou.aliyuncs.com/library/node:18-alpine|' frontend/Dockerfile
sed -i 's|^FROM nginx:alpine|# 使用阿里云镜像源\nFROM registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine|' frontend/Dockerfile

echo "✅ Dockerfile修复完成"
echo ""
echo "现在可以运行: docker compose up --build -d"
echo ""

