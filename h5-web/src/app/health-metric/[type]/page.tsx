'use client';

/**
 * [PRD-468 2026-05-12] 指标详情页（4 个指标通用模板）
 *
 * 路径：/health-metric/[type]?profileId=xxx
 *   type ∈ blood_pressure / blood_glucose / heart_rate / sleep / spo2
 *
 * 视觉基线：PRD-441/442（11 级天蓝 + 病历卡 + 中老年友好）
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Toast, Popup, Input, Button } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

const T = {
  brand50: '#f0f9ff',
  brand100: '#e0f2fe',
  brand200: '#bae6fd',
  brand300: '#7dd3fc',
  brand400: '#38bdf8',
  brand500: '#0ea5e9',
  brand600: '#0284c7',
  brand700: '#0369a1',
  brand800: '#075985',
  cardLineBlue: '3px solid #38bdf8',
  shadow: '0 4px 16px rgba(56, 189, 248, 0.08)',
};

const META: Record<string, {
  label: string;
  unit: string;
  fields: { name: string; label: string; placeholder?: string; suffix?: string }[];
  period?: { key: string; options: string[] };
  principalKey: string;
}> = {
  blood_pressure: {
    label: '血压',
    unit: 'mmHg',
    fields: [
      { name: 'systolic', label: '收缩压', suffix: 'mmHg', placeholder: '如 128' },
      { name: 'diastolic', label: '舒张压', suffix: 'mmHg', placeholder: '如 82' },
    ],
    period: { key: 'period', options: ['晨起', '午间', '晚间'] },
    principalKey: 'systolic',
  },
  blood_glucose: {
    label: '血糖',
    unit: 'mmol/L',
    fields: [
      { name: 'value', label: '数值', suffix: 'mmol/L', placeholder: '如 6.5' },
    ],
    period: { key: 'period', options: ['空腹', '餐前', '餐后', '睡前'] },
    principalKey: 'value',
  },
  heart_rate: {
    label: '心率',
    unit: 'bpm',
    fields: [
      { name: 'value', label: '心率', suffix: 'bpm', placeholder: '如 72' },
    ],
    period: { key: 'activity', options: ['静息', '运动'] },
    principalKey: 'value',
  },
  sleep: {
    label: '睡眠',
    unit: 'h',
    fields: [
      { name: 'duration_h', label: '总时长', suffix: 'h', placeholder: '如 7.5' },
      { name: 'deep_h', label: '深睡时长', suffix: 'h', placeholder: '如 2' },
    ],
    principalKey: 'duration_h',
  },
  spo2: {
    label: '血氧',
    unit: '%',
    fields: [
      { name: 'value', label: '血氧饱和度', suffix: '%', placeholder: '如 97' },
    ],
    period: { key: 'period', options: ['晨起', '午间', '晚间'] },
    principalKey: 'value',
  },
};

const DEVICE_LABELS: Record<string, string> = {
  huawei_watch: '⌚ 华为 Watch / GT 系列',
  xiaomi_band: '⌚ 小米手环 / Watch',
  glucometer: '📶 血糖仪',
  bp_meter: '💪 血压计',
  scale: '⚖️ 体重秤',
};

interface MetricRecord {
  id: number;
  metric_type: string;
  value: Record<string, any>;
  source: string;
  measured_at: string;
  created_at: string;
}

interface MetricHistoryResponse {
  metric_type: string;
  trend_7days: (number | null)[];
  records: MetricRecord[];
  total: number;
}

interface DeviceItem {
  id?: number;
  device_type: string;
  name: string;
  status: string; // active | unbound | coming_soon
  last_sync_at?: string | null;
}

function MedicalCard({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: '#fff', borderLeft: T.cardLineBlue, borderRadius: 16,
        padding: 16, boxShadow: T.shadow, ...style,
      }}
    >{children}</div>
  );
}

export default function HealthMetricDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const metricType = (params?.type as string) || 'blood_pressure';
  const profileId = Number(searchParams?.get('profileId') || 0);

  const meta = META[metricType];

  const [history, setHistory] = useState<MetricHistoryResponse | null>(null);
  const [devices, setDevices] = useState<DeviceItem[]>([]);

  // 录入弹窗
  const [popupVisible, setPopupVisible] = useState(false);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [periodValue, setPeriodValue] = useState<string>('');
  const [saving, setSaving] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (!profileId) return;
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/metric/${metricType}`);
      setHistory(res.data || res);
    } catch {
      setHistory(null);
    }
  }, [profileId, metricType]);

  const fetchDevices = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-profile-v3/devices');
      const data = res.data || res;
      setDevices(Array.isArray(data.items) ? data.items : []);
    } catch {
      setDevices([]);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
    fetchDevices();
  }, [fetchHistory, fetchDevices]);

  const handleSave = async () => {
    if (!profileId) {
      Toast.show({ icon: 'fail', content: 'profileId 缺失' });
      return;
    }
    const value: Record<string, any> = {};
    for (const f of meta.fields) {
      const v = formValues[f.name];
      if (!v) {
        Toast.show({ icon: 'fail', content: `请填写 ${f.label}` });
        return;
      }
      value[f.name] = Number(v);
      if (Number.isNaN(value[f.name])) {
        Toast.show({ icon: 'fail', content: `${f.label} 必须为数字` });
        return;
      }
    }
    if (meta.period && periodValue) {
      value[meta.period.key] = periodValue;
    }

    setSaving(true);
    try {
      await api.post(`/api/health-profile-v3/${profileId}/metric/${metricType}`, {
        value, source: 'manual',
      });
      Toast.show({ icon: 'success', content: '已保存' });
      setPopupVisible(false);
      setFormValues({});
      setPeriodValue('');
      await fetchHistory();
    } catch {
      Toast.show({ icon: 'fail', content: '保存失败，请重试' });
    } finally {
      setSaving(false);
    }
  };

  const handleBindDevice = async (deviceType: string) => {
    try {
      await api.post(`/api/health-profile-v3/devices/${deviceType}/bind`, {});
      Toast.show({ icon: 'success', content: '已绑定（占位通道）' });
      await fetchDevices();
    } catch {
      Toast.show({ icon: 'fail', content: '绑定失败' });
    }
  };

  const handleUnbindDevice = async (deviceType: string) => {
    try {
      await api.delete(`/api/health-profile-v3/devices/${deviceType}`);
      Toast.show({ icon: 'success', content: '已解绑' });
      await fetchDevices();
    } catch {
      Toast.show({ icon: 'fail', content: '解绑失败' });
    }
  };

  if (!meta) {
    return (
      <div>
        <GreenNavBar>未知指标</GreenNavBar>
        <div style={{ padding: 20 }}>未知 metric_type: {metricType}</div>
      </div>
    );
  }

  const latest = history?.records?.[0];

  // 趋势曲线 SVG（简易）
  const trend = history?.trend_7days || [null, null, null, null, null, null, null];
  const trendValues = trend.map((v) => (v == null ? 0 : v));
  const validValues = trendValues.filter((v) => v > 0);
  const min = validValues.length ? Math.min(...validValues) : 0;
  const max = validValues.length ? Math.max(...validValues) : 1;
  const range = max - min || 1;

  return (
    <div style={{ background: T.brand50, minHeight: '100vh', paddingBottom: 100 }}>
      <GreenNavBar>{meta.label}详情</GreenNavBar>

      {/* Hero 当前值 */}
      <div style={{ padding: '12px 16px' }}>
        <MedicalCard>
          <div style={{ fontSize: 13, color: T.brand800 }}>当前值</div>
          <div style={{ marginTop: 6 }}>
            {latest ? (
              <>
                <span style={{ fontSize: 22, fontWeight: 700, color: T.brand700 }}>
                  {metricType === 'blood_pressure'
                    ? `${latest.value?.systolic || '-'}/${latest.value?.diastolic || '-'}`
                    : latest.value?.[meta.principalKey] ?? '—'}
                </span>
                <span style={{ fontSize: 13, color: T.brand800, marginLeft: 4 }}>{meta.unit}</span>
                <div style={{ fontSize: 13, color: T.brand600, marginTop: 4 }}>
                  {latest.value?.period || latest.value?.activity || ''} · {new Date(latest.measured_at).toLocaleString('zh-CN')}
                </div>
              </>
            ) : (
              <div style={{ fontSize: 14, color: T.brand800 }}>暂无数据，点击下方「手工填写」录入</div>
            )}
          </div>
        </MedicalCard>
      </div>

      {/* 双按钮 */}
      <div style={{ padding: '12px 16px', display: 'flex', gap: 10 }}>
        <button
          data-testid="prd468-btn-manual"
          onClick={() => setPopupVisible(true)}
          style={{
            flex: 6, padding: '12px 0', background: T.brand500, color: '#fff',
            border: 'none', borderRadius: 22, fontSize: 16, fontWeight: 600, cursor: 'pointer',
          }}
        >✎ 手工填写</button>
        <button
          onClick={() => Toast.show({ icon: 'success', content: '请在下方设备列表中绑定' })}
          style={{
            flex: 4, padding: '12px 0', background: '#fff', color: T.brand500,
            border: `1px solid ${T.brand300}`, borderRadius: 22, fontSize: 16, fontWeight: 600, cursor: 'pointer',
          }}
        >⌚ 绑定设备</button>
      </div>

      {/* 7 天趋势 */}
      <div style={{ padding: '12px 16px' }}>
        <MedicalCard>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.brand700, marginBottom: 10 }}>7 天趋势</div>
          <svg width="100%" height="80" viewBox="0 0 280 80" preserveAspectRatio="none">
            {trendValues.map((v, i) => {
              if (v <= 0) return null;
              const x = (i / 6) * 280;
              const y = 80 - ((v - min) / range) * 60 - 10;
              return (
                <circle key={i} cx={x} cy={y} r={3} fill={T.brand500} />
              );
            })}
            <polyline
              points={trendValues
                .map((v, i) => {
                  if (v <= 0) return '';
                  return `${(i / 6) * 280},${80 - ((v - min) / range) * 60 - 10}`;
                })
                .filter(Boolean)
                .join(' ')}
              fill="none"
              stroke={T.brand400}
              strokeWidth={2}
            />
          </svg>
          <div style={{ fontSize: 13, color: T.brand600, marginTop: 6 }}>
            最近 {history?.records.length || 0} 条记录
          </div>
        </MedicalCard>
      </div>

      {/* 历史记录 */}
      <div style={{ padding: '12px 16px' }}>
        <MedicalCard>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.brand700, marginBottom: 10 }}>历史记录</div>
          {(history?.records || []).length === 0 ? (
            <div style={{ fontSize: 14, color: T.brand800, textAlign: 'center', padding: '24px 0' }}>
              暂无记录
            </div>
          ) : (
            (history?.records || []).map((r) => (
              <div
                key={r.id}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 0', borderBottom: `1px solid ${T.brand100}`,
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700 }}>
                    {metricType === 'blood_pressure'
                      ? `${r.value?.systolic}/${r.value?.diastolic}`
                      : r.value?.[meta.principalKey]}
                    <span style={{ fontSize: 12, color: T.brand800, marginLeft: 4 }}>{meta.unit}</span>
                  </div>
                  <div style={{ fontSize: 12, color: T.brand600, marginTop: 2 }}>
                    {new Date(r.measured_at).toLocaleString('zh-CN')}
                  </div>
                </div>
                <span
                  style={{
                    fontSize: 11, fontWeight: 600,
                    padding: '3px 8px', borderRadius: 10,
                    background: r.source === 'manual' ? T.brand100 : '#d1fae5',
                    color: r.source === 'manual' ? T.brand700 : '#065f46',
                  }}
                >
                  {r.source === 'manual' ? '✎ 手工' : `⌚ ${r.source}`}
                </span>
              </div>
            ))
          )}
        </MedicalCard>
      </div>

      {/* 设备绑定 */}
      <div style={{ padding: '12px 16px' }}>
        <MedicalCard>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.brand700, marginBottom: 10 }}>设备绑定</div>
          {devices.map((d) => (
            <div
              key={d.device_type}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 0', borderBottom: `1px solid ${T.brand100}`,
              }}
            >
              <span style={{ fontSize: 14, color: T.brand800 }}>{DEVICE_LABELS[d.device_type] || d.name}</span>
              {d.status === 'coming_soon' ? (
                <span style={{ fontSize: 13, color: '#9CA3AF' }}>敬请期待</span>
              ) : d.status === 'active' ? (
                <button
                  onClick={() => handleUnbindDevice(d.device_type)}
                  style={{
                    padding: '4px 12px', fontSize: 13, color: T.brand700,
                    background: T.brand100, border: 'none', borderRadius: 12, cursor: 'pointer',
                  }}
                >✓ 已绑定 解绑</button>
              ) : (
                <button
                  onClick={() => handleBindDevice(d.device_type)}
                  data-testid={`prd468-bind-${d.device_type}`}
                  style={{
                    padding: '4px 12px', fontSize: 13, color: '#fff',
                    background: T.brand500, border: 'none', borderRadius: 12, cursor: 'pointer',
                  }}
                >立即绑定</button>
              )}
            </div>
          ))}
        </MedicalCard>
      </div>

      {/* 手工填写弹窗 */}
      <Popup
        visible={popupVisible}
        onMaskClick={() => setPopupVisible(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        <div style={{ fontSize: 18, fontWeight: 600, color: T.brand700, marginBottom: 16 }}>
          手工填写{meta.label}
        </div>
        {meta.fields.map((f) => (
          <div key={f.name} style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: T.brand800, marginBottom: 4 }}>{f.label}</div>
            <Input
              type="number"
              placeholder={f.placeholder}
              value={formValues[f.name] || ''}
              onChange={(v) => setFormValues((s) => ({ ...s, [f.name]: v }))}
              style={{
                '--font-size': '16px', padding: '10px 12px',
                background: T.brand50, borderRadius: 8, border: `1px solid ${T.brand200}`,
              } as any}
            />
          </div>
        ))}
        {meta.period && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: T.brand800, marginBottom: 6 }}>时段</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {meta.period.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setPeriodValue(opt)}
                  style={{
                    padding: '6px 14px',
                    background: periodValue === opt ? T.brand500 : T.brand100,
                    color: periodValue === opt ? '#fff' : T.brand700,
                    border: 'none', borderRadius: 18, fontSize: 14, cursor: 'pointer',
                  }}
                >{opt}</button>
              ))}
            </div>
          </div>
        )}
        <Button
          block color="primary" loading={saving} onClick={handleSave}
          style={{ '--background-color': T.brand500, '--border-radius': '22px', height: 44, fontSize: 16 } as any}
        >保存</Button>
      </Popup>
    </div>
  );
}
