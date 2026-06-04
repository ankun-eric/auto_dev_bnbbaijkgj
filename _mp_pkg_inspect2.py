from _mp_pkg_inspect import run

out, err = run("docker exec gateway-nginx sh -c 'sed -n \"55,75p\" /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf'", timeout=60)
print(out)
if err.strip():
    print("ERR", err)
