#!/bin/bash
# 备用方案：如果阿里云镜像失败，使用中科大镜像

set -e

echo "=========================================="
echo "🔧 备用方案：使用中科大镜像源"
echo "=========================================="

cd /root/Navigation_Chatbot

# 修改Dockerfile使用中科大镜像
echo "📝 修改Dockerfile使用中科大镜像源..."

# 修改后端Dockerfile
sed -i '1s|.*|FROM docker.mirrors.ustc.edu.cn/library/python:3.11-slim|' backend/Dockerfile

# 修改前端Dockerfile
sed -i '1s|.*|FROM docker.mirrors.ustc.edu.cn/library/node:18-alpine AS build|' frontend/Dockerfile
sed -i '/^FROM nginx:alpine/s|.*|FROM docker.mirrors.ustc.edu.cn/library/nginx:alpine|' frontend/Dockerfile

echo "✅ Dockerfile已修改为使用中科大镜像源"
echo ""

# 手动拉取镜像
echo "📥 手动拉取基础镜像..."

docker pull docker.mirrors.ustc.edu.cn/library/python:3.11-slim
docker pull docker.mirrors.ustc.edu.cn/library/node:18-alpine
docker pull docker.mirrors.ustc.edu.cn/library/nginx:alpine

echo ""
echo "✅ 镜像拉取完成"
echo ""
echo "现在可以运行: docker compose up --build -d"
echo ""

