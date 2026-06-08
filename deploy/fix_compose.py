import re

path = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.prod.yml'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

img_map = {
    'backend': f'{DEPLOY_ID}-backend:latest',
    'admin-web': f'{DEPLOY_ID}-admin-web:latest',
    'h5-web': f'{DEPLOY_ID}-h5-web:latest',
}

for svc, img in img_map.items():
    # 在 build 块的最后一个子属性后插入 image 行
    # 模式: 在 dockerfile: ...行后、在 container_name: 行前插入
    pattern = rf'(  {svc}:\n    build:\n      context: \./{svc}\n      dockerfile: Dockerfile.*?\n)'
    repl = rf'\1    image: {img}\n'
    content = re.sub(pattern, repl, content, count=1, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('修改完成')
# 验证 YAML
import subprocess
result = subprocess.run(['docker', 'compose', '-f', path, 'config'], capture_output=True, text=True, cwd='/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27')
if result.returncode == 0:
    print('YAML 验证通过')
else:
    print('YAML 验证失败:', result.stderr)
