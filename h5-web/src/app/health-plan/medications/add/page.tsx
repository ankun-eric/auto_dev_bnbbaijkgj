'use client';

import { Suspense, useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Form, Input, Button, Checkbox, Toast, SpinLoading, TextArea, Picker, Switch, Mask } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import AiCallPanel, { AiCallDraft } from '@/components/medication/AiCallPanel';

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

const DISEASE_PRESETS = ['高血压', '糖尿病', '高血脂', '冠心病', '脑卒中', '哮喘', '慢阻肺', '痛风', '甲亢', '甲减'];

const TIME_HOUR_COL = Array.from({ length: 24 }, (_, i) => {
  const v = String(i).padStart(2, '0');
  return { label: v, value: v };
});
const TIME_MINUTE_COL = Array.from({ length: 60 }, (_, i) => {
  const v = String(i).padStart(2, '0');
  return { label: v, value: v };
});
const TIME_PICKER_COLUMNS = [TIME_HOUR_COL, TIME_MINUTE_COL];

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

  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [dosage, setDosage] = useState('');
  const [note, setNote] = useState('');
  const [drugSuggestions, setDrugSuggestions] = useState<DrugLibItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedDrugMeta, setSelectedDrugMeta] = useState<DrugLibItem | null>(null);
  const searchTimer = useRef<any>(null);

  const [dailyTimes, setDailyTimes] = useState(1);
  const [customTimes, setCustomTimes] = useState<string[]>(['08:00']);
  const [timePickerVisible, setTimePickerVisible] = useState<number | null>(null);
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [isLongTerm, setIsLongTerm] = useState(true);
  const [endDate, setEndDate] = useState('');
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [diseaseTags, setDiseaseTags] = useState<string[]>([]);
  const [customDisease, setCustomDisease] = useState('');
  // [PRD-HEALTH-OPT-V1 2026-05-14 R5] AI 外呼草稿
  const [aiCallDraft, setAiCallDraft] = useState<AiCallDraft>({
    ai_call_enabled: false,
    ai_call_dnd_start: '22:00',
    ai_call_dnd_end: '07:00',
  });

  useEffect(() => {
    if (dailyTimes > customTimes.length) {
      const newTimes = [...customTimes];
      while (newTimes.length < dailyTimes) {
        newTimes.push('08:00');
      }
      setCustomTimes(newTimes);
    } else if (dailyTimes < customTimes.length) {
      setCustomTimes(customTimes.slice(0, dailyTimes));
    }
  }, [dailyTimes]);

  useEffect(() => {
    if (!editId) return;
    const fetchMedication = async () => {
      try {
        const res: any = await api.get(`/api/health-plan/medications/${editId}`);
        const data = res.data || res;
        setName(data.medicine_name || '');
        setDosage(data.dosage || '');
        setNote(data.notes || '');
        if (data.custom_times && Array.isArray(data.custom_times) && data.custom_times.length > 0) {
          setCustomTimes(data.custom_times);
          setDailyTimes(data.custom_times.length);
        } else if (data.time_period && data.remind_time) {
          setCustomTimes([data.remind_time]);
          setDailyTimes(1);
        }
        if (data.start_date) setStartDate(data.start_date);
        if (data.end_date) { setEndDate(data.end_date); setIsLongTerm(false); }
        if (data.long_term !== undefined) setIsLongTerm(data.long_term);
        if (data.reminder_enabled !== undefined) setReminderEnabled(data.reminder_enabled);
        if (data.disease_tags) setDiseaseTags(data.disease_tags);
        if (data.frequency_per_day) setDailyTimes(data.frequency_per_day);
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setFetching(false);
      }
    };
    fetchMedication();
  }, [editId]);

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
  };

  const handlePhotoRecognition = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'environment';
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;
      Toast.show({ content: '正在识别…', icon: 'loading', duration: 0 });
      try {
        const formData = new FormData();
        formData.append('file', file);
        const ocrRes: any = await api.post('/api/ocr/recognize', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const ocrText = (ocrRes.data || ocrRes)?.text || '';
        if (ocrText) {
          const matchRes: any = await api.post('/api/prd469/medication-library/ocr', { image_text: ocrText });
          const items = (matchRes.data || matchRes)?.items || [];
          if (items.length > 0) {
            setName(items[0].name);
            setSelectedDrugMeta(items[0]);
            Toast.show({ content: `识别结果：${items[0].name}`, icon: 'success' });
          } else {
            Toast.show({ content: '未识别到药品，请手动输入', icon: 'fail' });
          }
        }
      } catch {
        Toast.show({ content: '识别失败', icon: 'fail' });
      } finally {
        Toast.clear();
      }
    };
    input.click();
  };

  const toggleDiseaseTag = (tag: string) => {
    setDiseaseTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const addCustomDisease = () => {
    const val = customDisease.trim();
    if (!val) return;
    if (diseaseTags.includes(val)) { setCustomDisease(''); return; }
    setDiseaseTags([...diseaseTags, val]);
    setCustomDisease('');
  };

  const updateCustomTime = (index: number, time: string) => {
    const newTimes = [...customTimes];
    newTimes[index] = time;
    setCustomTimes(newTimes);
  };

  const removeTimeSlot = (index: number) => {
    if (customTimes.length <= 1) return;
    const newTimes = customTimes.filter((_, i) => i !== index);
    setCustomTimes(newTimes);
    setDailyTimes(newTimes.length);
  };

  const addTimeSlot = () => {
    if (customTimes.length >= 6) return;
    setCustomTimes([...customTimes, '08:00']);
    setDailyTimes(customTimes.length + 1);
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      Toast.show({ content: '请输入药品名称', icon: 'fail' });
      return;
    }
    if (customTimes.length === 0) {
      Toast.show({ content: '请设置至少一个服药时间', icon: 'fail' });
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        medicine_name: name.trim(),
        dosage: dosage.trim(),
        notes: note.trim(),
        time_period: 'custom',
        remind_time: customTimes[0] || '08:00',
        frequency_per_day: dailyTimes,
        custom_times: customTimes,
        start_date: startDate || null,
        end_date: isLongTerm ? null : (endDate || null),
        long_term: isLongTerm,
        reminder_enabled: reminderEnabled,
        disease_tags: diseaseTags.length > 0 ? diseaseTags : null,
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
      } catch {}
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
    <div className="min-h-screen bg-gray-50 pb-24">
      <GreenNavBar>{isEdit ? '编辑用药提醒' : '添加用药提醒'}</GreenNavBar>

      <div className="px-4 pt-4">
        <div className="card">
          <div className="section-title">药品信息</div>
          <Form layout="vertical">
            <Form.Item label={<><span style={{ color: 'red' }}>*</span> 药品名称（支持联想搜索）</>}>
              <div style={{ position: 'relative' }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Input
                    placeholder="如：阿司匹林"
                    value={name}
                    onChange={handleNameChange}
                    clearable
                    style={{ flex: 1 }}
                  />
                  <button
                    onClick={handlePhotoRecognition}
                    data-testid="prd469-photo-recognize-btn"
                    style={{
                      padding: '8px 12px', background: '#16a34a', color: '#fff',
                      borderRadius: 8, border: 'none', fontSize: 16, cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >📷 拍照识药</button>
                </div>
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
                        data-testid={`prd469-drug-option-${d.id}`}
                        style={{
                          padding: '10px 12px', cursor: 'pointer',
                          borderBottom: '1px solid #f3f4f6',
                        }}
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

        <div className="card">
          <div className="section-title">
            <span style={{ color: 'red' }}>*</span> 服药时间设置
          </div>
          <div className="text-xs text-gray-400 mb-3">选择每日服药次数和时间点</div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <span style={{ fontSize: 12, color: '#6b7280', marginRight: 4, alignSelf: 'center' }}>每日次数：</span>
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <button
                key={n}
                onClick={() => setDailyTimes(n)}
                data-testid={`prd469-daily-times-${n}`}
                style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: dailyTimes === n ? '#22c55e' : '#f3f4f6',
                  color: dailyTimes === n ? '#fff' : '#374151',
                  border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >{n}</button>
            ))}
          </div>

          {customTimes.map((time, idx) => (
            <div key={idx} className="mb-3">
              <div
                style={{
                  display: 'flex', alignItems: 'center', padding: '12px 14px',
                  borderRadius: 12, background: '#22c55e10', border: '1px solid #22c55e30',
                }}
              >
                <span style={{ fontSize: 18, marginRight: 10 }}>⏰</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#374151', minWidth: 50 }}>
                  服药 {idx + 1}
                </span>
                <div
                  role="button"
                  tabIndex={0}
                  data-testid={`prd469-time-slot-${idx}`}
                  style={{
                    fontSize: 15, fontWeight: 600, color: '#22c55e',
                    padding: '6px 12px', borderRadius: 8,
                    border: '1px solid #22c55e40', background: '#fff',
                    cursor: 'pointer', marginLeft: 8,
                  }}
                  onClick={() => setTimePickerVisible(idx)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setTimePickerVisible(idx); }}
                >{time}</div>
                {customTimes.length > 1 && (
                  <button
                    onClick={() => removeTimeSlot(idx)}
                    data-testid={`prd469-remove-time-${idx}`}
                    style={{
                      marginLeft: 'auto', width: 28, height: 28, borderRadius: '50%',
                      background: '#fee2e2', color: '#ef4444', border: 'none',
                      fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >×</button>
                )}
              </div>
            </div>
          ))}
          {customTimes.length < 6 && (
            <button
              onClick={addTimeSlot}
              data-testid="prd469-add-time-slot"
              style={{
                width: '100%', padding: '10px 0', borderRadius: 12,
                background: '#f0fdf4', color: '#22c55e', border: '1px dashed #22c55e',
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >+ 添加服药时间</button>
          )}
        </div>

        <div className="card">
          <div className="section-title">日期设置</div>
          <Form.Item label="开始日期">
            <input
              type="date" value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              data-testid="prd469-start-date"
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }}
            />
          </Form.Item>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0' }}>
            <span style={{ fontSize: 14, color: '#374151' }}>长期服用</span>
            <Switch checked={isLongTerm} onChange={setIsLongTerm} />
          </div>
          {!isLongTerm && (
            <Form.Item label="结束日期">
              <input
                type="date" value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                data-testid="prd469-end-date"
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }}
              />
            </Form.Item>
          )}
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0' }}>
            <span style={{ fontSize: 15, fontWeight: 500 }}>🔔 开启用药提醒（App 推送 / 短信）</span>
            <Switch checked={reminderEnabled} onChange={setReminderEnabled} />
          </div>
        </div>

        {/* [PRD-HEALTH-OPT-V1 2026-05-14 R5] AI 外呼提醒面板 */}
        <AiCallPanel
          planId={editId ? Number(editId) : null}
          draftMode={!editId}
          initialDraft={aiCallDraft}
          onDraftChange={setAiCallDraft}
        />

        <div className="card">
          <div className="section-title">关联疾病（可选）</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
            {DISEASE_PRESETS.map((d) => {
              const active = diseaseTags.includes(d);
              return (
                <button
                  key={d}
                  onClick={() => toggleDiseaseTag(d)}
                  data-testid={`prd469-disease-tag-${d}`}
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
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text" value={customDisease}
              onChange={(e) => setCustomDisease(e.target.value)}
              placeholder="自定义疾病名称"
              style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 13, boxSizing: 'border-box' }}
              onKeyDown={(e) => { if (e.key === 'Enter') addCustomDisease(); }}
            />
            <button
              onClick={addCustomDisease}
              style={{ padding: '8px 16px', borderRadius: 8, background: '#22c55e', color: '#fff', border: 'none', fontSize: 13, cursor: 'pointer' }}
            >添加</button>
          </div>
        </div>
      </div>

      <Picker
        columns={TIME_PICKER_COLUMNS}
        visible={timePickerVisible !== null}
        title="选择提醒时间"
        value={
          timePickerVisible !== null
            ? (() => {
                const raw = customTimes[timePickerVisible] || '08:00';
                const [h = '00', m = '00'] = raw.split(':');
                return [h.padStart(2, '0'), m.padStart(2, '0')];
              })()
            : undefined
        }
        onClose={() => setTimePickerVisible(null)}
        onCancel={() => setTimePickerVisible(null)}
        onConfirm={(val) => {
          if (timePickerVisible !== null) {
            const [h, m] = val as string[];
            updateCustomTime(timePickerVisible, `${h}:${m}`);
          }
          setTimePickerVisible(null);
        }}
      />

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        <Button
          block
          color="primary"
          size="large"
          loading={submitting}
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #22c55e, #16a34a)', border: 'none', height: 48 }}
          onClick={handleSubmit}
        >
          {isEdit ? '保存修改' : '添加用药提醒'}
        </Button>
      </div>
    </div>
  );
}
