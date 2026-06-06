import paramiko, os, glob, random, string

f = open(r'C:\auto_output\bnbbaijkgj\_miniprogram_upload_result.txt', 'w')

try:
    os.chdir(r'C:\auto_output\bnbbaijkgj')
    
    zips = glob.glob('miniprogram_*.zip')
    if not zips:
        f.write('No zip found\n')
        exit()

    zip_path = zips[0]
    ts = zip_path.replace('miniprogram_','').replace('.zip','')
    rand_suffix = ''.join(random.choices('0123456789abcdef', k=4))
    new_name = f'miniprogram_{ts}{rand_suffix}.zip'
    os.rename(zip_path, new_name)
    f.write(f'Renamed: {new_name} ({os.path.getsize(new_name)} bytes)\n')

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

    # Ensure public dir exists
    ssh.exec_command('mkdir -p /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/public/')

    # Upload
    sftp = ssh.open_sftp()
    remote_path = f'/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/public/{new_name}'
    sftp.put(new_name, remote_path)
    sftp.close()
    f.write(f'Uploaded to {remote_path}\n')

    # Copy into container
    stdin, stdout, stderr = ssh.exec_command(f'docker cp {remote_path} 6b099ed3-7175-4a78-91f4-44570c84ed27-h5:/app/public/{new_name}')
    f.write(f'Docker cp: {stdout.read().decode()} {stderr.read().decode()}\n')

    # Verify download
    stdin, stdout, stderr = ssh.exec_command(f'curl -sIL --connect-timeout 10 -o /dev/null -w "%{{http_code}}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/{new_name}')
    code = stdout.read().decode().strip()
    f.write(f'HTTP status: {code}\n')

    download_url = f'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/{new_name}'
    f.write(f'\n=== DOWNLOAD URL ===\n{download_url}\n')
    f.write(f'Filename: {new_name}\n')

    ssh.close()
except Exception as e:
    import traceback
    f.write(f'ERROR: {e}\n{traceback.format_exc()}\n')

f.close()
print('Done')
