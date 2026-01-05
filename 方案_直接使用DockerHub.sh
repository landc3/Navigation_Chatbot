#!/bin/bash
# 方案：直接使用Docker Hub，配置更好的镜像加速

set -e

echo "=========================================="
echo "🔧 方案：直接使用Docker Hub + 优化配置"
echo "=========================================="

cd /root/Navigation_Chatbot

# 1. 更新Docker镜像加速器配置，添加更多源
echo "📝 更新Docker镜像加速器配置..."

cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://dockerhub.azk8s.cn",
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com",
    "https://docker.nju.edu.cn",
    "https://registry.cn-hangzhou.aliyuncs.com"
  ],
  "max-concurrent-downloads": 10,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# 重启Docker
echo "🔄 重启Docker服务..."
systemctl daemon-reload
systemctl restart docker

# 2. 修改Dockerfile使用Docker Hub（让镜像加速器自动处理）
echo ""
echo "📝 修改Dockerfile使用标准镜像名（让镜像加速器自动处理）..."

# 修改后端Dockerfile
cat > backend/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 拷贝整个仓库（配合 .dockerignore 排除 node_modules/dist 等）
COPY . /app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 修改前端Dockerfile
cat > frontend/Dockerfile << 'EOF'
FROM node:18-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci

COPY frontend/ /app/
RUN npm run build

FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
EOF

echo "✅ Dockerfile已恢复为标准镜像名"
echo ""

# 3. 验证镜像加速器
echo "📊 验证镜像加速器配置..."
docker info | grep -A 10 "Registry Mirrors" || echo "⚠️  无法显示镜像加速器配置"

echo ""
echo "=========================================="
echo "✅ 配置完成！"
echo "=========================================="
echo ""
echo "现在Docker会通过镜像加速器自动拉取镜像"
echo "运行: docker compose up --build -d"
echo ""

