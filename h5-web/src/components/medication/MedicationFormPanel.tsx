'use client';

/**
 * [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划新增/编辑表单 —— 通用面板。
 *
 * 使用方：
 *  - /ai-home/medication-plans/new
 *  - /ai-home/medication-plans/:id（编辑模式）
 *
 * 字段：药品名称 / 剂量（数值+单位）/ 用药频次 / 服用时机（多选）/
 *      服药开始日期（默认今天；允许过去；最长 today+1 年）/
 *      服药截止日期（≥ 开始日期）/ 备注（≤ 200 字）
 * 过去日期：仅在日期选择器下方显示浅灰色提示。
 */

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Dialog } from 'antd-mobile';
import api from '@/lib/api';

const DOSAGE_VALUES = [
  '1/4', '1/2', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
  '15', '20', '25', '30', '35', '40', '45', '50',
  '100', '150', '200', '250', '300', '350', '400', '450', '500',
];
const DOSAGE_UNITS = ['片', '粒', '袋', '支', '瓶', '贴', 'g', 'mL', 'mg', 'μg'];
const FREQ_OPTIONS = [
  { v: 1, label: '每日 1 次' },
  { v: 2, label: '每日 2 次' },
  { v: 3, label: '每日 3 次' },
  { v: 4, label: '每日 4 次' },
];
const TIMING_OPTIONS = ['饭前', '饭后', '随餐', '睡前', '晨起'];

const BLUE = '#4A9EE0';
const GREEN = '#22c55e';
const TEXT = '#111827';
const SUB = '#6B7280';

interface FormState {
  medicine_name: string;
  dosage_value: string;
  dosage_unit: string;
  frequency_per_day: number;
  guidance: string; // 主要 guidance（取第一个）
  guidance_list: string[]; // UI 多选
  start_date: string;
  end_date: string;
  long_term: boolean;
  notes: string;
}

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function maxStr() {
  const d = new Date();
  d.setFullYear(d.getFullYear() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function MedicationFormPanel({ planId }: { planId?: number }) {
  const router = useRouter();
  const editing = !!planId;
  const [form, setForm] = useState<FormState>({
    medicine_name: '',
    dosage_value: '1',
    dosage_unit: '片',
    frequency_per_day: 3,
    guidance: '饭后',
    guidance_list: ['饭后'],
    start_date: todayStr(),
    end_date: '',
    long_term: false,
    notes: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [loaded, setLoaded] = useState(!editing);

  useEffect(() => {
    if (!editing) return;
    (async () => {
      try {
        const res: any = await api.get(`/api/health-plan/medications/${planId}`);
        const d = res.data || res;
        setForm({
          medicine_name: d.medicine_name || '',
          dosage_value: d.dosage_value || '1',
          dosage_unit: d.dosage_unit || '片',
          frequency_per_day: d.frequency_per_day || 3,
          guidance: d.guidance || '饭后',
          guidance_list: d.guidance ? [d.guidance] : ['饭后'],
          start_date: d.start_date || todayStr(),
          end_date: d.end_date || '',
          long_term: !!d.long_term,
          notes: d.notes || '',
        });
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setLoaded(true);
      }
    })();
  }, [editing, planId]);

  const isPastStart = useMemo(() => {
    if (!form.start_date) return false;
    return form.start_date < todayStr();
  }, [form.start_date]);

  const handleSubmit = async () => {
    if (!form.medicine_name.trim()) {
      Toast.show({ content: '请填写药品名称' });
      return;
    }
    if (!form.long_term && form.end_date && form.end_date < form.start_date) {
      Toast.show({ content: '截止日期必须 ≥ 开始日期' });
      return;
    }
    if (form.notes && form.notes.length > 200) {
      Toast.show({ content: '备注不超过 200 字' });
      return;
    }
    setSubmitting(true);
    try {
      const payload: any = {
        medicine_name: form.medicine_name.trim(),
        dosage: `${form.dosage_value} ${form.dosage_unit}`,
        dosage_value: form.dosage_value,
        dosage_unit: form.dosage_unit,
        frequency_per_day: form.frequency_per_day,
        guidance: form.guidance_list[0] || form.guidance,
        start_date: form.start_date,
        long_term: form.long_term,
        notes: form.notes,
      };
      if (form.end_date && !form.long_term) {
        payload.end_date = form.end_date;
      }
      let id = planId;
      if (editing) {
        await api.put(`/api/health-plan/medications/${planId}`, payload);
      } else {
        const res: any = await api.post('/api/health-plan/medications', payload);
        id = (res.data || res)?.id;
      }
      Toast.show({ content: '已保存', icon: 'success' });
      // 跳列表 + tab + highlight
      const today = todayStr();
      let tab = 'in_progress';
      if (form.start_date > today) tab = 'not_started';
      else if (!form.long_term && form.end_date && form.end_date < today) tab = 'finished';
      router.push(`/ai-home/medication-plans?tab=${tab}${id ? `&highlight=${id}` : ''}`);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg =
        typeof detail === 'object'
          ? detail?.message || JSON.stringify(detail)
          : detail || '保存失败';
      Toast.show({ content: msg, icon: 'fail' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!editing) return;
    const ok = await Dialog.confirm({ content: '确定删除该用药计划吗？' });
    if (!ok) return;
    try {
      await api.delete(`/api/health-plan/medications/${planId}`);
      Toast.show({ content: '已删除', icon: 'success' });
      router.push('/ai-home/medication-plans');
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  if (!loaded) {
    return <div style={{ padding: 40, textAlign: 'center', color: SUB }}>加载中…</div>;
  }

  return (
    <div data-testid="med-form-panel" style={{ padding: 16 }}>
      <Section title="药品名称">
        <input
          data-testid="med-form-name"
          value={form.medicine_name}
          onChange={(e) => setForm({ ...form, medicine_name: e.target.value })}
          placeholder="如 阿司匹林肠溶片"
          style={inputStyle}
        />
      </Section>

      <Section title="剂量">
        <div style={{ display: 'flex', gap: 8 }}>
          <select
            data-testid="med-form-dosage-value"
            value={form.dosage_value}
            onChange={(e) => setForm({ ...form, dosage_value: e.target.value })}
            style={{ ...inputStyle, flex: 1 }}
          >
            {DOSAGE_VALUES.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
          <select
            data-testid="med-form-dosage-unit"
            value={form.dosage_unit}
            onChange={(e) => setForm({ ...form, dosage_unit: e.target.value })}
            style={{ ...inputStyle, flex: 1 }}
          >
            {DOSAGE_UNITS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
      </Section>

      <Section title="用药频次">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {FREQ_OPTIONS.map((f) => (
            <Chip
              key={f.v}
              active={form.frequency_per_day === f.v}
              onClick={() => setForm({ ...form, frequency_per_day: f.v })}
              testid={`med-form-freq-${f.v}`}
            >
              {f.label}
            </Chip>
          ))}
        </div>
      </Section>

      <Section title="服用时机（多选）">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {TIMING_OPTIONS.map((t) => (
            <Chip
              key={t}
              active={form.guidance_list.includes(t)}
              onClick={() => {
                const has = form.guidance_list.includes(t);
                const next = has
                  ? form.guidance_list.filter((x) => x !== t)
                  : [...form.guidance_list, t];
                setForm({ ...form, guidance_list: next, guidance: next[0] || t });
              }}
              testid={`med-form-timing-${t}`}
            >
              {t}
            </Chip>
          ))}
        </div>
      </Section>

      <Section title="服药开始日期">
        <input
          type="date"
          data-testid="med-form-start"
          value={form.start_date}
          max={maxStr()}
          onChange={(e) => setForm({ ...form, start_date: e.target.value })}
          style={inputStyle}
        />
        {isPastStart && (
          <div
            data-testid="med-form-past-hint"
            style={{ marginTop: 6, color: '#9CA3AF', fontSize: 12 }}
          >
            开始日期早于今天，将自动按已过去的天数计算服药记录
          </div>
        )}
      </Section>

      <Section title="服药截止日期">
        <input
          type="date"
          data-testid="med-form-end"
          value={form.end_date}
          min={form.start_date}
          disabled={form.long_term}
          onChange={(e) => setForm({ ...form, end_date: e.target.value })}
          style={inputStyle}
        />
        <label
          style={{
            marginTop: 8,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: SUB,
            cursor: 'pointer',
          }}
        >
          <input
            type="checkbox"
            data-testid="med-form-long-term"
            checked={form.long_term}
            onChange={(e) => setForm({ ...form, long_term: e.target.checked })}
          />
          长期服用
        </label>
      </Section>

      <Section title={`备注（${form.notes.length}/200）`}>
        <textarea
          data-testid="med-form-notes"
          value={form.notes}
          maxLength={200}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          rows={3}
          style={{ ...inputStyle, resize: 'vertical' }}
        />
      </Section>

      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        {editing && (
          <button
            onClick={handleDelete}
            data-testid="med-form-delete"
            style={{
              flex: 1,
              padding: '12px 0',
              background: '#fff',
              color: '#DC2626',
              border: '1px solid #FCA5A5',
              borderRadius: 24,
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            删除
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={submitting}
          data-testid="med-form-submit"
          style={{
            flex: 2,
            padding: '12px 0',
            background: BLUE,
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            fontSize: 15,
            fontWeight: 700,
            cursor: 'pointer',
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? '保存中…' : editing ? '保存修改' : '保存'}
        </button>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid #D1D5DB',
  fontSize: 14,
  boxSizing: 'border-box',
  background: '#fff',
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 13, color: '#374151', fontWeight: 600, marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
  testid,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  testid?: string;
}) {
  return (
    <button
      onClick={onClick}
      data-testid={testid}
      style={{
        padding: '6px 14px',
        borderRadius: 16,
        background: active ? BLUE : '#F3F4F6',
        color: active ? '#fff' : '#374151',
        border: 'none',
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  );
}
