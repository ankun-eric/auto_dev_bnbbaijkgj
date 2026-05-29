'use client';

/**
 * [PRD-468 2026-05-12] 指标详情页（4 个指标通用模板）
 *
 * 路径：/health-metric/[type]?profileId=xxx
 *   type ∈ blood_pressure / blood_glucose / heart_rate / sleep / spo2
 *
 * 视觉基线：PRD-441/442（11 级天蓝 + 病历卡 + 中老年友好）
 *
 * [BUGFIX-BP-TAB-OPTIMIZE-V1 2026-05-30] 血压 Tab 页面优化：
 *   1) 顶部超大主数值 + 三档色板（正常蓝 / 警告黄 / 严重橙）联动卡片底色 + 胶囊状态标签
 *   2) 同步信息行嵌入「绑定设备（血压计图标）」+「手工录入」入口
 *      - 绑定设备点击 → Toast「即将上线」（不跳转）
 *   3) 趋势图：标题"最近 7 天趋势"，双曲线（收缩压红 + 舒张压蓝），日/周/月/年切换（默认周）
 *   4) 底部"设备绑定"区块整块下线（与顶部入口功能重复）
 *   血糖/心率/睡眠/血氧 Tab 保持原模板不变。
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Popup, Input, Button } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { formatDateTime } from '@/lib/datetime';
import { judgeBp, getBpPalette, type BpJudgement } from '@/lib/bp-level';

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
  trend_dates?: string[];
  trend_day_labels?: string[];
  trend_systolic?: (number | null)[];
  trend_diastolic?: (number | null)[];
}

type BpTrendRange = 'day' | 'week' | 'month' | 'year';

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
      showToast('profileId 缺失', 'fail');
      return;
    }
    const value: Record<string, any> = {};
    for (const f of meta.fields) {
      const v = formValues[f.name];
      if (!v) {
        showToast(`请填写 ${f.label}`, 'fail');
        return;
      }
      value[f.name] = Number(v);
      if (Number.isNaN(value[f.name])) {
        showToast(`${f.label} 必须为数字`, 'fail');
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
      showToast('已保存', 'success');
      setPopupVisible(false);
      setFormValues({});
      setPeriodValue('');
      await fetchHistory();
    } catch {
      showToast('保存失败，请重试', 'fail');
    } finally {
      setSaving(false);
    }
  };

  const handleBindDevice = async (deviceType: string) => {
    try {
      await api.post(`/api/health-profile-v3/devices/${deviceType}/bind`, {});
      showToast('已绑定（占位通道）', 'success');
      await fetchDevices();
    } catch {
      showToast('绑定失败', 'fail');
    }
  };

  const handleUnbindDevice = async (deviceType: string) => {
    try {
      await api.delete(`/api/health-profile-v3/devices/${deviceType}`);
      showToast('已解绑', 'success');
      await fetchDevices();
    } catch {
      showToast('解绑失败', 'fail');
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

  // 血压 Tab 走专属布局
  if (metricType === 'blood_pressure') {
    return (
      <BloodPressurePage
        history={history}
        latest={latest}
        profileId={profileId}
        popupVisible={popupVisible}
        setPopupVisible={setPopupVisible}
        formValues={formValues}
        setFormValues={setFormValues}
        periodValue={periodValue}
        setPeriodValue={setPeriodValue}
        meta={meta}
        saving={saving}
        handleSave={handleSave}
      />
    );
  }

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
                  {latest.value?.period || latest.value?.activity || ''} · {formatDateTime(latest.measured_at)}
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
          onClick={() => showToast('请在下方设备列表中绑定', 'success')}
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
                    {formatDateTime(r.measured_at)}
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

// ─── [BUGFIX-BP-TAB-OPTIMIZE-V1 2026-05-30] 血压 Tab 专属布局 ─────────────────────

/** 血压计 SVG 图标（袖带 + 表盘语义） */
function BpMeterIcon({ size = 18, color = '#1B4DA0' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {/* 表盘主体 */}
      <rect x="3" y="6" width="13" height="11" rx="2" stroke={color} strokeWidth="1.6" />
      {/* 表盘上的指针 */}
      <circle cx="9.5" cy="11.5" r="2.5" stroke={color} strokeWidth="1.4" />
      <line x1="9.5" y1="11.5" x2="11" y2="9.5" stroke={color} strokeWidth="1.4" strokeLinecap="round" />
      {/* 袖带（右侧软管 + 球囊） */}
      <path d="M16 9 Q 20 9 20 12 Q 20 15 16 15" stroke={color} strokeWidth="1.4" fill="none" />
      <circle cx="20.5" cy="17" r="1.5" stroke={color} strokeWidth="1.4" />
    </svg>
  );
}

/** 极小内联手写图标 */
function PencilIcon({ size = 16, color = '#1B4DA0' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M14 4 L20 10 L8 22 H2 V16 Z" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

const BP_RANGE_OPTS: { key: BpTrendRange; label: string }[] = [
  { key: 'day', label: '日' },
  { key: 'week', label: '周' },
  { key: 'month', label: '月' },
  { key: 'year', label: '年' },
];

function formatBpSyncTime(measuredAt?: string | null): string {
  if (!measuredAt) return '';
  try {
    const d = new Date(measuredAt);
    const today = new Date();
    const isToday = d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    if (isToday) return `今日 ${hh}:${mm}`;
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${mo}-${dd} ${hh}:${mm}`;
  } catch {
    return formatDateTime(measuredAt);
  }
}

interface BloodPressurePageProps {
  history: MetricHistoryResponse | null;
  latest: MetricRecord | undefined;
  profileId: number;
  popupVisible: boolean;
  setPopupVisible: (v: boolean) => void;
  formValues: Record<string, string>;
  setFormValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  periodValue: string;
  setPeriodValue: (v: string) => void;
  meta: (typeof META)['blood_pressure'];
  saving: boolean;
  handleSave: () => void;
}

function BloodPressurePage(props: BloodPressurePageProps) {
  const { history, latest, popupVisible, setPopupVisible, formValues, setFormValues,
    periodValue, setPeriodValue, meta, saving, handleSave } = props;

  const [range, setRange] = useState<BpTrendRange>('week');

  const sbp = latest?.value?.systolic != null ? Number(latest.value.systolic) : null;
  const dbp = latest?.value?.diastolic != null ? Number(latest.value.diastolic) : null;
  const judgement: BpJudgement | null = useMemo(() => judgeBp(sbp, dbp), [sbp, dbp]);

  // 无数据态默认走"正常蓝"色板，提示文案适配
  const palette = getBpPalette(judgement?.color ?? 'blue');

  const syncText = useMemo(() => {
    if (!latest) return '尚无血压记录 · 请录入或绑定设备';
    const time = formatBpSyncTime(latest.measured_at);
    const src = latest.source;
    const srcText = src === 'manual' ? '手工录入' : '欧姆龙血压计自动同步';
    return `${time} · ${srcText}`;
  }, [latest]);

  const handleBindDeviceClick = () => {
    showToast('即将上线', 'success');
    // 埋点（占位）：health_archive.bp.bind_device.click
    try {
      // 通过 navigator.sendBeacon 静默上报；后端 /api/_frontend_log 已存在
      if (typeof navigator !== 'undefined' && (navigator as any).sendBeacon) {
        const payload = JSON.stringify({
          type: 'event',
          name: 'health_archive.bp.bind_device.click',
          ts: Date.now(),
          url: typeof window !== 'undefined' ? window.location.pathname : '',
        });
        const blob = new Blob([payload], { type: 'application/json' });
        const basePath = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/+$/, '');
        (navigator as any).sendBeacon(`${basePath}/api/_frontend_log`, blob);
      }
    } catch {
      // 埋点失败不影响主流程
    }
  };

  return (
    <div data-testid="bp-tab-page" style={{ background: '#F4F7FB', minHeight: '100vh', paddingBottom: 24 }}>
      <GreenNavBar>血压详情</GreenNavBar>

      {/* 顶部状态卡片：背景色随档位联动 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div
          data-testid="bp-status-card"
          data-bp-color={judgement?.color ?? 'blue'}
          data-bp-level={judgement?.level ?? 'unknown'}
          style={{
            background: palette.cardBg,
            border: `1px solid ${palette.border}`,
            borderRadius: 18,
            padding: '20px 18px 18px',
            position: 'relative',
          }}
        >
          {/* 主数值 */}
          <div style={{ textAlign: 'center', paddingTop: 4 }}>
            <span
              data-testid="bp-main-value"
              style={{
                fontSize: 58, fontWeight: 800, color: palette.text,
                letterSpacing: 1, lineHeight: 1.0,
              }}
            >
              {sbp != null && dbp != null ? `${sbp}/${dbp}` : '—'}
            </span>
            <span style={{ fontSize: 16, fontWeight: 600, color: palette.text, marginLeft: 8, opacity: 0.7 }}>
              mmHg
            </span>
          </div>

          {/* 同步信息行 + 绑定设备入口 + 手工录入 */}
          <div style={{
            marginTop: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
            flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 13, color: palette.text, opacity: 0.85, flex: 1, minWidth: 0 }}>
              {syncText}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                data-testid="bp-bind-device-btn"
                aria-label="绑定设备"
                onClick={handleBindDeviceClick}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '6px 10px', borderRadius: 16,
                  background: 'rgba(255,255,255,0.65)',
                  border: `1px solid ${palette.border}`,
                  color: palette.text, fontSize: 12, fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <BpMeterIcon size={16} color={palette.text} />
                <span>绑定设备</span>
              </button>
              <button
                data-testid="bp-manual-input-btn"
                aria-label="手工录入"
                onClick={() => setPopupVisible(true)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '6px 10px', borderRadius: 16,
                  background: 'rgba(255,255,255,0.65)',
                  border: `1px solid ${palette.border}`,
                  color: palette.text, fontSize: 12, fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <PencilIcon size={14} color={palette.text} />
                <span>手工录入</span>
              </button>
            </div>
          </div>

          {/* 状态胶囊 */}
          {judgement && (
            <div style={{ marginTop: 14, display: 'flex', justifyContent: 'center' }}>
              <span
                data-testid="bp-capsule"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '6px 16px', borderRadius: 999,
                  background: palette.capsuleBg, color: palette.capsuleText,
                  fontSize: 13, fontWeight: 700,
                  boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
                }}
              >
                <span aria-hidden="true">{judgement.icon}</span>
                <span>{judgement.capsuleLabel}</span>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 最近 7 天趋势 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div
          data-testid="bp-trend-card"
          style={{
            background: '#fff', borderRadius: 16, padding: '14px 14px 12px',
            boxShadow: '0 2px 10px rgba(14,165,233,0.06)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>最近 7 天趋势</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {BP_RANGE_OPTS.map(opt => (
                <button
                  key={opt.key}
                  data-testid={`bp-range-${opt.key}`}
                  onClick={() => setRange(opt.key)}
                  style={{
                    padding: '3px 10px', borderRadius: 12, border: 'none',
                    background: range === opt.key ? '#0EA5E9' : '#F1F5F9',
                    color: range === opt.key ? '#fff' : '#64748B',
                    fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  }}
                >{opt.label}</button>
              ))}
            </div>
          </div>
          <BpTrendChart
            sbp={history?.trend_systolic || [null, null, null, null, null, null, null]}
            dbp={history?.trend_diastolic || [null, null, null, null, null, null, null]}
            labels={history?.trend_day_labels || ['周三', '周四', '周五', '周六', '周日', '周一', '今日']}
          />
          {/* 图例 */}
          <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center', gap: 18 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#EF4444', display: 'inline-block' }} />
              收缩压（高压）
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#3B82F6', display: 'inline-block' }} />
              舒张压（低压）
            </span>
          </div>
        </div>
      </div>

      {/* 历史记录 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: '14px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E', marginBottom: 10 }}>历史记录</div>
          {(history?.records || []).length === 0 ? (
            <div style={{ fontSize: 14, color: '#6B7280', textAlign: 'center', padding: '24px 0' }}>
              暂无记录
            </div>
          ) : (
            (history?.records || []).map((r) => {
              const rSbp = r.value?.systolic != null ? Number(r.value.systolic) : null;
              const rDbp = r.value?.diastolic != null ? Number(r.value.diastolic) : null;
              const j = judgeBp(rSbp, rDbp);
              const rowPalette = getBpPalette(j?.color ?? 'blue');
              return (
                <div
                  key={r.id}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 0', borderBottom: '1px solid #E5E7EB',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#0C4A6E' }}>
                      {rSbp ?? '-'}/{rDbp ?? '-'}
                      <span style={{ fontSize: 12, color: '#6B7280', marginLeft: 4, fontWeight: 500 }}>mmHg</span>
                    </div>
                    <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
                      {formatDateTime(r.measured_at)} · {r.source === 'manual' ? '手工' : r.source}
                    </div>
                  </div>
                  {j && (
                    <span
                      style={{
                        fontSize: 11, fontWeight: 700,
                        padding: '3px 10px', borderRadius: 999,
                        background: rowPalette.capsuleBg, color: rowPalette.capsuleText,
                      }}
                    >
                      {j.label}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 【说明】底部"设备绑定"区域已按 BUGFIX-BP-TAB-OPTIMIZE-V1 整块下线，
          顶部状态卡片内已提供「绑定设备」入口，避免功能重复。 */}

      {/* 手工填写弹窗 */}
      <Popup
        visible={popupVisible}
        onMaskClick={() => setPopupVisible(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        <div style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E', marginBottom: 16 }}>
          手工填写{meta.label}
        </div>
        {meta.fields.map((f) => (
          <div key={f.name} style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 4 }}>{f.label}</div>
            <Input
              type="number"
              placeholder={f.placeholder}
              value={formValues[f.name] || ''}
              onChange={(v) => setFormValues((s) => ({ ...s, [f.name]: v }))}
              style={{
                '--font-size': '16px', padding: '10px 12px',
                background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd',
              } as any}
            />
          </div>
        ))}
        {meta.period && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>时段</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {meta.period.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setPeriodValue(opt)}
                  style={{
                    padding: '6px 14px',
                    background: periodValue === opt ? '#0ea5e9' : '#e0f2fe',
                    color: periodValue === opt ? '#fff' : '#0369a1',
                    border: 'none', borderRadius: 18, fontSize: 14, cursor: 'pointer',
                  }}
                >{opt}</button>
              ))}
            </div>
          </div>
        )}
        <Button
          block color="primary" loading={saving} onClick={handleSave}
          style={{ '--background-color': '#0ea5e9', '--border-radius': '22px', height: 44, fontSize: 16 } as any}
        >保存</Button>
      </Popup>
    </div>
  );
}

/** 血压双曲线 SVG 趋势图（收缩压红 / 舒张压蓝） */
function BpTrendChart({
  sbp, dbp, labels,
}: {
  sbp: (number | null)[];
  dbp: (number | null)[];
  labels: string[];
}) {
  const W = 320, H = 180;
  const PAD = { top: 14, right: 12, bottom: 26, left: 32 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  const allVals: number[] = [];
  sbp.forEach(v => { if (v != null) allVals.push(v); });
  dbp.forEach(v => { if (v != null) allVals.push(v); });

  // 设计要求建议 60–180 mmHg 范围；按实际数据自动适配
  let minV = 60, maxV = 180;
  if (allVals.length > 0) {
    minV = Math.min(60, Math.floor(Math.min(...allVals) / 10) * 10 - 5);
    maxV = Math.max(180, Math.ceil(Math.max(...allVals) / 10) * 10 + 5);
  }
  const range = maxV - minV || 1;
  const n = Math.max(sbp.length, dbp.length, labels.length, 7);

  const xScale = (i: number) => PAD.left + (n > 1 ? (i / (n - 1)) * cw : cw / 2);
  const yScale = (v: number) => PAD.top + ch - ((v - minV) / range) * ch;

  const buildPath = (values: (number | null)[]) => {
    const segs: string[] = [];
    let cmd = 'M';
    values.forEach((v, i) => {
      if (v != null) {
        segs.push(`${cmd}${xScale(i).toFixed(1)},${yScale(v).toFixed(1)}`);
        cmd = 'L';
      } else {
        cmd = 'M';
      }
    });
    return segs.join(' ');
  };

  const sbpPath = buildPath(sbp);
  const dbpPath = buildPath(dbp);

  // Y 轴 4 等分网格
  const gridVals = [minV, minV + range * 0.25, minV + range * 0.5, minV + range * 0.75, maxV];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }} data-testid="bp-trend-svg">
      {/* 网格 */}
      {gridVals.map((v, idx) => {
        const y = yScale(v);
        return (
          <g key={idx}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#E5E7EB" strokeWidth={0.6} />
            <text x={PAD.left - 4} y={y + 3} textAnchor="end" fill="#9CA3AF" fontSize={9}>{Math.round(v)}</text>
          </g>
        );
      })}
      {/* X 轴标签（最右一日「今日」高亮） */}
      {labels.slice(0, n).map((lab, i) => {
        const isToday = lab === '今日' || i === n - 1;
        return (
          <text
            key={i}
            x={xScale(i)} y={H - 8}
            textAnchor="middle"
            fill={isToday ? '#0EA5E9' : '#9CA3AF'}
            fontSize={isToday ? 11 : 10}
            fontWeight={isToday ? 700 : 400}
          >{lab}</text>
        );
      })}
      {/* 两条曲线 */}
      {sbpPath && <path d={sbpPath} fill="none" stroke="#EF4444" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />}
      {dbpPath && <path d={dbpPath} fill="none" stroke="#3B82F6" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />}
      {/* 数据点 */}
      {sbp.map((v, i) => v != null ? (
        <circle key={`s${i}`} cx={xScale(i)} cy={yScale(v)} r={3} fill="#EF4444" stroke="#fff" strokeWidth={1} />
      ) : null)}
      {dbp.map((v, i) => v != null ? (
        <circle key={`d${i}`} cx={xScale(i)} cy={yScale(v)} r={3} fill="#3B82F6" stroke="#fff" strokeWidth={1} />
      ) : null)}
      {/* 无数据态 */}
      {allVals.length === 0 && (
        <text x={W / 2} y={H / 2} textAnchor="middle" fill="#9CA3AF" fontSize={12}>暂无趋势数据</text>
      )}
    </svg>
  );
}
