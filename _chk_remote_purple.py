from _ssh_helper import run, DEPLOY_ID
rc, out, err = run(f"ls /home/ubuntu/{DEPLOY_ID} | head && echo --- && docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID}", timeout=30)
print(out)
print("RC=", rc, "ERR=", err)
