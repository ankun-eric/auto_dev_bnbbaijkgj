#!/bin/bash
# ============================================================
# Hotfix P0 部署脚本（2026-05-13）
# 目标：服务器代码停留在 6fa6a27（旧版本），未包含 BUG-460 修复
#       导致 GET /api/chat-sessions 返回 500（MySQL NULLS LAST 语法错误）
#       拉取最新 master 并 --no-cache 重建 backend + h5-web，让所有修复生效
# ============================================================

set -e

PROJECT_DIR="/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"

echo ""
echo "================================================"
echo "[$(date '+%F %T')] Hotfix P0 部署开始"
echo "================================================"
echo ""

cd "$PROJECT_DIR"

echo "--- 当前 HEAD 与远程对比 ---"
git fetch origin master
echo "本地 HEAD: $(git rev-parse HEAD)"
echo "远程 HEAD: $(git rev-parse origin/master)"

echo ""
echo "--- 拉取最新 master ---"
git checkout master 2>/dev/null || true
git reset --hard origin/master
echo "更新后 HEAD: $(git rev-parse HEAD)"
git log -3 --oneline

echo ""
echo "--- 验证 chat_history.py 中已包含 BUG-460 修复 ---"
if grep -q "pinned_at_is_null" backend/app/api/chat_history.py; then
    echo "[OK] BUG-460 修复已包含（pinned_at_is_null case 表达式存在）"
else
    echo "[FATAL] BUG-460 修复未找到，请检查代码"
    exit 1
fi

echo ""
echo "--- 停止 backend + h5-web 容器 ---"
docker compose stop backend h5-web || docker-compose stop backend h5-web

echo ""
echo "--- 删除旧镜像（确保 --no-cache 真正生效） ---"
docker compose rm -f backend h5-web || docker-compose rm -f backend h5-web

echo ""
echo "--- --no-cache 重建 backend + h5-web 镜像 ---"
docker compose build --no-cache backend h5-web || docker-compose build --no-cache backend h5-web

echo ""
echo "--- 启动 backend + h5-web ---"
docker compose up -d backend h5-web || docker-compose up -d backend h5-web

echo ""
echo "--- 等待 backend 启动（最长 60s） ---"
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" "https://newbb.test.bangbangvip.com/autodev/$PROJECT_ID/api/health" | grep -q "200\|404"; then
        echo "[OK] backend 已响应（第 ${i} 次尝试）"
        break
    fi
    sleep 2
done

echo ""
echo "--- 部署后状态 ---"
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep "$PROJECT_ID"

echo ""
echo "================================================"
echo "[$(date '+%F %T')] Hotfix P0 部署完成"
echo "================================================"
