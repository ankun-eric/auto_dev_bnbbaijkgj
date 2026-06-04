import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE=f'https://{HOST}/autodev/{DEPLOY_ID}'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect(HOST, username=USER, password=PWD, timeout=30)
def r(cmd, t=120):
  i,o,e=c.exec_command(cmd, timeout=t)
  out=o.read().decode('utf-8','replace'); err=e.read().decode('utf-8','replace')
  print(out + (('\n[stderr]\n'+err) if err.strip() else ''))
  print('exit=', o.channel.recv_exit_status())
print('=== H5 member-center page ===')
r(f"curl -sk -o /tmp/r.txt -w '%{{http_code}}\\n' '{BASE}/member-center/'; head -c 600 /tmp/r.txt | tr -d '\\r'; echo")
print('=== /api/member/plans ===')
r(f"curl -sk '{BASE}/api/member/plans' | head -c 600; echo")
print('=== OpenAPI 中检索新接口 ===')
r(f"curl -sk '{BASE}/api/openapi.json' | python3 -c 'import json,sys;d=json.load(sys.stdin);paths=[p for p in d[\"paths\"] if \"/api/member\" in p or \"/api/admin/users\" in p];print(\"\\n\".join(sorted(paths)))'")
c.close()
