from _ssh_helper import run
rc, out, err = run("sudo docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format '{{json .Config.Labels}}'")
print("OUT:", out)
print("ERR:", err)
print("RC:", rc)
