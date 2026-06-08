#!/bin/bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
echo '非首次部署，更新已有代码...'
git fetch --depth 1 origin main
git reset --hard origin/main
echo "当前 commit: $(git rev-parse --short HEAD)"
echo "Commit 信息: $(git log --oneline -1)"
