#!/usr/bin/env python3
"""仅运行 PRD-AICHAT-CAPSULE-V1 服务器自动化测试，不再重新部署。"""
import sys
from _deploy_aichat_capsule_v1 import run_tests

if __name__ == "__main__":
    sys.exit(run_tests())
