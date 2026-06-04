from _ssh_helper import run, put_file
put_file('backend/app/api/home_safety_v1.py', '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend/app/api/home_safety_v1.py')
print('uploaded')
rc, out, err = run(
    "sudo docker cp /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend/app/api/home_safety_v1.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/app/api/home_safety_v1.py && "
    "sudo docker exec -w /app 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest tests/test_home_safety_v1.py tests/test_home_safety_v2.py -v --tb=short -p no:warnings 2>&1 | tail -50",
    timeout=180,
)
print(out)
print('---ERR---', err[-500:] if err else '')
