'use client';

/**
 * [PRD-439 F-07 / BUG-HEALTH-ARCHIVE-V2 2026-05-16] 用药提醒管理页
 *
 * 路由: /medication-plans
 * - 顶部返回 + 标题"用药提醒管理"
 * - 新增/编辑/删除/启停 用药计划
 *
 * [BUG-HEALTH-ARCHIVE-V2] 统一数据源到 MedicationReminder（health-plan-v2）：
 * - 列表 GET：/api/health-plan/medications/list
 * - 新增 POST：/api/health-plan/medications
 * - 编辑 PUT：/api/health-plan/medications/{id}
 * - 删除 DELETE：/api/health-plan/medications/{id}
 * - 双 Tab：今日用药 / 全部在用药品
 */

import { useEffect, useState, useCallback } from 'react';
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
  patient_id?: number | null;
}

interface FormState {
  id?: number;
  drug_name: string;
  dosage: string;
  schedule: string;
  note: string;
  enabled: boolean;
  long_term: boolean;
  end_date: string;
}

const EMPTY_FORM: FormState = {
  drug_name: '',
  dosage: '',
  schedule: '08:00',
  note: '',
  enabled: true,
  long_term: true,
  end_date: '',
};

type Segment = 'today' | 'all';

export default function MedicationPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [segment, setSegment] = useState<Segment>('all');

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  };

  const fetchPlans = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/health-plan/medications/list');
      const data = res?.data || res;
      const arr = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
      setPlans(arr as Plan[]);
    } catch {
      showToast('加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (p: Plan) => {
    setForm({
      id: p.id,
      drug_name: p.drug_name || p.medicine_name || '',
      dosage: p.dosage,
      schedule: (p.schedule || []).join(','),
      note: p.note || p.notes || '',
      enabled: p.enabled,
      long_term: !!p.long_term,
      end_date: p.end_date || '',
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.drug_name.trim()) {
      showToast('请输入药品名称');
      return;
    }
    if (!form.dosage.trim()) {
      showToast('请输入剂量');
      return;
    }
    const schedule = form.schedule
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (schedule.length === 0) {
      showToast('请至少输入 1 个服用时间');
      return;
    }
    for (const t of schedule) {
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(t)) {
        showToast(`时间格式有误：${t}`);
        return;
      }
    }
    setSaving(true);
    try {
      const body = {
        medicine_name: form.drug_name.trim(),
        dosage: form.dosage.trim(),
        notes: form.note.trim() || null,
        time_period: 'custom',
        remind_time: schedule[0] || '08:00',
        frequency_per_day: schedule.length,
        custom_times: schedule,
        long_term: form.long_term,
        end_date: form.long_term ? null : (form.end_date || null),
        reminder_enabled: form.enabled,
      };
      if (form.id) {
        await api.put(`/api/health-plan/medications/${form.id}`, body);
      } else {
        await api.post('/api/health-plan/medications', body);
      }
      setModalOpen(false);
      try {
        sessionStorage.setItem('medication_changed', String(Date.now()));
      } catch {}
      await fetchPlans();
      showToast('保存成功');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || '保存失败';
      showToast(typeof msg === 'string' ? msg : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleEnabled = async (p: Plan) => {
    try {
      await api.put(`/api/health-plan/medications/${p.id}`, {
        reminder_enabled: !p.enabled,
      });
      await fetchPlans();
    } catch {
      showToast('切换失败');
    }
  };

  const handleDelete = async (p: Plan) => {
    const name = p.drug_name || p.medicine_name || '';
    if (typeof window !== 'undefined' && !window.confirm(`删除「${name}」？`)) return;
    try {
      await api.delete(`/api/health-plan/medications/${p.id}`);
      try {
        sessionStorage.setItem('medication_changed', String(Date.now()));
      } catch {}
      await fetchPlans();
      showToast('已删除');
    } catch {
      showToast('删除失败');
    }
  };

  // 双 Tab 过滤：今日用药 = 在用药品 ∩ 今天命中服药时间点
  // 由于「在用药品」每日均需服用（无每周/隔日重复字段），所以今日 Tab = 所有在用药品中 schedule 非空者
  const todayList = plans.filter((p) => Array.isArray(p.schedule) && p.schedule.length > 0);
  const allList = plans;
  const visibleList: Plan[] = segment === 'today' ? todayList : allList;

  return (
    <div
      data-testid="prd439-medication-plans-page"
      style={{
        minHeight: '100vh',
        background: 'var(--color-brand-50)',
        maxWidth: 750,
        margin: '0 auto',
      }}
    >
      {/* 顶部 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          background: '#fff',
          borderBottom: '1px solid #EAEBED',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <button
          onClick={() => router.back()}
          aria-label="返回"
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 22,
            cursor: 'pointer',
            color: '#1F2937',
            padding: 4,
            marginRight: 8,
          }}
        >
          ‹
        </button>
        <h1 style={{ margin: 0, fontSize: 17, fontWeight: 600, flex: 1 }}>用药提醒管理</h1>
        <button
          onClick={openCreate}
          style={{
            background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
            border: 'none',
            color: '#fff',
            padding: '6px 12px',
            borderRadius: 6,
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          + 新增用药计划
        </button>
      </div>

      {/* 双 Tab：今日用药 / 全部用药计划 */}
      <div
        data-testid="prd439-medication-plans-seg"
        style={{
          display: 'flex',
          background: '#fff',
          margin: '12px 16px 0',
          borderRadius: 20,
          padding: 4,
          boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
        }}
      >
        {[
          { id: 'today' as Segment, label: '今日用药', count: todayList.length },
          { id: 'all' as Segment, label: '全部用药计划', count: allList.length },
        ].map((s) => {
          const active = segment === s.id;
          return (
            <button
              key={s.id}
              data-testid={`prd439-medication-plans-seg-${s.id}`}
              onClick={() => setSegment(s.id)}
              style={{
                flex: 1,
                padding: '8px 0',
                borderRadius: 16,
                background: active ? 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)' : 'transparent',
                color: active ? '#fff' : '#6b7280',
                border: 'none',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {s.label}（{s.count}）
            </button>
          );
        })}
      </div>

      <div style={{ padding: '12px 16px' }}>
        {loading ? (
          <div style={{ color: '#9CA3AF', textAlign: 'center', padding: 32 }}>加载中…</div>
        ) : visibleList.length === 0 ? (
          <div
            data-testid="prd439-medication-plans-empty"
            style={{
              background: '#fff',
              padding: '40px 16px',
              borderRadius: 8,
              textAlign: 'center',
              color: '#9CA3AF',
            }}
          >
            {segment === 'today' ? '今日暂无用药计划' : '还没有用药计划，点击右上角添加一条'}
          </div>
        ) : (
          visibleList.map((p) => {
            const displayName = p.drug_name || p.medicine_name || '';
            return (
              <div
                key={p.id}
                data-testid="prd439-medication-plan-card"
                style={{
                  background: '#fff',
                  borderRadius: 8,
                  padding: 14,
                  marginBottom: 10,
                  opacity: p.enabled ? 1 : 0.6,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ flex: 1, fontSize: 15, fontWeight: 600, color: '#111827' }}>
                    {displayName}
                    {p.long_term && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 11,
                          padding: '2px 6px',
                          background: '#dcfce7',
                          color: '#16a34a',
                          borderRadius: 6,
                        }}
                      >
                        长期
                      </span>
                    )}
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#6B7280', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={p.enabled}
                      onChange={() => handleToggleEnabled(p)}
                    />
                    {p.enabled ? '启用' : '已停'}
                  </label>
                </div>
                <div style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>
                  剂量：{p.dosage || '-'}
                </div>
                <div style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>
                  时间：{(p.schedule || []).join('、') || '-'}
                </div>
                {(p.note || p.notes) && (
                  <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 8 }}>备注：{p.note || p.notes}</div>
                )}
                {!p.long_term && p.end_date && (
                  <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 8 }}>截止日期：{p.end_date}</div>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                  <button
                    onClick={() => openEdit(p)}
                    style={{
                      flex: 1,
                      background: '#F3F4F6',
                      border: '1px solid #E5E7EB',
                      color: '#374151',
                      padding: '6px 10px',
                      borderRadius: 6,
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleDelete(p)}
                    style={{
                      flex: 1,
                      background: '#FEF2F2',
                      border: '1px solid #FEE2E2',
                      color: '#DC2626',
                      padding: '6px 10px',
                      borderRadius: 6,
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 新增/编辑 Modal */}
      {modalOpen && (
        <div
          data-testid="prd439-medication-plan-modal"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: 20,
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff',
              width: '100%',
              maxWidth: 420,
              borderRadius: 12,
              padding: 16,
            }}
          >
            <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600 }}>
              {form.id ? '编辑用药计划' : '新增用药计划'}
            </h3>
            <Field label="药品名称">
              <input
                value={form.drug_name}
                onChange={(e) => setForm({ ...form, drug_name: e.target.value })}
                placeholder="如：阿司匹林"
                style={inputStyle}
              />
            </Field>
            <Field label="剂量">
              <input
                value={form.dosage}
                onChange={(e) => setForm({ ...form, dosage: e.target.value })}
                placeholder="如：1片 / 100mg"
                style={inputStyle}
              />
            </Field>
            <Field label="服用时间（多个用逗号分隔，HH:MM）">
              <input
                value={form.schedule}
                onChange={(e) => setForm({ ...form, schedule: e.target.value })}
                placeholder="08:00,14:00,20:00"
                style={inputStyle}
              />
            </Field>
            <Field label="备注">
              <input
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                placeholder="选填"
                style={inputStyle}
              />
            </Field>
            <div style={{ marginTop: 8 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#374151' }}>
                <input
                  type="checkbox"
                  checked={form.long_term}
                  onChange={(e) => setForm({ ...form, long_term: e.target.checked })}
                />
                长期服用
              </label>
            </div>
            {!form.long_term && (
              <Field label="截止日期">
                <input
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                  style={inputStyle}
                />
              </Field>
            )}
            <div style={{ marginTop: 8 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#374151' }}>
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                启用提醒
              </label>
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button
                onClick={() => setModalOpen(false)}
                disabled={saving}
                style={{
                  flex: 1,
                  background: '#F3F4F6',
                  border: 'none',
                  color: '#374151',
                  padding: '10px',
                  borderRadius: 6,
                  fontSize: 14,
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  flex: 1,
                  background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
                  border: 'none',
                  color: '#fff',
                  padding: '10px',
                  borderRadius: 6,
                  fontSize: 14,
                  cursor: 'pointer',
                  opacity: saving ? 0.6 : 1,
                }}
              >
                {saving ? '保存中…' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 100,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(0,0,0,0.75)',
            color: '#fff',
            padding: '8px 14px',
            borderRadius: 8,
            fontSize: 13,
            zIndex: 200,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  border: '1px solid #E5E7EB',
  borderRadius: 6,
  fontSize: 14,
  outline: 'none',
  boxSizing: 'border-box',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  );
}
