#!/usr/bin/env python3
import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com',22,'ubuntu','Benne-ai@#',timeout=20,allow_agent=False,look_for_keys=False)
stdin,stdout,stderr=c.exec_command('cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.prod.yml',timeout=10)
content=stdout.read().decode('utf-8','replace')
with open('C:/auto_output/bnbbaijkgj/_server_compose.txt','w',encoding='utf-8') as f:
    f.write(content)
print(f"Downloaded {len(content)} bytes")
c.close()
