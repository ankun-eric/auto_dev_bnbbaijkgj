import paramiko
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com",username='ubuntu',password='Newbang888',timeout=60)
si,so,se=c.exec_command(
    f"docker exec {DEPLOY_ID}-backend python -m pytest "
    f"tests/test_home_safety_v1.py "
    f"tests/test_home_safety_v2.py "
    f"tests/test_home_safety_v2_revision.py "
    f"tests/test_home_safety_gwid_ephone_v1.py "
    f"tests/test_home_safety_callback_datatype_v1.py "
    f"tests/test_home_safety_callback_schema_sync_v1.py "
    f"-v --tb=short 2>&1 | tail -100",
    timeout=900,
)
print(so.read().decode("utf-8","replace"))
c.close()
