'use client';

/**
 * [PRD-MED-PLAN-ADD-OPTIM-V1 2026-05-17] 添加用药计划页面优化版
 *
 * 字段（按 PRD §四 顺序）：
 *  1. 药品名称  —— 输入框 + ≥2 字开始联想下拉（最多 6 条）+ 允许手动兜底
 *  2. 用药时间  —— 抽屉：顶部 4 个频次卡片 + 下方按频次动态显示单行时间卡片（仅时间数字）
 *                 点击时间卡片弹出时:分滚轮
 *  3. 每次剂量  —— 数量轮（含 ¼/½）+ 单位轮
 *  4. 服用周期  —— 起始日固定"今天"+ 持续天数滚轮（默认 4 天，1-90）+ 右侧自动显示结束日期
 *  5. 服用时机  —— 5 个圆角标签单选：饭前/饭后/空腹/随餐/睡前
 *  6. 备注      —— 单行输入框，最多 30 字，实时字数
 *
 * 保存按钮始终可点击；点击时统一校验，失败 Toast "请先填写 XX"。
 * 兼容编辑模式（planId 存在时）。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Dialog } from 'antd-mobile';
import api from '@/lib/api';

// ────────────────── 常量 ──────────────────

const DOSAGE_VALUES = [
  '¼', '½', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
  '15', '20', '25', '30', '35', '40', '45', '50',
  '100', '150', '200', '250', '300', '350', '400', '450', '500',
];
const DOSAGE_UNITS = ['片', '粒', '袋', '支', '瓶', '贴', 'g', 'mL', 'mg', 'μg'];

const TIMING_OPTIONS = ['饭前', '饭后', '空腹', '随餐', '睡前'];

const FREQ_DEFAULTS: Record<number, string[]> = {
  1: ['08:00'],
  2: ['08:00', '18:00'],
  3: ['08:00', '12:00', '18:00'],
  4: ['08:00', '12:00', '18:00', '22:00'],
};

const NOTES_MAX = 30;
const DURATION_MIN = 1;
const DURATION_MAX = 90;
const DURATION_DEFAULT = 4;

const BLUE = '#4A9EE0';
const SUB = '#6B7280';

// ────────────────── 工具 ──────────────────

function today(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}
function todayStr(): string {
  const d = today();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d.getTime());
  r.setDate(r.getDate() + n);
  return r;
}
function fmtMonthDay(d: Date): string {
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}
function dosageStringForBackend(v: string): string {
  // 兼容后端：把 ¼/½ 转成 1/4 / 1/2，否则原样
  if (v === '¼') return '1/4';
  if (v === '½') return '1/2';
  return v;
}
function dosageStringForUI(v?: string | null): string {
  if (!v) return '1';
  if (v === '1/4') return '¼';
  if (v === '1/2') return '½';
  return v;
}

// ────────────────── 类型 ──────────────────

interface SuggestItem {
  id: number;
  name: string;
  generic_name?: string | null;
  spec?: string | null;
  manufacturer?: string | null;
}

interface FormState {
  medicine_name: string;
  dosage_value: string;
  dosage_unit: string;
  frequency_per_day: number;
  custom_times: string[]; // 长度等于 frequency_per_day
  guidance: string;       // 单选
  duration_days: number;  // 1-90
  notes: string;
}

// ────────────────── 主组件 ──────────────────

export default function MedicationFormPanel({ planId }: { planId?: number }) {
  const router = useRouter();
  const editing = !!planId;

  const [form, setForm] = useState<FormState>({
    medicine_name: '',
    dosage_value: '1',
    dosage_unit: '片',
    frequency_per_day: 1,
    custom_times: [...FREQ_DEFAULTS[1]],
    guidance: '',
    duration_days: DURATION_DEFAULT,
    notes: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [loaded, setLoaded] = useState(!editing);

  // 联想下拉状态
  const [suggests, setSuggests] = useState<SuggestItem[]>([]);
  const [showSuggest, setShowSuggest] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const suggestTimer = useRef<any>(null);

  // 抽屉：用药时间
  const [timeDrawerOpen, setTimeDrawerOpen] = useState(false);
  // 抽屉：剂量
  const [dosageDrawerOpen, setDosageDrawerOpen] = useState(false);
  // 抽屉：持续天数
  const [durationDrawerOpen, setDurationDrawerOpen] = useState(false);
  // 抽屉：单时间点滚轮（h:m）
  const [timePickerIdx, setTimePickerIdx] = useState<number | null>(null);

  // ───── 编辑模式加载 ─────
  useEffect(() => {
    if (!editing) return;
    (async () => {
      try {
        const res: any = await api.get(`/api/health-plan/medications/${planId}`);
        const d = res.data || res;
        const freq = d.frequency_per_day || 1;
        let times: string[] = Array.isArray(d.custom_times) && d.custom_times.length
          ? d.custom_times.slice(0, freq)
          : [...FREQ_DEFAULTS[Math.min(Math.max(freq, 1), 4)] || ['08:00']];
        while (times.length < freq) times.push('08:00');
        setForm({
          medicine_name: d.medicine_name || '',
          dosage_value: dosageStringForUI(d.dosage_value),
          dosage_unit: d.dosage_unit || '片',
          frequency_per_day: freq,
          custom_times: times,
          guidance: d.guidance || '',
          duration_days: d.duration_days || DURATION_DEFAULT,
          notes: (d.notes || '').slice(0, NOTES_MAX),
        });
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setLoaded(true);
      }
    })();
  }, [editing, planId]);

  // ───── 药品联想 ─────
  const triggerSuggest = (q: string) => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    if (!q || q.trim().length < 2) {
      setSuggests([]);
      setShowSuggest(false);
      return;
    }
    suggestTimer.current = setTimeout(async () => {
      setSuggestLoading(true);
      try {
        const res: any = await api.get('/api/medication-library/suggest', {
          params: { q: q.trim(), limit: 6 },
        });
        const data = res.data || res;
        const items: SuggestItem[] = data?.items || [];
        setSuggests(items);
        setShowSuggest(items.length > 0);
      } catch {
        setSuggests([]);
        setShowSuggest(false);
      } finally {
        setSuggestLoading(false);
      }
    }, 250);
  };

  // ───── 频次切换：保留已存在的时间点，新增的填默认 ─────
  const handleChangeFreq = (n: number) => {
    setForm((prev) => {
      const old = prev.custom_times;
      const def = FREQ_DEFAULTS[n] || ['08:00'];
      let next: string[];
      if (n <= old.length) {
        next = old.slice(0, n);
      } else {
        next = [...old];
        for (let i = old.length; i < n; i++) {
          next.push(def[i] || '08:00');
        }
      }
      // PRD §七：从 2 次/天 切回 1 次/天 时恢复默认（避免歧义）
      if (n === 1) {
        next = [...FREQ_DEFAULTS[1]];
      }
      return { ...prev, frequency_per_day: n, custom_times: next };
    });
  };

  // ───── 服用周期：右侧"至 X月X日" ─────
  const endDateStr = useMemo(() => {
    const d = addDays(today(), Math.max(form.duration_days - 1, 0));
    return fmtMonthDay(d);
  }, [form.duration_days]);

  // ───── 保存 ─────
  const handleSubmit = async () => {
    // 顺序校验
    if (!form.medicine_name.trim()) {
      Toast.show({ content: '请先填写药品名称' });
      return;
    }
    if (!form.frequency_per_day || form.custom_times.length !== form.frequency_per_day) {
      Toast.show({ content: '请先填写用药时间' });
      return;
    }
    for (const t of form.custom_times) {
      if (!t || !/^\d{2}:\d{2}$/.test(t)) {
        Toast.show({ content: '请先填写用药时间' });
        return;
      }
    }
    if (!form.dosage_value || !form.dosage_unit) {
      Toast.show({ content: '请先填写每次剂量' });
      return;
    }
    if (!form.duration_days || form.duration_days < DURATION_MIN || form.duration_days > DURATION_MAX) {
      Toast.show({ content: '请先填写服用周期' });
      return;
    }
    if (!form.guidance) {
      Toast.show({ content: '请先选择服用时机' });
      return;
    }

    setSubmitting(true);
    try {
      const startDate = todayStr();
      const dvBackend = dosageStringForBackend(form.dosage_value);
      const payload: any = {
        medicine_name: form.medicine_name.trim(),
        dosage: `${dvBackend} ${form.dosage_unit}`,
        dosage_value: dvBackend,
        dosage_unit: form.dosage_unit,
        frequency_per_day: form.frequency_per_day,
        custom_times: form.custom_times,
        remind_time: form.custom_times[0] || '08:00',
        time_period: 'custom',
        start_date: startDate,
        duration_days: form.duration_days,
        guidance: form.guidance,
        notes: form.notes || '',
        reminder_enabled: true,
        long_term: false,
      };
      let id = planId;
      if (editing) {
        await api.put(`/api/health-plan/medications/${planId}`, payload);
      } else {
        const res: any = await api.post('/api/health-plan/medications', payload);
        id = (res.data || res)?.id;
      }
      Toast.show({ content: '添加成功', icon: 'success' });
      router.back();
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
      {/* 1. 药品名称 + 联想 */}
      <Section title="药品名称" required>
        <div style={{ position: 'relative' }}>
          <input
            data-testid="med-form-name"
            value={form.medicine_name}
            onChange={(e) => {
              const v = e.target.value;
              setForm({ ...form, medicine_name: v });
              triggerSuggest(v);
            }}
            onFocus={() => {
              if (suggests.length > 0) setShowSuggest(true);
            }}
            onBlur={() => {
              // 留 200ms 让点击下拉先触发
              setTimeout(() => setShowSuggest(false), 200);
            }}
            placeholder="如 阿司匹林肠溶片"
            style={inputStyle}
            autoComplete="off"
          />
          {showSuggest && suggests.length > 0 && (
            <div
              data-testid="med-form-suggest-list"
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                background: '#fff',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                marginTop: 4,
                zIndex: 100,
                boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                maxHeight: 280,
                overflowY: 'auto',
              }}
            >
              {suggests.map((it) => (
                <div
                  key={it.id}
                  data-testid={`med-form-suggest-item-${it.id}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setForm((f) => ({ ...f, medicine_name: it.name }));
                    setShowSuggest(false);
                  }}
                  style={{
                    padding: '10px 12px',
                    borderBottom: '1px solid #F3F4F6',
                    cursor: 'pointer',
                    fontSize: 14,
                  }}
                >
                  <div style={{ color: '#111827', fontWeight: 500 }}>{it.name}</div>
                  {(it.generic_name || it.spec) && (
                    <div style={{ color: SUB, fontSize: 12, marginTop: 2 }}>
                      {[it.generic_name, it.spec].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {suggestLoading && (
            <div style={{ position: 'absolute', right: 12, top: 12, fontSize: 12, color: SUB }}>
              搜索中…
            </div>
          )}
        </div>
      </Section>

      {/* 2. 用药时间（抽屉触发器） */}
      <Section title="用药时间" required>
        <div
          data-testid="med-form-time-trigger"
          onClick={() => setTimeDrawerOpen(true)}
          style={{
            ...inputStyle,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ color: '#111827' }}>
            {form.frequency_per_day} 次/天 · {form.custom_times.join(' / ')}
          </span>
          <span style={{ color: SUB }}>›</span>
        </div>
      </Section>

      {/* 3. 每次剂量（抽屉触发器） */}
      <Section title="每次剂量" required>
        <div
          data-testid="med-form-dosage-trigger"
          onClick={() => setDosageDrawerOpen(true)}
          style={{
            ...inputStyle,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ color: '#111827' }}>
            {form.dosage_value} {form.dosage_unit}
          </span>
          <span style={{ color: SUB }}>›</span>
        </div>
      </Section>

      {/* 4. 服用周期 */}
      <Section title="服用周期" required>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <span style={{ color: '#374151', fontSize: 14 }}>开始：今天</span>
          <div
            data-testid="med-form-duration-trigger"
            onClick={() => setDurationDrawerOpen(true)}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: '1px solid #D1D5DB',
              background: '#fff',
              cursor: 'pointer',
              fontSize: 14,
              color: '#111827',
              minWidth: 90,
              textAlign: 'center',
            }}
          >
            持续 {form.duration_days} 天
          </div>
          <span data-testid="med-form-end-date" style={{ color: SUB, fontSize: 14 }}>
            至 {endDateStr}
          </span>
        </div>
      </Section>

      {/* 5. 服用时机 */}
      <Section title="服用时机" required>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {TIMING_OPTIONS.map((t) => (
            <Chip
              key={t}
              active={form.guidance === t}
              onClick={() => setForm({ ...form, guidance: t })}
              testid={`med-form-timing-${t}`}
            >
              {t}
            </Chip>
          ))}
        </div>
      </Section>

      {/* 6. 备注 */}
      <Section title="备注">
        <div style={{ position: 'relative' }}>
          <input
            data-testid="med-form-notes"
            value={form.notes}
            maxLength={NOTES_MAX}
            onChange={(e) => setForm({ ...form, notes: e.target.value.slice(0, NOTES_MAX) })}
            placeholder="选填，如服药提示"
            style={{ ...inputStyle, paddingRight: 56 }}
          />
          <span
            data-testid="med-form-notes-count"
            style={{
              position: 'absolute',
              right: 12,
              top: '50%',
              transform: 'translateY(-50%)',
              color: SUB,
              fontSize: 12,
            }}
          >
            {form.notes.length}/{NOTES_MAX}
          </span>
        </div>
      </Section>

      {/* 保存按钮（始终可点击） */}
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

      {/* ─────── 抽屉：用药时间 ─────── */}
      {timeDrawerOpen && (
        <BottomDrawer onClose={() => setTimeDrawerOpen(false)} title="用药时间">
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: '#374151', fontWeight: 600, marginBottom: 8 }}>
              用药频次
            </div>
            <div
              data-testid="med-form-freq-cards"
              style={{ display: 'flex', gap: 8 }}
            >
              {[1, 2, 3, 4].map((n) => (
                <FreqCard
                  key={n}
                  n={n}
                  active={form.frequency_per_day === n}
                  onClick={() => handleChangeFreq(n)}
                />
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#374151', fontWeight: 600, marginBottom: 8 }}>
              用药时间点
            </div>
            <div
              data-testid="med-form-time-cards"
              style={{
                display: 'flex',
                gap: 8,
                overflowX: 'auto',
                flexWrap: 'nowrap',
                paddingBottom: 4,
              }}
            >
              {form.custom_times.map((t, idx) => (
                <TimeCard
                  key={idx}
                  time={t}
                  onClick={() => setTimePickerIdx(idx)}
                  testid={`med-form-time-card-${idx}`}
                />
              ))}
            </div>
          </div>
          <div style={{ marginTop: 20, textAlign: 'right' }}>
            <button
              onClick={() => setTimeDrawerOpen(false)}
              style={confirmBtnStyle}
              data-testid="med-form-time-confirm"
            >
              确定
            </button>
          </div>
        </BottomDrawer>
      )}

      {/* ─────── 抽屉：剂量（两栏滚轮） ─────── */}
      {dosageDrawerOpen && (
        <BottomDrawer onClose={() => setDosageDrawerOpen(false)} title="每次剂量">
          <div style={{ display: 'flex', gap: 12 }}>
            <WheelColumn
              testid="med-form-dosage-value"
              items={DOSAGE_VALUES}
              value={form.dosage_value}
              onChange={(v) => setForm({ ...form, dosage_value: v })}
            />
            <WheelColumn
              testid="med-form-dosage-unit"
              items={DOSAGE_UNITS}
              value={form.dosage_unit}
              onChange={(v) => setForm({ ...form, dosage_unit: v })}
            />
          </div>
          <div style={{ marginTop: 16, textAlign: 'right' }}>
            <button
              onClick={() => setDosageDrawerOpen(false)}
              style={confirmBtnStyle}
              data-testid="med-form-dosage-confirm"
            >
              确定
            </button>
          </div>
        </BottomDrawer>
      )}

      {/* ─────── 抽屉：持续天数滚轮 ─────── */}
      {durationDrawerOpen && (
        <BottomDrawer onClose={() => setDurationDrawerOpen(false)} title="持续天数">
          <WheelColumn
            testid="med-form-duration-wheel"
            items={Array.from({ length: DURATION_MAX - DURATION_MIN + 1 }, (_, i) =>
              String(DURATION_MIN + i)
            )}
            value={String(form.duration_days)}
            onChange={(v) => {
              const n = parseInt(v, 10);
              if (!isNaN(n) && n >= DURATION_MIN && n <= DURATION_MAX) {
                setForm({ ...form, duration_days: n });
              }
            }}
            suffix="天"
          />
          <div style={{ marginTop: 16, textAlign: 'right' }}>
            <button
              onClick={() => setDurationDrawerOpen(false)}
              style={confirmBtnStyle}
              data-testid="med-form-duration-confirm"
            >
              确定
            </button>
          </div>
        </BottomDrawer>
      )}

      {/* ─────── 抽屉：单时间点滚轮（时:分） ─────── */}
      {timePickerIdx !== null && (
        <TimePickerDrawer
          value={form.custom_times[timePickerIdx]}
          onConfirm={(v) => {
            const next = [...form.custom_times];
            next[timePickerIdx!] = v;
            setForm({ ...form, custom_times: next });
            setTimePickerIdx(null);
          }}
          onCancel={() => setTimePickerIdx(null)}
        />
      )}
    </div>
  );
}

// ────────────────── 小组件 ──────────────────

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid #D1D5DB',
  fontSize: 14,
  boxSizing: 'border-box',
  background: '#fff',
};

const confirmBtnStyle: React.CSSProperties = {
  padding: '8px 24px',
  background: BLUE,
  color: '#fff',
  border: 'none',
  borderRadius: 20,
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
};

function Section({
  title,
  required,
  children,
}: {
  title: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 13, color: '#374151', fontWeight: 600, marginBottom: 6 }}>
        {title}
        {required && <span style={{ color: '#EF4444', marginLeft: 4 }}>*</span>}
      </div>
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
        padding: '8px 18px',
        borderRadius: 20,
        background: active ? BLUE : '#F3F4F6',
        color: active ? '#fff' : '#374151',
        border: 'none',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  );
}

function FreqCard({
  n,
  active,
  onClick,
}: {
  n: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      data-testid={`med-form-freq-card-${n}`}
      style={{
        flex: 1,
        padding: '12px 0',
        borderRadius: 8,
        background: active ? BLUE : '#F3F4F6',
        color: active ? '#fff' : '#374151',
        border: 'none',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
        textAlign: 'center',
      }}
    >
      {n}次/天
    </button>
  );
}

function TimeCard({
  time,
  onClick,
  testid,
}: {
  time: string;
  onClick: () => void;
  testid?: string;
}) {
  return (
    <button
      onClick={onClick}
      data-testid={testid}
      style={{
        minWidth: 76,
        padding: '14px 16px',
        borderRadius: 10,
        background: '#F3F4F6',
        color: '#111827',
        border: 'none',
        fontSize: 18,
        fontWeight: 600,
        cursor: 'pointer',
        flex: '0 0 auto',
      }}
    >
      {time}
    </button>
  );
}

// 底部抽屉容器
function BottomDrawer({
  onClose,
  title,
  children,
}: {
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
      data-testid="med-form-bottom-drawer"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          width: '100%',
          maxWidth: 600,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: 20,
          maxHeight: '80vh',
          overflowY: 'auto',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 700, color: '#111827' }}>{title}</div>
          <button
            onClick={onClose}
            style={{
              border: 'none',
              background: 'transparent',
              fontSize: 20,
              cursor: 'pointer',
              color: SUB,
            }}
            aria-label="close"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// 单列滚轮（简化实现：可滚动列表 + 高亮中间项）
function WheelColumn({
  items,
  value,
  onChange,
  testid,
  suffix,
}: {
  items: string[];
  value: string;
  onChange: (v: string) => void;
  testid?: string;
  suffix?: string;
}) {
  const ITEM_H = 40;
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const idx = items.indexOf(value);
    if (idx >= 0) {
      ref.current.scrollTop = idx * ITEM_H;
    }
  }, [value, items]);

  const handleScroll = () => {
    if (!ref.current) return;
    const top = ref.current.scrollTop;
    const idx = Math.round(top / ITEM_H);
    const next = items[Math.max(0, Math.min(items.length - 1, idx))];
    if (next !== value) onChange(next);
  };

  return (
    <div
      style={{
        flex: 1,
        position: 'relative',
        height: ITEM_H * 5,
        background: '#FAFAFA',
        borderRadius: 8,
        overflow: 'hidden',
      }}
      data-testid={testid}
    >
      {/* 中间高亮条 */}
      <div
        style={{
          position: 'absolute',
          top: ITEM_H * 2,
          left: 0,
          right: 0,
          height: ITEM_H,
          background: 'rgba(74,158,224,0.08)',
          borderTop: '1px solid #E5E7EB',
          borderBottom: '1px solid #E5E7EB',
          pointerEvents: 'none',
        }}
      />
      <div
        ref={ref}
        onScroll={handleScroll}
        style={{
          height: '100%',
          overflowY: 'auto',
          scrollSnapType: 'y mandatory',
          paddingTop: ITEM_H * 2,
          paddingBottom: ITEM_H * 2,
          boxSizing: 'border-box',
        }}
      >
        {items.map((it) => (
          <div
            key={it}
            onClick={() => onChange(it)}
            style={{
              height: ITEM_H,
              lineHeight: `${ITEM_H}px`,
              textAlign: 'center',
              fontSize: 16,
              color: it === value ? '#111827' : '#9CA3AF',
              fontWeight: it === value ? 700 : 400,
              scrollSnapAlign: 'center',
              cursor: 'pointer',
            }}
          >
            {it}
            {suffix || ''}
          </div>
        ))}
      </div>
    </div>
  );
}

// 时:分滚轮
function TimePickerDrawer({
  value,
  onConfirm,
  onCancel,
}: {
  value: string;
  onConfirm: (v: string) => void;
  onCancel: () => void;
}) {
  const [hh, setHh] = useState(value.split(':')[0] || '08');
  const [mm, setMm] = useState(value.split(':')[1] || '00');
  const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
  const minutes = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));
  return (
    <BottomDrawer onClose={onCancel} title="选择时间">
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <WheelColumn
          testid="med-form-time-hh"
          items={hours}
          value={hh}
          onChange={setHh}
        />
        <span style={{ fontSize: 20, fontWeight: 700 }}>:</span>
        <WheelColumn
          testid="med-form-time-mm"
          items={minutes}
          value={mm}
          onChange={setMm}
        />
      </div>
      <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button
          onClick={onCancel}
          style={{
            padding: '8px 18px',
            background: '#fff',
            color: '#374151',
            border: '1px solid #D1D5DB',
            borderRadius: 20,
            fontSize: 14,
            cursor: 'pointer',
          }}
          data-testid="med-form-time-cancel"
        >
          取消
        </button>
        <button
          onClick={() => {
            if (hh && mm) onConfirm(`${hh}:${mm}`);
          }}
          style={confirmBtnStyle}
          data-testid="med-form-time-ok"
        >
          确定
        </button>
      </div>
    </BottomDrawer>
  );
}
