#!/bin/bash
echo "=== 容器 working_dir 标签 ==="
docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
echo "=== 项目目录列表 ==="
ls -la /home/ubuntu/ | grep -i autodev
ls -la /opt/ 2>/dev/null | head
ls -la /srv/ 2>/dev/null | head
ls -la /home/ubuntu/projects/ 2>/dev/null | head
find /home/ubuntu /opt /srv -maxdepth 4 -name 'docker-compose*.yml' -path '*6b099ed3*' 2>/dev/null
