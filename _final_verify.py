import paramiko
import json
import sys

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
D = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out.strip(), err.strip()

final = {}

out, _ = run(f'docker ps --filter name={D} --format "table {{{{.Names}}}}\t{{{{.Status}}}}"')
final['containers'] = out.replace('\n', ' | ')

out, _ = run(f'docker exec {D}-backend python3 -c "import urllib.request; print(urllib.request.urlopen(\\\"http://localhost:8000/api/health\\\").read().decode())"')
final['backend_health'] = out

out, _ = run(f'docker exec {D}-h5 node -e "var h=require(\\\"http\\\");h.get(\\\"http://localhost:3001/\\\",function(r){{var d=\\\"\\\";r.on(\\\"data\\\",function(c){{d+=c}});r.on(\\\"end\\\",function(){{console.log(d.substring(0,300))}})}}).on(\\\"error\\\",function(e){{console.log(\\\"ERR:\\\"+e.message)}})"')
final['h5_health'] = out[:500]

out, _ = run(f'docker exec {D}-admin node -e "var h=require(\\\"http\\\");h.get(\\\"http://localhost:3000/admin/\\\",function(r){{var d=\\\"\\\";r.on(\\\"data\\\",function(c){{d+=c}});r.on(\\\"end\\\",function(){{console.log(d.substring(0,300))}})}}).on(\\\"error\\\",function(e){{console.log(\\\"ERR:\\\"+e.message)}})"')
final['admin_health'] = out[:500]

out, _ = run(f'curl -sk https://localhost/api/health -H "Host: {D}.noob-ai.test.bangbangvip.com"')
final['gateway_api'] = out

out, _ = run(f'curl -sk -o /dev/null -w "%{{http_code}}" https://localhost/ -H "Host: {D}.noob-ai.test.bangbangvip.com"')
final['gateway_h5_http_code'] = out

out, _ = run(f'curl -sk -o /dev/null -w "%{{http_code}}" https://localhost/admin/ -H "Host: {D}.noob-ai.test.bangbangvip.com"')
final['gateway_admin_http_code'] = out

out, _ = run(f'docker logs --tail 5 {D}-h5 2>&1')
final['h5_logs'] = out

print("=== FINAL VERIFY RESULTS ===")
for k, v in final.items():
    print(f"{k}: {v}")

with open('C:/auto_output/bnbbaijkgj/_final_verify_result.json', 'w') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)

client.close()
