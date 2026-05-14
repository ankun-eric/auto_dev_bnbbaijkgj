#!/usr/bin/env python3
"""[PRD-HEALTH-OPT-V1] 仅运行服务器自动化测试（跳过部署）"""
from _deploy_health_opt_v1 import run_tests
import sys
sys.exit(run_tests())
