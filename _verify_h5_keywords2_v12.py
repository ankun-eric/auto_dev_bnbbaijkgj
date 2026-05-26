"""用 node 探针验证 H5 chunks 关键词"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

NODE_PROBE = r'''
const fs = require('fs');
const path = require('path');
const dirs = [
  '/app/.next/static/chunks/app/health-profile/i-guard',
  '/app/.next/static/chunks/app/health-profile',
];
const need_in = ['主守护人转让', '守护中', '待守护', '我守护的人'];
const need_out = ['体验全新', '体验全新版'];
for (const d of dirs) {
  let files = [];
  try { files = fs.readdirSync(d).filter(f => f.endsWith('.js')).map(f => path.join(d, f)); } catch (e) {}
  for (const f of files) {
    const buf = fs.readFileSync(f, 'utf-8');
    const info = {};
    for (const k of need_in.concat(need_out)) {
      const re = new RegExp(k, 'g');
      info[k] = (buf.match(re) || []).length;
    }
    console.log(f);
    for (const k of Object.keys(info)) {
      const ok = (need_in.includes(k) && info[k] > 0) || (need_out.includes(k) && info[k] === 0);
      console.log(`  ${ok ? 'OK' : 'FAIL'} ${k}: count=${info[k]}`);
    }
  }
}
'''


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = cli.open_sftp()
    with sftp.open("/tmp/probe_iguard.js", "w") as f:
        f.write(NODE_PROBE)
    sftp.close()
    cmd = (
        f"docker cp /tmp/probe_iguard.js {TOKEN}-h5:/tmp/probe_iguard.js && "
        f"docker exec {TOKEN}-h5 node /tmp/probe_iguard.js"
    )
    print("$", cmd[:200])
    si, so, se = cli.exec_command(cmd, timeout=60)
    print(so.read().decode("utf-8", errors="ignore"))
    print(se.read().decode("utf-8", errors="ignore"))
    cli.close()


if __name__ == "__main__":
    main()
