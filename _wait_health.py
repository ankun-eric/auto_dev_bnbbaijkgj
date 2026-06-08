import subprocess, time, os, json

os.chdir('/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27')

print("=== 等待容器健康检查通过 ===")
MAX_WAIT = 24
for i in range(1, MAX_WAIT + 1):
    result = subprocess.run(
        ['docker', 'compose', '-f', 'docker-compose.prod.yml', 'ps', '-q'],
        capture_output=True, text=True
    )
    total = len([l for l in result.stdout.strip().split('\n') if l])
    
    result2 = subprocess.run(
        ['docker', 'compose', '-f', 'docker-compose.prod.yml', 'ps', '--format', 'json'],
        capture_output=True, text=True
    )
    healthy = 0
    for line in result2.stdout.strip().split('\n'):
        if line.strip():
            try:
                d = json.loads(line)
                if d.get('Health') == 'healthy':
                    healthy += 1
            except:
                pass
    
    print(f"  [{i}/{MAX_WAIT}] {healthy}/{total} 容器已健康")
    if total > 0 and healthy == total:
        print("所有容器健康检查通过")
        break
    time.sleep(5)

print("\n=== 连接 gateway-nginx 到网络 ===")
subprocess.run(
    ['docker', 'network', 'connect', '6b099ed3-7175-4a78-91f4-44570c84ed27-network', 'gateway-nginx'],
    capture_output=True
)
print("网络连接完成")

print("\n=== 最终容器状态 ===")
subprocess.run(
    ['docker', 'compose', '-f', 'docker-compose.prod.yml', 'ps'],
)
