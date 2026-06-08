import subprocess, time

for i in range(30):
    time.sleep(5)
    r = subprocess.run(
        ['docker','ps','--filter','name=6b099ed3-','--format','{{.Names}} {{.Status}}'],
        capture_output=True, text=True
    )
    lines = [l for l in r.stdout.strip().split('\n') if l]
    h = sum(1 for l in lines if 'healthy' in l.lower())
    print(f"[{i+1}/30] {h}/{len(lines)} healthy")
    print(r.stdout)
    if h >= 3:
        print("HEALTH_OK")
        break
else:
    print("HEALTH_TIMEOUT")
