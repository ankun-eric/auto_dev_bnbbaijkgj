"""降级方案：直接 SFTP 上传心率详情页改动文件到服务器（GitHub 不可达时使用）。"""
import importlib.util, os
spec = importlib.util.spec_from_file_location("ssh_helper", os.path.join(os.path.dirname(__file__), "_ssh_helper.py"))
sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)

REMOTE = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
FILES = [
    ("h5-web/src/lib/heart-rate-level.ts", f"{REMOTE}/h5-web/src/lib/heart-rate-level.ts"),
    ("h5-web/src/app/health-metric/[type]/page.tsx", f"{REMOTE}/h5-web/src/app/health-metric/[type]/page.tsx"),
    ("backend/app/api/health_metric_card_v1.py", f"{REMOTE}/backend/app/api/health_metric_card_v1.py"),
    ("backend/tests/test_heart_rate_detail_rule_v1_20260531.py", f"{REMOTE}/backend/tests/test_heart_rate_detail_rule_v1_20260531.py"),
]
for local, remote in FILES:
    sh.put_file(local, remote)
    print(f"uploaded: {remote}")
print("DONE")
