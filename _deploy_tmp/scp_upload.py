import paramiko
import os
import sys
import stat

def upload_dir(sftp, local_path, remote_path, excludes):
    try:
        sftp.stat(remote_path)
    except FileNotFoundError:
        sftp.mkdir(remote_path)
    
    for item in os.listdir(local_path):
        if item in excludes:
            continue
        local_item = os.path.join(local_path, item)
        remote_item = remote_path + '/' + item
        
        skip_ext = ('.apk', '.zip', '.tar', '.tar.gz', '.pyc')
        if any(item.endswith(ext) for ext in skip_ext):
            continue
            
        if os.path.isfile(local_item):
            print(f"  Uploading: {local_item}")
            sftp.put(local_item, remote_item)
        elif os.path.isdir(local_item):
            print(f"  Dir: {remote_item}")
            upload_dir(sftp, local_item, remote_item, excludes)

def main():
    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    local_base = sys.argv[4]
    remote_base = sys.argv[5]
    
    excludes = {
        'node_modules', '.git', '__pycache__', '.next', 
        'flutter_app', 'miniprogram', 'verify-miniprogram',
        'mem', '_deploy_tmp', 'build_artifacts', 'apk_download',
        '.chat_output', '.consulting_output', 'user_docs', 'docs',
        'tests', 'uploads', '.pytest_cache', '.tools', 'ui_design_outputs',
        '.github', '.cursor', '.vscode', 'agent-transcripts',
        '.gitignore', '.gitattributes'
    }
    
    dirs_to_upload = ['backend', 'admin-web', 'h5-web']
    files_to_upload = ['docker-compose.prod.yml', 'gateway-routes.conf']
    
    env_files = ['.env', 'backend/.env', 'admin-web/.env.local', 'h5-web/.env.local']
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password, timeout=30)
    sftp = client.open_sftp()
    
    try:
        sftp.stat(remote_base)
    except FileNotFoundError:
        sftp.mkdir(remote_base)
    
    for f in files_to_upload:
        local_f = os.path.join(local_base, f)
        if os.path.exists(local_f):
            print(f"Uploading file: {f}")
            sftp.put(local_f, remote_base + '/' + f)
    
    for f in env_files:
        local_f = os.path.join(local_base, f)
        if os.path.exists(local_f):
            print(f"Uploading env: {f}")
            remote_f = remote_base + '/' + f.replace('\\', '/')
            remote_dir = '/'.join(remote_f.rsplit('/', 1)[:-1])
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)
            sftp.put(local_f, remote_f)
    
    for d in dirs_to_upload:
        local_d = os.path.join(local_base, d)
        remote_d = remote_base + '/' + d
        if os.path.isdir(local_d):
            print(f"\nUploading directory: {d}/")
            upload_dir(sftp, local_d, remote_d, excludes)
    
    sftp.close()
    client.close()
    print("\nUpload complete!")

if __name__ == '__main__':
    main()
