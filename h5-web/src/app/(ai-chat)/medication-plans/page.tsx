'use client';

/**
 * [PRD-MED-PLAN-V1 2026-05-16] 用药计划模块优化
 *
 * 路由: /medication-plans
 * 改动要点：
 * 1. 顶部固定温馨提示：⚠️ 用药请遵循医嘱
 * 2. 表单字段精简：每日次数（默认 3 次）→ 动态生成时间选择器；剂量数值+单位（严格预设）；
 *    服用周期 = 开始日期 + 服用天数（默认今天 +5 天）；用药指导单选；备注最多 30 字
 * 3. 移除 拍照识药入口、单条「用药提醒」开关、单条「AI 外呼」开关、用户侧关联疾病选择
 * 4. AI 外呼提醒变成全局开关（迁移到健康提醒/共管），列表展示 📞 标识 + 关闭时顶部引导横幅
 * 5. 同名药「进行中」去重（后端 409 → 前端弹窗）
 * 6. 服用周期到期自动归档（由后端处理）
 */

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface Plan {
  id: number;
  drug_name: string;
  medicine_name?: string;
  dosage: string;
  schedule: string[];
  note?: string | null;
  notes?: string | null;
  enabled: boolean;
  status?: string;
  long_term?: boolean;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  patient_id?: number | null;
  // [PRD-MED-PLAN-V1]
  dosage_value?: string | null;
  dosage_unit?: string | null;
  guidance?: string | null;
  ai_call_badge?: boolean;
  is_ongoing?: boolean;
  frequency_per_day?: number | null;
}

const DOSAGE_VALUES = [
  '1/4', '1/2', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
  '15', '20', '25', '30', '35', '40', '45', '50',
  '100', '150', '200', '250', '300', '350', '400', '450', '500',
];
const DOSAGE_UNITS = ['片', '粒', '袋', '支', '瓶', '贴', '克(g)', '毫升(mL)', '毫克(mg)', '微克(μg)'];
const GUIDANCE_OPTIONS = ['餐前', '餐后', '空腹', '随餐服用', '睡前'];
const FREQ_DEFAULT_TIMES: Record<number, string[]> = {
  1: ['08:00'],
  2: ['08:00', '20:00'],
  3: ['08:00', '12:00', '20:00'],
  4: ['08:00', '12:00', '18:00', '22:00'],
};

interface FormState {
  id?: number;
  drug_name: string;
  frequency_per_day: number;
  times: string[];
  dosage_value: string;
  dosage_unit: string;
  start_date: string;
  duration_days: number;
  guidance: string;
  note: string;
}

function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00');
  d.setDate(d.getDate() + days - 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

function emptyForm(): FormState {
  return {
    drug_name: '',
    frequency_per_day: 3,
    times: [...FREQ_DEFAULT_TIMES[3]],
    dosage_value: '',
    dosage_unit: '',
    start_date: todayISO(),
    duration_days: 5,
    guidance: '',
    note: '',
  };
}

const BANNER_DISMISS_KEY = 'med_plan_aicall_banner_dismiss_at';

type Segment = 'all' | 'archived';

export default function MedicationPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [segment, setSegment] = useState<Segment>('all');
  const [aiCallEnabled, setAiCallEnabled] = useState<boolean>(false);
  const [bannerDismissed, setBannerDismissed] = useState<boolean>(false);
  const [dupModal, setDupModal] = useState<{ name: string; existingId: number } | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  };

  // 启动时检查横幅 7 天内是否曾被关闭
  useEffect(() => {
    try {
      const v = localStorage.getItem(BANNER_DISMISS_KEY);
      if (v) {
        const ts = Number(v);
        if (!Number.isNaN(ts) && Date.now() - ts < 7 * 24 * 60 * 60 * 1000) {
          setBannerDismissed(true);
        }
      }
    } catch {}
  }, []);

  const fetchPlans = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/health-plan/medications/list', {
        params: { segment: segment === 'archived' ? 'archived' : undefined },
      });
      const data = res?.data || res;
      const arr = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
      setPlans(arr as Plan[]);
      if (typeof data?.ai_call_enabled === 'boolean') {
        setAiCallEnabled(!!data.ai_call_enabled);
      }
    } catch {
      showToast('加载失败');
    } finally {
      setLoading(false);
    }
  }, [segment]);

  useEffect(() => { fetchPlans(); }, [fetchPlans]);

  const openCreate = () => {
    setForm(emptyForm());
    setModalOpen(true);
  };

  const openEdit = (p: Plan) => {
    const sched = (p.schedule && p.schedule.length > 0) ? p.schedule : ['08:00'];
    const freq = p.frequency_per_day || sched.length || 3;
    setForm({
      id: p.id,
      drug_name: p.drug_name || p.medicine_name || '',
      frequency_per_day: Math.min(4, Math.max(1, freq)),
      times: sched.slice(0, 4),
      dosage_value: p.dosage_value || '',
      dosage_unit: p.dosage_unit || '',
      start_date: p.start_date || todayISO(),
      duration_days: p.duration_days || 5,
      guidance: p.guidance || '',
      note: p.note || p.notes || '',
    });
    setModalOpen(true);
  };

  // 改变每日次数 → 自动重建时间数组（保留已填写部分）
  const changeFrequency = (n: number) => {
    const def = FREQ_DEFAULT_TIMES[n] || ['08:00'];
    const next: string[] = [];
    for (let i = 0; i < n; i++) {
      next.push(form.times[i] || def[i] || '08:00');
    }
    setForm({ ...form, frequency_per_day: n, times: next });
  };

  const setTimeAt = (idx: number, value: string) => {
    const next = [...form.times];
    next[idx] = value;
    setForm({ ...form, times: next });
  };

  const computedEndDate = useMemo(() => {
    if (!form.start_date || !form.duration_days || form.duration_days < 1) return '';
    return addDays(form.start_date, form.duration_days);
  }, [form.start_date, form.duration_days]);

  const handleSave = async () => {
    const name = form.drug_name.trim();
    if (!name) { showToast('请输入药品名称'); return; }
    if (name.length > 30) { showToast('药品名称最多 30 字'); return; }
    if (form.frequency_per_day < 1 || form.frequency_per_day > 4) {
      showToast('每日次数应在 1~4 之间'); return;
    }
    for (const t of form.times) {
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(t)) {
        showToast(`时间格式错：${t}`); return;
      }
    }
    if (new Set(form.times).size !== form.times.length) {
      showToast('同一计划内时间不可重复'); return;
    }
    if (!form.dosage_value || !form.dosage_unit) { showToast('请选择剂量与单位'); return; }
    if (!form.start_date) { showToast('请选择开始日期'); return; }
    if (!form.duration_days || form.duration_days < 1) { showToast('服用天数 ≥ 1'); return; }
    if (!form.guidance) { showToast('请选择用药指导'); return; }
    if (form.note.length > 30) { showToast('备注最多 30 字'); return; }

    setSaving(true);
    try {
      const dosageText = `${form.dosage_value} ${form.dosage_unit}`;
      const body = {
        medicine_name: name,
        dosage: dosageText,
        notes: form.note.trim() || null,
        time_period: 'custom',
        remind_time: form.times[0] || '08:00',
        frequency_per_day: form.frequency_per_day,
        custom_times: [...form.times],
        long_term: false,
        start_date: form.start_date,
        duration_days: form.duration_days,
        end_date: computedEndDate || null,
        // 单条「用药提醒」字段不再暴露给用户：默认始终启用
        reminder_enabled: true,
        // 结构化新字段
        dosage_value: form.dosage_value,
        dosage_unit: form.dosage_unit,
        guidance: form.guidance,
      };
      if (form.id) {
        await api.put(`/api/health-plan/medications/${form.id}`, body);
      } else {
        await api.post('/api/health-plan/medications', body);
      }
      setModalOpen(false);
      try { sessionStorage.setItem('medication_changed', String(Date.now())); } catch {}
      await fetchPlans();
      showToast('保存成功');
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (status === 409 && detail && typeof detail === 'object' && detail.code === 'MEDICATION_DUPLICATE_ACTIVE') {
        setDupModal({ name: detail.existing_name || form.drug_name, existingId: detail.existing_id });
      } else {
        const msg = (typeof detail === 'string' ? detail : detail?.message) || '保存失败';
        showToast(typeof msg === 'string' ? msg : '保存失败');
      }
    } finally { setSaving(false); }
  };

  const handleDelete = async (p: Plan) => {
    const name = p.drug_name || p.medicine_name || '';
    if (typeof window !== 'undefined' && !window.confirm(`删除「${name}」？`)) return;
    try {
      await api.delete(`/api/health-plan/medications/${p.id}`);
      try { sessionStorage.setItem('medication_changed', String(Date.now())); } catch {}
      await fetchPlans();
      showToast('已删除');
    } catch { showToast('删除失败'); }
  };

  const dismissBanner = () => {
    setBannerDismissed(true);
    try { localStorage.setItem(BANNER_DISMISS_KEY, String(Date.now())); } catch {}
  };

  const goToHealthReminder = () => {
    // 跳转到健康档案 - 共管与提醒 Tab，里面会含「用药 AI 外呼提醒」开关
    try { sessionStorage.setItem('health_profile_focus_tab', 'care-reminder'); } catch {}
    router.push('/health-profile?tab=care-reminder');
  };

  const showBanner = !aiCallEnabled && !bannerDismissed && segment === 'all';

  return (
    <div
      data-testid="med-plan-v1-page"
      style={{ minHeight: '100vh', background: '#F0F9FF', maxWidth: 750, margin: '0 auto' }}
    >
      {/* 顶部 */}
      <div style={{
        display: 'flex', alignItems: 'center', padding: '12px 16px', background: '#fff',
        borderBottom: '1px solid #EAEBED', position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={() => router.back()} aria-label="返回"
          style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer', color: '#1F2937', padding: 4, marginRight: 8 }}>‹</button>
        <h1 style={{ margin: 0, fontSize: 17, fontWeight: 600, flex: 1 }}>用药计划</h1>
        <button onClick={openCreate}
          data-testid="med-plan-v1-add-btn"
          style={{
            background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
            border: 'none', color: '#fff', padding: '6px 12px', borderRadius: 6, fontSize: 13, cursor: 'pointer',
          }}>+ 新增用药计划</button>
      </div>

      {/* AI 外呼引导横幅（关时显示） */}
      {showBanner && (
        <div
          data-testid="med-plan-v1-aicall-banner"
          style={{
            display: 'flex', alignItems: 'center', gap: 8, margin: '10px 16px 0',
            padding: '10px 12px', background: '#EFF6FF', border: '1px solid #BFDBFE',
            borderRadius: 8, color: '#1D4ED8', fontSize: 13,
          }}
        >
          <span style={{ flex: 1, cursor: 'pointer' }} onClick={goToHealthReminder}>
            📞 开启 AI 外呼提醒 可电话提醒按时吃药 →
          </span>
          <button
            onClick={dismissBanner}
            aria-label="关闭"
            style={{ background: 'transparent', border: 'none', fontSize: 16, color: '#64748B', cursor: 'pointer' }}
          >×</button>
        </div>
      )}

      {/* Tab：进行中 / 历史 */}
      <div style={{
        display: 'flex', background: '#fff', margin: '12px 16px 0', borderRadius: 20, padding: 4,
        boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
      }}>
        {[
          { id: 'all' as Segment, label: '进行中' },
          { id: 'archived' as Segment, label: '历史用药' },
        ].map((s) => {
          const active = segment === s.id;
          return (
            <button key={s.id}
              data-testid={`med-plan-v1-tab-${s.id}`}
              onClick={() => setSegment(s.id)}
              style={{
                flex: 1, padding: '8px 0', borderRadius: 16,
                background: active ? 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)' : 'transparent',
                color: active ? '#fff' : '#6b7280',
                border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s',
              }}>{s.label}</button>
          );
        })}
      </div>

      <div style={{ padding: '12px 16px' }}>
        {loading ? (
          <div style={{ color: '#9CA3AF', textAlign: 'center', padding: 32 }}>加载中…</div>
        ) : plans.length === 0 ? (
          <div data-testid="med-plan-v1-empty"
            style={{ background: '#fff', padding: '40px 16px', borderRadius: 8, textAlign: 'center', color: '#9CA3AF' }}>
            {segment === 'archived' ? '暂无历史用药' : '还没有用药计划，点击右上角添加一条'}
          </div>
        ) : (
          plans.map((p) => {
            const displayName = p.drug_name || p.medicine_name || '';
            const showBadge = !!p.ai_call_badge;
            return (
              <div key={p.id}
                data-testid="med-plan-v1-card"
                style={{ background: '#fff', borderRadius: 8, padding: 14, marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ flex: 1, fontSize: 15, fontWeight: 600, color: '#111827' }}>{displayName}</div>
                  {p.is_ongoing === false && (
                    <span style={{ fontSize: 11, padding: '2px 6px', background: '#F3F4F6', color: '#6B7280', borderRadius: 6 }}>已结束</span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>剂量：{p.dosage || '-'}</div>
                {p.guidance && (
                  <div style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>用药指导：{p.guidance}</div>
                )}
                {(p.start_date || p.end_date) && (
                  <div style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>
                    服用周期：{p.start_date || '-'} ~ {p.end_date || (p.long_term ? '长期' : '-')}
                  </div>
                )}
                {/* 时间 + 电话标识 */}
                <div data-testid="med-plan-v1-times"
                  style={{ fontSize: 13, color: '#374151', marginBottom: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {(p.schedule || []).length === 0 ? '时间：-' : (p.schedule || []).map((t) => (
                    <span key={t} data-testid="med-plan-v1-time-slot"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      {showBadge && <span data-testid="med-plan-v1-aicall-icon" style={{ color: '#0284C7' }}>📞</span>}
                      {t}
                    </span>
                  ))}
                </div>
                {(p.note || p.notes) && (
                  <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 8 }}>备注：{p.note || p.notes}</div>
                )}
                {segment !== 'archived' && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                    <button onClick={() => openEdit(p)}
                      style={{ flex: 1, background: '#F3F4F6', border: '1px solid #E5E7EB', color: '#374151', padding: '6px 10px', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}>编辑</button>
                    <button onClick={() => handleDelete(p)}
                      style={{ flex: 1, background: '#FEF2F2', border: '1px solid #FEE2E2', color: '#DC2626', padding: '6px 10px', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}>删除</button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 新增/编辑 Modal */}
      {modalOpen && (
        <div
          data-testid="med-plan-v1-modal"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 20 }}
          onClick={() => setModalOpen(false)}
        >
          <div onClick={(e) => e.stopPropagation()}
            style={{ background: '#fff', width: '100%', maxWidth: 460, borderRadius: 12, padding: 16, maxHeight: '90vh', overflowY: 'auto' }}>
            {/* [PRD-MED-PLAN-V1] 顶部温馨提示 */}
            <div data-testid="med-plan-v1-warning"
              style={{ background: '#FEF3C7', color: '#92400E', padding: '8px 12px', borderRadius: 6, fontSize: 13, marginBottom: 12 }}>
              ⚠️ 用药请遵循医嘱
            </div>

            <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600 }}>{form.id ? '编辑用药计划' : '新增用药计划'}</h3>

            <Field label="药品名称">
              <input
                value={form.drug_name}
                onChange={(e) => setForm({ ...form, drug_name: e.target.value })}
                placeholder="请输入药品名称（如：阿司匹林肠溶片）"
                maxLength={30}
                data-testid="med-plan-v1-input-name"
                style={inputStyle}
              />
            </Field>

            <Field label="每日次数">
              <select
                value={form.frequency_per_day}
                onChange={(e) => changeFrequency(Number(e.target.value))}
                data-testid="med-plan-v1-select-freq"
                style={inputStyle}
              >
                {[1, 2, 3, 4].map((n) => (
                  <option key={n} value={n}>{n} 次</option>
                ))}
              </select>
            </Field>

            <Field label="用药时间">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {form.times.map((t, i) => (
                  <input key={i} type="time"
                    data-testid={`med-plan-v1-time-${i}`}
                    value={t}
                    onChange={(e) => setTimeAt(i, e.target.value)}
                    style={inputStyle}
                  />
                ))}
              </div>
            </Field>

            <Field label="每次剂量">
              <div style={{ display: 'flex', gap: 8 }}>
                <select
                  value={form.dosage_value}
                  onChange={(e) => setForm({ ...form, dosage_value: e.target.value })}
                  data-testid="med-plan-v1-select-dosage-value"
                  style={{ ...inputStyle, flex: 1 }}
                >
                  <option value="">数值</option>
                  {DOSAGE_VALUES.map((v) => (<option key={v} value={v}>{v}</option>))}
                </select>
                <select
                  value={form.dosage_unit}
                  onChange={(e) => setForm({ ...form, dosage_unit: e.target.value })}
                  data-testid="med-plan-v1-select-dosage-unit"
                  style={{ ...inputStyle, flex: 1 }}
                >
                  <option value="">单位</option>
                  {DOSAGE_UNITS.map((v) => (<option key={v} value={v}>{v}</option>))}
                </select>
              </div>
            </Field>

            <Field label="服用周期">
              <div style={{ display: 'flex', gap: 8 }}>
                <input type="date"
                  value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                  data-testid="med-plan-v1-input-start-date"
                  style={{ ...inputStyle, flex: 1 }}
                />
                <input type="number" min={1}
                  value={form.duration_days}
                  onChange={(e) => setForm({ ...form, duration_days: Math.max(1, Number(e.target.value) || 1) })}
                  data-testid="med-plan-v1-input-duration"
                  style={{ ...inputStyle, width: 100 }}
                />
                <span style={{ alignSelf: 'center', fontSize: 13, color: '#6B7280' }}>天</span>
              </div>
              {computedEndDate && (
                <div data-testid="med-plan-v1-end-date"
                  style={{ fontSize: 12, color: '#6B7280', marginTop: 6 }}>结束日期：{computedEndDate}</div>
              )}
            </Field>

            <Field label="用药指导">
              <div data-testid="med-plan-v1-guidance" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {GUIDANCE_OPTIONS.map((g) => {
                  const active = form.guidance === g;
                  return (
                    <button key={g} type="button"
                      data-testid={`med-plan-v1-guidance-${g}`}
                      onClick={() => setForm({ ...form, guidance: g })}
                      style={{
                        padding: '6px 12px', borderRadius: 16, fontSize: 13, cursor: 'pointer',
                        border: active ? '1px solid #0284C7' : '1px solid #E5E7EB',
                        background: active ? '#E0F2FE' : '#fff',
                        color: active ? '#0284C7' : '#374151',
                      }}>{g}</button>
                  );
                })}
              </div>
            </Field>

            <Field label={`备注（${form.note.length}/30）`}>
              <textarea
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value.slice(0, 30) })}
                placeholder="选填"
                maxLength={30}
                data-testid="med-plan-v1-input-note"
                style={{ ...inputStyle, minHeight: 60 }}
              />
            </Field>

            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button onClick={() => setModalOpen(false)} disabled={saving}
                style={{ flex: 1, background: '#F3F4F6', border: 'none', color: '#374151', padding: '10px', borderRadius: 6, fontSize: 14, cursor: 'pointer' }}>取消</button>
              <button onClick={handleSave} disabled={saving}
                data-testid="med-plan-v1-submit"
                style={{
                  flex: 1, background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
                  border: 'none', color: '#fff', padding: '10px', borderRadius: 6, fontSize: 14, cursor: 'pointer', opacity: saving ? 0.6 : 1,
                }}>{saving ? '保存中…' : '保存'}</button>
            </div>
          </div>
        </div>
      )}

      {/* 同名药提示弹窗 */}
      {dupModal && (
        <div
          data-testid="med-plan-v1-dup-modal"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 20 }}
          onClick={() => setDupModal(null)}
        >
          <div onClick={(e) => e.stopPropagation()}
            style={{ background: '#fff', width: '100%', maxWidth: 320, borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>同名药品提醒</div>
            <div style={{ fontSize: 13, color: '#374151', marginBottom: 16 }}>
              您已有一条进行中的【{dupModal.name}】用药计划，是否要去查看/修改？
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setDupModal(null)}
                style={{ flex: 1, background: '#F3F4F6', border: 'none', color: '#374151', padding: '10px', borderRadius: 6, fontSize: 14, cursor: 'pointer' }}>取消</button>
              <button onClick={() => {
                const id = dupModal.existingId;
                setDupModal(null);
                setModalOpen(false);
                fetchPlans().then(() => {
                  const plan = plans.find((x) => x.id === id);
                  if (plan) openEdit(plan);
                });
              }}
                style={{ flex: 1, background: '#0284C7', border: 'none', color: '#fff', padding: '10px', borderRadius: 6, fontSize: 14, cursor: 'pointer' }}>去查看</button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 100, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.75)', color: '#fff', padding: '8px 14px', borderRadius: 8, fontSize: 13, zIndex: 300,
        }}>{toast}</div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', border: '1px solid #E5E7EB',
  borderRadius: 6, fontSize: 14, outline: 'none', boxSizing: 'border-box',
  background: '#fff',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  );
}
