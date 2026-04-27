'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Tabs, Popup, Toast, ImageUploader, type ImageUploadItem } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';

interface HealthData {
  height?: number;
  weight?: number;
  waist?: number;
  bmi?: number;
  blood_pressure_systolic?: number;
  blood_pressure_diastolic?: number;
  heart_rate?: number;
  blood_sugar?: number;
  body_temperature?: number;
}

interface SportSleepData {
  steps_today?: number;
  steps_trend?: { date: string; steps: number }[];
  sleep_records?: { date: string; duration: number; quality: string }[];
}

interface MedicalItem {
  id: string;
  type: string;
  title: string;
  date: string;
  file_url?: string;
}

interface HealthInfo {
  chronic_diseases: string[];
  past_diseases: string[];
  allergies: string[];
  genetic_diseases: string[];
  lifestyle: {
    smoking?: string;
    drinking?: string;
    exercise?: string;
  };
}

export default function HealthArchivePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('health-data');
  const [healthData, setHealthData] = useState<HealthData>({});
  const [sportSleep, setSportSleep] = useState<SportSleepData>({});
  const [medicalItems, setMedicalItems] = useState<MedicalItem[]>([]);
  const [healthInfo, setHealthInfo] = useState<HealthInfo>({ chronic_diseases: [], past_diseases: [], allergies: [], genetic_diseases: [], lifestyle: {} });
  const [editField, setEditField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [medicalCategory, setMedicalCategory] = useState('病历');

  useEffect(() => {
    api.get('/api/health/archive/data').then((res: any) => {
      setHealthData(res.data || res);
    }).catch(() => {});

    api.get('/api/health/archive/sport-sleep').then((res: any) => {
      setSportSleep(res.data || res);
    }).catch(() => {});

    api.get('/api/health/archive/medical-records').then((res: any) => {
      const data = res.data || res;
      setMedicalItems(Array.isArray(data.items) ? data.items : []);
    }).catch(() => {});

    api.get('/api/health/archive/health-info').then((res: any) => {
      const data = res.data || res;
      setHealthInfo({
        chronic_diseases: data.chronic_diseases || [],
        past_diseases: data.past_diseases || [],
        allergies: data.allergies || [],
        genetic_diseases: data.genetic_diseases || [],
        lifestyle: data.lifestyle || {},
      });
    }).catch(() => {});
  }, []);

  const saveHealthData = async (field: string, value: string) => {
    try {
      await api.put('/api/health/archive/data', { [field]: Number(value) || 0 });
      setHealthData(prev => ({ ...prev, [field]: Number(value) || 0 }));
      Toast.show({ content: '保存成功', icon: 'success' });
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
    setEditField(null);
  };

  const healthDataFields = [
    { key: 'height', label: '身高', unit: 'cm', icon: '📏' },
    { key: 'weight', label: '体重', unit: 'kg', icon: '⚖️' },
    { key: 'waist', label: '腰围', unit: 'cm', icon: '📐' },
    { key: 'bmi', label: 'BMI', unit: '', icon: '📊' },
    { key: 'blood_pressure_systolic', label: '收缩压', unit: 'mmHg', icon: '❤️' },
    { key: 'blood_pressure_diastolic', label: '舒张压', unit: 'mmHg', icon: '💙' },
    { key: 'heart_rate', label: '心率', unit: 'bpm', icon: '💓' },
    { key: 'blood_sugar', label: '血糖', unit: 'mmol/L', icon: '🩸' },
    { key: 'body_temperature', label: '体温', unit: '°C', icon: '🌡️' },
  ];

  const medicalCategories = ['病历', '体检报告', '药物', '其它'];

  return (
    <div className="min-h-screen" style={{ background: THEME.background }}>
      <NavBar
        onBack={() => router.back()}
        style={{ background: THEME.cardBg, '--border-bottom': `1px solid ${THEME.divider}` } as React.CSSProperties}
      >
        <span style={{ color: THEME.textPrimary, fontWeight: 600 }}>健康档案</span>
      </NavBar>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{
          '--active-title-color': THEME.primary,
          '--active-line-color': THEME.primary,
          '--title-font-size': '14px',
        } as React.CSSProperties}
      >
        <Tabs.Tab title="健康数据" key="health-data" />
        <Tabs.Tab title="运动睡眠" key="sport-sleep" />
        <Tabs.Tab title="就医资料" key="medical" />
        <Tabs.Tab title="健康信息" key="health-info" />
      </Tabs>

      <div className="px-4 py-3">
        {activeTab === 'health-data' && (
          <div className="grid grid-cols-2 gap-3">
            {healthDataFields.map(field => (
              <div
                key={field.key}
                className="rounded-2xl p-4 cursor-pointer active:opacity-80"
                style={{ background: THEME.cardBg }}
                onClick={() => { setEditField(field.key); setEditValue(String((healthData as any)[field.key] || '')); }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span>{field.icon}</span>
                  <span className="text-xs" style={{ color: THEME.textSecondary }}>{field.label}</span>
                </div>
                <div className="text-xl font-bold" style={{ color: THEME.textPrimary }}>
                  {(healthData as any)[field.key] ?? '--'}
                  <span className="text-xs font-normal ml-1" style={{ color: THEME.textSecondary }}>{field.unit}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'sport-sleep' && (
          <div>
            {/* Steps */}
            <div className="rounded-2xl p-4 mb-3" style={{ background: THEME.cardBg }}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold" style={{ color: THEME.textPrimary }}>今日步数</span>
                <span className="text-xs" style={{ color: THEME.textSecondary }}>目标 8000 步</span>
              </div>
              <div className="text-3xl font-bold mb-3" style={{ color: THEME.primary }}>
                {sportSleep.steps_today ?? 0}
              </div>

              {/* 7-day trend */}
              {sportSleep.steps_trend && sportSleep.steps_trend.length > 0 && (
                <div>
                  <div className="text-xs mb-2" style={{ color: THEME.textSecondary }}>7日趋势</div>
                  <div className="flex items-end gap-1 h-20">
                    {sportSleep.steps_trend.map((d, i) => {
                      const max = Math.max(...sportSleep.steps_trend!.map(s => s.steps), 1);
                      const pct = (d.steps / max) * 100;
                      return (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                          <div
                            className="w-full rounded-t"
                            style={{ height: `${Math.max(pct, 5)}%`, background: THEME.primary, minHeight: 4, opacity: 0.3 + (pct / 100) * 0.7 }}
                          />
                          <span className="text-xs" style={{ color: THEME.textSecondary, fontSize: 10 }}>
                            {new Date(d.date).getDate()}日
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Sleep */}
            <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
              <div className="text-sm font-semibold mb-3" style={{ color: THEME.textPrimary }}>睡眠记录</div>
              {sportSleep.sleep_records && sportSleep.sleep_records.length > 0 ? (
                <div className="space-y-2">
                  {sportSleep.sleep_records.map((r, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b" style={{ borderColor: THEME.divider }}>
                      <span className="text-sm" style={{ color: THEME.textPrimary }}>{r.date}</span>
                      <div className="text-right">
                        <span className="text-sm font-medium" style={{ color: THEME.primary }}>{r.duration}h</span>
                        <span className="text-xs ml-2" style={{ color: THEME.textSecondary }}>{r.quality}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-sm" style={{ color: THEME.textSecondary }}>暂无睡眠记录</div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'medical' && (
          <div>
            <div className="flex gap-2 mb-3">
              {medicalCategories.map(cat => (
                <button
                  key={cat}
                  className="px-3 py-1.5 rounded-full text-xs font-medium"
                  style={{
                    background: medicalCategory === cat ? THEME.primary : THEME.primaryLight,
                    color: medicalCategory === cat ? '#fff' : THEME.primary,
                  }}
                  onClick={() => setMedicalCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Upload area */}
            <div
              className="flex flex-col items-center justify-center py-8 rounded-2xl mb-3 cursor-pointer"
              style={{ background: THEME.cardBg, border: `2px dashed ${THEME.divider}` }}
            >
              <span className="text-3xl mb-2">📤</span>
              <span className="text-sm" style={{ color: THEME.textSecondary }}>点击上传{medicalCategory}</span>
            </div>

            {/* List */}
            {medicalItems.filter(m => m.type === medicalCategory).map(item => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3 rounded-xl mb-2" style={{ background: THEME.cardBg }}>
                <span className="text-xl">📄</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate" style={{ color: THEME.textPrimary }}>{item.title}</div>
                  <div className="text-xs" style={{ color: THEME.textSecondary }}>{item.date}</div>
                </div>
              </div>
            ))}

            {medicalItems.filter(m => m.type === medicalCategory).length === 0 && (
              <div className="text-center py-6 text-sm" style={{ color: THEME.textSecondary }}>暂无{medicalCategory}记录</div>
            )}
          </div>
        )}

        {activeTab === 'health-info' && (
          <div className="space-y-3">
            <InfoSection title="慢性病" items={healthInfo.chronic_diseases} />
            <InfoSection title="既往病史" items={healthInfo.past_diseases} />
            <InfoSection title="过敏史" items={healthInfo.allergies} />
            <InfoSection title="家族遗传病" items={healthInfo.genetic_diseases} />

            <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
              <div className="text-sm font-semibold mb-3" style={{ color: THEME.textPrimary }}>生活习惯</div>
              <div className="space-y-3">
                {[
                  { key: 'smoking', label: '吸烟', icon: '🚬' },
                  { key: 'drinking', label: '饮酒', icon: '🍺' },
                  { key: 'exercise', label: '运动', icon: '🏃' },
                ].map(item => (
                  <div key={item.key} className="flex items-center justify-between py-2 border-b" style={{ borderColor: THEME.divider }}>
                    <div className="flex items-center gap-2">
                      <span>{item.icon}</span>
                      <span className="text-sm" style={{ color: THEME.textPrimary }}>{item.label}</span>
                    </div>
                    <span className="text-sm" style={{ color: THEME.textSecondary }}>
                      {(healthInfo.lifestyle as any)[item.key] || '未填写'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Edit popup */}
      <Popup
        visible={!!editField}
        onMaskClick={() => setEditField(null)}
        position="bottom"
        bodyStyle={{ borderRadius: '20px 20px 0 0' }}
      >
        <div className="px-4 py-5">
          <div className="flex items-center justify-between mb-4">
            <span className="text-base font-bold" style={{ color: THEME.textPrimary }}>
              编辑{healthDataFields.find(f => f.key === editField)?.label}
            </span>
            <button className="text-2xl leading-none" style={{ color: THEME.textSecondary }} onClick={() => setEditField(null)}>×</button>
          </div>
          <input
            type="number"
            className="w-full px-4 py-3 rounded-xl outline-none text-base"
            style={{ background: THEME.background, color: THEME.textPrimary, border: `1px solid ${THEME.divider}` }}
            placeholder="请输入数值"
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            autoFocus
          />
          <div className="text-xs mt-2 mb-4" style={{ color: THEME.textSecondary }}>
            单位：{healthDataFields.find(f => f.key === editField)?.unit || ''}
          </div>
          <button
            className="w-full py-3 rounded-xl text-white font-medium text-sm"
            style={{ background: THEME.primary }}
            onClick={() => editField && saveHealthData(editField, editValue)}
          >
            保存
          </button>
        </div>
      </Popup>
    </div>
  );
}

function InfoSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
      <div className="text-sm font-semibold mb-2" style={{ color: THEME.textPrimary }}>{title}</div>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item, i) => (
            <span
              key={i}
              className="px-3 py-1 rounded-full text-xs"
              style={{ background: THEME.primaryLight, color: THEME.primary }}
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <div className="text-sm" style={{ color: THEME.textSecondary }}>暂未填写</div>
      )}
    </div>
  );
}
