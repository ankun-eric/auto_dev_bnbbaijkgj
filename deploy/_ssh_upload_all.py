import paramiko
import os
import sys

def ensure_remote_dir(sftp, remote_dir):
    dirs_to_create = []
    current = remote_dir
    while current and current != '/':
        try:
            sftp.stat(current)
            break
        except FileNotFoundError:
            dirs_to_create.append(current)
            current = os.path.dirname(current)
    
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except:
            pass

def main():
    host = 'newbb.test.bangbangvip.com'
    user = 'ubuntu'
    password = 'Newbang888'
    proj_dir = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
    local_base = r'C:\auto_output\bnbbaijkgj'
    
    files_to_upload = [
        r'h5-web\src\app\(ai-chat)\ai-home\page.tsx',
        r'h5-web\src\app\(ai-chat)\layout.tsx',
        r'h5-web\src\app\(ai-chat)\feedback\page.tsx',
        r'h5-web\src\app\(ai-chat)\chat-history\page.tsx',
        r'h5-web\src\app\(ai-chat)\account-security\page.tsx',
        r'h5-web\src\app\(ai-chat)\ai-settings\page.tsx',
        r'h5-web\src\app\(ai-chat)\health-archive\page.tsx',
        r'h5-web\src\components\ai-chat\Sidebar.tsx',
        r'h5-web\src\components\ai-chat\SharePanel.tsx',
        r'h5-web\src\components\ai-chat\RecommendCards.tsx',
        r'h5-web\src\components\ai-chat\ConsultantPicker.tsx',
        r'h5-web\src\components\ai-chat\MoreMenu.tsx',
        r'h5-web\src\lib\theme.ts',
    ]
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=22, username=user, password=password, timeout=30)
    
    sftp = client.open_sftp()
    
    for rel_path in files_to_upload:
        local_path = os.path.join(local_base, rel_path)
        remote_path = proj_dir + '/' + rel_path.replace('\\', '/')
        
        if not os.path.exists(local_path):
            print(f"SKIP (not found): {rel_path}")
            continue
        
        remote_dir = os.path.dirname(remote_path)
        ensure_remote_dir(sftp, remote_dir)
        
        sftp.put(local_path, remote_path)
        stat = sftp.stat(remote_path)
        print(f"OK [{stat.st_size:>8} bytes] {rel_path}")
    
    sftp.close()
    client.close()
    print(f"\nAll {len(files_to_upload)} files uploaded successfully!")

if __name__ == "__main__":
    main()
