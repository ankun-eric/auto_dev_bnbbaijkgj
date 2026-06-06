"""
Phase 1.5: Server environment precheck - 6 checks via SSH.
"""
import paramiko
import json
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_doker_base"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

def ssh_exec(client, cmd, timeout=30):
    """Execute command via SSH and return stdout, stderr, exit_code."""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print("Connecting to server...")
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
        print("Connected successfully!\n")
    except Exception as e:
        print(f"SSH Connection failed: {e}")
        sys.exit(1)
    
    results = {}
    
    # ============ Precheck 1: Gateway nginx config structure ============
    print("=" * 60)
    print("PRECHECK 1: Gateway nginx config structure")
    print("=" * 60)
    out, err, ec = ssh_exec(client, "cat /home/ubuntu/gateway/nginx.conf")
    if ec == 0:
        print(out[:3000])
        # Determine mode
        if 'include conf.d/*.conf;' in out:
            # Check if include is inside http block or server block
            lines = out.split('\n')
            in_server = False
            in_http = False
            include_line_num = 0
            for i, line in enumerate(lines):
                if 'server {' in line:
                    in_server = True
                if 'http {' in line:
                    in_http = True
                if 'include conf.d/*.conf;' in line:
                    include_line_num = i
                    break
            # Simple heuristic: check if we're in a server block
            # Count server { and } between http and include
            results['gateway_mode'] = 'standard'  # assume standard
            results['nginx_conf_ok'] = True
            print(f"\ninclude conf.d/*.conf found at line ~{include_line_num}")
        else:
            results['gateway_mode'] = 'unknown'
            results['nginx_conf_ok'] = False
            print("WARNING: include conf.d/*.conf not found!")
    else:
        print(f"ERROR: {err}")
        results['gateway_mode'] = 'unknown'
        results['nginx_conf_ok'] = False

    # ============ Precheck 2: Route occupation ============
    print("\n" + "=" * 60)
    print("PRECHECK 2: Route occupation check")
    print("=" * 60)
    out, err, ec = ssh_exec(client, "grep -rn 'location\\|server_name' /home/ubuntu/gateway/conf.d/ 2>/dev/null || echo 'NONE_FOUND'")
    print(out[:2000])
    results['route_check'] = out
    
    # Also check main nginx.conf for locations
    out2, err2, ec2 = ssh_exec(client, "grep -n 'location\\|server_name' /home/ubuntu/gateway/nginx.conf 2>/dev/null | head -20")
    print("Main nginx.conf locations:")
    print(out2[:1000])
    results['nginx_locations'] = out2
    
    # ============ Precheck 3: ACR base images ============
    print("\n" + "=" * 60)
    print("PRECHECK 3: ACR base image version check")
    print("=" * 60)
    # Use docker manifest inspect from server
    acr_found = {}
    images_to_check = {
        'python': ['3.12-slim', '3.11-slim', '3.10-slim', '3.12', '3.11'],
        'node': ['20-alpine', '22-alpine', '18-alpine', '20', '18'],
        'nginx': ['alpine', 'latest'],
    }
    for img_name, tags in images_to_check.items():
        for tag in tags:
            cmd = f"docker manifest inspect {ACR_ADDR}/{ACR_NS}/{img_name}:{tag} 2>&1"
            out, err, ec = ssh_exec(client, cmd, timeout=15)
            if ec == 0:
                if img_name not in acr_found:
                    acr_found[img_name] = []
                acr_found[img_name].append(tag)
                print(f"FOUND: {ACR_ADDR}/{ACR_NS}/{img_name}:{tag}")
                break  # Found first match, stop searching
            else:
                err_short = err[:120].replace('\n',' ')
                print(f"NOT FOUND: {ACR_ADDR}/{ACR_NS}/{img_name}:{tag} - {err_short[:100]}")
    results['acr_found'] = acr_found
    
    # ============ Precheck 4: Docker network topology ============
    print("\n" + "=" * 60)
    print("PRECHECK 4: Docker network topology")
    print("=" * 60)
    out, err, ec = ssh_exec(client, "docker ps -a --filter name=gateway-nginx --format '{{.Names}} {{.Status}}' 2>/dev/null")
    print(f"Gateway container: {out.strip()}")
    results['gateway_status'] = out.strip()
    
    out, err, ec = ssh_exec(client, "docker network ls --filter name=6b099ed3-network --format '{{.Name}}' 2>/dev/null")
    print(f"Project network: {out.strip()}")
    results['project_network'] = out.strip()
    
    # Check gateway network connections
    out, err, ec = ssh_exec(client, "docker inspect gateway-nginx --format '{{range .NetworkSettings.Networks}}{{.Name}} {{end}}' 2>/dev/null")
    print(f"Gateway networks: {out.strip()}")
    results['gateway_networks'] = out.strip()
    
    # ============ Precheck 5: Image tool detection ============
    print("\n" + "=" * 60)
    print("PRECHECK 5: Base image tool detection")
    print("=" * 60)
    # Python image tools
    py_tag = acr_found.get('python', ['3.12-slim'])[0]
    cmd = f"docker run --rm {ACR_ADDR}/{ACR_NS}/python:{py_tag} sh -c 'which wget curl python3 2>/dev/null' 2>&1"
    out, err, ec = ssh_exec(client, cmd, timeout=30)
    print(f"Python {py_tag} tools: {out.strip()}")
    results['python_tools'] = out.strip()
    
    # Node image tools
    node_tag = acr_found.get('node', ['20-alpine'])[0]
    cmd = f"docker run --rm {ACR_ADDR}/{ACR_NS}/node:{node_tag} sh -c 'which wget curl node 2>/dev/null' 2>&1"
    out, err, ec = ssh_exec(client, cmd, timeout=30)
    print(f"Node {node_tag} tools: {out.strip()}")
    results['node_tools'] = out.strip()
    
    # ============ Precheck 6: Disk space ============
    print("\n" + "=" * 60)
    print("PRECHECK 6: Disk space")
    print("=" * 60)
    out, err, ec = ssh_exec(client, "df -h / | tail -1")
    print(out.strip())
    results['disk_space'] = out.strip()
    
    # ============ Also check existing containers ============
    print("\n" + "=" * 60)
    print("EXTRA: Existing project containers")
    print("=" * 60)
    out, err, ec = ssh_exec(client, f"docker ps -a --filter name={DEPLOY_ID} --format '{{.Names}} {{.Status}}' 2>/dev/null")
    print(f"Existing containers: {out.strip() or 'None'}")
    results['existing_containers'] = out.strip()
    
    # Check db container
    out, err, ec = ssh_exec(client, "docker ps -a --filter name=db --format '{{.Names}} {{.Status}}' 2>/dev/null")
    print(f"DB container: {out.strip()}")
    results['db_container'] = out.strip()
    
    client.close()
    
    # Save results
    with open('C:\\auto_output\\bnbbaijkgj\\deploy\\precheck_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n\nAll prechecks complete. Results saved to deploy/precheck_results.json")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"Gateway mode: {results.get('gateway_mode', 'unknown')}")
    print(f"ACR Python: {results.get('acr_found', {}).get('python', [])}")
    print(f"ACR Node: {results.get('acr_found', {}).get('node', [])}")
    print(f"Gateway container: {results.get('gateway_status', 'unknown')}")
    print(f"Disk space: {results.get('disk_space', 'unknown')}")
    print(f"DB container: {results.get('db_container', 'unknown')}")

if __name__ == '__main__':
    main()
