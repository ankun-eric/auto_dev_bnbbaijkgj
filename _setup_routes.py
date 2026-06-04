"""把 6b099ed3 项目接入 gateway-nginx：
1. 在 docker-compose 中暴露宿主端口（backend 19400 / admin 19401 / h5 19402）
2. 重启服务
3. 在 gateway-nginx 容器的 conf.d 中放路由文件
4. reload gateway nginx
"""
from _ssh_helper import run, put_file

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GW_CONF_LOCAL = "/home/ubuntu/gateway/conf.d/"

# Step 1: patch docker-compose.prod.yml to expose ports
print("=== Step 1: Patch docker-compose to expose ports ===")
patch_cmd = f"""
cd {PROJ_DIR}
# backup
cp docker-compose.prod.yml docker-compose.prod.yml.bak.v2
# patch ports
python3 - <<'PY'
import re
p = 'docker-compose.prod.yml'
with open(p) as f: t=f.read()

# backend: expose 8000 -> ports 19400:8000
t = re.sub(
    r'(  backend:.*?expose:\\s*\\n\\s*- "8000")',
    '''\\1\n    ports:\n      - "19400:8000"''',
    t, count=1, flags=re.DOTALL,
)
# admin-web: expose 3000 -> ports 19401:3000
t = re.sub(
    r'(  admin-web:.*?expose:\\s*\\n\\s*- "3000")',
    '''\\1\n    ports:\n      - "19401:3000"''',
    t, count=1, flags=re.DOTALL,
)
# h5-web: expose 3001 -> ports 19402:3001
t = re.sub(
    r'(  h5-web:.*?expose:\\s*\\n\\s*- "3001")',
    '''\\1\n    ports:\n      - "19402:3001"''',
    t, count=1, flags=re.DOTALL,
)
with open(p,'w') as f: f.write(t)
print("Patched")
PY

grep -A1 'expose:' docker-compose.prod.yml | head -25
"""
rc, out, err = run(patch_cmd, timeout=60)
print(out)
print("ERR:", err[:500])

print("\n=== Step 2: Recreate containers to apply port mapping ===")
rc, out, err = run(
    f"cd {PROJ_DIR} && sudo docker compose -f docker-compose.prod.yml up -d 2>&1 | tail -30",
    timeout=300,
)
print(out)

print("\n=== Step 3: Verify host ports listening ===")
rc, out, err = run("sudo ss -tlnp | grep -E ':1940[0-2]'", timeout=10)
print(out)

print("\n=== Step 4: Write gateway-nginx route conf ===")
GW_CONF = f"""# 网关 nginx 路由：项目 /autodev/{DEPLOY_ID}
# 居家安全设备 PRD v2 部署接入

# 后端 API（FastAPI）
location ^~ /autodev/{DEPLOY_ID}/api/ {{
    proxy_pass http://host.containers.internal:19400/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /autodev/{DEPLOY_ID};
    proxy_read_timeout 120s;
    client_max_body_size 100m;
}}

# 后端 uploads/docs
location ^~ /autodev/{DEPLOY_ID}/uploads/ {{
    proxy_pass http://host.containers.internal:19400/uploads/;
    proxy_set_header Host $host;
}}
location ^~ /autodev/{DEPLOY_ID}/docs {{
    proxy_pass http://host.containers.internal:19400/docs;
    proxy_set_header Host $host;
}}
location ^~ /autodev/{DEPLOY_ID}/openapi.json {{
    proxy_pass http://host.containers.internal:19400/openapi.json;
    proxy_set_header Host $host;
}}

# 兼容回调接收路径 /callback/home_safety/...（无 basePath 前缀的直连）
location ^~ /autodev/{DEPLOY_ID}/callback/ {{
    proxy_pass http://host.containers.internal:19400/callback/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}}

# 管理后台（Next.js）
location ^~ /autodev/{DEPLOY_ID}/admin {{
    proxy_pass http://host.containers.internal:19401;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 120s;
}}

# H5 用户端（Next.js）—— 根路径（必须最后定义，作为兜底）
location ^~ /autodev/{DEPLOY_ID}/ {{
    proxy_pass http://host.containers.internal:19402;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 120s;
}}
"""
# Write to a temp file locally
with open("_gw_route.conf", "w", encoding="utf-8") as f:
    f.write(GW_CONF)
put_file("_gw_route.conf", "/tmp/_gw_route.conf")
rc, out, err = run(
    f"cp /tmp/_gw_route.conf /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf && ls -la /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf",
    timeout=15,
)
print(out, err)

print("\n=== Step 5: Reload gateway-nginx ===")
rc, out, err = run("podman exec gateway-nginx nginx -t 2>&1", timeout=15)
print("Test:", out, err)
rc, out, err = run("podman exec gateway-nginx nginx -s reload 2>&1", timeout=15)
print("Reload:", out, err)

print("\n=== Step 6: Smoke test ===")
rc, out, err = run(
    f"curl -sk -w '\\nHTTP %{{http_code}}\\n' "
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/home_safety/callback/alarm "
    f"-X POST -H 'Content-Type: application/json' "
    f"--data '{{\"msgId\":\"setup_route_v2\",\"param\":{{\"devId\":\"NOEXIST1\",\"devType\":\"1\",\"occurTime\":1547100617645}},\"dataType\":\"call-msg\"}}'",
    timeout=30,
)
print("Callback:", out)

rc, out, err = run(
    f"curl -sk -w '\\nHTTP %{{http_code}}\\n' "
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/home-safety",
    timeout=30,
)
print("Admin:", out[:400])
