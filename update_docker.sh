#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
NC='\033[0m' # 无颜色

echo -e "${GREEN}>>> 开始平滑更新业务容器...${NC}"

# 1. 检查是否存在 .env 文件，防止挂载路径失效
if [ ! -f .env ]; then
    echo "警告: 未发现 .env 文件，请确保环境变量配置正确。"
fi

# 2. 仅针对 octofyagent-backend 和 octofyagent-frontend 进行构建和启动
# --build 会检测代码变更并重新生成镜像
# 数据库容器 (milvus, etcd, minio) 会保持运行，不会被重置
docker compose up -d --build backend frontend

# 3. 清理构建过程中产生的虚悬镜像（dangling images），释放硬盘空间
echo -e "${GREEN}>>> 正在清理临时镜像...${NC}"
docker image prune -f

echo -e "${GREEN}>>> 更新完成！Octofy AI Agent 业务已重启，数据库连接保持中。${NC}"