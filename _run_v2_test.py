from _ssh_helper import run
rc, out, err = run(
    "sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -c "
    "'cd /app && python -m pytest tests/test_home_safety_v2.py::test_v2_compat_flat_payload "
    "tests/test_home_safety_v2.py::test_v2_vendor_payload_field_mapping -v --tb=long 2>&1' > /tmp/v2test.txt; "
    "tail -100 /tmp/v2test.txt",
    timeout=120,
)
print(out)
print("---ERR---", err)
