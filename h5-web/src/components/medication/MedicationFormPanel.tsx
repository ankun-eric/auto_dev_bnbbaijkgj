'use client';

/**
 * [PRD-MED-PLAN-OPTIM-V1 2026-05-17] 用药计划表单（终版）
 *
 * 主色统一：#0EA5E9（替换原 #4A9EE0）
 * 顶部医嘱提示条常驻
 * 全字段统一为"标题+值同行"列表行样式
 * 服用周期：开始日期 + 结束日期 + 长期开关三字段；表单页双行展示
 * 服用时机：5 标签 Tag-B 视觉单选（饭前/饭后/空腹/随餐/睡前）
 * 备注：单行 30 字
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Dialog } from 'antd-mobile';
import api from '@/lib/api';
import MedicalAdviceTip from './MedicalAdviceTip';
import CycleDrawer, { CycleValue } from './CycleDrawer';
// [BUG-MED-V1 2026-05-21 Bug1-附] 删除后通知铃铛/今日用药胶囊/Hero 刷新
import { publishBellEvent } from '@/lib/bell-event-bus';

const DOSAGE_VALUES = [
  '¼', '½', '1', '2', '3', '4', '5', '6', '8', '10',
];
const DOSAGE_UNITS = ['片', '粒', 'mL', '滴', '袋', '支', '包', '瓶'];

const TIMING_OPTIONS = ['饭前', '饭后', '空腹', '随餐', '睡前'];

const FREQ_DEFAULTS: Record<number, string[]> = {
  1: ['08:00'],
  2: ['08:00', '20:00'],
  3: ['08:00', '14:00', '20:00'],
  4: ['08:00', '12:00', '16:00', '20:00'],
};

// [PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18] 备注全端统一 200 字
const NOTES_MAX = 200;

const PRIMARY = '#0EA5E9';
const TEXT = '#1F2937';
const SUB = '#6B7280';
const TAG_BG = '#E0F2FE';
const TAG_TEXT = PRIMARY;
const DIVIDER = '#E5E7EB';

// ────────────────── 工具 ──────────────────

function today(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}
function toISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function parseISO(s: string | null | undefined): Date | null {
  if (!s) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  d.setHours(0, 0, 0, 0);
  return d;
}
function diffDays(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / 86400000) + 1;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d.getTime());
  r.setDate(r.getDate() + n);
  return r;
}
function dosageForBackend(v: string): string {
  if (v === '¼') return '1/4';
  if (v === '½') return '1/2';
  return v;
}
function dosageForUI(v?: string | null): string {
  if (!v) return '1';
  if (v === '1/4') return '¼';
  if (v === '1/2') return '½';
  return v;
}

/**
 * [PRD-MED-PLAN-OPTIM-V1 F-07-1] 服用时机老数据迁移映射兜底
 * 旧枚举值（小程序老版/早期 H5）→ 新枚举
 */
function migrateTiming(raw?: string | null): string {
  if (!raw) return '';
  const map: Record<string, string> = {
    '早上': '饭前',
    '中午': '饭后',
    '下午': '饭后',
    '晚上': '饭后',
    '睡前': '睡前',
    morning: '饭前',
    noon: '饭后',
    afternoon: '饭后',
    evening: '饭后',
    bedtime: '睡前',
  };
  if (TIMING_OPTIONS.includes(raw)) return raw;
  return map[raw] || raw;
}

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
  custom_times: string[];
  guidance: string;
  startDate: string;       // YYYY-MM-DD
  endDate: string | null;  // null = 长期
  isLongTerm: boolean;
  notes: string;
}

/**
 * [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18]
 * 新增可选 props 支撑「抽屉模式」（AI 对话识药结果加入用药计划）：
 *   - mode='drawer' 时不调用 router.back()，改为调用 onSaved/onCancel
 *   - prefillName: 识药结果药品名自动预填
 *   - prefillGenericName: 识药通用名
 *   - familyMemberId: 咨询人 ID（None=本人）
 *   - hideDelete: 抽屉模式下不显示删除按钮
 */
export interface MedicationFormPanelProps {
  planId?: number;
  mode?: 'page' | 'drawer';
  prefillName?: string;
  prefillGenericName?: string;
  familyMemberId?: number | null;
  hideDelete?: boolean;
  onSaved?: (newId: number | null) => void;
  onCancel?: () => void;
}

export default function MedicationFormPanel(props: MedicationFormPanelProps) {
  const {
    planId,
    mode = 'page',
    prefillName,
    prefillGenericName,
    familyMemberId,
    hideDelete = false,
    onSaved,
    onCancel,
  } = props;
  const router = useRouter();
  const editing = !!planId;
  const isDrawer = mode === 'drawer';

  const [form, setForm] = useState<FormState>(() => {
    const t = today();
    return {
      medicine_name: prefillName || '',
      dosage_value: '1',
      dosage_unit: '片',
      frequency_per_day: 2,
      custom_times: [...FREQ_DEFAULTS[2]],
      guidance: '',
      startDate: toISO(t),
      endDate: toISO(addDays(t, 4)),
      isLongTerm: false,
      notes: '',
    };
  });
  const [submitting, setSubmitting] = useState(false);
  const [loaded, setLoaded] = useState(!editing);

  const [suggests, setSuggests] = useState<SuggestItem[]>([]);
  const [showSuggest, setShowSuggest] = useState(false);
  const suggestTimer = useRef<any>(null);

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');

  const [timeDrawerOpen, setTimeDrawerOpen] = useState(false);
  const [dosageDrawerOpen, setDosageDrawerOpen] = useState(false);
  const [cycleDrawerOpen, setCycleDrawerOpen] = useState(false);
  const [notesDrawerOpen, setNotesDrawerOpen] = useState(false);
  const [timePickerIdx, setTimePickerIdx] = useState<number | null>(null);

  // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.2] 必填字段错误集合，
  // key ∈ {'name','time','dosage','cycle','timing'}；保存校验失败 → 设置；
  // 用户点击 / 修改对应字段 → 立即从集合中移除。
  const [errFields, setErrFields] = useState<Set<string>>(new Set());
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const clearErr = (k: string) => {
    setErrFields((prev) => {
      if (!prev.has(k)) return prev;
      const next = new Set(prev);
      next.delete(k);
      return next;
    });
  };

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
          : [...(FREQ_DEFAULTS[Math.min(Math.max(freq, 1), 4)] || ['08:00'])];
        while (times.length < freq) times.push('08:00');
        const isLT = !!d.long_term;
        const startStr = d.start_date || toISO(today());
        const endStr = isLT ? null : (d.end_date || null);
        setForm({
          medicine_name: d.medicine_name || '',
          dosage_value: dosageForUI(d.dosage_value),
          dosage_unit: d.dosage_unit || '片',
          frequency_per_day: freq,
          custom_times: times,
          guidance: migrateTiming(d.guidance),
          startDate: startStr,
          endDate: endStr,
          isLongTerm: isLT,
          notes: (d.notes || '').slice(0, NOTES_MAX),
        });
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setLoaded(true);
      }
    })();
  }, [editing, planId]);

  const triggerSuggest = (q: string) => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    if (!q || q.trim().length < 2) {
      setSuggests([]);
      setShowSuggest(false);
      return;
    }
    suggestTimer.current = setTimeout(async () => {
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
      }
    }, 250);
  };

  const handleChangeFreq = (n: number) => {
    setForm((prev) => {
      const def = FREQ_DEFAULTS[n] || ['08:00'];
      return { ...prev, frequency_per_day: n, custom_times: [...def] };
    });
  };

  // ───── 服用周期展示（双行）─────
  const cycleDisplay = useMemo(() => {
    if (form.isLongTerm) {
      return {
        main: `${form.startDate} 至 长期`,
        sub: '长期服用',
        subColor: PRIMARY,
        subWeight: 500,
      };
    }
    const s = parseISO(form.startDate);
    const e = parseISO(form.endDate);
    return {
      main: `${form.startDate || '—'} 至 ${form.endDate || '—'}`,
      sub: s && e ? `共 ${diffDays(s, e)} 天` : '—',
      subColor: SUB,
      subWeight: 400,
    };
  }, [form.startDate, form.endDate, form.isLongTerm]);

  // ───── 保存 ─────
  // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.2]
  // 校验必填字段，返回未通过的字段 key 列表；同时把列表写入 errFields，
  // 滚动定位到第一个未通过字段（顶部 padding 80px 避免被吸顶元素遮挡）。
  const validateRequired = (): string[] => {
    const errs: string[] = [];
    if (!form.medicine_name.trim()) errs.push('name');
    if (
      !form.frequency_per_day ||
      form.custom_times.length !== form.frequency_per_day ||
      form.custom_times.some((t) => !t)
    ) {
      errs.push('time');
    }
    if (!form.dosage_value || !form.dosage_unit) errs.push('dosage');
    if (!form.startDate) {
      errs.push('cycle');
    } else if (!form.isLongTerm) {
      const s = parseISO(form.startDate);
      const e = parseISO(form.endDate);
      if (!e) errs.push('cycle');
      else if (s && e.getTime() < s.getTime()) errs.push('cycle');
    }
    if (!form.guidance) errs.push('timing');
    setErrFields(new Set(errs));
    if (errs.length > 0) {
      const first = errs[0];
      const el = rowRefs.current[first];
      if (el && typeof el.scrollIntoView === 'function') {
        try {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch {
          // 兼容旧 WebView
          el.scrollIntoView();
        }
      }
    }
    return errs;
  };

  const handleSubmit = async () => {
    const errs = validateRequired();
    if (errs.length > 0) {
      Toast.show({ content: '请填写带 * 号的必填项' });
      return;
    }

    // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.3] 新增模式下，先调用 check-duplicate
    // 命中已存在 → 弹窗「该药已加入用药计划，是否重新编辑？」
    if (!editing) {
      try {
        const dupRes: any = await api.post(
          '/api/health-plan/medications/check-duplicate',
          {
            drug_name: form.medicine_name.trim(),
            taker_id:
              familyMemberId !== undefined && familyMemberId !== null && familyMemberId > 0
                ? familyMemberId
                : 0,
          },
        );
        const dupData = dupRes?.data?.data || dupRes?.data || dupRes;
        if (dupData && dupData.exists && dupData.plan_id) {
          const ok = await Dialog.confirm({
            title: '提示',
            content: '该药已加入用药计划,是否重新编辑?',
            confirmText: '确定',
            cancelText: '取消',
          });
          if (!ok) {
            return;
          }
          if (isDrawer) {
            // 抽屉模式下：把 newId 回吐给上层，让上层切换为「打开编辑用药抽屉」
            onSaved?.(dupData.plan_id);
            return;
          }
          // 页面模式：跳转编辑页（采用 router.push）
          try {
            router.push(`/ai-home/medication-plans/${dupData.plan_id}/edit`);
          } catch {
            // 退化方案
            window.location.href = `/ai-home/medication-plans/${dupData.plan_id}/edit`;
          }
          return;
        }
      } catch {
        // check-duplicate 失败不阻塞保存，由后端 409 兜底
      }
    }

    setSubmitting(true);
    try {
      const dvBackend = dosageForBackend(form.dosage_value);
      const s = parseISO(form.startDate);
      const e = parseISO(form.endDate);
      const duration = form.isLongTerm || !s || !e ? null : diffDays(s, e);
      const payload: any = {
        medicine_name: form.medicine_name.trim(),
        dosage: `${dvBackend} ${form.dosage_unit}`,
        dosage_value: dvBackend,
        dosage_unit: form.dosage_unit,
        frequency_per_day: form.frequency_per_day,
        custom_times: form.custom_times,
        remind_time: form.custom_times[0] || '08:00',
        time_period: 'custom',
        start_date: form.startDate,
        end_date: form.isLongTerm ? null : form.endDate,
        duration_days: duration,
        long_term: form.isLongTerm,
        guidance: form.guidance,
        notes: form.notes || '',
        reminder_enabled: true,
      };
      // [PRD-AI-DRUG-CARD-MEDPLAN-V1] 抽屉模式带咨询人 + 通用名
      if (familyMemberId !== undefined && familyMemberId !== null && familyMemberId > 0) {
        payload.family_member_id = familyMemberId;
      }
      if (prefillGenericName) {
        payload.generic_name = prefillGenericName;
      }
      let newId: number | null = null;
      if (editing) {
        await api.put(`/api/health-plan/medications/${planId}`, payload);
        newId = planId || null;
      } else {
        const res: any = await api.post('/api/health-plan/medications', payload);
        newId = (res?.data?.id ?? res?.id ?? null) as number | null;
      }
      Toast.show({ content: editing ? '保存成功' : '已加入用药计划', icon: 'success' });
      if (isDrawer) {
        onSaved?.(newId);
      } else {
        router.back();
      }
    } catch (err: any) {
      // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.3] 后端 409 兜底：弹「该药已加入用药计划，是否重新编辑？」
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      const isDup =
        status === 409 &&
        typeof detail === 'object' &&
        detail?.code === 'MEDICATION_DUPLICATE_ACTIVE';
      if (isDup && !editing) {
        const existingId: number | undefined = detail?.existing_id;
        const ok = await Dialog.confirm({
          title: '提示',
          content: '该药已加入用药计划,是否重新编辑?',
          confirmText: '确定',
          cancelText: '取消',
        });
        if (ok && existingId) {
          if (isDrawer) {
            onSaved?.(existingId);
          } else {
            try {
              router.push(`/ai-home/medication-plans/${existingId}/edit`);
            } catch {
              window.location.href = `/ai-home/medication-plans/${existingId}/edit`;
            }
          }
        }
      } else {
        const msg = typeof detail === 'object' ? detail?.message || JSON.stringify(detail) : detail || '保存失败';
        Toast.show({ content: msg, icon: 'fail' });
      }
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
      // [BUG-MED-V1 2026-05-21 Bug1-附] 通知铃铛/胶囊/Hero 立即刷新
      publishBellEvent('badge:refresh', { source: 'medication:plan:deleted', plan_id: planId });
      router.push('/ai-home/medication-plans');
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  if (!loaded) {
    return <div style={{ padding: 40, textAlign: 'center', color: SUB }}>加载中…</div>;
  }

  const timeDisplay = `每日 ${form.frequency_per_day} 次 · ${form.custom_times.join(' / ')}`;
  const dosageDisplay = `${form.dosage_value} ${form.dosage_unit}`;

  return (
    <div data-testid="med-form-panel" style={{ background: '#F4F6F9', minHeight: '100%' }}>
      <MedicalAdviceTip />

      {/* 表单卡片：标题+值同行 */}
      <div
        style={{
          background: '#fff',
          margin: '0 14px',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
        }}
      >
        {/* 药品名称 */}
        <Row
          title="药品名称"
          required
          hasError={errFields.has('name')}
          errMsg="请填写药品名称"
          rowRef={(el) => {
            rowRefs.current['name'] = el;
          }}
          onClick={() => {
            clearErr('name');
            setEditingName(true);
            setNameDraft(form.medicine_name);
          }}
          right={
            <span style={{ color: form.medicine_name ? TEXT : '#9CA3AF', fontSize: 14 }}>
              {form.medicine_name || '请输入药品名称'}
            </span>
          }
          testid="row-name"
        />

        {/* 用药时间 */}
        <Row
          title="用药时间"
          required
          hasError={errFields.has('time')}
          errMsg="请选择用药时间"
          rowRef={(el) => {
            rowRefs.current['time'] = el;
          }}
          onClick={() => {
            clearErr('time');
            setTimeDrawerOpen(true);
          }}
          right={
            <span style={{ color: TEXT, fontSize: 14 }} data-testid="value-time">
              {timeDisplay}
            </span>
          }
          testid="row-time"
        />

        {/* 每次剂量 */}
        <Row
          title="每次剂量"
          required
          hasError={errFields.has('dosage')}
          errMsg="请选择每次剂量"
          rowRef={(el) => {
            rowRefs.current['dosage'] = el;
          }}
          onClick={() => {
            clearErr('dosage');
            setDosageDrawerOpen(true);
          }}
          right={
            <span style={{ color: TEXT, fontSize: 14 }} data-testid="value-dosage">
              {dosageDisplay}
            </span>
          }
          testid="row-dosage"
        />

        {/* 服用周期：双行展示 */}
        <Row
          title="服用周期"
          required
          tall
          hasError={errFields.has('cycle')}
          errMsg="请选择服用周期"
          rowRef={(el) => {
            rowRefs.current['cycle'] = el;
          }}
          onClick={() => {
            clearErr('cycle');
            setCycleDrawerOpen(true);
          }}
          right={
            <div
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}
              data-testid="value-cycle"
            >
              <div style={{ fontSize: 14, color: TEXT, lineHeight: 1.25 }}>{cycleDisplay.main}</div>
              <div
                style={{
                  fontSize: 12,
                  color: cycleDisplay.subColor,
                  fontWeight: cycleDisplay.subWeight as any,
                  marginTop: 2,
                  lineHeight: 1.25,
                }}
              >
                {cycleDisplay.sub}
              </div>
            </div>
          }
          testid="row-cycle"
        />

        {/* 服用时机：Tag-B 单选 */}
        <Row
          title="服用时机"
          required
          tall
          hasError={errFields.has('timing')}
          errMsg="请选择服用时机"
          rowRef={(el) => {
            rowRefs.current['timing'] = el;
          }}
          right={
            <div
              style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'flex-end', maxWidth: '70%' }}
              data-testid="value-timing"
            >
              {TIMING_OPTIONS.map((t) => {
                const active = form.guidance === t;
                return (
                  <button
                    key={t}
                    data-testid={`timing-${t}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      clearErr('timing');
                      setForm({ ...form, guidance: t });
                    }}
                    style={{
                      padding: '6px 14px',
                      borderRadius: 16,
                      border: 'none',
                      background: active ? PRIMARY : TAG_BG,
                      color: active ? '#fff' : TAG_TEXT,
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    {t}
                  </button>
                );
              })}
            </div>
          }
          testid="row-timing"
          showArrow={false}
        />

        {/* 备注 */}
        <Row
          title="备注"
          onClick={() => setNotesDrawerOpen(true)}
          last
          right={
            <span style={{ color: form.notes ? TEXT : '#9CA3AF', fontSize: 14, maxWidth: 180, textAlign: 'right' }}>
              {form.notes || '可填补充说明'}
            </span>
          }
          testid="row-notes"
        />
      </div>

      {/* 保存按钮 */}
      <div style={{ padding: 16, display: 'flex', gap: 12 }}>
        {editing && !hideDelete && (
          <button
            data-testid="med-form-delete"
            onClick={handleDelete}
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
        {isDrawer && (
          <button
            data-testid="med-form-cancel"
            onClick={() => onCancel?.()}
            style={{
              flex: 1,
              padding: '12px 0',
              background: '#fff',
              color: '#374151',
              border: '1px solid #D1D5DB',
              borderRadius: 24,
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            取消
          </button>
        )}
        <button
          data-testid="med-form-submit"
          onClick={handleSubmit}
          disabled={submitting}
          style={{
            flex: 2,
            padding: '12px 0',
            background: PRIMARY,
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

      {/* 药品名输入抽屉 */}
      {editingName && (
        <BottomDrawer
          title="药品名称"
          onClose={() => {
            setEditingName(false);
            setShowSuggest(false);
          }}
        >
          <div style={{ position: 'relative' }}>
            <input
              data-testid="name-input"
              value={nameDraft}
              autoFocus
              onChange={(e) => {
                const v = e.target.value;
                setNameDraft(v);
                triggerSuggest(v);
              }}
              placeholder="请输入药品名称"
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #D1D5DB',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
            {showSuggest && suggests.length > 0 && (
              <div
                data-testid="name-suggest-list"
                style={{
                  marginTop: 8,
                  border: '1px solid #E5E7EB',
                  borderRadius: 8,
                  maxHeight: 220,
                  overflowY: 'auto',
                }}
              >
                {suggests.map((it) => (
                  <div
                    key={it.id}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setNameDraft(it.name);
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
          </div>
          <DrawerFooter
            onCancel={() => {
              setEditingName(false);
              setShowSuggest(false);
            }}
            onConfirm={() => {
              setForm({ ...form, medicine_name: nameDraft.trim() });
              if (nameDraft.trim()) clearErr('name');
              setEditingName(false);
              setShowSuggest(false);
            }}
          />
        </BottomDrawer>
      )}

      {/* 用药时间抽屉 */}
      {timeDrawerOpen && (
        <BottomDrawer title="用药时间" onClose={() => setTimeDrawerOpen(false)}>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: '#374151', fontWeight: 600, marginBottom: 8 }}>
              每日服药次数
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[1, 2, 3, 4].map((n) => {
                const active = form.frequency_per_day === n;
                return (
                  <button
                    key={n}
                    data-testid={`freq-${n}`}
                    onClick={() => handleChangeFreq(n)}
                    style={{
                      flex: 1,
                      padding: '10px 0',
                      borderRadius: 16,
                      border: 'none',
                      background: active ? PRIMARY : TAG_BG,
                      color: active ? '#fff' : PRIMARY,
                      fontSize: 14,
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    {n} 次
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#374151', fontWeight: 600, marginBottom: 8 }}>
              具体时间点
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {form.custom_times.map((t, idx) => (
                <div
                  key={idx}
                  onClick={() => setTimePickerIdx(idx)}
                  data-testid={`time-row-${idx}`}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 10,
                    background: '#F9FAFB',
                    border: '1px solid #E5E7EB',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ color: SUB, fontSize: 13 }}>第 {idx + 1} 次</span>
                  <span style={{ color: TEXT, fontSize: 16, fontWeight: 600 }}>{t}</span>
                </div>
              ))}
            </div>
          </div>
          <DrawerFooter
            onCancel={() => setTimeDrawerOpen(false)}
            onConfirm={() => setTimeDrawerOpen(false)}
          />
        </BottomDrawer>
      )}

      {/* 剂量抽屉 */}
      {dosageDrawerOpen && (
        <BottomDrawer title="每次剂量" onClose={() => setDosageDrawerOpen(false)}>
          <div style={{ display: 'flex', gap: 12 }}>
            <WheelColumn
              testid="dosage-value-wheel"
              items={DOSAGE_VALUES}
              value={form.dosage_value}
              onChange={(v) => setForm({ ...form, dosage_value: v })}
            />
            <WheelColumn
              testid="dosage-unit-wheel"
              items={DOSAGE_UNITS}
              value={form.dosage_unit}
              onChange={(v) => setForm({ ...form, dosage_unit: v })}
            />
          </div>
          <div style={{ textAlign: 'center', marginTop: 8, color: SUB, fontSize: 13 }}>
            每次 {form.dosage_value} {form.dosage_unit}
          </div>
          <DrawerFooter
            onCancel={() => setDosageDrawerOpen(false)}
            onConfirm={() => setDosageDrawerOpen(false)}
          />
        </BottomDrawer>
      )}

      {/* 服用周期抽屉 */}
      {cycleDrawerOpen && (
        <CycleDrawer
          value={{ startDate: form.startDate, endDate: form.endDate, isLongTerm: form.isLongTerm }}
          onCancel={() => setCycleDrawerOpen(false)}
          onConfirm={(v: CycleValue) => {
            setForm({ ...form, startDate: v.startDate, endDate: v.endDate, isLongTerm: v.isLongTerm });
            setCycleDrawerOpen(false);
          }}
        />
      )}

      {/* 备注抽屉 */}
      {notesDrawerOpen && (
        <NotesDrawer
          initial={form.notes}
          onCancel={() => setNotesDrawerOpen(false)}
          onConfirm={(v) => {
            setForm({ ...form, notes: v });
            setNotesDrawerOpen(false);
          }}
        />
      )}

      {/* 单时间点滚轮 */}
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

function Row({
  title,
  required,
  right,
  onClick,
  testid,
  showArrow = true,
  tall = false,
  last = false,
  hasError = false,
  errMsg,
  rowRef,
}: {
  title: string;
  required?: boolean;
  right: React.ReactNode;
  onClick?: () => void;
  testid?: string;
  showArrow?: boolean;
  tall?: boolean;
  last?: boolean;
  /** [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.2] 该行命中必填错误 → label 变红 + 下方红色错误提示 */
  hasError?: boolean;
  errMsg?: string;
  rowRef?: (el: HTMLDivElement | null) => void;
}) {
  return (
    <div
      ref={rowRef}
      data-testid={testid}
      data-haserror={hasError ? '1' : '0'}
      onClick={onClick}
      style={{
        padding: tall ? '12px 14px' : '12px 14px',
        minHeight: tall ? 56 : 48,
        borderBottom: last ? 'none' : `1px solid ${DIVIDER}`,
        cursor: onClick ? 'pointer' : 'default',
        background: '#fff',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', minHeight: tall ? 32 : 24 }}>
        <div
          style={{
            flexShrink: 0,
            fontSize: 14,
            color: hasError ? '#EF4444' : TEXT,
            fontWeight: 500,
            minWidth: 80,
          }}
        >
          {title}
          {required && <span style={{ color: '#EF4444', marginLeft: 2 }}>*</span>}
        </div>
        <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end', overflow: 'hidden' }}>{right}</div>
        {showArrow && <span style={{ marginLeft: 8, color: '#9CA3AF', fontSize: 16 }}>›</span>}
      </div>
      {hasError && errMsg && (
        <div
          data-testid={`${testid || 'row'}-error`}
          style={{ marginTop: 4, marginLeft: 0, fontSize: 12, color: '#EF4444', lineHeight: 1.5 }}
        >
          {errMsg}
        </div>
      )}
    </div>
  );
}

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
        background: 'rgba(0,0,0,0.4)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
      data-testid="bottom-drawer"
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
            textAlign: 'center',
            fontSize: 15,
            fontWeight: 600,
            color: '#111827',
            paddingBottom: 12,
            borderBottom: `1px solid ${DIVIDER}`,
            marginBottom: 16,
          }}
        >
          {title}
        </div>
        {children}
      </div>
    </div>
  );
}

function DrawerFooter({ onCancel, onConfirm }: { onCancel: () => void; onConfirm: () => void }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
      <button
        onClick={onCancel}
        data-testid="drawer-cancel"
        style={{
          flex: 1,
          height: 40,
          borderRadius: 8,
          border: '1px solid #E5E7EB',
          background: '#fff',
          color: '#6B7280',
          fontSize: 14,
          cursor: 'pointer',
        }}
      >
        取消
      </button>
      <button
        onClick={onConfirm}
        data-testid="drawer-confirm"
        style={{
          flex: 1,
          height: 40,
          borderRadius: 8,
          border: 'none',
          background: PRIMARY,
          color: '#fff',
          fontSize: 14,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        确定
      </button>
    </div>
  );
}

function NotesDrawer({
  initial,
  onConfirm,
  onCancel,
}: {
  initial: string;
  onConfirm: (v: string) => void;
  onCancel: () => void;
}) {
  const [val, setVal] = useState(initial);
  return (
    <BottomDrawer title="备注" onClose={onCancel}>
      <div style={{ position: 'relative' }}>
        {/* [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.4] 备注：多行 textarea，默认 3 行高度，
            最大 200 字，右下角字数计数器 */}
        <textarea
          data-testid="notes-input"
          autoFocus
          value={val}
          maxLength={NOTES_MAX}
          rows={3}
          onChange={(e) => setVal(e.target.value.slice(0, NOTES_MAX))}
          placeholder="可填补充说明"
          style={{
            width: '100%',
            padding: '10px 12px',
            paddingBottom: 28,
            borderRadius: 8,
            border: '1px solid #D1D5DB',
            fontSize: 14,
            lineHeight: 1.6,
            boxSizing: 'border-box',
            resize: 'none',
            fontFamily: 'inherit',
          }}
        />
        <span
          style={{
            position: 'absolute',
            right: 12,
            bottom: 8,
            color: SUB,
            fontSize: 12,
          }}
          data-testid="notes-count"
        >
          {val.length}/{NOTES_MAX}
        </span>
      </div>
      <DrawerFooter onCancel={onCancel} onConfirm={() => onConfirm(val.trim())} />
    </BottomDrawer>
  );
}

function WheelColumn({
  items,
  value,
  onChange,
  testid,
}: {
  items: string[];
  value: string;
  onChange: (v: string) => void;
  testid?: string;
}) {
  const ITEM_H = 40;
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const idx = items.indexOf(value);
    if (idx >= 0) ref.current.scrollTop = idx * ITEM_H;
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
      style={{ flex: 1, position: 'relative', height: ITEM_H * 5, background: '#FAFAFA', borderRadius: 8, overflow: 'hidden' }}
      data-testid={testid}
    >
      <div
        style={{
          position: 'absolute',
          top: ITEM_H * 2,
          left: 0,
          right: 0,
          height: ITEM_H,
          background: 'rgba(14,165,233,0.08)',
          borderTop: `1px solid ${DIVIDER}`,
          borderBottom: `1px solid ${DIVIDER}`,
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
          </div>
        ))}
      </div>
    </div>
  );
}

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
    <BottomDrawer title="选择时间" onClose={onCancel}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <WheelColumn testid="time-hh" items={hours} value={hh} onChange={setHh} />
        <span style={{ fontSize: 20, fontWeight: 700 }}>:</span>
        <WheelColumn testid="time-mm" items={minutes} value={mm} onChange={setMm} />
      </div>
      <DrawerFooter onCancel={onCancel} onConfirm={() => onConfirm(`${hh}:${mm}`)} />
    </BottomDrawer>
  );
}
