#!/usr/bin/env python3
"""确认线上 H5 已含睡眠新代码：抓 sleep 详情页 HTML 引用的 chunk，grep 关键字"""
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd

H5 = '6b099ed3-7175-4a78-91f4-44570c84ed27-h5'
ssh = get_ssh()
# 直接在 h5 容器内 grep 构建产物
run_cmd(ssh, f'docker exec {H5} sh -c "grep -rl \\"睡眠充足\\" .next/ 2>/dev/null | head -5"', 60)
run_cmd(ssh, f'docker exec {H5} sh -c "grep -rl \\"sleep-status-card\\" .next/ 2>/dev/null | head -5"', 60)
run_cmd(ssh, f'docker exec {H5} sh -c "grep -rl \\"sleep-trend-bar\\" .next/ 2>/dev/null | head -5"', 60)
ssh.close()
