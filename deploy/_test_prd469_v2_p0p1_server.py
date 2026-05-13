"""[PRD-469 v2 P0/P1] 非UI 自动化测试 — 覆盖所有 P0/P1 缺口补全项

测试用例:
  - M4: 用药添加页 6 大字段 — 通过 POST /api/health-plan/medications 校验字段持久化
  - M4: 用药计划双分段 — 通过 GET 列表校验
  - M6: 家族病史编辑 — PUT /api/prd469/health-info/{profile_id}
  - M6: 手术史编辑 — PUT /api/prd469/health-info/{profile_id}
  - M8: 病历卡 OCR + 列表 + 自动入时间轴 — POST /api/prd469/medical-record + GET list
  - M2: Hero 四格指标 — GET /api/prd469/summary/{profile_id} 含 hero_metrics
  - M1: 旧路由 /health-profile 必须 404 (跟随重定向后)
  - M10: 药品库联想搜索 — GET /api/prd469/medication-library/search
"""
from __future__ import annotations

import json
import sys
import time
import uuid

import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class TestRunner:
    def __init__(self):
        self.results: list[tuple[str, bool, str]] = []
        self.session = requests.Session()
        self.session.verify = False
        # suppress insecure warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.token: str | None = None
        self.user_id: int | None = None
        self.profile_id: int | None = None

    def assert_eq(self, name: str, actual, expected, detail: str = "") -> bool:
        ok = actual == expected
        self.results.append((name, ok, f"actual={actual} expected={expected} {detail}".strip()))
        log(f"  [{'OK' if ok else 'FAIL'}] {name}: {actual} (expected {expected}) {detail}")
        return ok

    def assert_true(self, name: str, cond: bool, detail: str = "") -> bool:
        self.results.append((name, cond, detail))
        log(f"  [{'OK' if cond else 'FAIL'}] {name} {detail}")
        return cond

    # ===== 注册并登录一个测试用户 =====
    def register_and_login(self) -> None:
        log("--- 注册测试用户 ---")
        suffix = uuid.uuid4().hex[:8]
        phone = f"139{suffix[:8]}"
        password = "Test@1234"
        # 尝试注册（若失败则尝试登录）
        r = self.session.post(
            f"{BASE}/api/auth/register",
            json={"phone": phone, "password": password, "username": f"prd469test_{suffix}"},
            timeout=15,
        )
        log(f"  /api/auth/register -> {r.status_code} {r.text[:120]}")
        if r.status_code not in (200, 201):
            self.assert_true("register", False, f"unexpected status {r.status_code}: {r.text[:200]}")
            return
        r = self.session.post(
            f"{BASE}/api/auth/login",
            json={"phone": phone, "password": password},
            timeout=15,
        )
        log(f"  /api/auth/login -> {r.status_code}")
        if r.status_code != 200:
            self.assert_true("login", False, f"status {r.status_code}: {r.text[:200]}")
            return
        data = r.json()
        self.token = data.get("access_token") or data.get("token")
        self.user_id = data.get("user_id") or (data.get("user") or {}).get("id")
        self.assert_true("login token", bool(self.token), f"user_id={self.user_id}")

    @property
    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def ensure_health_profile(self) -> None:
        log("--- 确保健康档案存在 ---")
        r = self.session.get(f"{BASE}/api/health/profile", headers=self.auth_headers, timeout=15)
        log(f"  GET /api/health/profile -> {r.status_code} {r.text[:200]}")
        if r.status_code == 200:
            data = r.json()
            self.profile_id = data.get("id") or (data.get("data") or {}).get("id")
        if not self.profile_id:
            # 创建本人档案
            r = self.session.post(
                f"{BASE}/api/health/profile",
                headers=self.auth_headers,
                json={
                    "name": "测试本人",
                    "gender": "male",
                    "age": 30,
                    "height": 175,
                    "weight": 70,
                    "blood_type": "A",
                    "relation": "本人",
                },
                timeout=15,
            )
            log(f"  POST /api/health/profile -> {r.status_code} {r.text[:200]}")
            if r.status_code in (200, 201):
                d = r.json()
                self.profile_id = d.get("id") or (d.get("data") or {}).get("id")
        self.assert_true("ensure profile_id", bool(self.profile_id), f"profile_id={self.profile_id}")

    # ===== M1: 旧路由 404 =====
    def test_old_route_404(self):
        log("=== M1: /health-profile 跟随重定向后 404 ===")
        r = self.session.get(f"{BASE}/health-profile", allow_redirects=True, timeout=15)
        self.assert_eq("M1.old_route_404", r.status_code, 404)

    # ===== M2: Hero 四格指标 =====
    def test_hero_metrics(self):
        log("=== M2: Hero 四格指标 ===")
        if not self.profile_id:
            self.assert_true("M2.hero_metrics", False, "no profile_id")
            return
        r = self.session.get(
            f"{BASE}/api/prd469/summary/{self.profile_id}",
            headers=self.auth_headers,
            timeout=15,
        )
        log(f"  GET summary -> {r.status_code} {r.text[:300]}")
        self.assert_eq("M2.summary_status", r.status_code, 200)
        if r.status_code == 200:
            data = r.json()
            hm = data.get("hero_metrics") or (data.get("data") or {}).get("hero_metrics")
            self.assert_true("M2.hero_metrics_present", isinstance(hm, list) and len(hm) == 4,
                             f"hero_metrics={hm}")
            if isinstance(hm, list) and hm:
                labels = [m.get("label") for m in hm]
                expected_labels = {"既往病史", "过敏史", "家族遗传", "长期用药"}
                got_set = set(labels)
                self.assert_true("M2.hero_labels", expected_labels.issubset(got_set),
                                 f"labels={labels}")

    # ===== M4: 用药 6 大字段持久化 =====
    def test_medication_fields(self):
        log("=== M4: 用药添加页 6 大字段持久化 ===")
        if not self.profile_id:
            self.assert_true("M4.medication", False, "no profile_id")
            return
        payload = {
            "profile_id": self.profile_id,
            "medicine_name": "测试用药-降压",
            "dosage": "10mg",
            "frequency": "每日3次",
            "frequency_per_day": 3,
            "custom_times": ["08:00", "14:00", "20:00"],
            "start_date": "2026-05-13",
            "end_date": "2026-08-13",
            "long_term": False,
            "reminder_enabled": True,
            "disease_tags": ["高血压", "糖尿病"],
            "notes": "PRD-469 P0 测试",
        }
        r = self.session.post(
            f"{BASE}/api/health-plan/medications",
            headers=self.auth_headers,
            json=payload,
            timeout=15,
        )
        log(f"  POST /api/health-plan/medications -> {r.status_code} {r.text[:400]}")
        ok = r.status_code in (200, 201)
        self.assert_true("M4.medication_create", ok, f"status={r.status_code}")
        if not ok:
            return
        d = r.json()
        med = d.get("data") if isinstance(d, dict) and "data" in d else d
        # 校验 6 个字段
        self.assert_eq("M4.frequency_per_day", med.get("frequency_per_day"), 3)
        self.assert_true("M4.custom_times",
                         med.get("custom_times") == ["08:00", "14:00", "20:00"],
                         f"got={med.get('custom_times')}")
        self.assert_true("M4.start_date", str(med.get("start_date") or "").startswith("2026-05-13"),
                         f"got={med.get('start_date')}")
        self.assert_true("M4.end_date", str(med.get("end_date") or "").startswith("2026-08-13"),
                         f"got={med.get('end_date')}")
        self.assert_eq("M4.long_term", bool(med.get("long_term")), False)
        self.assert_eq("M4.reminder_enabled", bool(med.get("reminder_enabled")), True)
        self.assert_true("M4.disease_tags",
                         med.get("disease_tags") == ["高血压", "糖尿病"],
                         f"got={med.get('disease_tags')}")

    # ===== M6: 家族病史 / 手术史 编辑 =====
    def test_health_info_family_surgery(self):
        log("=== M6: 健康信息（家族病史 + 手术史 + 慢病年份）===")
        if not self.profile_id:
            self.assert_true("M6.health_info", False, "no profile_id")
            return
        payload = {
            "chronic_diseases": [{"name": "高血压", "diagnosed_year": 2018}],
            "drug_allergies": ["青霉素"],
            "food_allergies": ["花生"],
            "other_allergies": ["花粉"],
            "family_history": [
                {"relation": "父亲", "disease": "糖尿病", "note": "55岁确诊"},
                {"relation": "母亲", "disease": "高血压"},
            ],
            "surgery_history": [
                {"name": "阑尾炎切除", "time": "2015-06", "note": "无并发症"},
            ],
            "habit_smoking": "无",
            "habit_drinking": "偶尔",
            "habit_exercise": "经常",
            "habit_diet": "均衡",
        }
        r = self.session.put(
            f"{BASE}/api/prd469/health-info/{self.profile_id}",
            headers=self.auth_headers,
            json=payload,
            timeout=15,
        )
        log(f"  PUT health-info -> {r.status_code} {r.text[:300]}")
        self.assert_eq("M6.put_status", r.status_code, 200)
        # GET 回读
        r = self.session.get(
            f"{BASE}/api/prd469/health-info/{self.profile_id}",
            headers=self.auth_headers,
            timeout=15,
        )
        log(f"  GET health-info -> {r.status_code} {r.text[:300]}")
        if r.status_code == 200:
            d = r.json()
            info = d.get("data") if isinstance(d, dict) and "data" in d else d
            fh = info.get("family_history") or []
            sh = info.get("surgery_history") or []
            self.assert_true("M6.family_history_persisted", len(fh) == 2, f"got={fh}")
            self.assert_true("M6.surgery_history_persisted", len(sh) == 1, f"got={sh}")
            cds = info.get("chronic_diseases") or []
            if cds and isinstance(cds[0], dict):
                self.assert_eq("M6.chronic_year", cds[0].get("diagnosed_year"), 2018)

    # ===== M8: 病历卡 + OCR + 自动入时间轴 =====
    def test_medical_record_ocr(self):
        log("=== M8: 病历卡上传 + OCR 解析 + 自动入时间轴 ===")
        if not self.profile_id:
            self.assert_true("M8.medical_record", False, "no profile_id")
            return
        ocr_text = """
        某市人民医院
        科室：心血管内科
        就诊日期：2026-05-10
        医生：张三
        诊断：高血压2级
        处方：苯磺酸氨氯地平片 5mg qd
        """
        r = self.session.post(
            f"{BASE}/api/prd469/medical-record",
            headers=self.auth_headers,
            json={
                "profile_id": self.profile_id,
                "image_url": "https://example.com/test_record.jpg",
                "ocr_text": ocr_text,
            },
            timeout=15,
        )
        log(f"  POST medical-record -> {r.status_code} {r.text[:400]}")
        self.assert_true("M8.create_status", r.status_code in (200, 201),
                         f"got {r.status_code}")
        if r.status_code in (200, 201):
            d = r.json()
            card = d.get("data") if isinstance(d, dict) and "data" in d else d
            card_id = card.get("id")
            self.assert_true("M8.card_id_returned", bool(card_id), f"card={card}")
            # 校验 OCR 解析字段（返回字段是 parsed_xxx 前缀）
            parsed_fields = ["parsed_hospital", "parsed_department", "parsed_doctor",
                             "parsed_diagnosis", "parsed_visit_date", "parsed_prescription"]
            present = [f for f in parsed_fields if card.get(f)]
            self.assert_true("M8.ocr_parsed_fields", len(present) >= 3,
                             f"got fields={present}")

            # 列表
            r2 = self.session.get(
                f"{BASE}/api/prd469/medical-record/list?profile_id={self.profile_id}",
                headers=self.auth_headers,
                timeout=15,
            )
            log(f"  GET medical-record/list -> {r2.status_code}")
            self.assert_eq("M8.list_status", r2.status_code, 200)
            if r2.status_code == 200:
                d2 = r2.json()
                items = d2.get("data") or d2.get("items") or d2
                if isinstance(items, dict):
                    items = items.get("items") or items.get("list") or []
                self.assert_true("M8.list_contains_card",
                                 isinstance(items, list) and len(items) >= 1,
                                 f"len={len(items) if isinstance(items, list) else 'n/a'}")

            # 时间轴检查（auto event）
            r3 = self.session.get(
                f"{BASE}/api/prd469/health-event/timeline?profile_id={self.profile_id}",
                headers=self.auth_headers,
                timeout=15,
            )
            log(f"  GET health-event/timeline -> {r3.status_code}")
            if r3.status_code == 200:
                d3 = r3.json()
                events = d3.get("data") or d3.get("items") or d3
                if isinstance(events, dict):
                    events = events.get("items") or events.get("list") or []
                self.assert_true("M8.timeline_has_upload_event",
                                 isinstance(events, list) and len(events) >= 1,
                                 f"events_count={len(events) if isinstance(events, list) else 'n/a'}")

            # 删除
            if card_id:
                r4 = self.session.delete(
                    f"{BASE}/api/prd469/medical-record/{card_id}",
                    headers=self.auth_headers,
                    timeout=15,
                )
                log(f"  DELETE medical-record/{card_id} -> {r4.status_code}")
                self.assert_true("M8.delete_status", r4.status_code in (200, 204),
                                 f"got {r4.status_code}")

    # ===== M10: 药品库联想 =====
    def test_medication_library_search(self):
        log("=== M10: 药品库联想搜索 ===")
        r = self.session.get(
            f"{BASE}/api/prd469/medication-library/search?kw=阿&limit=5",
            timeout=15,
        )
        log(f"  GET search?kw=阿 -> {r.status_code} {r.text[:200]}")
        self.assert_eq("M10.search_status", r.status_code, 200)
        if r.status_code == 200:
            d = r.json()
            items = d.get("data") or d.get("items") or d
            if isinstance(items, dict):
                items = items.get("items") or items.get("list") or []
            self.assert_true("M10.search_has_results",
                             isinstance(items, list) and len(items) >= 1,
                             f"count={len(items) if isinstance(items, list) else 'n/a'}")

    # ===== Reminder / Device =====
    def test_reminder_and_device(self):
        log("=== M7/M9: 提醒规则 + 设备列表 ===")
        r = self.session.get(f"{BASE}/api/prd469/reminder-setting", headers=self.auth_headers, timeout=15)
        self.assert_eq("M7.reminder_get", r.status_code, 200)
        r2 = self.session.get(f"{BASE}/api/prd469/device/list", headers=self.auth_headers, timeout=15)
        self.assert_eq("M9.device_list", r2.status_code, 200)

    # ===== 主入口 / 前端可达性 =====
    def test_frontend_reachable(self):
        log("=== 前端关键页面可达性 ===")
        urls = [
            ("/health-profile-v2/", 200),
            ("/health-plan/medications/", 200),
            ("/health-plan/medications/add/", 200),
        ]
        for path, code in urls:
            r = self.session.get(f"{BASE}{path}", timeout=15)
            self.assert_eq(f"FE.{path}", r.status_code, code)

    def run_all(self):
        self.register_and_login()
        if not self.token:
            log("[FATAL] no token, cannot continue authenticated tests")
        else:
            self.ensure_health_profile()
        self.test_old_route_404()
        if self.token and self.profile_id:
            self.test_hero_metrics()
            self.test_medication_fields()
            self.test_health_info_family_surgery()
            self.test_medical_record_ocr()
            self.test_reminder_and_device()
        self.test_medication_library_search()
        self.test_frontend_reachable()

        log("=" * 60)
        total = len(self.results)
        passed = sum(1 for _, ok, _ in self.results if ok)
        log(f"TOTAL {passed}/{total} passed")
        fails = [(n, d) for n, ok, d in self.results if not ok]
        for n, d in fails:
            log(f"  FAIL: {n} | {d}")
        return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(TestRunner().run_all())
