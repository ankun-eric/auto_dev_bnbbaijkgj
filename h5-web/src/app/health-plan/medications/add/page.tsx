'use client';

/**
 * [PRD-469 v2 P0 M4] 添加用药提醒页（重做）
 * 关键新增字段：
 * - 每日次数（1-6 次）
 * - 自定义时间点（增删任意时间）
 * - 开始/结束日期（含「长期服用」开关）
 * - 提醒开关（默认开启）
 * - 关联疾病标签（多选）
 * - 拍照识药入口（调用 /api/ocr/recognize → /api/prd469/medication-library/ocr）
 */

import { Suspense, useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Form, Input, Button, Toast, SpinLoading, TextArea, Picker, Switch } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface DrugLibItem {
  id: number;
  name: string;
  generic_name?: string;
  spec?: string;
  manufacturer?: string;
  category?: string;
  rx_type?: string;
  disease_tags?: string[];
}

const DISEASE_PRESETS = ['高血压', '糖尿病', '高血脂', '冠心病', '脑卒中', '慢阻肺', '哮喘', '慢性肾病', '甲状腺', '痛风', '关节炎', '骨质疏松'];

const FREQ_OPTIONS = [1, 2, 3, 4, 5, 6];

const TIME_HOUR_COL = Array.from({ length: 24 }, (_, i) => {
  const v = String(i).padStart(2, '0');
  return { label: v, value: v };
});
const TIME_MINUTE_COL = Array.from({ length: 60 }, (_, i) => {
  const v = String(i).padStart(2, '0');
  return { label: v, value: v };
});
const TIME_PICKER_COLUMNS = [TIME_HOUR_COL, TIME_MINUTE_COL];

const PERIOD_DEFAULTS: Record<number, string[]> = {
  1: ['08:00'],
  2: ['08:00', '20:00'],
  3: ['08:00', '12:30', '20:00'],
  4: ['08:00', '12:30', '18:00', '22:00'],
  5: ['08:00', '11:00', '14:00', '18:00', '22:00'],
  6: ['07:00', '10:00', '13:00', '16:00', '19:00', '22:00'],
};

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function MedicationAddPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><SpinLoading color="primary" /></div>}>
      <MedicationAddContent />
    </Suspense>
  );
}

function MedicationAddContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get('id');
  const isEdit = !!editId;

  const [fetching, setFetching] = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [dosage, setDosage] = useState('');
  const [note, setNote] = useState('');

  // P0 新字段
  const [frequency, setFrequency] = useState<number>(1);
  const [customTimes, setCustomTimes] = useState<string[]>(['08:00']);
  const [startDate, setStartDate] = useState<string>(todayStr());
  const [endDate, setEndDate] = useState<string>('');
  const [longTerm, setLongTerm] = useState<boolean>(false);
  const [reminderEnabled, setReminderEnabled] = useState<boolean>(true);
  const [diseaseTags, setDiseaseTags] = useState<string[]>([]);
  const [customDisease, setCustomDisease] = useState<string>('');

  const [drugSuggestions, setDrugSuggestions] = useState<DrugLibItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedDrugMeta, setSelectedDrugMeta] = useState<DrugLibItem | null>(null);
  const searchTimer = useRef<any>(null);

  const [timePickerIdx, setTimePickerIdx] = useState<number | null>(null);

  const fileRef = useRef<HTMLInputElement | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);

  useEffect(() => {
    if (!editId) return;
    const fetchMed = async () => {
      try {
        const res: any = await api.get(`/api/health-plan/medications/${editId}`);
        const d = res.data || res;
        setName(d.medicine_name || '');
        setDosage(d.dosage || '');
        setNote(d.notes || '');
        if (Array.isArray(d.custom_times) && d.custom_times.length > 0) {
          setCustomTimes(d.custom_times);
          setFrequency(d.frequency_per_day || d.custom_times.length);
        } else if (d.remind_time) {
          setCustomTimes([d.remind_time]);
          setFrequency(d.frequency_per_day || 1);
        }
        if (d.start_date) setStartDate(d.start_date);
        if (d.end_date) setEndDate(d.end_date);
        if (typeof d.long_term === 'boolean') setLongTerm(d.long_term);
        if (typeof d.reminder_enabled === 'boolean') setReminderEnabled(d.reminder_enabled);
        if (Array.isArray(d.disease_tags)) setDiseaseTags(d.disease_tags);
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setFetching(false);
      }
    };
    fetchMed();
  }, [editId]);

  const handleFreqChange = (n: number) => {
    setFrequency(n);
    if (customTimes.length === 0 || customTimes.length !== n) {
      setCustomTimes(PERIOD_DEFAULTS[n] || Array(n).fill('08:00'));
    }
  };

  const updateTimeAt = (idx: number, val: string) => {
    setCustomTimes((prev) => prev.map((t, i) => (i === idx ? val : t)));
  };

  const addCustomTime = () => {
    if (customTimes.length >= 6) {
      Toast.show({ content: '最多 6 个时间点', icon: 'fail' });
      return;
    }
    setCustomTimes([...customTimes, '08:00']);
    setFrequency(customTimes.length + 1);
  };

  const removeCustomTime = (idx: number) => {
    if (customTimes.length <= 1) {
      Toast.show({ content: '至少保留 1 个时间点', icon: 'fail' });
      return;
    }
    const next = customTimes.filter((_, i) => i !== idx);
    setCustomTimes(next);
    setFrequency(next.length);
  };

  const handleNameChange = (val: string) => {
    setName(val);
    setSelectedDrugMeta(null);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (!val.trim() || val.trim().length < 2) {
      setDrugSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    searchTimer.current = setTimeout(async () => {
      try {
        const res: any = await api.get(`/api/prd469/medication-library/search?kw=${encodeURIComponent(val.trim())}&limit=8`);
        const data = res.data || res;
        const items: DrugLibItem[] = Array.isArray(data.items) ? data.items : [];
        setDrugSuggestions(items);
        setShowSuggestions(items.length > 0);
      } catch {
        setDrugSuggestions([]);
        setShowSuggestions(false);
      }
    }, 300);
  };

  const pickDrug = (drug: DrugLibItem) => {
    setName(drug.name);
    setSelectedDrugMeta(drug);
    setShowSuggestions(false);
    // 自动填充关联疾病标签
    if (drug.disease_tags && drug.disease_tags.length > 0) {
      const merged = Array.from(new Set([...diseaseTags, ...drug.disease_tags]));
      setDiseaseTags(merged);
    }
  };

  const toggleDisease = (d: string) => {
    setDiseaseTags((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]));
  };

  const addCustomDisease = () => {
    const d = customDisease.trim();
    if (!d) return;
    if (!diseaseTags.includes(d)) setDiseaseTags([...diseaseTags, d]);
    setCustomDisease('');
  };

  const handleOcr = async (file: File) => {
    setOcrLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      // 1) 通用 OCR 识别图片
      const ocrRes: any = await api.post('/api/ocr/recognize', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const ocrData = ocrRes?.data || ocrRes;
      const text = ocrData?.text || ocrData?.ocr_text || '';
      if (!text) {
        Toast.show({ content: 'OCR 未识别到内容', icon: 'fail' });
        return;
      }
      // 2) 在药品库做匹配
      const matchRes: any = await api.post('/api/prd469/medication-library/ocr', { image_text: text });
      const items: DrugLibItem[] = (matchRes?.data?.items) || matchRes?.items || [];
      if (items.length === 0) {
        Toast.show({ content: '未在药品库匹配到药品', icon: 'fail' });
        return;
      }
      pickDrug(items[0]);
      Toast.show({ content: `识别到「${items[0].name}」`, icon: 'success' });
    } catch (e) {
      Toast.show({ content: '识别失败', icon: 'fail' });
    } finally {
      setOcrLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      Toast.show({ content: '请输入药品名称', icon: 'fail' });
      return;
    }
    if (customTimes.length === 0) {
      Toast.show({ content: '请至少设置 1 个用药时间点', icon: 'fail' });
      return;
    }

    setSubmitting(true);
    try {
      const payload: any = {
        medicine_name: name.trim(),
        dosage: dosage.trim(),
        notes: note.trim(),
        time_period: '',
        remind_time: customTimes[0] || '',
        frequency_per_day: frequency,
        custom_times: customTimes,
        start_date: startDate || undefined,
        end_date: longTerm ? undefined : (endDate || undefined),
        long_term: longTerm,
        reminder_enabled: reminderEnabled,
        disease_tags: diseaseTags,
      };

      if (isEdit) {
        await api.put(`/api/health-plan/medications/${editId}`, payload);
        Toast.show({ content: '修改成功', icon: 'success' });
      } else {
        await api.post('/api/health-plan/medications', payload);
        Toast.show({ content: '添加成功', icon: 'success' });
      }
      try {
        sessionStorage.setItem('medication_changed', String(Date.now()));
      } catch {
        /* 忽略 */
      }
      router.back();
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    } finally {
      setSubmitting(false);
    }
  };

  if (fetching) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>{isEdit ? '编辑用药提醒' : '添加用药提醒'}</GreenNavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-32" data-testid="prd469-med-add-page">
      <GreenNavBar>{isEdit ? '编辑用药提醒' : '添加用药提醒'}</GreenNavBar>

      <div className="px-4 pt-4 space-y-3">
        {/* 药品信息卡 */}
        <div className="bg-white rounded-xl p-4" style={{ borderLeft: '3px solid #22c55e' }}>
          <div className="text-base font-semibold text-gray-800 mb-3">药品信息</div>

          {/* 拍照识药入口 */}
          <button
            data-testid="prd469-ocr-btn"
            onClick={() => fileRef.current?.click()}
            disabled={ocrLoading}
            style={{
              width: '100%', padding: '10px 12px', borderRadius: 10,
              background: 'linear-gradient(135deg, #4ade80, #16a34a)', color: '#fff',
              border: 'none', fontSize: 14, fontWeight: 600, marginBottom: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
          >
            {ocrLoading ? '识别中…' : '📷 拍照识药（OCR 自动识别药名）'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleOcr(f);
              e.target.value = '';
            }}
          />

          <Form layout="vertical">
            <Form.Item label={<><span style={{ color: 'red' }}>*</span> 药品名称（支持联想搜索）</>}>
              <div style={{ position: 'relative' }}>
                <Input
                  data-testid="prd469-input-medname"
                  placeholder="如：阿司匹林"
                  value={name}
                  onChange={handleNameChange}
                  clearable
                />
                {showSuggestions && drugSuggestions.length > 0 && (
                  <div
                    data-testid="prd469-drug-suggestions"
                    style={{
                      position: 'absolute', left: 0, right: 0, top: '100%', zIndex: 10,
                      background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
                      marginTop: 4, maxHeight: 240, overflowY: 'auto',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                    }}
                  >
                    {drugSuggestions.map((d) => (
                      <div
                        key={d.id}
                        onClick={() => pickDrug(d)}
                        style={{ padding: '10px 12px', cursor: 'pointer', borderBottom: '1px solid #f3f4f6' }}
                      >
                        <div style={{ fontSize: 14, fontWeight: 600, color: '#1f2937' }}>
                          {d.name}{d.generic_name && d.generic_name !== d.name ? `（${d.generic_name}）` : ''}
                        </div>
                        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                          {[d.spec, d.manufacturer, d.rx_type].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {selectedDrugMeta && (
                <div style={{ fontSize: 12, color: '#16a34a', marginTop: 6 }}>
                  ✓ 已从药品库选择：{selectedDrugMeta.rx_type ? `[${selectedDrugMeta.rx_type}] ` : ''}
                  {(selectedDrugMeta.disease_tags || []).join('、')}
                </div>
              )}
            </Form.Item>

            <Form.Item label="用药剂量">
              <Input placeholder="如：1片、2粒、5ml" value={dosage} onChange={setDosage} clearable />
            </Form.Item>

            <Form.Item label="备注">
              <TextArea placeholder="如：饭后服用、需空腹" value={note} onChange={setNote} rows={2} maxLength={200} showCount />
            </Form.Item>
          </Form>
        </div>

        {/* 每日次数 + 自定义时间点 */}
        <div className="bg-white rounded-xl p-4" style={{ borderLeft: '3px solid #22c55e' }}>
          <div className="text-base font-semibold text-gray-800 mb-2">
            <span style={{ color: 'red' }}>*</span> 每日次数
          </div>
          <div className="flex gap-2 mb-4 flex-wrap" data-testid="prd469-frequency-row">
            {FREQ_OPTIONS.map((n) => {
              const active = frequency === n;
              return (
                <button
                  key={n}
                  data-testid={`prd469-freq-${n}`}
                  onClick={() => handleFreqChange(n)}
                  style={{
                    minWidth: 56, padding: '8px 14px', borderRadius: 18,
                    background: active ? '#22c55e' : '#f3f4f6',
                    color: active ? '#fff' : '#374151',
                    border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >{n} 次</button>
              );
            })}
          </div>

          <div className="text-sm font-semibold text-gray-700 mb-2 flex items-center justify-between">
            <span>提醒时间点</span>
            <button
              data-testid="prd469-add-time"
              onClick={addCustomTime}
              style={{
                padding: '4px 10px', borderRadius: 12, background: '#dcfce7', color: '#16a34a',
                border: 'none', fontSize: 12, fontWeight: 600,
              }}
            >+ 添加时间</button>
          </div>
          <div className="space-y-2">
            {customTimes.map((t, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 p-2 rounded-lg"
                style={{ background: '#f9fafb' }}
              >
                <span className="text-sm text-gray-500" style={{ width: 50 }}>第{idx + 1}次</span>
                <button
                  data-testid={`prd469-time-${idx}`}
                  onClick={() => setTimePickerIdx(idx)}
                  style={{
                    flex: 1, padding: '8px 12px', borderRadius: 8,
                    background: '#fff', border: '1px solid #d1d5db',
                    fontSize: 14, color: '#1f2937', textAlign: 'left',
                  }}
                >{t}</button>
                {customTimes.length > 1 && (
                  <button
                    onClick={() => removeCustomTime(idx)}
                    style={{
                      padding: '4px 10px', borderRadius: 8, background: '#fee2e2', color: '#dc2626',
                      border: 'none', fontSize: 12,
                    }}
                  >删除</button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 用药日期 */}
        <div className="bg-white rounded-xl p-4" style={{ borderLeft: '3px solid #22c55e' }}>
          <div className="text-base font-semibold text-gray-800 mb-3">用药周期</div>

          <div className="mb-3">
            <div className="text-sm text-gray-500 mb-1">开始日期</div>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              data-testid="prd469-start-date"
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14, boxSizing: 'border-box' }}
            />
          </div>

          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-700">长期服用（无截止日）</span>
            <Switch
              data-testid="prd469-long-term"
              checked={longTerm}
              onChange={setLongTerm}
              style={{ '--checked-color': '#22c55e' } as React.CSSProperties}
            />
          </div>

          {!longTerm && (
            <div>
              <div className="text-sm text-gray-500 mb-1">结束日期</div>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                data-testid="prd469-end-date"
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14, boxSizing: 'border-box' }}
              />
            </div>
          )}
        </div>

        {/* 提醒开关 */}
        <div className="bg-white rounded-xl p-4 flex items-center justify-between" style={{ borderLeft: '3px solid #22c55e' }}>
          <div>
            <div className="text-base font-semibold text-gray-800">🔔 服药提醒</div>
            <div className="text-xs text-gray-500 mt-1">按设置的时间点推送站内/微信提醒</div>
          </div>
          <Switch
            data-testid="prd469-reminder-switch"
            checked={reminderEnabled}
            onChange={setReminderEnabled}
            style={{ '--checked-color': '#22c55e' } as React.CSSProperties}
          />
        </div>

        {/* 关联疾病 */}
        <div className="bg-white rounded-xl p-4" style={{ borderLeft: '3px solid #22c55e' }}>
          <div className="text-base font-semibold text-gray-800 mb-2">关联疾病（多选）</div>
          <div className="text-xs text-gray-500 mb-3">
            标记此药用于治疗哪些疾病，便于在病历卡 / 健康事件中关联展示
          </div>
          <div className="flex gap-2 flex-wrap mb-3" data-testid="prd469-disease-tags">
            {DISEASE_PRESETS.map((d) => {
              const active = diseaseTags.includes(d);
              return (
                <button
                  key={d}
                  data-testid={`prd469-disease-${d}`}
                  onClick={() => toggleDisease(d)}
                  style={{
                    padding: '6px 12px', borderRadius: 14,
                    background: active ? '#22c55e' : '#f3f4f6',
                    color: active ? '#fff' : '#374151',
                    border: 'none', fontSize: 13, cursor: 'pointer',
                  }}
                >{d}</button>
              );
            })}
          </div>
          {/* 自定义疾病 */}
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="自定义疾病名"
              value={customDisease}
              onChange={(e) => setCustomDisease(e.target.value)}
              style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13 }}
            />
            <button
              onClick={addCustomDisease}
              style={{ padding: '8px 14px', borderRadius: 8, background: '#22c55e', color: '#fff', border: 'none', fontSize: 13 }}
            >添加</button>
          </div>
          {diseaseTags.length > 0 && (
            <div className="mt-3 flex gap-2 flex-wrap">
              {diseaseTags.filter((d) => !DISEASE_PRESETS.includes(d)).map((d) => (
                <span
                  key={d}
                  style={{ padding: '4px 10px', borderRadius: 12, background: '#dcfce7', color: '#166534', fontSize: 12 }}
                >
                  {d}
                  <span
                    onClick={() => toggleDisease(d)}
                    style={{ marginLeft: 6, cursor: 'pointer', color: '#9ca3af' }}
                  >×</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 时间选择器 */}
      <Picker
        columns={TIME_PICKER_COLUMNS}
        visible={timePickerIdx !== null}
        title="选择提醒时间"
        value={
          timePickerIdx !== null
            ? (() => {
                const [h = '08', m = '00'] = (customTimes[timePickerIdx] || '08:00').split(':');
                return [h.padStart(2, '0'), m.padStart(2, '0')];
              })()
            : undefined
        }
        onClose={() => setTimePickerIdx(null)}
        onCancel={() => setTimePickerIdx(null)}
        onConfirm={(val) => {
          if (timePickerIdx !== null) {
            const [h, m] = val as string[];
            updateTimeAt(timePickerIdx, `${h}:${m}`);
          }
          setTimePickerIdx(null);
        }}
      />

      {/* 底部保存按钮 */}
      <div
        className="fixed bottom-0 left-0 right-0 p-4 bg-white"
        style={{
          maxWidth: 750,
          margin: '0 auto',
          boxShadow: '0 -2px 8px rgba(0,0,0,0.06)',
          paddingBottom: 'calc(16px + env(safe-area-inset-bottom))',
        }}
      >
        <Button
          block
          color="primary"
          size="large"
          loading={submitting}
          data-testid="prd469-save-medication"
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #4ade80, #16a34a)', border: 'none', height: 48 }}
          onClick={handleSubmit}
        >
          {isEdit ? '保存修改' : '添加用药提醒'}
        </Button>
      </div>
    </div>
  );
}
