import subprocess, sys, os, re, json
from datetime import datetime

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
ACR_REGISTRY = 'crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com'
ACR_USER = 'ankun888'
ACR_PASS = 'xiaobai888'
ACR_BASE_NS = 'noob_doker_base'
ACR_PROJECT_NS = 'noob_ai_apps'
WORK_DIR = f'/home/ubuntu/{DEPLOY_ID}'
VERSION_TAG = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def run(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr, file=sys.stderr)
    return r

print(f"VERSION_TAG={VERSION_TAG}")
print("=== ACR login ===")
r = run(f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR_REGISTRY}", timeout=30)
if r.returncode != 0:
    print("WARN: ACR login failed, will continue without ACR")

os.chdir(WORK_DIR)

print("=== Pull base images from ACR ===")
for root_dir in ['backend', 'admin-web', 'h5-web']:
    df_path = os.path.join(WORK_DIR, root_dir, 'Dockerfile')
    if not os.path.isfile(df_path):
        continue
    print(f"  Processing {root_dir}/Dockerfile")
    with open(df_path) as f:
        for line in f:
            m = re.match(r'^FROM\s+(\S+)', line.strip())
            if not m:
                continue
            raw_img = m.group(1)
            if raw_img.startswith('--platform') or raw_img.lower() == 'scratch':
                continue
            parts = raw_img.split(':', 1)
            img_name = parts[0]
            img_tag = parts[1] if len(parts) > 1 else 'latest'
            safe_name = img_name.replace('/', '_')
            acr_base = f"{ACR_REGISTRY}/{ACR_BASE_NS}/{safe_name}:{img_tag}"
            print(f"    Pulling {acr_base}")
            r2 = run(f"docker pull {acr_base}", timeout=120)
            if r2.returncode != 0:
                print(f"    ACR miss, fallback to Docker Hub: {raw_img}")
                r3 = run(f"docker pull {raw_img}", timeout=300)
                if r3.returncode != 0:
                    print(f"    ERROR: cannot pull {raw_img}")
                    sys.exit(1)
                run(f"docker tag {raw_img} {acr_base}", timeout=10)
                run(f"docker push {acr_base}", timeout=120)

print("=== Build backend ===")
r = run(f"docker build -t {DEPLOY_ID}-backend:{VERSION_TAG} -t {DEPLOY_ID}-backend:latest -f ./backend/Dockerfile ./backend/", timeout=900, cwd=WORK_DIR)
if r.returncode != 0:
    print("ERROR: backend build failed")
    sys.exit(1)

print("=== Build admin-web ===")
r = run(f"docker build -t {DEPLOY_ID}-admin-web:{VERSION_TAG} -t {DEPLOY_ID}-admin-web:latest --build-arg NEXT_PUBLIC_API_URL=/api --build-arg NEXT_PUBLIC_BASE_PATH=/admin -f ./admin-web/Dockerfile ./admin-web/", timeout=900, cwd=WORK_DIR)
if r.returncode != 0:
    print("ERROR: admin-web build failed")
    sys.exit(1)

print("=== Build h5-web ===")
r = run(f"docker build -t {DEPLOY_ID}-h5-web:{VERSION_TAG} -t {DEPLOY_ID}-h5-web:latest --build-arg NEXT_PUBLIC_API_URL=/api --build-arg NEXT_PUBLIC_BASE_PATH= -f ./h5-web/Dockerfile ./h5-web/", timeout=900, cwd=WORK_DIR)
if r.returncode != 0:
    print("ERROR: h5-web build failed")
    sys.exit(1)

print("=== Build done, listing images ===")
run(f"docker images --filter 'reference={DEPLOY_ID}-*' --format '{{{{.Repository}}}}:{{{{.Tag}}}} {{{{.Size}}}}'", timeout=10)

# Push to ACR
print("=== Push to ACR ===")
for svc, name in [('backend', 'backend'), ('admin-web', 'admin-web'), ('h5-web', 'h5-web')]:
    local_img = f"{DEPLOY_ID}-{name}"
    acr_img = f"{ACR_REGISTRY}/{ACR_PROJECT_NS}/{local_img}"
    run(f"docker tag {local_img}:{VERSION_TAG} {acr_img}:{VERSION_TAG}", timeout=10)
    run(f"docker tag {local_img}:latest {acr_img}:latest", timeout=10)
    r = run(f"docker push {acr_img}:{VERSION_TAG}", timeout=300)
    if r.returncode != 0:
        print(f"WARN: ACR push failed for {name} (non-blocking)")
    else:
        run(f"docker push {acr_img}:latest", timeout=300)

print(f"BUILD_SUCCESS VERSION_TAG={VERSION_TAG}")
