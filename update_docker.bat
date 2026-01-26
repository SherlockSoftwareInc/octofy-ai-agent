@echo off
echo >>> 开始平滑更新业务容器...

:: 仅构建和重启业务服务
docker compose up -d --build backend frontend

:: 清理构建碎片的镜像
echo >>> 正在清理无用镜像...
docker image prune -f

echo >>> 更新成功！
pause