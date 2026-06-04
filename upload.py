"""
Upload files to server via SSH using base64 chunked transfer.
"""
import subprocess
import base64
import os
import sys

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_exec(cmd, timeout=30):
    """Execute command via SSH with password piped in."""
    full_cmd = f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {USER}@{SERVER} "{cmd}"'
    proc = subprocess.run(
        full_cmd,
        shell=True,
        input=PASSWORD + "\n",
        capture_output=True,
        text=True,
        timeout=timeout
    )
    if proc.returncode != 0:
        print(f"SSH ERROR (exit {proc.returncode}): {proc.stderr}")
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode

def upload_file(local_path, remote_path):
    """Upload a file using base64 chunked transfer over SSH."""
    if not os.path.exists(local_path):
        print(f"Local file not found: {local_path}")
        return False
    
    with open(local_path, 'rb') as f:
        data = f.read()
    
    b64_data = base64.b64encode(data).decode('ascii')
    file_size = len(data)
    print(f"Uploading {local_path} ({file_size} bytes, {len(b64_data)} b64 chars) -> {remote_path}")
    
    # Remove existing file
    ssh_exec(f"rm -f {remote_path}.b64")
    
    # Split into chunks of 4000 chars
    chunk_size = 4000
    chunks = [b64_data[i:i+chunk_size] for i in range(0, len(b64_data), chunk_size)]
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        # Escape special characters for shell
        escaped = chunk.replace("'", "'\"'\"'")
        cmd = f"printf '%s' '{escaped}' >> {remote_path}.b64"
        stdout, stderr, rc = ssh_exec(cmd)
        if rc != 0:
            print(f"Failed at chunk {i+1}/{total_chunks}")
            return False
        if (i + 1) % 50 == 0:
            print(f"  Chunk {i+1}/{total_chunks}...")
    
    # Decode and verify
    print(f"Decoding base64...")
    ssh_exec(f"base64 -d {remote_path}.b64 > {remote_path} && rm {remote_path}.b64")
    
    # Verify size
    stdout, _, _ = ssh_exec(f"wc -c < {remote_path}")
    remote_size = int(stdout.strip()) if stdout.strip().isdigit() else 0
    if remote_size == file_size:
        print(f"Upload OK: {remote_path} ({remote_size} bytes)")
        return True
    else:
        print(f"Size mismatch: local={file_size} remote={remote_size}")
        return False

def main():
    files_to_upload = [
        ("backend/app/api/safety_rope_v1.py", f"{REMOTE_DIR}/backend/app/api/safety_rope_v1.py"),
        ("backend/app/main.py", f"{REMOTE_DIR}/backend/app/main.py"),
        ("h5-web/src/app/care-home/page.tsx", f"{REMOTE_DIR}/h5-web/src/app/care-home/page.tsx"),
        ("h5-web/src/app/care-safety-rope/page.tsx", f"{REMOTE_DIR}/h5-web/src/app/care-safety-rope/page.tsx"),
        ("backend/tests/test_safety_rope_v1_20260603.py", f"{REMOTE_DIR}/backend/tests/test_safety_rope_v1_20260603.py"),
    ]
    
    base_dir = r"C:\auto_output\bnbbaijkgj"
    
    for local_rel, remote_path in files_to_upload:
        local_path = os.path.join(base_dir, local_rel)
        if not upload_file(local_path, remote_path):
            print(f"FAILED to upload {local_rel}")
            sys.exit(1)
    
    print("\nAll files uploaded successfully!")

if __name__ == "__main__":
    main()
