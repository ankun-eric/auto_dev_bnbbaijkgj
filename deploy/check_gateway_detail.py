import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    i,o,e = ssh.exec_command(cmd, timeout=15)
    return o.read().decode('utf-8',errors='replace').strip()

lines = []

lines.append("=== Gateway conf.d files ===")
lines.append(run('docker exec gateway-nginx ls -la /etc/nginx/conf.d/ 2>/dev/null'))

lines.append("\n=== Gateway nginx.conf includes ===")
lines.append(run('docker exec gateway-nginx grep -rn "conf.d\|include" /etc/nginx/nginx.conf 2>/dev/null'))

lines.append("\n=== Project conf on host (first 30 lines) ===")
lines.append(run('head -30 /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>/dev/null'))

lines.append("\n=== Gateway volume mounts ===")
lines.append(run('docker inspect gateway-nginx --format "{{range .Mounts}}{{.Source}} -> {{.Destination}} {{.Mode}}\n{{end}}" 2>/dev/null'))

lines.append("\n=== Gateway container conf.d files ===")
lines.append(run('docker exec gateway-nginx cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>/dev/null | head -20'))

lines.append("\n=== Project network ID ===")
lines.append(run('docker network inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-network --format "{{.Id}}" 2>/dev/null'))

lines.append("\n=== Gateway network IDs ===")
lines.append(run('docker inspect gateway-nginx --format "{{range .NetworkSettings.Networks}}{{.NetworkID}}\n{{end}}" 2>/dev/null'))

lines.append("\n=== External curl test ===")
lines.append(run('curl -sk https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>/dev/null'))

lines.append("\n=== External curl test H5 ===")
lines.append(run('curl -sk -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ 2>/dev/null'))

lines.append("\n=== External curl test Admin ===")
lines.append(run('curl -sk -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/ 2>/dev/null'))

result = '\n'.join(lines)
with open('deploy/gateway_detail_result.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print('DONE')
ssh.close()
