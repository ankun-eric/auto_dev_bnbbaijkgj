from _ssh_helper import run, put_file
put_file('_dbg.py', '/tmp/_dbg.py')
rc, out, err = run("sudo docker cp /tmp/_dbg.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/_dbg.py && sudo docker exec -w /app 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python _dbg.py", timeout=120)
print(out)
print('---ERR---')
print(err)
