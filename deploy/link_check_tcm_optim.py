"""TCM 体质测评功能优化 — 关键链路外部可达性验证（从服务器发起 curl）"""
import sys
sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'


def curl_code(ssh, method, path):
    full = f'{BASE_URL}{path}'
    cmd = f'curl -s -o /dev/null -w "%{{http_code}}" -X {method} "{full}" --max-time 15'
    out, _, _ = run_cmd(ssh, cmd, timeout=20)
    return out.strip() or '000'


def main():
    ssh = create_client()
    try:
        links = [
            # 后端核心（本次改动点）
            ('GET', '/api/health', '健康检查'),
            ('GET', '/api/constitution/archive', '体质档案列表（核心：member_label）'),
            ('GET', '/api/tcm/diagnoses?page=1&page_size=5', 'TCM 诊断列表（核心：member_label）'),
            ('GET', '/api/tcm/questions', 'TCM 测评题目'),
            ('GET', '/api/family/members', '家庭成员列表'),
            # H5 前端页面（本次改动点）
            ('GET', '/tcm', 'TCM 主页（含测评记录）'),
            ('GET', '/tcm/questions', 'TCM 答题页（含 StepBar）'),
            ('GET', '/tcm/archive', 'TCM 档案（已弃用，应重定向至 /tcm）'),
            ('GET', '/tcm/diagnosis/1', 'TCM 诊断详情（已弃用，应重定向至 /tcm/result/1）'),
            ('GET', '/tcm/result/1', 'TCM 体质测评结果（新规范入口）'),
            # 其他主要 H5 页面回归验证
            ('GET', '/', 'H5 首页'),
            ('GET', '/services', '服务列表'),
            ('GET', '/health-profile', '健康档案'),
            ('GET', '/family', '家庭成员'),
        ]
        print(f'▶ 项目基础 URL: {BASE_URL}')
        print(f'▶ 链接总数: {len(links)}\n')

        report = []
        for method, path, desc in links:
            code = curl_code(ssh, method, path)
            # 可达判定：2xx / 3xx / 401/403（鉴权保护视为可达）/ 405
            reachable = (
                code.startswith('2')
                or code.startswith('3')
                or code in ('401', '403', '405')
            )
            flag = '✅' if reachable else '❌'
            print(f'{flag} [{code}] {method:5s} {path:60s} — {desc}')
            report.append((flag, code, method, path, desc))

        ok = sum(1 for r in report if r[0] == '✅')
        print(f'\n===== 汇总: 可达 {ok}/{len(report)} =====')
        if ok == len(report):
            print('🎉 全部链接可达')
            return 0
        else:
            print('⚠️ 存在不可达链接：')
            for flag, code, m, p, d in report:
                if flag != '✅':
                    print(f'  {flag} [{code}] {m} {p} — {d}')
            return 1
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
