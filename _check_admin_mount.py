import paramiko
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=60)
def sh(c,t=60):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace')

print("--- admin mounts ---")
print(sh(f"docker inspect {DEPLOY_ID}-admin --format '{{{{range .Mounts}}}}{{{{.Type}}}}: {{{{.Source}}}} -> {{{{.Destination}}}}\\n{{{{end}}}}'"))
print("--- admin entrypoint/cmd ---")
print(sh(f"docker inspect {DEPLOY_ID}-admin --format '{{{{.Config.Cmd}}}} | {{{{.Config.Entrypoint}}}} | {{{{.Path}}}} {{{{.Args}}}}'"))
print("--- find seed-import on host ---")
print(sh("find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/admin-web -name 'seed-import' -o -name 'page.tsx' 2>/dev/null | head -20"))
print("--- if /app is mounted from host, check host file ---")
print(sh(f"ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/admin-web/src/app/'(admin)'/system/seed-import/ 2>&1"))
print("--- compare container file mtime ---")
print(sh(f"docker exec {DEPLOY_ID}-admin sh -c 'stat /app/src/app/\"(admin)\"/system/seed-import/page.tsx'"))
cli.close()
