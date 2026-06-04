from _ssh_helper import run
# Test what nginx sees - try resolving from host
print("=== Resolve from host ===")
rc,out,err=run("getent hosts 6b099ed3-7175-4a78-91f4-44570c84ed27-backend || echo 'NORESOLVE'", timeout=10)
print(out)

# nginx error log
print("\n=== Nginx error log (last 30) ===")
rc,out,err=run("sudo tail -30 /var/log/nginx/error.log 2>&1 || sudo journalctl -u nginx -n 30 --no-pager 2>&1 | tail -30", timeout=20)
print(out)

# Test the actual http call from host with verbose
print("\n=== Direct curl to localhost from host ===")
rc,out,err=run("curl -sk -w 'HTTP %{http_code}\\n' https://localhost//api/home_safety/callback/alarm -X POST -H 'Content-Type: application/json' --data '{\"msgId\":\"t1\",\"param\":{\"devId\":\"X\",\"devType\":\"1\",\"occurTime\":1547100617645},\"dataType\":\"call-msg\"}' --resolve localhost:443:127.0.0.1 -H 'Host: newbb.test.bangbangvip.com'", timeout=20)
print(out)
print("ERR:", err[:500])

# How does it work for an existing project? Look at other UUID
print("\n=== Other project nginx config ===")
rc,out,err=run("sudo cat /etc/nginx/conf.d/routes/85048269-7f40-4ae8-88e2-0f3ce1ce19d1.conf 2>&1 | head -30", timeout=20)
print(out)
