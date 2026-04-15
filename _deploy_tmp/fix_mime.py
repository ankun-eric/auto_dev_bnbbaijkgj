import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888')

# Check if nginx.conf includes mime.types
stdin, stdout, stderr = ssh.exec_command('docker exec gateway cat /etc/nginx/nginx.conf | head -20')
print("Current nginx.conf top:")
print(stdout.read().decode())

# Check if mime.types exists in container
stdin, stdout, stderr = ssh.exec_command('docker exec gateway ls /etc/nginx/mime.types 2>/dev/null && echo EXISTS || echo NOT_FOUND')
print("mime.types:", stdout.read().decode())

# The issue is that our custom nginx.conf doesn't include mime.types
# Let's add it to the http block
conf_path = '/home/ubuntu/gateway/nginx.conf'
stdin, stdout, stderr = ssh.exec_command(f'cat {conf_path}')
conf = stdout.read().decode()

if 'include       /etc/nginx/mime.types' not in conf and 'include /etc/nginx/mime.types' not in conf:
    new_conf = conf.replace(
        'http {',
        'http {\n    include       /etc/nginx/mime.types;\n    default_type  application/octet-stream;'
    )
    stdin, stdout, stderr = ssh.exec_command(f"cat > {conf_path} << 'HEREDOC'\n{new_conf}\nHEREDOC")
    stdout.read()
    print("Updated nginx.conf with mime.types include")

    # Reload nginx
    stdin, stdout, stderr = ssh.exec_command('docker exec gateway nginx -t 2>&1')
    test_result = stdout.read().decode()
    print("nginx -t:", test_result)

    if 'test is successful' in test_result:
        stdin, stdout, stderr = ssh.exec_command('docker exec gateway nginx -s reload 2>&1')
        print("Reload:", stdout.read().decode())
        print("Reload stderr:", stderr.read().decode())
        print("Nginx reloaded successfully")
    else:
        print("Nginx config test failed, reverting...")
        stdin, stdout, stderr = ssh.exec_command(f"cat > {conf_path} << 'HEREDOC'\n{conf}\nHEREDOC")
        stdout.read()
else:
    print("mime.types already included")

ssh.close()
