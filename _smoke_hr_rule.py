"""非UI自动化测试：在 backend 容器内验证心率判读逻辑 + 通过 gateway 验证关键 API 可达。"""
import importlib.util, os
spec = importlib.util.spec_from_file_location("ssh_helper", os.path.join(os.path.dirname(__file__), "_ssh_helper.py"))
sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)

C = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

py = (
    "from app.api.health_metric_card_v1 import _judge_status as j;"
    "cases=[(40,'slow'),(59,'slow'),(60,'normal'),(72,'normal'),(100,'normal'),(101,'fast'),(130,'fast'),(0,'unknown')];"
    "r=[(v,k,j('heart_rate',{'value':v})['key']) for v,k in cases];"
    "bad=[x for x in r if x[1]!=x[2]];"
    "print('RESULTS:', r);"
    "print('ALL_PASS' if not bad else ('FAIL:'+str(bad)))"
)
cmd = f'docker exec {C} python -c "{py}"'
rc, out, err = sh.run(cmd, timeout=120)
print("=== 心率判读逻辑验证 ===")
print(out.strip())
if err.strip():
    print("STDERR:", err.strip())
print("rc=", rc)
