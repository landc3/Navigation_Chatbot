#!/bin/bash
# 配置Docker使用阿里云镜像加速器
# 解决Docker Hub连接超时问题

set -e

echo "=========================================="
echo "🐳 配置Docker镜像加速器"
echo "=========================================="

# 创建Docker配置目录
mkdir -p /etc/docker

# 配置阿里云镜像加速器
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://registry.cn-hangzhou.aliyuncs.com",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ],
  "max-concurrent-downloads": 10,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

echo "✅ Docker镜像加速器配置完成"

# 重启Docker服务
echo "🔄 重启Docker服务..."
systemctl daemon-reload
systemctl restart docker

# 验证配置
echo "📊 验证Docker配置..."
docker info | grep -A 10 "Registry Mirrors"

echo ""
echo "=========================================="
echo "✅ 配置完成！"
echo "=========================================="
echo ""
echo "现在可以重新运行: docker compose up --build -d"
echo ""

