"""验证后端 chat schema 已经接受新字段 ai_function_type / capture_purpose
通过查 openapi 文档"""
import paramiko, json
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

# 通过 backend openapi 看 ChatMessageCreate
_, o, _ = c.exec_command(
    "curl -s 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/openapi.json' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get(\"components\",{}).get(\"schemas\",{}).get(\"ChatMessageCreate\",{}), ensure_ascii=False, indent=2))'"
)
out = o.read().decode()
print(out[:3000])
c.close()
