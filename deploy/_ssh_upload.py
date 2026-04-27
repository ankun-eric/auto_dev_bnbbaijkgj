import paramiko
import os
import sys

def main():
    host = 'newbb.test.bangbangvip.com'
    user = 'ubuntu'
    password = 'Newbang888'
    proj_dir = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
    
    local_file = r'C:\auto_output\bnbbaijkgj\h5-web\src\app\(ai-chat)\ai-home\page.tsx'
    remote_file = f'{proj_dir}/h5-web/src/app/(ai-chat)/ai-home/page.tsx'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=22, username=user, password=password, timeout=30)
    
    # First ensure the directory exists
    remote_dir = os.path.dirname(remote_file)
    stdin, stdout, stderr = client.exec_command(f'mkdir -p "{remote_dir}"')
    stdout.channel.recv_exit_status()
    
    # Upload the file via SFTP
    sftp = client.open_sftp()
    print(f"Uploading {local_file}")
    print(f"  -> {remote_file}")
    sftp.put(local_file, remote_file)
    
    # Verify
    stat = sftp.stat(remote_file)
    print(f"Upload complete. Remote file size: {stat.st_size} bytes")
    sftp.close()
    
    # Verify content on server
    stdin, stdout, stderr = client.exec_command(f'head -5 "{remote_file}"')
    stdout.channel.recv_exit_status()
    print(f"\nFirst 5 lines of remote file:")
    print(stdout.read().decode())
    
    client.close()
    print("Done!")

if __name__ == "__main__":
    main()
