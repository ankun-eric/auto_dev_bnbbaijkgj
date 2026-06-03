from _ssh_helper import run
rc, out, err = run(
    "sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -c "
    "'cd /app && python -m pytest tests/test_home_safety_v2.py::test_v2_compat_flat_payload "
    "-v --tb=long -p no:warnings 2>&1' ",
    timeout=120,
)
print(out)
print("---ERR---", err)
