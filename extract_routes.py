import os
import re

api_dir = r"C:\auto_output\bnbbaijkgj\backend\app\api"

param_replacements = {
    "user_id": "1", "id": "1", "target_id": "1", "member_id": "1",
    "order_id": "1", "plan_id": "1", "category_id": "1",
    "token": "test123", "session_id": "test123", "orderId": "1",
    "type": "blood_pressure", "adcode": "110000",
    "message_id": "1", "expert_id": "1", "article_id": "1",
    "news_id": "1", "nav_id": "1", "word_id": "1", "config_id": "1",
    "template_id": "1", "item_id": "1", "cat_id": "1", "rt_id": "1",
    "dp_id": "1", "level_id": "1", "contact_id": "1",
    "address_id": "1", "card_id": "1", "user_card_id": "1",
    "coupon_id": "1", "form_id": "1", "field_id": "1",
    "phone_id": "1", "request_id": "1", "mig_id": "1",
    "tid": "1", "batch_id": "1", "code_id": "1", "partner_id": "1",
    "binding_id": "1", "catalog_id": "1", "group_id": "1",
    "alert_id": "1", "diagnosis_id": "1", "answer_id": "1",
    "constitution_type": "qixu", "consultant_id": "1",
    "record_id": "1", "share_token": "test123", "chat_type": "health",
}

def replace_params(path):
    def repl(m):
        param = m.group(1)
        return param_replacements.get(param, "1")
    return re.sub(r'\{(\w+)\}', repl, path)

router_prefixes = {}
route_entries = []

for root, dirs, files in os.walk(api_dir):
    for fname in sorted(files):
        if not fname.endswith('.py') or fname == '__init__.py':
            continue
        fpath = os.path.join(root, fname)
        rel = os.path.relpath(fpath, r"C:\auto_output\bnbbaijkgj\backend")
        
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                lines = f.read().split('\n')
        except:
            continue
        
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r'^\s*(\w+)\s*=\s*APIRouter\s*\((.*)\)\s*$', line)
            if m:
                var_name = m.group(1)
                args = m.group(2)
                pfx_match = re.search(r'prefix\s*=\s*["\']([^"\']*)["\']', args)
                prefix = pfx_match.group(1) if pfx_match else ""
                router_prefixes.setdefault(fpath, []).append((var_name, prefix))
            else:
                # Multi-line APIRouter definition
                m2 = re.match(r'^\s*(\w+)\s*=\s*APIRouter\s*\(\s*$', line)
                if m2:
                    var_name = m2.group(1)
                    prefix = ""
                    for j in range(i+1, min(i+10, len(lines))):
                        pfx_m = re.search(r'prefix\s*=\s*["\']([^"\']*)["\']', lines[j])
                        if pfx_m:
                            prefix = pfx_m.group(1)
                        if re.search(r'\)\s*$', lines[j]):
                            break
                    router_prefixes.setdefault(fpath, []).append((var_name, prefix))
            i += 1
        
        for i, line in enumerate(lines, 1):
            m = re.match(r'^\s*@(\w+)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']*)["\']', line)
            if m:
                router_var, method, path = m.group(1), m.group(2).upper(), m.group(3)
                route_entries.append((rel, i, router_var, method, path))
            else:
                m2 = re.match(r'^\s*@(\w+)\.(get|post|put|patch|delete)\s*\(\s*$', line)
                if m2:
                    router_var, method = m2.group(1), m2.group(2).upper()
                    for j in range(i, min(i+10, len(lines))):
                        pm = re.search(r'["\']([^"\']*)["\']', lines[j])
                        if pm:
                            path = pm.group(1)
                            route_entries.append((rel, i, router_var, method, path))
                            break

for rel, line_no, router_var, method, path in route_entries:
    actual_file = os.path.join(r"C:\auto_output\bnbbaijkgj\backend", rel)
    prefixes = router_prefixes.get(actual_file, [])
    prefix = ""
    for var_name, pfx in prefixes:
        if var_name == router_var:
            prefix = pfx
            break
    full_path = prefix + path
    full_path = replace_params(full_path)
    if not full_path.startswith('/'):
        full_path = '/' + full_path
    print(f"{method} {full_path} → {rel}:{line_no}")
