'use client';

/**
 * [PRD-468 2026-05-12] 指标详情页（4 个指标通用模板）
 *
 * 路径：/health-metric/[type]?profileId=xxx
 *   type ∈ blood_pressure / blood_glucose / heart_rate / sleep / spo2
 *
 * 视觉基线：PRD-441/442（11 级天蓝 + 病历卡 + 中老年友好）
 *
 * [BUGFIX-BP-TAB-OPTIMIZE-V1 2026-05-30] 血压 Tab 页面优化（v1）：
 *   1) 顶部超大主数值 + 三档色板（正常蓝 / 警告黄 / 严重橙）联动卡片底色 + 胶囊状态标签
 *   2) 同步信息行嵌入「绑定设备（血压计图标）」+「手工录入」入口
 *   3) 趋势图：标题"最近 7 天趋势"，双曲线（收缩压红 + 舒张压蓝），日/周/月/年切换（默认周）
 *   4) 底部"设备绑定"区块整块下线（与顶部入口功能重复）
 *
 * [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 血压卡片优化（v2，本次）：
 *   - 顶部主卡片保持原样（移除其内嵌的小按钮，保留主数值/同步信息/胶囊）
 *   - 主卡片与趋势图之间新增并排大按钮区：手工录入(实心主色) + 绑定设备(描边白底)
 *   - 趋势图：仅保留 日/周 两档（默认周）；Y 轴固定 40-200；
 *           收缩压/舒张压两条线各自范围带 + 平均值连线 + 数据点；
 *           参考线 SBP=140 / DBP=90；点击数据点弹窗（详细信息）；
 *           空状态插画 + 双按钮；日视图横轴 0-24h 散点连线。
 *   血糖/心率/睡眠/血氧 Tab 保持原模板不变。
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Popup, Input, Button } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { formatDateTime, parseServerTime, formatFriendlyTime } from '@/lib/datetime';
import { judgeBp, getBpPalette, type BpJudgement } from '@/lib/bp-level';
import { judgeHeartRate, getHrPalette, HR_NORMAL_RANGE_TEXT, type HrJudgement } from '@/lib/heart-rate-level';
import {
  judgeBg, getBgPalette, normalizeScene, BG_SCENE_LABEL, BG_TARGET_RANGE,
  BG_SCENE_CODE, BG_SCENE_OPTIONS, formatBgSourceCapsule, sceneKeyToCode,
  type BgJudgement, type BgScene,
} from '@/lib/bg-level';

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

// [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 血压趋势图仅保留 日/周 两档
type BpTrendRange = 'day' | 'week';

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

// [PRD-HEALTH-METRIC-CARD-UNIFY-V1 §七] AI 解读组件（本次 / 趋势），四指标通用
function MetricAiBlock({ profileId, metricType, latestId, metricLabel }: {
  profileId: number;
  metricType: string;
  latestId: number;
  metricLabel: string;
}) {
  const [drawer, setDrawer] = useState<null | { mode: 'single' | 'trend'; loading: boolean; content: string }>(null);
  const [range, setRange] = useState<'7d' | '30d' | '90d'>('7d');

  const callApi = async (mode: 'single' | 'trend') => {
    setDrawer({ mode, loading: true, content: '' });
    try {
      if (mode === 'single') {
        const r: any = await api.post(
          `/api/health-metric-v1/${profileId}/${metricType}/ai-explain-single`,
          { record_id: latestId }
        );
        const d = r?.data?.data ?? r?.data ?? r;
        setDrawer({ mode, loading: false, content: d?.content || '' });
      } else {
        const r: any = await api.post(
          `/api/health-metric-v1/${profileId}/${metricType}/ai-explain-trend`,
          { range }
        );
        const d = r?.data?.data ?? r?.data ?? r;
        const text = [d?.summary, d?.trend && '', d?.trend, d?.advice && '\n建议：', d?.advice]
          .filter(Boolean).join('\n');
        setDrawer({ mode, loading: false, content: text });
      }
    } catch {
      setDrawer({ mode, loading: false, content: '解读失败，请稍后重试。' });
    }
  };

  return (
    <MedicalCard>
      <div style={{ fontSize: 16, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>🤖 AI 解读</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <button
          data-testid={`metric-ai-single-${metricType}`}
          onClick={() => callApi('single')}
          style={{
            flex: 1, padding: '10px 0',
            background: 'linear-gradient(135deg, #38BDF8 0%, #0EA5E9 100%)',
            color: '#fff', border: 'none', borderRadius: 10,
            fontSize: 13, fontWeight: 700, cursor: 'pointer',
          }}
        >🤖 解读本次{metricLabel}</button>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', gap: 4, background: '#F1F5F9', borderRadius: 10, padding: 2, flexShrink: 0 }}>
          {(['7d', '30d', '90d'] as const).map(k => (
            <button
              key={k}
              data-testid={`metric-ai-range-${k}-${metricType}`}
              onClick={() => setRange(k)}
              style={{
                padding: '4px 10px', borderRadius: 8, border: 'none',
                background: range === k ? '#0EA5E9' : 'transparent',
                color: range === k ? '#fff' : '#64748B',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >{k === '7d' ? '7天' : k === '30d' ? '30天' : '90天'}</button>
          ))}
        </div>
        <button
          data-testid={`metric-ai-trend-${metricType}`}
          onClick={() => callApi('trend')}
          style={{
            flex: 1, padding: '8px 0',
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9', borderRadius: 10,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}
        >📈 解读 {range === '7d' ? '7' : range === '30d' ? '30' : '90'} 天趋势</button>
      </div>
      <Popup
        visible={!!drawer}
        onMaskClick={() => setDrawer(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '70vh', overflowY: 'auto' }}
      >
        {drawer && (
          <div data-testid="metric-ai-drawer">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E' }}>
                🤖 AI 解读{drawer.mode === 'single' ? '本次' : '趋势'}
              </span>
              <button onClick={() => setDrawer(null)} style={{ background: 'transparent', border: 'none', fontSize: 20, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ background: '#F8FAFC', borderRadius: 12, padding: 14, minHeight: 100, fontSize: 14, color: '#0F172A', whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {drawer.loading ? '正在分析…' : drawer.content}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF', textAlign: 'center' }}>
              ⚠️ AI 建议仅供参考，不能替代医生诊断
            </div>
          </div>
        )}
      </Popup>
    </MedicalCard>
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
        refresh={fetchHistory}
      />
    );
  }

  // [PRD-GLUCOSE-CARD-OPTIMIZE-V1 2026-05-30] 血糖 Tab 走专属布局（参考血压详情页）
  if (metricType === 'blood_glucose') {
    return (
      <BloodGlucosePage
        history={history}
        latest={latest}
        profileId={profileId}
        devices={devices}
        refresh={fetchHistory}
      />
    );
  }

  // [PRD-HR-ALIGN-BP-V1 2026-06-01] 心率 Tab 走专属精装布局（全面对齐血压详情页）
  if (metricType === 'heart_rate') {
    return (
      <HeartRatePage
        history={history}
        latest={latest}
        profileId={profileId}
        meta={meta}
        refresh={fetchHistory}
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
          {(() => {
            // [PRD-HEART-RATE-DETAIL-RULE-V1 2026-05-31] 心率详情页展示规则
            const isHeartRate = metricType === 'heart_rate';
            const hrRaw = isHeartRate && latest?.value?.value != null ? Number(latest.value.value) : null;
            const hrValue = hrRaw != null && !Number.isNaN(hrRaw) && hrRaw > 0 ? hrRaw : null;
            const hrJudgement = isHeartRate ? judgeHeartRate(hrValue) : null;
            const hrPalette = hrJudgement ? getHrPalette(hrJudgement.color) : null;
            return (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: 13, color: T.brand800 }}>当前值</div>
                  {/* 心率状态胶囊：仅在有数据时显示（无数据隐藏） */}
                  {isHeartRate && hrJudgement && hrPalette && (
                    <span
                      data-testid="hr-status-capsule"
                      style={{
                        padding: '2px 12px', borderRadius: 999, fontSize: 13, fontWeight: 700,
                        background: hrPalette.capsuleBg, color: hrPalette.capsuleText,
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                      }}
                    >
                      <span>{hrJudgement.icon}</span>
                      <span>{hrJudgement.label}</span>
                    </span>
                  )}
                </div>
                <div style={{ marginTop: 6 }}>
                  {isHeartRate ? (
                    // 心率：有数据显示数值，无数据显示「--」+ 引导文案
                    hrValue != null ? (
                      <>
                        <span data-testid="hr-value" style={{ fontSize: 22, fontWeight: 700, color: T.brand700 }}>
                          {hrValue}
                        </span>
                        <span style={{ fontSize: 13, color: T.brand800, marginLeft: 4 }}>{meta.unit}</span>
                        <div style={{ fontSize: 13, color: T.brand600, marginTop: 4 }}>
                          {latest?.value?.period || latest?.value?.activity || ''} · {latest ? formatDateTime(latest.measured_at) : ''}
                        </div>
                      </>
                    ) : (
                      <>
                        <span data-testid="hr-value" style={{ fontSize: 22, fontWeight: 700, color: T.brand700 }}>--</span>
                        <span style={{ fontSize: 13, color: T.brand800, marginLeft: 4 }}>{meta.unit}</span>
                        <div data-testid="hr-empty-hint" style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>
                          暂无数据，点击下方「手工填写」录入心率
                        </div>
                      </>
                    )
                  ) : latest ? (
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
                {/* 心率参考范围那行字：静态文案，恒定显示，不依赖年龄 */}
                {isHeartRate && (
                  <div
                    data-testid="hr-normal-range"
                    style={{
                      marginTop: 10, paddingTop: 10, borderTop: `1px solid ${T.brand100}`,
                      fontSize: 13, color: T.brand600,
                    }}
                  >
                    📋 {HR_NORMAL_RANGE_TEXT}
                  </div>
                )}
              </>
            );
          })()}
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

      {/* 历史记录（PRD-HEALTH-METRIC-CARD-UNIFY-V1 §4：最近 5 条 + 全部入口） */}
      <div style={{ padding: '12px 16px' }}>
        <MedicalCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 600, color: T.brand700 }}>历史记录</span>
            <span
              data-testid="metric-history-all-entry"
              onClick={() => router.push(`/health-metric/${metricType}/history?profileId=${profileId}`)}
              style={{ fontSize: 13, color: T.brand500, cursor: 'pointer', fontWeight: 600 }}
            >全部 ›</span>
          </div>
          {(history?.records || []).length === 0 ? (
            <div style={{ fontSize: 14, color: T.brand800, textAlign: 'center', padding: '24px 0' }}>
              暂无记录，点击右上角「+录入」开始记录
            </div>
          ) : (
            (history?.records || []).slice(0, 5).map((r) => (
              <div
                key={r.id}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 0', borderBottom: `1px solid ${T.brand100}`,
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700 }}>
                    {(formatDateTime(r.measured_at) || '').slice(11, 16)}　
                    {metricType === 'blood_pressure'
                      ? `${r.value?.systolic}/${r.value?.diastolic}`
                      : r.value?.[meta.principalKey]}
                    <span style={{ fontSize: 12, color: T.brand800, marginLeft: 4 }}>{meta.unit}</span>
                  </div>
                  <div style={{ fontSize: 12, color: T.brand600, marginTop: 2, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(r.value?.period || r.value?.activity) && (
                      <span style={{ padding: '1px 6px', background: T.brand100, borderRadius: 999 }}>
                        {r.value?.period || r.value?.activity}
                      </span>
                    )}
                    <span style={{
                      padding: '1px 6px', borderRadius: 999,
                      background: r.source === 'manual' ? T.brand100 : '#d1fae5',
                      color: r.source === 'manual' ? T.brand700 : '#065f46',
                    }}>
                      {r.source === 'manual' ? '手工录入' : '设备同步'}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </MedicalCard>
      </div>

      {/* 🤖 AI 解读（PRD §七：四指标全覆盖） */}
      {latest && (
        <div style={{ padding: '12px 16px' }}>
          <MetricAiBlock
            profileId={profileId}
            metricType={metricType}
            latestId={latest.id}
            metricLabel={meta.label}
          />
        </div>
      )}

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

/**
 * [PRD-GLUCOSE-CARD-ALIGN-BP-V1 2026-05-31] 血糖仪 SVG 图标
 * （仪表主体 + 屏幕 + 试纸/血滴语义，与 BpMeterIcon 风格一致）
 */
function BgMeterIcon({ size = 18, color = '#0EA5E9' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {/* 仪表主体 */}
      <rect x="5" y="3" width="11" height="15" rx="2" stroke={color} strokeWidth="1.6" />
      {/* 屏幕 */}
      <rect x="7.5" y="5.5" width="6" height="4" rx="1" stroke={color} strokeWidth="1.3" />
      {/* 屏幕下方按钮 */}
      <line x1="7.5" y1="12.5" x2="13.5" y2="12.5" stroke={color} strokeWidth="1.3" strokeLinecap="round" />
      {/* 试纸条 */}
      <path d="M16 14 H20 V16 H16" stroke={color} strokeWidth="1.3" strokeLinejoin="round" />
      {/* 血滴 */}
      <path d="M20 18.5 q 1.6 2 0 3.5 q -1.6 -1.5 0 -3.5 Z" stroke={color} strokeWidth="1.2" fill="none" />
    </svg>
  );
}

// [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 仅保留 日/周 两档
const BP_RANGE_OPTS: { key: BpTrendRange; label: string }[] = [
  { key: 'day', label: '日' },
  { key: 'week', label: '周' },
];

/**
 * [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30 §3.3] 首页/详情页统一时间格式化（北京时间口径）：
 *   - 当天     → 今日 HH:mm
 *   - 昨天     → 昨日 HH:mm
 *   - 2~6 天前 → X 天前
 *   - 同年超过 6 天 → MM-DD
 *   - 跨年       → YYYY-MM-DD
 *
 * [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 改为统一调用 formatFriendlyTime（北京时间口径），
 * 修复"今日 HH:mm 少 8 小时"的时区 Bug。
 */
export function formatBpSyncTime(measuredAt?: string | null): string {
  if (!measuredAt) return '';
  const text = formatFriendlyTime(measuredAt);
  if (!text) return '';
  return text;
}

/**
 * [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30 §3.3] 来源文案统一格式化：
 *   - manual              → 手工录入
 *   - device:{deviceName} → {deviceName}·自动同步
 *   - 其它非空 source     → {source}·自动同步
 */
export function formatBpSource(source?: string | null, deviceName?: string | null): string {
  if (!source) return '手工录入';
  const s = String(source).trim();
  if (!s || s === 'manual') return '手工录入';
  // 优先取设备名（如有）
  const dn = (deviceName || '').trim();
  if (dn) return `${dn}·自动同步`;
  // 兼容形如 device:omron 或 omron
  const last = s.split(':').pop() || s;
  const map: Record<string, string> = {
    omron: '欧姆龙血压计',
    huawei_watch: '华为 Watch',
    xiaomi_band: '小米手环',
    bp_meter: '血压计',
  };
  return `${map[last] || last}·自动同步`;
}

/** [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30 §3.3] 首页/详情页统一展示「时间 · 来源」单行文案。 */
export function formatBpTimeSource(measuredAt?: string | null, source?: string | null, deviceName?: string | null): string {
  const t = formatBpSyncTime(measuredAt);
  const s = formatBpSource(source, deviceName);
  if (!t) return s;
  return `${t} · ${s}`;
}

/** [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30 §6] 单条记录档位文案（与详情页文案一致）。 */
export function bpLevelLabel(sbp?: number | null, dbp?: number | null): string {
  const j = judgeBp(sbp ?? null, dbp ?? null);
  return j ? j.label : '';
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
  refresh: () => Promise<void>;
}

function BloodPressurePage(props: BloodPressurePageProps) {
  const { history, latest, popupVisible, setPopupVisible, formValues, setFormValues,
    periodValue, setPeriodValue, meta, saving, handleSave, refresh } = props;
  const router = useRouter();

  // [PRD-BP-DETAIL-OPTIMIZE-V1 AC-04~AC-08] 历史记录「...」操作面板 + 修改 + 删除
  const [actionRecord, setActionRecord] = useState<MetricRecord | null>(null);
  const [editRecord, setEditRecord] = useState<MetricRecord | null>(null);
  const [editSbp, setEditSbp] = useState('');
  const [editDbp, setEditDbp] = useState('');
  const [editPeriod, setEditPeriod] = useState('');
  const [deletingRecord, setDeletingRecord] = useState<MetricRecord | null>(null);

  // [PRD-BP-DETAIL-OPTIMIZE-V1 AC-06] 修改保存：PUT 完整更新原记录，不新增重复记录
  const handleEditSave = useCallback(async () => {
    if (!editRecord || !props.profileId) return;
    const s = Number(editSbp);
    const d = Number(editDbp);
    if (!editSbp || Number.isNaN(s) || !editDbp || Number.isNaN(d)) {
      showToast('请输入有效的收缩压/舒张压', 'fail');
      return;
    }
    if (s < 40 || s > 300 || d < 20 || d > 200) {
      showToast('血压数值超出合理范围', 'fail');
      return;
    }
    try {
      await api.put(`/api/health-profile-v3/${props.profileId}/metric/blood_pressure/${editRecord.id}`, {
        value: { systolic: s, diastolic: d, period: editPeriod || undefined },
        measured_at: editRecord.measured_at,
      });
      showToast('已更新', 'success');
      setEditRecord(null);
      await refresh();
    } catch {
      showToast('更新失败', 'fail');
    }
  }, [editRecord, editSbp, editDbp, editPeriod, props.profileId, refresh]);

  // [PRD-BP-DETAIL-OPTIMIZE-V1 AC-08] 删除：确认后 toast「已删除」+ 列表刷新
  const handleDelete = useCallback(async (record: MetricRecord) => {
    if (!props.profileId) return;
    try {
      await api.delete(`/api/health-profile-v3/${props.profileId}/metric/blood_pressure/${record.id}`);
      showToast('已删除', 'success');
      setDeletingRecord(null);
      await refresh();
    } catch {
      showToast('删除失败', 'fail');
    }
  }, [props.profileId, refresh]);

  // [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30 §5.2] 默认选中"周"，仅保留 日/周
  const [range, setRange] = useState<BpTrendRange>('week');
  // 数据点点击弹窗
  const [pointPopup, setPointPopup] = useState<BpPointDetail | null>(null);

  // [PRD-BP-AI-EXPLAIN-V1 2026-05-31] AI 解读抽屉与缓存（对齐血糖）
  const [aiDrawer, setAiDrawer] = useState<{ mode: 'single' | 'trend'; loading: boolean; text: string } | null>(null);
  const aiCacheRef = (typeof window !== 'undefined') ? ((window as any).__bpAiCache ||= new Map<string, { ts: number; text: string }>()) : new Map();

  const sbp = latest?.value?.systolic != null ? Number(latest.value.systolic) : null;
  const dbp = latest?.value?.diastolic != null ? Number(latest.value.diastolic) : null;
  const judgement: BpJudgement | null = useMemo(() => judgeBp(sbp, dbp), [sbp, dbp]);

  // 无数据态默认走"正常蓝"色板，提示文案适配
  const palette = getBpPalette(judgement?.color ?? 'blue');

  const syncText = useMemo(() => {
    if (!latest) return '尚无血压记录 · 请录入或绑定设备';
    return formatBpTimeSource(latest.measured_at, latest.source);
  }, [latest]);

  const handleBindDeviceClick = () => {
    showToast('即将上线', 'success');
    // 埋点（占位）：health_archive.bp.bind_device.click
    try {
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

  // [PRD §5.6] 当前周期是否无任何数据
  const records: MetricRecord[] = history?.records || [];
  const isEmptyForRange = useMemo(() => {
    if (range === 'week') {
      // 最近 7 天聚合：trend_systolic / trend_diastolic 全为 null
      const s = history?.trend_systolic || [];
      const d = history?.trend_diastolic || [];
      const hasAny = [...s, ...d].some(v => v != null);
      return !hasAny;
    }
    // 日视图：仅看今天的记录（按北京时间口径）
    const today = new Date();
    const todayBj = new Date(today.getTime() + 8 * 60 * 60 * 1000);
    return records.filter(r => {
      const d = parseServerTime(r.measured_at);
      if (!d) return false;
      const bj = new Date(d.getTime() + 8 * 60 * 60 * 1000);
      return bj.getUTCFullYear() === todayBj.getUTCFullYear()
        && bj.getUTCMonth() === todayBj.getUTCMonth()
        && bj.getUTCDate() === todayBj.getUTCDate();
    }).length === 0;
  }, [range, history, records]);

  // [PRD-BP-AI-EXPLAIN-V1 2026-05-31] AI 解读 — 接入真实大模型，规则文案降级（对齐血糖）
  const requestAi = useCallback(async (mode: 'single' | 'trend') => {
    // [PRD-BP-DETAIL-OPTIMIZE-V1 AC-02] 无血压记录时点击解读：toast 轻提示，不进入解读流程
    if (mode === 'single' && !latest?.id) {
      showToast('暂无血压记录，请先录入一次再点击解读。', 'success');
      return;
    }
    const cacheKey = mode === 'single' ? `single:${latest?.id ?? 0}` : `trend:${range}`;
    const cached = aiCacheRef.get(cacheKey);
    if (cached && Date.now() - cached.ts < 5 * 60 * 1000) {
      setAiDrawer({ mode, loading: false, text: cached.text });
      return;
    }
    setAiDrawer({ mode, loading: true, text: '' });
    try {
      let text = '';
      if (mode === 'single') {
        if (!latest?.id) {
          text = '暂无血压记录，请先录入一次再点击解读。';
        } else {
          try {
            const r: any = await api.post('/api/bp-v1/ai-explain-single', {
              record_id: Number(latest.id),
              profile_id: props.profileId,
            });
            const d = r?.data?.data ?? r?.data ?? r;
            text = d?.content || '';
            if (!text) throw new Error('empty');
          } catch {
            const j = judgement;
            const sStr = sbp != null ? sbp : '-';
            const dStr = dbp != null ? dbp : '-';
            if (!j) {
              text = '暂无可解读的血压数据。';
            } else if (j.level === 'normal') {
              text = `本次血压 ${sStr}/${dStr} mmHg，属于正常范围。建议保持规律作息、清淡饮食和适量运动，继续按当前节奏监测。`;
            } else if (j.level === 'mild_high') {
              text = `本次血压 ${sStr}/${dStr} mmHg，属于轻度偏高（正常高值）。建议减少高盐高脂饮食、控制体重、每天散步 30 分钟，1 周后复测；若持续偏高请就医评估。`;
            } else if (j.level === 'mid_high') {
              text = `本次血压 ${sStr}/${dStr} mmHg，属于中度偏高（1 级高血压）。建议低盐低脂饮食、戒烟限酒、规律运动，并尽快到心内科或全科门诊就诊评估是否需要药物治疗。`;
            } else if (j.level === 'severe_high') {
              text = `本次血压 ${sStr}/${dStr} mmHg，属于严重偏高。建议立即静坐休息 15 分钟后复测，若仍持续偏高请尽快前往医院急诊或心内科就诊。`;
            } else if (j.level === 'low') {
              text = `本次血压 ${sStr}/${dStr} mmHg，偏低。建议适量饮水、慢起慢站，避免空腹时间过长；若伴有头晕乏力请及时就医。`;
            } else {
              text = `本次血压 ${sStr}/${dStr} mmHg。建议保持规律监测，如有不适请及时就医。`;
            }
          }
        }
      } else {
        const rangeKey: '7d' | '30d' = range === 'week' ? '7d' : '7d';
        try {
          const r: any = await api.post('/api/bp-v1/ai-explain-trend', {
            range: rangeKey,
            profile_id: props.profileId,
          });
          const d = r?.data?.data ?? r?.data ?? r;
          const lines: string[] = [];
          if (d?.summary) lines.push(d.summary);
          if (d?.trend) lines.push('', d.trend);
          if (d?.advice) lines.push('', '建议：', d.advice);
          text = lines.join('\n');
          if (!text.trim()) throw new Error('empty');
        } catch {
          text = '基于近期血压数据，建议保持低盐低脂饮食与适量运动，每天固定时段监测血压并记录；如长期偏高请尽快就医评估。';
        }
      }
      aiCacheRef.set(cacheKey, { ts: Date.now(), text });
      setAiDrawer({ mode, loading: false, text });
    } catch {
      setAiDrawer({ mode, loading: false, text: '解读失败，请稍后重试。' });
    }
  }, [latest, range, aiCacheRef, props.profileId, judgement, sbp, dbp]);

  return (
    <div data-testid="bp-tab-page" style={{ background: '#F4F7FB', minHeight: '100vh', paddingBottom: 24 }}>
      <GreenNavBar>血压详情</GreenNavBar>

      {/* [PRD §四] 顶部主卡片保持原样：主数值 + 同步信息 + 状态胶囊（移除内嵌小按钮） */}
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

          {/* 同步信息行（仅展示「时间·来源」） */}
          <div style={{ marginTop: 14, textAlign: 'center' }}>
            <span data-testid="bp-sync-text" style={{ fontSize: 13, color: palette.text, opacity: 0.85 }}>
              {syncText}
            </span>
          </div>

          {/* 状态胶囊 */}
          {judgement && (
            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center' }}>
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

      {/* [PRD-BP-DETAIL-OPTIMIZE-V2 2026-06-01 §需求1] AI 解读本次血压：从趋势图区移动到顶部最新记录卡片正下方 */}
      <div style={{ padding: '12px 16px 0' }}>
        <button
          data-testid="bp-ai-single"
          onClick={() => requestAi('single')}
          style={{
            width: '100%', height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, #38BDF8 0%, #0EA5E9 100%)', color: '#fff',
            border: 'none', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(14,165,233,0.24)',
          }}
        >🤖 AI 解读本次血压</button>
      </div>

      {/* [PRD §四] 主卡片 ↔ 趋势图之间：并排大按钮（手工录入实心 + 绑定设备描边） */}
      <div data-testid="bp-action-row" style={{ padding: '12px 16px 0', display: 'flex', gap: 10 }}>
        <button
          data-testid="bp-action-manual"
          onClick={() => setPopupVisible(true)}
          style={{
            flex: 1, height: 44, borderRadius: 12, border: 'none',
            background: '#0EA5E9', color: '#fff',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(14,165,233,0.24)',
          }}
        >
          <PencilIcon size={16} color="#fff" />
          <span>手工录入</span>
        </button>
        <button
          data-testid="bp-action-bind"
          onClick={handleBindDeviceClick}
          style={{
            flex: 1, height: 44, borderRadius: 12,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
          }}
        >
          <BpMeterIcon size={16} color="#0EA5E9" />
          <span>绑定设备</span>
        </button>
      </div>

      {/* [PRD §五] 最近 7 天趋势 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div
          data-testid="bp-trend-card"
          style={{
            background: '#fff', borderRadius: 16, padding: '14px 14px 12px',
            boxShadow: '0 2px 10px rgba(14,165,233,0.06)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>
              {range === 'day' ? '今日趋势' : '最近 7 天趋势'}
            </span>
            <div data-testid="bp-range-segmented" style={{ display: 'flex', gap: 4, background: '#F1F5F9', borderRadius: 12, padding: 2 }}>
              {BP_RANGE_OPTS.map(opt => (
                <button
                  key={opt.key}
                  data-testid={`bp-range-${opt.key}`}
                  data-active={range === opt.key ? 'true' : 'false'}
                  onClick={() => setRange(opt.key)}
                  style={{
                    padding: '4px 14px', borderRadius: 10, border: 'none',
                    background: range === opt.key ? '#0EA5E9' : 'transparent',
                    color: range === opt.key ? '#fff' : '#64748B',
                    fontSize: 12, fontWeight: 700, cursor: 'pointer',
                    transition: 'background 200ms ease',
                  }}
                >{opt.label}</button>
              ))}
            </div>
          </div>

          {isEmptyForRange ? (
            <BpEmptyState
              range={range}
              onManual={() => setPopupVisible(true)}
              onBind={handleBindDeviceClick}
            />
          ) : range === 'week' ? (
            <BpWeekTrendChart
              records={records}
              labels={history?.trend_day_labels || []}
              dates={history?.trend_dates || []}
              onPointClick={setPointPopup}
            />
          ) : (
            <BpDayTrendChart
              records={records}
              onPointClick={setPointPopup}
            />
          )}

          {/* 图例 + 参考线说明 */}
          {!isEmptyForRange && (
            <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 14 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
                <span style={{ width: 18, height: 3, background: '#1B4DA0', display: 'inline-block', borderRadius: 2 }} />
                收缩压（参考线 140）
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
                <span style={{ width: 18, height: 3, background: '#7DB1F2', display: 'inline-block', borderRadius: 2 }} />
                舒张压（参考线 90）
              </span>
            </div>
          )}
        </div>
      </div>

      {/* [PRD-BP-DETAIL-OPTIMIZE-V2 2026-06-01 §需求1] 趋势图区只保留「AI 解读趋势」按钮（「解读本次」已移到顶部主卡片下方） */}
      <div style={{ padding: '12px 16px 0' }}>
        <button
          data-testid="bp-ai-trend"
          onClick={() => requestAi('trend')}
          style={{
            width: '100%', height: 40, borderRadius: 10,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9', fontSize: 14, fontWeight: 700, cursor: 'pointer',
          }}
        >🤖 AI 解读趋势</button>
      </div>

      {/* 历史记录（PRD-HEALTH-METRIC-CARD-UNIFY-V1 §4：最近 5 条 + 全部入口） */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: '14px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>历史记录</span>
            <span
              data-testid="bp-history-all-entry"
              onClick={() => router.push(`/health-metric/blood_pressure/history?profileId=${props.profileId}`)}
              style={{ fontSize: 13, color: '#0EA5E9', cursor: 'pointer', fontWeight: 600 }}
            >全部 ›</span>
          </div>
          {(history?.records || []).length === 0 ? (
            <div style={{ fontSize: 14, color: '#6B7280', textAlign: 'center', padding: '24px 0' }}>
              暂无记录，点击右上角「+录入」开始记录
            </div>
          ) : (
            (history?.records || []).slice(0, 5).map((r) => {
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
                      {formatDateTime(r.measured_at)} · {formatBpSource(r.source)}
                      {r.value?.period ? ` · ${r.value.period}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
                    {/* [PRD-BP-DETAIL-OPTIMIZE-V1 AC-04] 「...」三点入口 → 底部操作面板 */}
                    <button
                      data-testid={`bp-row-more-${r.id}`}
                      onClick={(e) => { e.stopPropagation(); setActionRecord(r); }}
                      style={{
                        background: 'transparent', border: 'none', cursor: 'pointer',
                        fontSize: 20, fontWeight: 700, color: '#94A3B8', lineHeight: 1,
                        padding: '0 4px',
                      }}
                      aria-label="更多操作"
                    >⋯</button>
                  </div>
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

      {/* [PRD-BP-DETAIL-OPTIMIZE-V1 AC-04~AC-11] 历史记录「...」底部操作面板（修改 / 删除）— 与血糖共用模板 */}
      <MetricActionSheet
        testid="bp-action-sheet"
        record={actionRecord}
        onClose={() => setActionRecord(null)}
        onEdit={(r) => {
          setActionRecord(null);
          setEditRecord(r);
          setEditSbp(r.value?.systolic != null ? String(r.value.systolic) : '');
          setEditDbp(r.value?.diastolic != null ? String(r.value.diastolic) : '');
          setEditPeriod(typeof r.value?.period === 'string' ? r.value.period : '');
        }}
        onDelete={(r) => { setActionRecord(null); setDeletingRecord(r); }}
      />

      {/* [PRD-BP-DETAIL-OPTIMIZE-V1 AC-06] 修改血压记录 - 完整修改 value / 场景 / 时间，PUT 更新 */}
      <Popup
        visible={!!editRecord}
        onMaskClick={() => setEditRecord(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '85vh', overflowY: 'auto' }}
      >
        {editRecord && (
          <div data-testid="bp-edit-popup">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>编辑血压记录</span>
              <button onClick={() => setEditRecord(null)} style={{ background: 'transparent', border: 'none', fontSize: 18, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
              {formatDateTime(editRecord.measured_at)}
            </div>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>收缩压（mmHg）</div>
              <Input
                data-testid="bp-edit-systolic"
                type="number"
                value={editSbp}
                onChange={(v) => setEditSbp(v)}
                style={{ '--font-size': '16px', padding: '10px 12px', background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' } as any}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>舒张压（mmHg）</div>
              <Input
                data-testid="bp-edit-diastolic"
                type="number"
                value={editDbp}
                onChange={(v) => setEditDbp(v)}
                style={{ '--font-size': '16px', padding: '10px 12px', background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' } as any}
              />
            </div>

            {meta.period && (
              <>
                <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>时段</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
                  {meta.period.options.map((opt) => (
                    <button
                      key={opt}
                      data-testid={`bp-edit-period-${opt}`}
                      onClick={() => setEditPeriod(opt)}
                      style={{
                        padding: '6px 14px',
                        background: editPeriod === opt ? '#0ea5e9' : '#e0f2fe',
                        color: editPeriod === opt ? '#fff' : '#0369a1',
                        border: 'none', borderRadius: 18, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >{opt}</button>
                  ))}
                </div>
              </>
            )}

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                data-testid="bp-edit-delete"
                onClick={() => setDeletingRecord(editRecord)}
                style={{ flex: 1, padding: '10px 0', background: '#fff', color: '#DC2626',
                  border: '1px solid #DC2626', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >删除</button>
              <button
                data-testid="bp-edit-save"
                onClick={handleEditSave}
                style={{ flex: 2, padding: '10px 0', background: '#0ea5e9', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >保存</button>
            </div>
          </div>
        )}
      </Popup>

      {/* [PRD-BP-DETAIL-OPTIMIZE-V1 AC-07] 删除二次确认 */}
      <Popup
        visible={!!deletingRecord}
        onMaskClick={() => setDeletingRecord(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        {deletingRecord && (
          <div data-testid="bp-delete-confirm">
            <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E', marginBottom: 10 }}>确认删除</div>
            <div style={{ fontSize: 14, color: '#374151', marginBottom: 16 }}>
              确认删除这条记录？此操作不可撤销
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 8 }}>
                {formatDateTime(deletingRecord.measured_at)} · {deletingRecord.value?.systolic ?? '-'}/{deletingRecord.value?.diastolic ?? '-'} mmHg
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setDeletingRecord(null)}
                style={{ flex: 1, padding: '10px 0', background: '#fff', color: '#475569',
                  border: '1px solid #CBD5E1', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >取消</button>
              <button
                data-testid="bp-delete-confirm-btn"
                onClick={() => { handleDelete(deletingRecord); setEditRecord(null); }}
                style={{ flex: 1, padding: '10px 0', background: '#DC2626', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >确认删除</button>
            </div>
          </div>
        )}
      </Popup>

      {/* [PRD §5.5] 数据点点击弹窗（详版） */}
      <BpPointPopup detail={pointPopup} onClose={() => setPointPopup(null)} />

      {/* [PRD-BP-AI-EXPLAIN-V1 2026-05-31] AI 解读抽屉（对齐血糖） */}
      <Popup
        visible={!!aiDrawer}
        onMaskClick={() => setAiDrawer(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '70vh', overflowY: 'auto' }}
      >
        {aiDrawer && (
          <div data-testid="bp-ai-drawer">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E' }}>🤖 AI 解读</span>
              <button onClick={() => setAiDrawer(null)} style={{ background: 'transparent', border: 'none', fontSize: 20, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 14 }}>
              {aiDrawer.mode === 'single'
                ? `基于：${latest ? formatDateTime(latest.measured_at) + ' 血压 ' + (sbp ?? '-') + '/' + (dbp ?? '-') + ' mmHg' : '当前无记录'}`
                : `基于：${range === 'day' ? '今天' : '近 7 天'}所有血压记录`}
            </div>
            <div style={{ background: '#F8FAFC', borderRadius: 12, padding: 14, minHeight: 100, fontSize: 14, color: '#0F172A', whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {aiDrawer.loading ? '正在分析…' : aiDrawer.text}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF', textAlign: 'center' }}>
              ⚠️ AI 建议仅供参考，不能替代医生诊断
            </div>
          </div>
        )}
      </Popup>
    </div>
  );
}

// [PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 内部数据结构
export interface BpPointDetail {
  measured_at: string;
  systolic: number | null;
  diastolic: number | null;
  label: string;          // 档位名（如 "轻度偏高"）
  level?: string | null;
  period?: string | null;  // 测量时段
  source: string;
  /** 仅周视图传入：当日所有原始记录数（>1 时弹窗顶部加注释） */
  recordsCountInDay?: number;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

function ymd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

/** [PRD §5.5] 数据点点击弹窗 */
function BpPointPopup({ detail, onClose }: { detail: BpPointDetail | null; onClose: () => void }) {
  const j = detail ? judgeBp(detail.systolic, detail.diastolic) : null;
  const palette = getBpPalette(j?.color ?? 'blue');
  return (
    <Popup
      visible={!!detail}
      onMaskClick={onClose}
      bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 18 }}
    >
      {detail && (
        <div data-testid="bp-point-popup">
          <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E', marginBottom: 10 }}>
            血压详情
          </div>
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 8 }}>
            {formatDateTime(detail.measured_at)}
          </div>
          <div style={{ height: 1, background: '#E5E7EB', margin: '8px 0' }} />
          <DetailRow k="收缩压" v={detail.systolic != null ? `${detail.systolic} mmHg` : '—'} />
          <DetailRow k="舒张压" v={detail.diastolic != null ? `${detail.diastolic} mmHg` : '—'} />
          <DetailRow k="档位" v={
            <span data-testid="bp-point-level" style={{
              padding: '2px 10px', borderRadius: 999,
              background: palette.capsuleBg, color: palette.capsuleText,
              fontSize: 12, fontWeight: 700,
            }}>{detail.label || '—'}</span>
          } />
          {detail.period && <DetailRow k="测量时段" v={detail.period} />}
          <DetailRow k="来源" v={formatBpSource(detail.source)} />
          {detail.recordsCountInDay && detail.recordsCountInDay > 1 && (
            <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 6 }}>
              当日共 {detail.recordsCountInDay} 次测量，此处显示当日均值
            </div>
          )}
          <Button
            block color="primary" onClick={onClose}
            style={{ '--background-color': '#0EA5E9', '--border-radius': '12px', height: 40, fontSize: 14, marginTop: 14 } as any}
          >知道了</Button>
        </div>
      )}
    </Popup>
  );
}

function DetailRow({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0' }}>
      <span style={{ fontSize: 13, color: '#6B7280' }}>{k}</span>
      <span style={{ fontSize: 14, color: '#0C4A6E', fontWeight: 600 }}>{v}</span>
    </div>
  );
}

/** [PRD §5.6] 趋势图空状态 */
function BpEmptyState({ range, onManual, onBind }: { range: BpTrendRange; onManual: () => void; onBind: () => void }) {
  return (
    <div data-testid="bp-trend-empty" style={{ padding: '20px 8px 8px', textAlign: 'center' }}>
      {/* 简洁血压计插画（行内 SVG，主色调） */}
      <svg width="96" height="72" viewBox="0 0 96 72" style={{ display: 'block', margin: '0 auto 8px' }} aria-hidden="true">
        <rect x="14" y="20" width="52" height="34" rx="6" stroke="#0EA5E9" strokeWidth="1.6" fill="#F0F9FF" />
        <circle cx="32" cy="37" r="8" stroke="#0EA5E9" strokeWidth="1.6" fill="#fff" />
        <line x1="32" y1="37" x2="36" y2="32" stroke="#EF4444" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M66 28 Q 82 28 82 38 Q 82 50 66 50" stroke="#0EA5E9" strokeWidth="1.6" fill="none" />
        <circle cx="84" cy="55" r="3" stroke="#0EA5E9" strokeWidth="1.6" fill="#fff" />
        <line x1="48" y1="32" x2="58" y2="32" stroke="#94A3B8" strokeWidth="1.4" />
        <line x1="48" y1="40" x2="58" y2="40" stroke="#94A3B8" strokeWidth="1.4" />
        <line x1="48" y1="48" x2="55" y2="48" stroke="#94A3B8" strokeWidth="1.4" />
      </svg>
      <div style={{ fontSize: 15, fontWeight: 700, color: '#0C4A6E' }}>
        {range === 'day' ? '今日还没有测量记录' : '本周还没有测量记录'}
      </div>
      <div style={{ fontSize: 13, color: '#6B7280', marginTop: 6 }}>
        点击上方"手工录入"或"绑定设备"开始记录吧
      </div>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 14 }}>
        <button
          data-testid="bp-empty-manual"
          onClick={onManual}
          style={{
            padding: '8px 18px', borderRadius: 10, border: 'none',
            background: '#0EA5E9', color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer',
          }}
        >立即录入</button>
        <button
          data-testid="bp-empty-bind"
          onClick={onBind}
          style={{
            padding: '8px 18px', borderRadius: 10,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9',
            fontSize: 13, fontWeight: 700, cursor: 'pointer',
          }}
        >绑定设备</button>
      </div>
    </div>
  );
}

// ─── 趋势图常量 ──────────────────────────────────────────────────
// [PRD §5.3.4] Y 轴固定 40 - 200 mmHg
const BP_Y_MIN = 40;
const BP_Y_MAX = 200;
const BP_Y_TICKS = [40, 80, 120, 160, 200];
// [PRD §5.3.5] 参考线 SBP=140 / DBP=90
const BP_REF_SBP = 140;
const BP_REF_DBP = 90;

const BP_SBP_LINE = '#1B4DA0';   // 收缩压：深蓝
const BP_DBP_LINE = '#7DB1F2';   // 舒张压：浅蓝
const BP_SBP_BAND = 'rgba(27,77,160,0.10)';   // 范围带：深蓝 10%
const BP_DBP_BAND = 'rgba(125,177,242,0.18)'; // 范围带：浅蓝 18%

/** 简单平滑曲线（Catmull-Rom 转 Bezier） */
function smoothPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return '';
  if (points.length === 1) return `M${points[0].x},${points[0].y}`;
  const segs: string[] = [`M${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(i + 2, points.length - 1)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    segs.push(`C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`);
  }
  return segs.join(' ');
}

/** [PRD §5.3] 周视图趋势图：每天范围带 + 平均值平滑连线 + 数据点 */
function BpWeekTrendChart({
  records, labels, dates, onPointClick,
}: {
  records: MetricRecord[];
  labels: string[];
  dates: string[];
  onPointClick: (d: BpPointDetail) => void;
}) {
  const W = 340, H = 220;
  const PAD = { top: 14, right: 14, bottom: 28, left: 36 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  // 构造最近 7 天日期序列（按北京时间口径；与后端 trend_dates 对齐；若空则前端兜底生成）
  const today = new Date();
  const todayBj = new Date(today.getTime() + 8 * 60 * 60 * 1000);
  const days: string[] = (dates && dates.length === 7) ? dates : Array.from({ length: 7 }, (_, i) => {
    const d = new Date(Date.UTC(todayBj.getUTCFullYear(), todayBj.getUTCMonth(), todayBj.getUTCDate() - (6 - i)));
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(d.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  });
  const dayLabels: string[] = (labels && labels.length === 7) ? labels : days.map((s, i) => i === 6 ? '今日' : s.slice(5).replace('-', '/'));

  // 按日聚合 sbp / dbp 数据
  type DayAgg = {
    sbpMin: number | null; sbpMax: number | null; sbpAvg: number | null;
    dbpMin: number | null; dbpMax: number | null; dbpAvg: number | null;
    count: number;
    representative?: MetricRecord;
  };
  const aggMap: Record<string, DayAgg> = {};
  days.forEach(d => {
    aggMap[d] = { sbpMin: null, sbpMax: null, sbpAvg: null, dbpMin: null, dbpMax: null, dbpAvg: null, count: 0 };
  });
  records.forEach(r => {
    const dRaw = parseServerTime(r.measured_at);
    if (!dRaw) return;
    const dBj = new Date(dRaw.getTime() + 8 * 60 * 60 * 1000);
    const y = dBj.getUTCFullYear();
    const m = String(dBj.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(dBj.getUTCDate()).padStart(2, '0');
    const key = `${y}-${m}-${dd}`;
    if (!(key in aggMap)) return;
    const agg = aggMap[key];
    const sv = r.value?.systolic != null ? Number(r.value.systolic) : null;
    const dv = r.value?.diastolic != null ? Number(r.value.diastolic) : null;
    if (sv != null && !Number.isNaN(sv)) {
      agg.sbpMin = agg.sbpMin == null ? sv : Math.min(agg.sbpMin, sv);
      agg.sbpMax = agg.sbpMax == null ? sv : Math.max(agg.sbpMax, sv);
      agg.sbpAvg = agg.sbpAvg == null ? sv : agg.sbpAvg + sv; // 累加，下方均值化
    }
    if (dv != null && !Number.isNaN(dv)) {
      agg.dbpMin = agg.dbpMin == null ? dv : Math.min(agg.dbpMin, dv);
      agg.dbpMax = agg.dbpMax == null ? dv : Math.max(agg.dbpMax, dv);
      agg.dbpAvg = agg.dbpAvg == null ? dv : agg.dbpAvg + dv;
    }
    agg.count += 1;
    // 取当日最近一条作为代表（records 由后端按 measured_at desc 返回）
    if (!agg.representative) agg.representative = r;
  });
  // 把 sum 转为均值
  Object.values(aggMap).forEach(a => {
    if (a.count > 0) {
      if (a.sbpAvg != null) a.sbpAvg = +(a.sbpAvg / Math.max(a.count, 1)).toFixed(1);
      if (a.dbpAvg != null) a.dbpAvg = +(a.dbpAvg / Math.max(a.count, 1)).toFixed(1);
    }
  });

  const xScale = (i: number) => PAD.left + (i / 6) * cw;
  const yScale = (v: number) => PAD.top + ch - ((v - BP_Y_MIN) / (BP_Y_MAX - BP_Y_MIN)) * ch;

  // 构造范围带 path（上沿 max → 下沿 min）
  const buildBand = (kind: 'sbp' | 'dbp'): string => {
    const ups: { x: number; y: number }[] = [];
    const downs: { x: number; y: number }[] = [];
    days.forEach((d, i) => {
      const a = aggMap[d];
      const max = kind === 'sbp' ? a.sbpMax : a.dbpMax;
      const min = kind === 'sbp' ? a.sbpMin : a.dbpMin;
      if (max != null && min != null && max !== min) {
        ups.push({ x: xScale(i), y: yScale(max) });
        downs.push({ x: xScale(i), y: yScale(min) });
      }
    });
    if (ups.length < 2) return '';
    const upPath = ups.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const downPath = downs.slice().reverse().map(p => `L${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    return `${upPath} ${downPath} Z`;
  };

  const sbpAvgPoints: { x: number; y: number; i: number; v: number }[] = [];
  const dbpAvgPoints: { x: number; y: number; i: number; v: number }[] = [];
  days.forEach((d, i) => {
    const a = aggMap[d];
    if (a.sbpAvg != null) sbpAvgPoints.push({ x: xScale(i), y: yScale(a.sbpAvg), i, v: a.sbpAvg });
    if (a.dbpAvg != null) dbpAvgPoints.push({ x: xScale(i), y: yScale(a.dbpAvg), i, v: a.dbpAvg });
  });
  const sbpLinePath = smoothPath(sbpAvgPoints);
  const dbpLinePath = smoothPath(dbpAvgPoints);

  // 异常天背景：当日 sbpAvg/dbpAvg 落入"偏高/严重"档
  const abnormalDays: number[] = [];
  days.forEach((d, i) => {
    const a = aggMap[d];
    const j = judgeBp(a.sbpAvg, a.dbpAvg);
    if (j && j.level !== 'normal') abnormalDays.push(i);
  });

  const handlePointClick = (i: number) => {
    const dKey = days[i];
    const a = aggMap[dKey];
    if (!a || a.count === 0) return;
    const rep = a.representative;
    const j = judgeBp(a.sbpAvg, a.dbpAvg);
    onPointClick({
      measured_at: rep ? rep.measured_at : dKey,
      systolic: a.sbpAvg,
      diastolic: a.dbpAvg,
      label: j ? j.label : '',
      level: j ? j.level : null,
      period: rep?.value?.period || rep?.value?.activity || null,
      source: rep ? rep.source : 'manual',
      recordsCountInDay: a.count,
    });
  };

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
      data-testid="bp-trend-svg"
      data-bp-range="week"
    >
      {/* 异常天背景 */}
      {abnormalDays.map(i => {
        const x1 = xScale(Math.max(i - 0.5, 0));
        const x2 = xScale(Math.min(i + 0.5, 6));
        return (
          <rect
            key={`ab${i}`}
            data-testid="bp-abnormal-bg"
            x={x1} y={PAD.top}
            width={Math.max(x2 - x1, 4)}
            height={ch}
            fill="rgba(245,183,61,0.10)"
          />
        );
      })}
      {/* Y 轴网格 + 标签 */}
      {BP_Y_TICKS.map(v => {
        const y = yScale(v);
        return (
          <g key={`g${v}`}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#E5E7EB" strokeWidth={0.6} />
            <text x={PAD.left - 4} y={y + 3} textAnchor="end" fill="#9CA3AF" fontSize={10}>{v}</text>
          </g>
        );
      })}
      {/* 参考线 SBP=140 / DBP=90 */}
      <line
        data-testid="bp-ref-sbp"
        x1={PAD.left} x2={W - PAD.right}
        y1={yScale(BP_REF_SBP)} y2={yScale(BP_REF_SBP)}
        stroke="#9CA3AF" strokeWidth={0.8} strokeDasharray="4 3"
      />
      <text x={W - PAD.right - 2} y={yScale(BP_REF_SBP) - 3} textAnchor="end" fill="#9CA3AF" fontSize={9}>SBP 140</text>
      <line
        data-testid="bp-ref-dbp"
        x1={PAD.left} x2={W - PAD.right}
        y1={yScale(BP_REF_DBP)} y2={yScale(BP_REF_DBP)}
        stroke="#9CA3AF" strokeWidth={0.8} strokeDasharray="4 3"
      />
      <text x={W - PAD.right - 2} y={yScale(BP_REF_DBP) - 3} textAnchor="end" fill="#9CA3AF" fontSize={9}>DBP 90</text>
      {/* X 轴标签 */}
      {dayLabels.map((lab, i) => {
        const isToday = i === 6 || lab === '今日';
        return (
          <text
            key={`x${i}`}
            x={xScale(i)} y={H - 8}
            textAnchor="middle"
            fill={isToday ? '#0EA5E9' : '#9CA3AF'}
            fontSize={isToday ? 11 : 10}
            fontWeight={isToday ? 700 : 400}
          >{lab}</text>
        );
      })}
      {/* 范围带 */}
      <path data-testid="bp-band-sbp" d={buildBand('sbp')} fill={BP_SBP_BAND} />
      <path data-testid="bp-band-dbp" d={buildBand('dbp')} fill={BP_DBP_BAND} />
      {/* 平均值平滑连线 */}
      {sbpLinePath && <path d={sbpLinePath} fill="none" stroke={BP_SBP_LINE} strokeWidth={2.4} strokeLinecap="round" />}
      {dbpLinePath && <path d={dbpLinePath} fill="none" stroke={BP_DBP_LINE} strokeWidth={2.4} strokeLinecap="round" />}
      {/* 数据点（按当日均值档位染色） */}
      {sbpAvgPoints.map(p => {
        const a = aggMap[days[p.i]];
        const j = judgeBp(a.sbpAvg, a.dbpAvg);
        const fill = j ? getBpPalette(j.color).capsuleBg : '#3B82F6';
        return (
          <circle
            key={`sp${p.i}`}
            data-testid={`bp-point-sbp-${p.i}`}
            cx={p.x} cy={p.y} r={4.5}
            fill={fill} stroke="#fff" strokeWidth={1.5}
            style={{ cursor: 'pointer' }}
            onClick={() => handlePointClick(p.i)}
          />
        );
      })}
      {dbpAvgPoints.map(p => {
        const a = aggMap[days[p.i]];
        const j = judgeBp(a.sbpAvg, a.dbpAvg);
        const fill = j ? getBpPalette(j.color).capsuleBg : '#3B82F6';
        return (
          <circle
            key={`dp${p.i}`}
            data-testid={`bp-point-dbp-${p.i}`}
            cx={p.x} cy={p.y} r={3.5}
            fill={fill} stroke="#fff" strokeWidth={1.2}
            opacity={0.9}
            style={{ cursor: 'pointer' }}
            onClick={() => handlePointClick(p.i)}
          />
        );
      })}
    </svg>
  );
}

/** [PRD §5.4] 日视图趋势图：当日 24h 散点 + 双线连线 */
function BpDayTrendChart({
  records, onPointClick,
}: {
  records: MetricRecord[];
  onPointClick: (d: BpPointDetail) => void;
}) {
  const W = 340, H = 220;
  const PAD = { top: 14, right: 14, bottom: 28, left: 36 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  const today = new Date();
  // [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 按北京时间口径过滤"今日"并构造坐标
  const bjOf = (iso?: string | null): Date | null => {
    const d = parseServerTime(iso);
    if (!d) return null;
    return new Date(d.getTime() + 8 * 60 * 60 * 1000);
  };
  const todayBj = new Date(today.getTime() + 8 * 60 * 60 * 1000);
  const isSameBjDay = (a: Date, b: Date) =>
    a.getUTCFullYear() === b.getUTCFullYear() &&
    a.getUTCMonth() === b.getUTCMonth() &&
    a.getUTCDate() === b.getUTCDate();
  // 当日记录按时间升序
  const dayRecords = records
    .filter(r => {
      const t = bjOf(r.measured_at);
      return t != null && isSameBjDay(t, todayBj);
    })
    .slice()
    .sort((a, b) => {
      const ta = parseServerTime(a.measured_at);
      const tb = parseServerTime(b.measured_at);
      return (ta ? ta.getTime() : 0) - (tb ? tb.getTime() : 0);
    });

  const xScale = (date: Date) => {
    // date 已经是"北京时间口径"的 Date（用 UTC 字段读取北京时分）
    const minutes = date.getUTCHours() * 60 + date.getUTCMinutes();
    return PAD.left + (minutes / (24 * 60)) * cw;
  };
  const yScale = (v: number) => PAD.top + ch - ((v - BP_Y_MIN) / (BP_Y_MAX - BP_Y_MIN)) * ch;

  const sbpPoints: { x: number; y: number; r: MetricRecord }[] = [];
  const dbpPoints: { x: number; y: number; r: MetricRecord }[] = [];
  dayRecords.forEach(r => {
    const t = bjOf(r.measured_at);
    if (!t) return;
    const sv = r.value?.systolic != null ? Number(r.value.systolic) : null;
    const dv = r.value?.diastolic != null ? Number(r.value.diastolic) : null;
    if (sv != null && !Number.isNaN(sv)) sbpPoints.push({ x: xScale(t), y: yScale(sv), r });
    if (dv != null && !Number.isNaN(dv)) dbpPoints.push({ x: xScale(t), y: yScale(dv), r });
  });

  const sbpPath = sbpPoints.length >= 2 ? smoothPath(sbpPoints.map(p => ({ x: p.x, y: p.y }))) : '';
  const dbpPath = dbpPoints.length >= 2 ? smoothPath(dbpPoints.map(p => ({ x: p.x, y: p.y }))) : '';

  const hourTicks = [0, 6, 12, 18, 24];

  const handleClick = (r: MetricRecord) => {
    const sv = r.value?.systolic != null ? Number(r.value.systolic) : null;
    const dv = r.value?.diastolic != null ? Number(r.value.diastolic) : null;
    const j = judgeBp(sv, dv);
    onPointClick({
      measured_at: r.measured_at,
      systolic: sv,
      diastolic: dv,
      label: j ? j.label : '',
      level: j ? j.level : null,
      period: r.value?.period || r.value?.activity || null,
      source: r.source,
    });
  };

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
      data-testid="bp-trend-svg"
      data-bp-range="day"
    >
      {/* Y 轴网格 + 标签 */}
      {BP_Y_TICKS.map(v => {
        const y = yScale(v);
        return (
          <g key={`g${v}`}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#E5E7EB" strokeWidth={0.6} />
            <text x={PAD.left - 4} y={y + 3} textAnchor="end" fill="#9CA3AF" fontSize={10}>{v}</text>
          </g>
        );
      })}
      {/* 参考线 */}
      <line x1={PAD.left} x2={W - PAD.right} y1={yScale(BP_REF_SBP)} y2={yScale(BP_REF_SBP)}
        stroke="#9CA3AF" strokeWidth={0.8} strokeDasharray="4 3" data-testid="bp-ref-sbp" />
      <line x1={PAD.left} x2={W - PAD.right} y1={yScale(BP_REF_DBP)} y2={yScale(BP_REF_DBP)}
        stroke="#9CA3AF" strokeWidth={0.8} strokeDasharray="4 3" data-testid="bp-ref-dbp" />
      {/* X 轴 0:00 - 24:00 */}
      {hourTicks.map(h => {
        const x = PAD.left + (h / 24) * cw;
        return (
          <text
            key={`x${h}`}
            x={x} y={H - 8}
            textAnchor="middle"
            fill="#9CA3AF" fontSize={10}
          >{`${String(h).padStart(2, '0')}:00`}</text>
        );
      })}
      {/* 双线连线 */}
      {sbpPath && <path d={sbpPath} fill="none" stroke={BP_SBP_LINE} strokeWidth={2.2} strokeLinecap="round" />}
      {dbpPath && <path d={dbpPath} fill="none" stroke={BP_DBP_LINE} strokeWidth={2.2} strokeLinecap="round" />}
      {/* 数据点 */}
      {sbpPoints.map((p, i) => (
        <circle
          key={`s${i}`}
          data-testid={`bp-day-point-sbp-${i}`}
          cx={p.x} cy={p.y} r={4} fill={BP_SBP_LINE} stroke="#fff" strokeWidth={1.2}
          style={{ cursor: 'pointer' }}
          onClick={() => handleClick(p.r)}
        />
      ))}
      {dbpPoints.map((p, i) => (
        <circle
          key={`d${i}`}
          data-testid={`bp-day-point-dbp-${i}`}
          cx={p.x} cy={p.y} r={4} fill={BP_DBP_LINE} stroke="#fff" strokeWidth={1.2}
          style={{ cursor: 'pointer' }}
          onClick={() => handleClick(p.r)}
        />
      ))}
    </svg>
  );
}

/** [遗留] 血压双曲线 SVG 趋势图（保留以兼容其它入口；当前血压详情页已切换至 BpWeekTrendChart / BpDayTrendChart） */
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

// ─────────────────────────────────────────────────────────────────────────────
// [PRD-GLUCOSE-CARD-OPTIMIZE-V1 2026-05-30] 血糖详情页（参考血压详情页布局）
// ─────────────────────────────────────────────────────────────────────────────

type BgTrendRange = 'today' | 'week' | 'month';

const BG_RANGE_OPTS: { key: BgTrendRange; label: string }[] = [
  { key: 'today', label: '今天' },
  { key: 'week', label: '7天' },
  { key: 'month', label: '30天' },
];

interface BloodGlucosePageProps {
  history: MetricHistoryResponse | null;
  latest: MetricRecord | undefined;
  profileId: number;
  devices: DeviceItem[];
  refresh: () => Promise<void>;
}

// [PRD-BP-DETAIL-OPTIMIZE-V1 AC-09/AC-11] 历史记录「...」底部操作面板（修改 / 删除）
// 血糖与血压共用此组件，保证两端面板样式、动画、文案完全一致
function MetricActionSheet({
  record,
  onClose,
  onEdit,
  onDelete,
  testid,
}: {
  record: MetricRecord | null;
  onClose: () => void;
  onEdit: (r: MetricRecord) => void;
  onDelete: (r: MetricRecord) => void;
  testid?: string;
}) {
  return (
    <Popup
      visible={!!record}
      onMaskClick={onClose}
      bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: '8px 0 12px' }}
    >
      {record && (
        <div data-testid={testid || 'metric-action-sheet'}>
          <div style={{ padding: '10px 20px 6px', textAlign: 'center', fontSize: 13, color: '#94A3B8' }}>
            选择操作
          </div>
          <button
            data-testid="metric-action-edit"
            onClick={() => onEdit(record)}
            style={{
              width: '100%', padding: '14px 0', background: 'transparent', border: 'none',
              borderTop: '1px solid #F1F5F9', fontSize: 16, color: '#0C4A6E', fontWeight: 600,
              cursor: 'pointer',
            }}
          >修改</button>
          <button
            data-testid="metric-action-delete"
            onClick={() => onDelete(record)}
            style={{
              width: '100%', padding: '14px 0', background: 'transparent', border: 'none',
              borderTop: '1px solid #F1F5F9', fontSize: 16, color: '#DC2626', fontWeight: 600,
              cursor: 'pointer',
            }}
          >删除</button>
          <button
            data-testid="metric-action-cancel"
            onClick={onClose}
            style={{
              width: '100%', padding: '14px 0', marginTop: 8, background: 'transparent', border: 'none',
              borderTop: '8px solid #F4F7FB', fontSize: 16, color: '#64748B', fontWeight: 600,
              cursor: 'pointer',
            }}
          >取消</button>
        </div>
      )}
    </Popup>
  );
}

function BloodGlucosePage({ history, latest, profileId, devices, refresh }: BloodGlucosePageProps) {
  const router = useRouter();

  // 录入抽屉 — [PRD-GLUCOSE-CARD-OPTIMIZE-V2] 测量类型默认不选中
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [inputTab, setInputTab] = useState<'manual' | 'device'>('manual');
  const [bgValue, setBgValue] = useState('');
  const [bgScene, setBgScene] = useState<BgScene | null>(null);
  const [bgNote, setBgNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [sceneError, setSceneError] = useState(false);

  // 编辑历史记录 — 支持完整修改 value + scene + measured_at
  const [editRecord, setEditRecord] = useState<MetricRecord | null>(null);
  const [editScene, setEditScene] = useState<BgScene>('random');
  const [editValue, setEditValue] = useState('');

  // 删除二次确认
  const [deletingRecord, setDeletingRecord] = useState<MetricRecord | null>(null);
  const [swipedRowId, setSwipedRowId] = useState<number | null>(null);

  // [PRD-BP-DETAIL-OPTIMIZE-V1 AC-09] 「...」三点操作面板（底部滑出，含 修改/删除）
  const [actionRecord, setActionRecord] = useState<MetricRecord | null>(null);

  // AI 解读抽屉
  const [aiDrawer, setAiDrawer] = useState<{ mode: 'single' | 'trend'; loading: boolean; text: string } | null>(null);
  const aiCacheRef = (typeof window !== 'undefined') ? ((window as any).__bgAiCache ||= new Map<string, { ts: number; text: string }>()) : new Map();

  // 趋势图档位
  const [range, setRange] = useState<BgTrendRange>('week');

  // 主数值与判定
  const latestValue = latest?.value?.value != null ? Number(latest.value.value) : null;
  const latestScene: BgScene = normalizeScene(latest?.value?.period ?? latest?.value?.scene);
  const judgement = useMemo(() => judgeBg(latestValue, latestScene), [latestValue, latestScene]);
  const palette = getBgPalette(judgement?.color ?? 'blue');
  const sourceCapsule = formatBgSourceCapsule(latest?.source);

  const records: MetricRecord[] = history?.records || [];
  const hasGlucoseDevice = devices.some(d => d.device_type === 'glucometer' && d.status === 'active');

  // 时间·来源
  const syncText = useMemo(() => {
    if (!latest) return '尚无血糖记录 · 请录入或绑定设备';
    return formatBpTimeSource(latest.measured_at, latest.source);
  }, [latest]);

  // [PRD-GLUCOSE-CARD-ALIGN-BP-V1 2026-05-31] 绑定设备入口（对齐血压：提示"即将上线" + 埋点，不跳转）
  const handleBindDeviceClick = useCallback(() => {
    showToast('即将上线', 'success');
    // 埋点（占位）：health_archive.bg.bind_device.click
    try {
      if (typeof navigator !== 'undefined' && (navigator as any).sendBeacon) {
        const payload = JSON.stringify({
          type: 'event',
          name: 'health_archive.bg.bind_device.click',
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
  }, []);

  const handleSave = useCallback(async () => {
    if (!profileId) {
      showToast('profileId 缺失', 'fail');
      return;
    }
    const v = Number(bgValue);
    if (!bgValue || Number.isNaN(v)) {
      showToast('请输入有效的数值', 'fail');
      return;
    }
    if (v < 0.5 || v > 35) {
      showToast('数值应在 0.5–35 之间', 'fail');
      return;
    }
    if (!bgScene) {
      setSceneError(true);
      showToast('请选择测量类型', 'fail');
      return;
    }
    setSaving(true);
    try {
      await Promise.all([
        api.post(`/api/health-profile-v3/${profileId}/metric/blood_glucose`, {
          value: { value: v, period: bgScene, period_label: BG_SCENE_LABEL[bgScene] },
          source: inputTab === 'device' ? 'device:glucometer' : 'manual',
          note: bgNote.trim() || undefined,
        }),
        api.post(`/api/glucose-v1/records`, {
          value: v,
          scene: bgScene,
          note: bgNote.trim() || undefined,
        }).catch(() => null),
      ]);
      showToast('已保存', 'success');
      setDrawerVisible(false);
      setBgValue('');
      setBgNote('');
      setBgScene(null);
      setSceneError(false);
      await refresh();
    } catch {
      showToast('保存失败，请重试', 'fail');
    } finally {
      setSaving(false);
    }
  }, [bgValue, bgScene, bgNote, inputTab, profileId, refresh]);

  // [PRD-GLUCOSE-CARD-OPTIMIZE-V2 AC-06] 编辑保存：完整修改原记录（PUT），不再"新增一条"
  const handleEditSave = useCallback(async () => {
    if (!editRecord || !profileId) return;
    const v = Number(editValue || editRecord.value?.value);
    if (Number.isNaN(v) || v < 0.5 || v > 35) {
      showToast('数值应在 0.5–35 之间', 'fail');
      return;
    }
    try {
      await api.put(`/api/health-profile-v3/${profileId}/metric/blood_glucose/${editRecord.id}`, {
        value: v,
        period: editScene,
        measured_at: editRecord.measured_at,
        remark: editRecord.value?.note || '',
      }).catch(async () => {
        // 兜底：调用 glucose-v1 PUT
        await api.put(`/api/glucose-v1/records/${editRecord.id}`, {
          value: v,
          scene: editScene,
        });
      });
      showToast('已更新', 'success');
      setEditRecord(null);
      setEditValue('');
      await refresh();
    } catch {
      showToast('更新失败', 'fail');
    }
  }, [editRecord, editScene, editValue, profileId, refresh]);

  // [PRD-GLUCOSE-CARD-OPTIMIZE-V2 AC-07] 删除记录
  const handleDelete = useCallback(async (record: MetricRecord) => {
    if (!profileId) return;
    try {
      await api.delete(`/api/health-profile-v3/${profileId}/metric/blood_glucose/${record.id}`).catch(async () => {
        await api.delete(`/api/glucose-v1/records/${record.id}`);
      });
      showToast('已删除', 'success');
      setDeletingRecord(null);
      setSwipedRowId(null);
      await refresh();
    } catch {
      showToast('删除失败', 'fail');
    }
  }, [profileId, refresh]);

  // [PRD-GLUCOSE-CARD-OPTIMIZE-V2 §五/§七] AI 解读 — 接入真实大模型，规则文案降级
  const requestAi = useCallback(async (mode: 'single' | 'trend') => {
    const cacheKey = mode === 'single' ? `single:${latest?.id ?? 0}` : `trend:${range}`;
    const cached = aiCacheRef.get(cacheKey);
    if (cached && Date.now() - cached.ts < 5 * 60 * 1000) {
      setAiDrawer({ mode, loading: false, text: cached.text });
      return;
    }
    setAiDrawer({ mode, loading: true, text: '' });
    try {
      let text = '';
      if (mode === 'single') {
        if (!latest?.id) {
          text = '暂无血糖记录，请先录入一次再点击解读。';
        } else {
          try {
            const r: any = await api.post('/api/glucose-v1/ai-explain-single', {
              record_id: Number(latest.id),
              profile_id: profileId,
            });
            const d = r?.data?.data ?? r?.data ?? r;
            text = d?.content || '';
            if (!text) throw new Error('empty');
          } catch {
            // 网络异常兜底：本地规则文案
            const v = latestValue;
            const sc = latestScene;
            const j = v != null ? judgeBg(v, sc) : null;
            const cn = BG_SCENE_LABEL[sc];
            if (j?.level === 'normal') {
              text = `本次${cn}血糖 ${v} mmol/L，属于正常范围。建议保持规律饮食与适量运动，继续按当前节奏监测。`;
            } else if (j?.level === 'low') {
              text = `本次${cn}血糖 ${v} mmol/L，略低于推荐范围。建议立即少量补充含糖食物（糖水/果汁），15 分钟后复测。`;
            } else if (j?.level === 'high') {
              text = `本次${cn}血糖 ${v} mmol/L，略高于推荐范围。建议减少精制主食与含糖饮料，餐后散步 20 分钟，2 小时后复测。`;
            } else if (j?.level === 'low_critical') {
              text = `本次${cn}血糖 ${v} mmol/L，明显偏低，请立即补糖；必要时联系家人或就医。`;
            } else if (j?.level === 'high_critical') {
              text = `本次${cn}血糖 ${v} mmol/L，明显偏高，建议尽快就医评估，可多饮温水。`;
            } else {
              text = '暂无可解读数据。';
            }
          }
        }
      } else {
        const rangeKey = range === 'today' ? '7d' : range === 'week' ? '7d' : '30d';
        try {
          const r: any = await api.post('/api/glucose-v1/ai-explain-trend', {
            range: rangeKey,
            profile_id: profileId,
          });
          const d = r?.data?.data ?? r?.data ?? r;
          const lines: string[] = [];
          if (d?.summary) lines.push(d.summary);
          if (d?.trend) lines.push('', d.trend);
          if (d?.advice) lines.push('', '建议：', d.advice);
          text = lines.join('\n');
          if (!text.trim()) throw new Error('empty');
        } catch {
          text = '基于近期数据，建议保持规律饮食与适量运动，每周记录 3 次以上空腹与餐后血糖。';
        }
      }
      aiCacheRef.set(cacheKey, { ts: Date.now(), text });
      setAiDrawer({ mode, loading: false, text });
    } catch {
      setAiDrawer({ mode, loading: false, text: '解读失败，请稍后重试。' });
    }
  }, [latest, latestValue, latestScene, range, aiCacheRef, profileId]);

  // 趋势图分线数据（空腹/餐后/睡前）
  const trendData = useMemo(() => {
    const buckets: Record<'fasting' | 'after_meal' | 'bedtime', { x: number; y: number; raw: MetricRecord }[]> = {
      fasting: [], after_meal: [], bedtime: [],
    };
    const now = new Date();
    const todayBj = new Date(now.getTime() + 8 * 60 * 60 * 1000);
    const cutoffDays = range === 'today' ? 1 : range === 'week' ? 7 : 30;
    records.forEach(r => {
      const v = r.value?.value != null ? Number(r.value.value) : null;
      if (v == null || Number.isNaN(v)) return;
      const d = parseServerTime(r.measured_at);
      if (!d) return;
      const dBj = new Date(d.getTime() + 8 * 60 * 60 * 1000);
      const diffMs = todayBj.getTime() - dBj.getTime();
      if (range === 'today') {
        if (todayBj.getUTCFullYear() !== dBj.getUTCFullYear()
          || todayBj.getUTCMonth() !== dBj.getUTCMonth()
          || todayBj.getUTCDate() !== dBj.getUTCDate()) return;
      } else {
        if (diffMs > cutoffDays * 24 * 3600 * 1000) return;
        if (diffMs < 0) return;
      }
      const sc = normalizeScene(r.value?.period ?? r.value?.scene);
      // x: today 维度按小时；week/month 维度按距今天数（越小越靠右）
      const x = range === 'today'
        ? (dBj.getUTCHours() + dBj.getUTCMinutes() / 60)
        : (cutoffDays - 1 - Math.floor(diffMs / (24 * 3600 * 1000)));
      if (sc === 'fasting') buckets.fasting.push({ x, y: v, raw: r });
      else if (sc === 'after_meal_2h' || sc === 'after_meal_1h') buckets.after_meal.push({ x, y: v, raw: r });
      else if (sc === 'before_sleep') buckets.bedtime.push({ x, y: v, raw: r });
      // random / dawn 不入图，但展示在历史
    });
    return buckets;
  }, [records, range]);

  return (
    <div data-testid="bg-tab-page" style={{ background: '#F4F7FB', minHeight: '100vh', paddingBottom: 24 }}>
      {/* [PRD-GLUCOSE-CARD-ALIGN-BP-V1 2026-05-31 §改动2] 去掉导航栏右上角的「+ 录入」，统一收到主卡片下方大按钮 */}
      <GreenNavBar>血糖</GreenNavBar>

      {/* 主卡片 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div
          data-testid="bg-status-card"
          data-bg-color={judgement?.color ?? 'blue'}
          data-bg-level={judgement?.level ?? 'unknown'}
          style={{
            background: palette.cardBg,
            border: `1px solid ${palette.border}`,
            borderRadius: 18,
            padding: '20px 18px 18px',
          }}
        >
          <div style={{ textAlign: 'center', paddingTop: 4 }}>
            <span data-testid="bg-main-value" style={{ fontSize: 58, fontWeight: 800, color: palette.text, letterSpacing: 1, lineHeight: 1.0 }}>
              {latestValue != null ? latestValue.toFixed(1) : '—'}
            </span>
            <span style={{ fontSize: 16, fontWeight: 600, color: palette.text, marginLeft: 8, opacity: 0.7 }}>
              mmol/L
            </span>
          </div>

          <div style={{ marginTop: 14, textAlign: 'center' }}>
            <span data-testid="bg-sync-text" style={{ fontSize: 13, color: palette.text, opacity: 0.85 }}>
              {syncText}
            </span>
          </div>

          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
            {judgement && (
              <span
                data-testid="bg-capsule"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '6px 16px', borderRadius: 999,
                  background: palette.capsuleBg, color: palette.capsuleText,
                  fontSize: 13, fontWeight: 700,
                  boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
                }}
              >
                <span aria-hidden="true">{judgement.icon}</span>
                <span>{judgement.label}</span>
              </span>
            )}
            {/* [PRD-GLUCOSE-CARD-OPTIMIZE-V2 AC-13] 主卡片显示测量类型标签 */}
            {latest && (
              <span
                data-testid="bg-period-capsule"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '6px 12px', borderRadius: 999,
                  background: '#F1F5F9', color: '#0C4A6E',
                  fontSize: 12, fontWeight: 700,
                }}
              >
                🩸 {BG_SCENE_LABEL[latestScene]}
              </span>
            )}
            {latest && (
              <span
                data-testid="bg-source-capsule"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '6px 12px', borderRadius: 999,
                  background: sourceCapsule.isDevice ? '#DBEAFE' : '#F1F5F9',
                  color: sourceCapsule.isDevice ? '#1E40AF' : '#475569',
                  fontSize: 12, fontWeight: 700,
                }}
              >
                {sourceCapsule.isDevice ? '🔵' : '⚪'} {sourceCapsule.label}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* [PRD-GLUCOSE-CARD-ALIGN-BP-V1 2026-05-31 §改动1] 主卡片下方并排大按钮：手工录入（实心蓝）｜ 绑定设备（描边白底），对齐血压详情页 */}
      <div data-testid="bg-action-row" style={{ padding: '12px 16px 0', display: 'flex', gap: 10 }}>
        <button
          data-testid="bg-action-manual"
          onClick={() => { setInputTab('manual'); setDrawerVisible(true); }}
          style={{
            flex: 1, height: 44, borderRadius: 12, border: 'none',
            background: '#0EA5E9', color: '#fff',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(14,165,233,0.24)',
          }}
        >
          <PencilIcon size={16} color="#fff" />
          <span>手工录入</span>
        </button>
        <button
          data-testid="bg-action-bind"
          onClick={handleBindDeviceClick}
          style={{
            flex: 1, height: 44, borderRadius: 12,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
          }}
        >
          <BgMeterIcon size={16} color="#0EA5E9" />
          <span>绑定设备</span>
        </button>
      </div>

      {/* 目标范围参考 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div data-testid="bg-target-card" style={{ background: '#fff', borderRadius: 14, padding: '12px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#0C4A6E', marginBottom: 6 }}>📏 目标范围（医学标准）</div>
          <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
            空腹 {BG_TARGET_RANGE.fasting.label.replace('空腹 ', '')}　·　餐后 2h {BG_TARGET_RANGE.after_meal_2h.label.replace('餐后 2h ', '')}　·　睡前 {BG_TARGET_RANGE.before_sleep.label.replace('睡前 ', '')}
          </div>
        </div>
      </div>

      {/* 趋势图 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div data-testid="bg-trend-card" style={{ background: '#fff', borderRadius: 16, padding: '14px 14px 12px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>📈 趋势</span>
            <div data-testid="bg-range-segmented" style={{ display: 'flex', gap: 4, background: '#F1F5F9', borderRadius: 12, padding: 2 }}>
              {BG_RANGE_OPTS.map(opt => (
                <button
                  key={opt.key}
                  data-testid={`bg-range-${opt.key}`}
                  data-active={range === opt.key ? 'true' : 'false'}
                  onClick={() => setRange(opt.key)}
                  style={{
                    padding: '4px 12px', borderRadius: 10, border: 'none',
                    background: range === opt.key ? '#0EA5E9' : 'transparent',
                    color: range === opt.key ? '#fff' : '#64748B',
                    fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  }}
                >{opt.label}</button>
              ))}
            </div>
          </div>

          <BgTrendChart
            data={trendData}
            range={range}
          />

          <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 14 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
              <span style={{ width: 14, height: 3, background: '#1E40AF', display: 'inline-block', borderRadius: 2 }} />
              空腹
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
              <span style={{ width: 14, height: 3, background: '#F97316', display: 'inline-block', borderRadius: 2 }} />
              餐后 2h
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
              <span style={{ width: 14, height: 3, background: '#8B5CF6', display: 'inline-block', borderRadius: 2 }} />
              睡前
            </span>
          </div>
        </div>
      </div>

      {/* [PRD-GLUCOSE-CARD-ALIGN-BP-V1 2026-05-31 §改动4] AI 解读区（完整保留：本次 + 趋势），顺序对齐血压：趋势图之后 */}
      <div style={{ padding: '12px 16px 0' }}>
        <button
          data-testid="bg-ai-single"
          onClick={() => requestAi('single')}
          style={{
            width: '100%', height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, #38BDF8 0%, #0EA5E9 100%)', color: '#fff',
            border: 'none', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(14,165,233,0.24)',
          }}
        >🤖 AI 解读本次血糖</button>
        <button
          data-testid="bg-ai-trend"
          onClick={() => requestAi('trend')}
          style={{
            width: '100%', height: 40, borderRadius: 10, marginTop: 10,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9', fontSize: 14, fontWeight: 700, cursor: 'pointer',
          }}
        >🤖 AI 解读趋势</button>
      </div>

      {/* 历史记录（PRD-HEALTH-METRIC-CARD-UNIFY-V1 §4：最近 5 条 + 全部入口） */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: '14px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>历史记录</span>
            <span
              data-testid="bg-history-all-entry"
              onClick={() => router.push(`/health-metric/blood_glucose/history?profileId=${profileId}`)}
              style={{ fontSize: 13, color: '#0EA5E9', cursor: 'pointer', fontWeight: 600 }}
            >全部 ›</span>
          </div>
          {records.length === 0 ? (
            <div style={{ fontSize: 14, color: '#6B7280', textAlign: 'center', padding: '24px 0' }}>
              暂无记录，点击上方「手工录入」开始记录
            </div>
          ) : (
            records.slice(0, 5).map(r => {
              const v = r.value?.value != null ? Number(r.value.value) : null;
              const sc = normalizeScene(r.value?.period ?? r.value?.scene);
              const j = judgeBg(v, sc);
              const rowPalette = getBgPalette(j?.color ?? 'blue');
              const src = formatBgSourceCapsule(r.source);
              const isSwiped = swipedRowId === r.id;
              return (
                <div
                  key={r.id}
                  data-testid={`bg-history-row-${r.id}`}
                  style={{ position: 'relative', overflow: 'hidden', borderBottom: '1px solid #E5E7EB' }}
                  onTouchStart={(e) => { (e.currentTarget as any)._sx = e.touches[0].clientX; }}
                  onTouchEnd={(e) => {
                    const sx = (e.currentTarget as any)._sx;
                    const dx = sx ? sx - e.changedTouches[0].clientX : 0;
                    if (dx > 40) setSwipedRowId(r.id);
                    else if (dx < -40) setSwipedRowId(null);
                  }}
                >
                  <div
                    onClick={() => {
                      if (isSwiped) { setSwipedRowId(null); return; }
                      setEditRecord(r);
                      setEditScene(sc);
                      setEditValue(String(v ?? ''));
                    }}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 0', cursor: 'pointer',
                      transform: isSwiped ? 'translateX(-72px)' : 'translateX(0)',
                      transition: 'transform 0.2s',
                      background: '#fff',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: '#0C4A6E' }}>
                        {formatDateTime(r.measured_at)?.slice(11, 16) || ''}　{v != null ? v.toFixed(1) : '-'}
                        <span style={{ fontSize: 11, color: '#6B7280', marginLeft: 4, fontWeight: 500 }}>mmol/L</span>
                      </div>
                      <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <span data-testid={`bg-row-period-${r.id}`} style={{ padding: '1px 8px', background: '#F1F5F9', borderRadius: 999 }}>{BG_SCENE_LABEL[sc]}</span>
                        <span style={{ padding: '1px 8px', background: src.isDevice ? '#DBEAFE' : '#F1F5F9', color: src.isDevice ? '#1E40AF' : '#475569', borderRadius: 999 }}>{src.label}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
                      {/* [PRD-BP-DETAIL-OPTIMIZE-V1 AC-09] 「...」三点入口 → 底部操作面板 */}
                      <button
                        data-testid={`bg-row-more-${r.id}`}
                        onClick={(e) => { e.stopPropagation(); setSwipedRowId(null); setActionRecord(r); }}
                        style={{
                          background: 'transparent', border: 'none', cursor: 'pointer',
                          fontSize: 20, fontWeight: 700, color: '#94A3B8', lineHeight: 1,
                          padding: '0 4px',
                        }}
                        aria-label="更多操作"
                      >⋯</button>
                    </div>
                  </div>
                  {/* 左滑显示的删除按钮 */}
                  <button
                    data-testid={`bg-row-delete-${r.id}`}
                    onClick={(e) => { e.stopPropagation(); setDeletingRecord(r); }}
                    style={{
                      position: 'absolute', top: 0, right: 0, bottom: 0, width: 64,
                      background: '#DC2626', color: '#fff', border: 'none', cursor: 'pointer',
                      fontSize: 13, fontWeight: 600,
                      transform: isSwiped ? 'translateX(0)' : 'translateX(64px)',
                      transition: 'transform 0.2s',
                    }}
                  >删除</button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 更多功能入口 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: '4px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0C4A6E', padding: '10px 0' }}>⚙️ 更多功能</div>
          <BgMenuItem label="🔔 血糖预警设置" onClick={() => showToast('血糖预警设置即将上线', 'success')} />
          <BgMenuItem label="⏰ 测量提醒" onClick={() => showToast('测量提醒即将上线', 'success')} />
          <BgMenuItem label="📄 健康报告" onClick={() => showToast('健康报告即将上线', 'success')} last />
        </div>
      </div>

      {/* 录入抽屉 */}
      <Popup
        visible={drawerVisible}
        onMaskClick={() => setDrawerVisible(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '80vh', overflowY: 'auto' }}
      >
        <div data-testid="bg-input-drawer">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E' }}>录入血糖</span>
            <button onClick={() => setDrawerVisible(false)} style={{ background: 'transparent', border: 'none', fontSize: 20, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
          </div>

          {/* Tab */}
          <div style={{ display: 'flex', background: '#F1F5F9', borderRadius: 10, padding: 4, marginBottom: 14 }}>
            {[
              { k: 'manual' as const, lab: '手动录入' },
              { k: 'device' as const, lab: '设备读取' },
            ].map(t => (
              <button
                key={t.k}
                data-testid={`bg-tab-${t.k}`}
                onClick={() => setInputTab(t.k)}
                style={{
                  flex: 1, padding: '8px 0', borderRadius: 8, border: 'none',
                  background: inputTab === t.k ? '#fff' : 'transparent',
                  color: inputTab === t.k ? '#0EA5E9' : '#64748B',
                  fontSize: 14, fontWeight: 700, cursor: 'pointer',
                  boxShadow: inputTab === t.k ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                }}
              >{t.lab}</button>
            ))}
          </div>

          {inputTab === 'device' && !hasGlucoseDevice && (
            <div data-testid="bg-no-device" style={{ background: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: 10, padding: 14, marginBottom: 14 }}>
              <div style={{ fontSize: 13, color: '#92400E', marginBottom: 8 }}>暂未绑定设备</div>
              <button
                data-testid="bg-go-bind"
                onClick={() => { setDrawerVisible(false); router.push('/devices'); }}
                style={{ padding: '6px 14px', background: '#F59E0B', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}
              >去绑定</button>
            </div>
          )}

          {/* 数值 */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>数值</div>
            <Input
              data-testid="bg-input-value"
              type="number"
              placeholder="如 6.5"
              value={bgValue}
              onChange={(v) => setBgValue(v)}
              style={{ '--font-size': '16px', padding: '10px 12px', background: inputTab === 'device' ? '#EFF6FF' : '#f0f9ff', borderRadius: 8, border: inputTab === 'device' ? '1px dashed #3B82F6' : '1px solid #bae6fd' } as any}
            />
            <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>单位：mmol/L，合理范围 0.5–35</div>
          </div>

          {/* [PRD-GLUCOSE-CARD-OPTIMIZE-V2 AC-01/AC-02] 测量类型 6 种 + 强制必选 */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>
              测量类型 <span style={{ color: '#DC2626' }}>*</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {BG_SCENE_OPTIONS.map(sc => (
                <button
                  key={sc}
                  data-testid={`bg-scene-${sc}`}
                  onClick={() => { setBgScene(sc); setSceneError(false); }}
                  style={{
                    padding: '8px 0',
                    background: bgScene === sc ? '#0ea5e9' : '#e0f2fe',
                    color: bgScene === sc ? '#fff' : '#0369a1',
                    border: sceneError && !bgScene ? '1px solid #DC2626' : 'none',
                    borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >{BG_SCENE_LABEL[sc]}</button>
              ))}
            </div>
            {sceneError && !bgScene && (
              <div data-testid="bg-scene-error" style={{ marginTop: 6, fontSize: 12, color: '#DC2626' }}>
                ⚠ 请选择测量类型
              </div>
            )}
            {!bgScene && !sceneError && (
              <div style={{ marginTop: 6, fontSize: 11, color: '#9CA3AF' }}>请选择测量类型</div>
            )}
          </div>

          {/* 备注 */}
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>备注（选填）</div>
            <Input
              placeholder="如：早餐后 2 小时"
              value={bgNote}
              onChange={(v) => setBgNote(v)}
              style={{ '--font-size': '14px', padding: '10px 12px', background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' } as any}
            />
          </div>

          <Button
            data-testid="bg-input-save"
            data-disabled={!bgScene || !bgValue ? 'true' : 'false'}
            block color="primary" loading={saving} onClick={handleSave}
            style={{
              '--background-color': (!bgScene || !bgValue) ? '#94A3B8' : '#0ea5e9',
              '--border-radius': '22px', height: 44, fontSize: 16,
              opacity: (!bgScene || !bgValue) ? 0.7 : 1,
            } as any}
          >保存</Button>
        </div>
      </Popup>

      {/* [PRD-BP-DETAIL-OPTIMIZE-V1 AC-09] 「...」底部操作面板（修改 / 删除）— 与血压共用 MetricActionSheet 模板 */}
      <MetricActionSheet
        testid="bg-action-sheet"
        record={actionRecord}
        onClose={() => setActionRecord(null)}
        onEdit={(r) => {
          const v = r.value?.value != null ? Number(r.value.value) : null;
          const sc = normalizeScene(r.value?.period ?? r.value?.scene);
          setActionRecord(null);
          setEditRecord(r);
          setEditScene(sc);
          setEditValue(String(v ?? ''));
        }}
        onDelete={(r) => { setActionRecord(null); setDeletingRecord(r); }}
      />

      {/* [PRD-GLUCOSE-CARD-OPTIMIZE-V2 AC-06] 编辑历史记录 - 完整修改 + 删除 */}
      <Popup
        visible={!!editRecord}
        onMaskClick={() => { setEditRecord(null); setEditValue(''); }}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '85vh', overflowY: 'auto' }}
      >
        {editRecord && (
          <div data-testid="bg-edit-popup">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>编辑血糖记录</span>
              <button onClick={() => { setEditRecord(null); setEditValue(''); }} style={{ background: 'transparent', border: 'none', fontSize: 18, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
              {formatDateTime(editRecord.measured_at)}
            </div>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>数值（mmol/L）</div>
              <Input
                data-testid="bg-edit-value"
                type="number"
                value={editValue || String(editRecord.value?.value || '')}
                onChange={(v) => setEditValue(v)}
                style={{ '--font-size': '16px', padding: '10px 12px', background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' } as any}
              />
            </div>

            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>测量类型</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 16 }}>
              {BG_SCENE_OPTIONS.map(sc => (
                <button
                  key={sc}
                  data-testid={`bg-edit-scene-${sc}`}
                  onClick={() => setEditScene(sc)}
                  style={{
                    padding: '8px 0',
                    background: editScene === sc ? '#0ea5e9' : '#e0f2fe',
                    color: editScene === sc ? '#fff' : '#0369a1',
                    border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >{BG_SCENE_LABEL[sc]}</button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                data-testid="bg-edit-delete"
                onClick={() => setDeletingRecord(editRecord)}
                style={{ flex: 1, padding: '10px 0', background: '#fff', color: '#DC2626',
                  border: '1px solid #DC2626', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >删除</button>
              <button
                data-testid="bg-edit-save"
                onClick={handleEditSave}
                style={{ flex: 2, padding: '10px 0', background: '#0ea5e9', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >保存</button>
            </div>
          </div>
        )}
      </Popup>

      {/* [PRD-GLUCOSE-CARD-OPTIMIZE-V2 AC-07] 删除二次确认 */}
      <Popup
        visible={!!deletingRecord}
        onMaskClick={() => setDeletingRecord(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        {deletingRecord && (
          <div data-testid="bg-delete-confirm">
            <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E', marginBottom: 10 }}>确认删除</div>
            <div style={{ fontSize: 14, color: '#374151', marginBottom: 16 }}>
              确认删除这条血糖记录？此操作不可撤销。
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 8 }}>
                {formatDateTime(deletingRecord.measured_at)} · {deletingRecord.value?.value} mmol/L
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setDeletingRecord(null)}
                style={{ flex: 1, padding: '10px 0', background: '#fff', color: '#475569',
                  border: '1px solid #CBD5E1', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >取消</button>
              <button
                data-testid="bg-delete-confirm-btn"
                onClick={() => { handleDelete(deletingRecord); setEditRecord(null); }}
                style={{ flex: 1, padding: '10px 0', background: '#DC2626', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >确认删除</button>
            </div>
          </div>
        )}
      </Popup>

      {/* AI 解读抽屉 */}
      <Popup
        visible={!!aiDrawer}
        onMaskClick={() => setAiDrawer(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '70vh', overflowY: 'auto' }}
      >
        {aiDrawer && (
          <div data-testid="bg-ai-drawer">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E' }}>🤖 AI 解读</span>
              <button onClick={() => setAiDrawer(null)} style={{ background: 'transparent', border: 'none', fontSize: 20, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 14 }}>
              {aiDrawer.mode === 'single'
                ? `基于：${latest ? formatDateTime(latest.measured_at) + ' ' + BG_SCENE_LABEL[latestScene] + ' ' + (latestValue ?? '-') + ' mmol/L' : '当前无记录'}`
                : `基于：${range === 'today' ? '今天' : range === 'week' ? '近 7 天' : '近 30 天'}所有记录`}
            </div>
            <div style={{ background: '#F8FAFC', borderRadius: 12, padding: 14, minHeight: 100, fontSize: 14, color: '#0F172A', whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {aiDrawer.loading ? '正在分析…' : aiDrawer.text}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF', textAlign: 'center' }}>
              ⚠️ AI 建议仅供参考，不能替代医生诊断
            </div>
          </div>
        )}
      </Popup>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════
// [PRD-HR-ALIGN-BP-V1 2026-06-01] 心率详情页（全面对齐血压精装样式）
//   - 浅蓝灰底 + 蓝色系主题
//   - 大号居中数值 + 居中彩色胶囊 + 底卡按档位变色（正常蓝 / 偏慢偏快橙）
//   - 双 AI 按钮：解读本次 / 解读趋势（复用通用指标 AI 接口）
//   - 趋势图：日/周切换 + 点击数据点弹窗 + 正常参考线（60 / 100）
//   - 历史记录：每条可编辑 / 可删除，带档位配色
// ════════════════════════════════════════════════════════════════════════

interface HeartRatePageProps {
  history: MetricHistoryResponse | null;
  latest: MetricRecord | undefined;
  profileId: number;
  meta: (typeof META)['heart_rate'];
  refresh: () => Promise<void>;
}

type HrTrendRange = 'day' | 'week';
const HR_RANGE_OPTS: { key: HrTrendRange; label: string }[] = [
  { key: 'day', label: '日' },
  { key: 'week', label: '周' },
];

interface HrPointDetail {
  measured_at: string;
  value: number | null;
  label: string;
  source: string;
  activity?: string | null;
}

function hrValueOf(r: MetricRecord | undefined | null): number | null {
  if (!r) return null;
  const raw = r.value?.value != null ? Number(r.value.value) : null;
  return raw != null && !Number.isNaN(raw) && raw > 0 ? raw : null;
}

function HeartRatePage(props: HeartRatePageProps) {
  const { history, latest, meta, refresh } = props;
  const router = useRouter();

  // 录入弹窗
  const [popupVisible, setPopupVisible] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [inputActivity, setInputActivity] = useState('');
  const [saving, setSaving] = useState(false);

  // 历史「...」操作面板 + 编辑 + 删除
  const [actionRecord, setActionRecord] = useState<MetricRecord | null>(null);
  const [editRecord, setEditRecord] = useState<MetricRecord | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editActivity, setEditActivity] = useState('');
  const [deletingRecord, setDeletingRecord] = useState<MetricRecord | null>(null);

  // 趋势图
  const [range, setRange] = useState<HrTrendRange>('week');
  const [pointPopup, setPointPopup] = useState<HrPointDetail | null>(null);

  // AI 解读抽屉与缓存（复用血压/血糖框架，调用通用指标 AI 接口）
  const [aiDrawer, setAiDrawer] = useState<{ mode: 'single' | 'trend'; loading: boolean; text: string } | null>(null);
  const aiCacheRef = (typeof window !== 'undefined') ? ((window as any).__hrAiCache ||= new Map<string, { ts: number; text: string }>()) : new Map();

  const hrValue = hrValueOf(latest);
  const judgement: HrJudgement | null = useMemo(() => judgeHeartRate(hrValue), [hrValue]);
  // 无数据态默认走「正常蓝」色板
  const palette = getHrPalette(judgement?.color ?? 'blue');

  const records: MetricRecord[] = history?.records || [];

  const syncText = useMemo(() => {
    if (!latest || hrValue == null) return '尚无心率记录 · 请录入或绑定设备';
    return formatBpTimeSource(latest.measured_at, latest.source);
  }, [latest, hrValue]);

  const handleSave = useCallback(async () => {
    if (!props.profileId) {
      showToast('profileId 缺失', 'fail');
      return;
    }
    const v = Number(inputValue);
    if (!inputValue || Number.isNaN(v)) {
      showToast('请输入有效的心率', 'fail');
      return;
    }
    if (v < 20 || v > 300) {
      showToast('心率应在 20–300 之间', 'fail');
      return;
    }
    setSaving(true);
    try {
      const value: Record<string, any> = { value: v };
      if (inputActivity) value.activity = inputActivity;
      await api.post(`/api/health-profile-v3/${props.profileId}/metric/heart_rate`, {
        value, source: 'manual',
      });
      showToast('已保存', 'success');
      setPopupVisible(false);
      setInputValue('');
      setInputActivity('');
      await refresh();
    } catch {
      showToast('保存失败，请重试', 'fail');
    } finally {
      setSaving(false);
    }
  }, [inputValue, inputActivity, props.profileId, refresh]);

  const handleEditSave = useCallback(async () => {
    if (!editRecord || !props.profileId) return;
    const v = Number(editValue);
    if (!editValue || Number.isNaN(v) || v < 20 || v > 300) {
      showToast('心率应在 20–300 之间', 'fail');
      return;
    }
    try {
      await api.put(`/api/health-profile-v3/${props.profileId}/metric/heart_rate/${editRecord.id}`, {
        value: { value: v, activity: editActivity || undefined },
        measured_at: editRecord.measured_at,
      });
      showToast('已更新', 'success');
      setEditRecord(null);
      await refresh();
    } catch {
      showToast('更新失败', 'fail');
    }
  }, [editRecord, editValue, editActivity, props.profileId, refresh]);

  const handleDelete = useCallback(async (record: MetricRecord) => {
    if (!props.profileId) return;
    try {
      await api.delete(`/api/health-profile-v3/${props.profileId}/metric/heart_rate/${record.id}`);
      showToast('已删除', 'success');
      setDeletingRecord(null);
      await refresh();
    } catch {
      showToast('删除失败', 'fail');
    }
  }, [props.profileId, refresh]);

  const handleBindDeviceClick = useCallback(() => {
    showToast('即将上线', 'success');
    try {
      if (typeof navigator !== 'undefined' && (navigator as any).sendBeacon) {
        const payload = JSON.stringify({
          type: 'event', name: 'health_archive.hr.bind_device.click', ts: Date.now(),
          url: typeof window !== 'undefined' ? window.location.pathname : '',
        });
        const blob = new Blob([payload], { type: 'application/json' });
        const basePath = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/+$/, '');
        (navigator as any).sendBeacon(`${basePath}/api/_frontend_log`, blob);
      }
    } catch { /* 埋点失败不影响主流程 */ }
  }, []);

  // [PRD-HR-ALIGN-BP-V1 §4.2] AI 解读 — 复用血压话术框架，替换为心率指标参数
  const requestAi = useCallback(async (mode: 'single' | 'trend') => {
    if (mode === 'single' && !latest?.id) {
      showToast('暂无心率记录，请先录入一次再点击解读。', 'success');
      return;
    }
    const cacheKey = mode === 'single' ? `single:${latest?.id ?? 0}` : `trend:${range}`;
    const cached = aiCacheRef.get(cacheKey);
    if (cached && Date.now() - cached.ts < 5 * 60 * 1000) {
      setAiDrawer({ mode, loading: false, text: cached.text });
      return;
    }
    setAiDrawer({ mode, loading: true, text: '' });
    try {
      let text = '';
      if (mode === 'single') {
        try {
          const r: any = await api.post(
            `/api/health-metric-v1/${props.profileId}/heart_rate/ai-explain-single`,
            { record_id: Number(latest!.id) }
          );
          const d = r?.data?.data ?? r?.data ?? r;
          text = d?.content || '';
          if (!text) throw new Error('empty');
        } catch {
          const vStr = hrValue != null ? hrValue : '-';
          const j = judgement;
          if (!j) {
            text = '暂无可解读的心率数据。';
          } else if (j.level === 'normal') {
            text = `本次心率 ${vStr} bpm，处于正常范围（60–100 次/分）。建议保持规律作息、适量运动，继续按当前节奏监测。`;
          } else if (j.level === 'slow') {
            text = `本次心率 ${vStr} bpm，偏慢（低于 60 次/分）。若为长期规律运动者多属正常；若伴有头晕、乏力、胸闷，建议尽快就医评估心脏功能。`;
          } else {
            text = `本次心率 ${vStr} bpm，偏快（高于 100 次/分）。建议先静坐休息几分钟后复测，避免咖啡因与剧烈活动；若持续偏快或伴心慌、胸闷，请及时就医。`;
          }
        }
      } else {
        const rangeKey: '7d' | '30d' = range === 'week' ? '7d' : '7d';
        try {
          const r: any = await api.post(
            `/api/health-metric-v1/${props.profileId}/heart_rate/ai-explain-trend`,
            { range: rangeKey }
          );
          const d = r?.data?.data ?? r?.data ?? r;
          const lines: string[] = [];
          if (d?.summary) lines.push(d.summary);
          if (d?.trend) lines.push('', d.trend);
          if (d?.advice) lines.push('', '建议：', d.advice);
          text = lines.join('\n');
          if (!text.trim()) throw new Error('empty');
        } catch {
          text = '基于近期心率数据，建议保持规律作息与适量有氧运动，固定时段（如晨起静息）测量并记录；如静息心率长期偏快或偏慢，请就医评估。';
        }
      }
      aiCacheRef.set(cacheKey, { ts: Date.now(), text });
      setAiDrawer({ mode, loading: false, text });
    } catch {
      setAiDrawer({ mode, loading: false, text: '解读失败，请稍后重试。' });
    }
  }, [latest, range, aiCacheRef, props.profileId, judgement, hrValue]);

  // 趋势数据：日视图按小时散点，周视图按距今天数；空状态判定
  const trendPoints = useMemo(() => {
    const pts: { x: number; y: number; raw: MetricRecord }[] = [];
    const now = new Date();
    const todayBj = new Date(now.getTime() + 8 * 60 * 60 * 1000);
    const cutoffDays = range === 'week' ? 7 : 1;
    records.forEach(r => {
      const v = hrValueOf(r);
      if (v == null) return;
      const d = parseServerTime(r.measured_at);
      if (!d) return;
      const dBj = new Date(d.getTime() + 8 * 60 * 60 * 1000);
      const diffMs = todayBj.getTime() - dBj.getTime();
      if (range === 'day') {
        if (todayBj.getUTCFullYear() !== dBj.getUTCFullYear()
          || todayBj.getUTCMonth() !== dBj.getUTCMonth()
          || todayBj.getUTCDate() !== dBj.getUTCDate()) return;
        pts.push({ x: dBj.getUTCHours() + dBj.getUTCMinutes() / 60, y: v, raw: r });
      } else {
        if (diffMs < 0 || diffMs > cutoffDays * 24 * 3600 * 1000) return;
        pts.push({ x: cutoffDays - 1 - Math.floor(diffMs / (24 * 3600 * 1000)), y: v, raw: r });
      }
    });
    return pts;
  }, [records, range]);

  const isEmptyForRange = trendPoints.length === 0;

  return (
    <div data-testid="hr-tab-page" style={{ background: '#F4F7FB', minHeight: '100vh', paddingBottom: 24 }}>
      <GreenNavBar>心率详情</GreenNavBar>

      {/* 顶部主卡片：大号居中数值 + 时间·来源 + 居中彩色胶囊（底卡按档位变色） */}
      <div style={{ padding: '12px 16px 0' }}>
        <div
          data-testid="hr-status-card"
          data-hr-color={judgement?.color ?? 'blue'}
          data-hr-level={judgement?.level ?? 'unknown'}
          style={{
            background: palette.cardBg,
            border: `1px solid ${palette.border}`,
            borderRadius: 18,
            padding: '20px 18px 18px',
            position: 'relative',
          }}
        >
          <div style={{ textAlign: 'center', paddingTop: 4 }}>
            <span
              data-testid="hr-main-value"
              style={{ fontSize: 58, fontWeight: 800, color: palette.text, letterSpacing: 1, lineHeight: 1.0 }}
            >
              {hrValue != null ? hrValue : '—'}
            </span>
            <span style={{ fontSize: 16, fontWeight: 600, color: palette.text, marginLeft: 8, opacity: 0.7 }}>
              bpm
            </span>
          </div>

          <div style={{ marginTop: 14, textAlign: 'center' }}>
            <span data-testid="hr-sync-text" style={{ fontSize: 13, color: palette.text, opacity: 0.85 }}>
              {syncText}
            </span>
          </div>

          {judgement && (
            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center' }}>
              <span
                data-testid="hr-capsule"
                style={{
                  display: 'inline-flex', alignItems: 'center',
                  padding: '6px 16px', borderRadius: 999,
                  background: palette.capsuleBg, color: palette.capsuleText,
                  fontSize: 13, fontWeight: 700,
                  boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
                }}
              >
                <span>{judgement.label}</span>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* AI 解读本次心率：顶部主卡片正下方（对齐血压 v2 布局） */}
      <div style={{ padding: '12px 16px 0' }}>
        <button
          data-testid="hr-ai-single"
          onClick={() => requestAi('single')}
          style={{
            width: '100%', height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, #38BDF8 0%, #0EA5E9 100%)', color: '#fff',
            border: 'none', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(14,165,233,0.24)',
          }}
        >🤖 AI 解读本次心率</button>
      </div>

      {/* 主卡片 ↔ 趋势图之间：并排大按钮（手工录入实心 + 绑定设备描边） */}
      <div data-testid="hr-action-row" style={{ padding: '12px 16px 0', display: 'flex', gap: 10 }}>
        <button
          data-testid="hr-action-manual"
          onClick={() => setPopupVisible(true)}
          style={{
            flex: 1, height: 44, borderRadius: 12, border: 'none',
            background: '#0EA5E9', color: '#fff',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(14,165,233,0.24)',
          }}
        >
          <PencilIcon size={16} color="#fff" />
          <span>手工录入</span>
        </button>
        <button
          data-testid="hr-action-bind"
          onClick={handleBindDeviceClick}
          style={{
            flex: 1, height: 44, borderRadius: 12,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
          }}
        >
          <span>⌚ 绑定设备</span>
        </button>
      </div>

      {/* 趋势图：日/周切换 + 点击数据点弹窗 + 正常参考线（60/100） */}
      <div style={{ padding: '12px 16px 0' }}>
        <div
          data-testid="hr-trend-card"
          style={{ background: '#fff', borderRadius: 16, padding: '14px 14px 12px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>
              {range === 'day' ? '今日趋势' : '最近 7 天趋势'}
            </span>
            <div data-testid="hr-range-segmented" style={{ display: 'flex', gap: 4, background: '#F1F5F9', borderRadius: 12, padding: 2 }}>
              {HR_RANGE_OPTS.map(opt => (
                <button
                  key={opt.key}
                  data-testid={`hr-range-${opt.key}`}
                  data-active={range === opt.key ? 'true' : 'false'}
                  onClick={() => setRange(opt.key)}
                  style={{
                    padding: '4px 14px', borderRadius: 10, border: 'none',
                    background: range === opt.key ? '#0EA5E9' : 'transparent',
                    color: range === opt.key ? '#fff' : '#64748B',
                    fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  }}
                >{opt.label}</button>
              ))}
            </div>
          </div>

          {isEmptyForRange ? (
            <div data-testid="hr-trend-empty" style={{ padding: '30px 8px', textAlign: 'center' }}>
              <svg width="80" height="64" viewBox="0 0 80 64" style={{ display: 'block', margin: '0 auto 8px' }} aria-hidden="true">
                <path d="M6 40 L18 40 L24 24 L32 52 L40 32 L48 44 L56 40 L74 40" stroke="#0EA5E9" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <div style={{ fontSize: 14, color: '#6B7280' }}>暂无数据，点击上方「手工录入」开始记录</div>
            </div>
          ) : (
            <HrTrendChart points={trendPoints} range={range} onPointClick={setPointPopup} />
          )}

          {!isEmptyForRange && (
            <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 14 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151' }}>
                <span style={{ width: 18, height: 3, background: '#0EA5E9', display: 'inline-block', borderRadius: 2 }} />
                心率（参考线 60 / 100）
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 趋势图区只保留「AI 解读趋势」按钮 */}
      <div style={{ padding: '12px 16px 0' }}>
        <button
          data-testid="hr-ai-trend"
          onClick={() => requestAi('trend')}
          style={{
            width: '100%', height: 40, borderRadius: 10,
            background: '#fff', color: '#0EA5E9',
            border: '1px solid #0EA5E9', fontSize: 14, fontWeight: 700, cursor: 'pointer',
          }}
        >🤖 AI 解读趋势</button>
      </div>

      {/* 历史记录（最近 5 条 + 全部入口，带档位配色 + 可改可删） */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: '14px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>历史记录</span>
            <span
              data-testid="hr-history-all-entry"
              onClick={() => router.push(`/health-metric/heart_rate/history?profileId=${props.profileId}`)}
              style={{ fontSize: 13, color: '#0EA5E9', cursor: 'pointer', fontWeight: 600 }}
            >全部 ›</span>
          </div>
          {records.length === 0 ? (
            <div style={{ fontSize: 14, color: '#6B7280', textAlign: 'center', padding: '24px 0' }}>
              暂无记录，点击上方「手工录入」开始记录
            </div>
          ) : (
            records.slice(0, 5).map((r) => {
              const v = hrValueOf(r);
              const j = judgeHeartRate(v);
              const rowPalette = getHrPalette(j?.color ?? 'blue');
              return (
                <div
                  key={r.id}
                  data-testid={`hr-history-row-${r.id}`}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 0', borderBottom: '1px solid #E5E7EB',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#0C4A6E' }}>
                      {v ?? '-'}
                      <span style={{ fontSize: 12, color: '#6B7280', marginLeft: 4, fontWeight: 500 }}>bpm</span>
                    </div>
                    <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
                      {formatDateTime(r.measured_at)} · {formatBpSource(r.source)}
                      {r.value?.activity ? ` · ${r.value.activity}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
                    <button
                      data-testid={`hr-row-more-${r.id}`}
                      onClick={(e) => { e.stopPropagation(); setActionRecord(r); }}
                      style={{
                        background: 'transparent', border: 'none', cursor: 'pointer',
                        fontSize: 20, fontWeight: 700, color: '#94A3B8', lineHeight: 1, padding: '0 4px',
                      }}
                      aria-label="更多操作"
                    >⋯</button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 手工填写弹窗 */}
      <Popup
        visible={popupVisible}
        onMaskClick={() => setPopupVisible(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        <div data-testid="hr-input-popup">
          <div style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E', marginBottom: 16 }}>手工填写心率</div>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 4 }}>心率（bpm）</div>
            <Input
              data-testid="hr-input-value"
              type="number"
              placeholder="如 72"
              value={inputValue}
              onChange={(v) => setInputValue(v)}
              style={{ '--font-size': '16px', padding: '10px 12px', background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' } as any}
            />
            <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>{HR_NORMAL_RANGE_TEXT}</div>
          </div>
          {meta.period && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>测量状态</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {meta.period.options.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setInputActivity(opt)}
                    style={{
                      padding: '6px 14px',
                      background: inputActivity === opt ? '#0ea5e9' : '#e0f2fe',
                      color: inputActivity === opt ? '#fff' : '#0369a1',
                      border: 'none', borderRadius: 18, fontSize: 14, cursor: 'pointer',
                    }}
                  >{opt}</button>
                ))}
              </div>
            </div>
          )}
          <Button
            data-testid="hr-input-save"
            block color="primary" loading={saving} onClick={handleSave}
            style={{ '--background-color': '#0ea5e9', '--border-radius': '22px', height: 44, fontSize: 16 } as any}
          >保存</Button>
        </div>
      </Popup>

      {/* 「...」底部操作面板（修改 / 删除）— 复用 MetricActionSheet */}
      <MetricActionSheet
        testid="hr-action-sheet"
        record={actionRecord}
        onClose={() => setActionRecord(null)}
        onEdit={(r) => {
          setActionRecord(null);
          setEditRecord(r);
          setEditValue(hrValueOf(r) != null ? String(hrValueOf(r)) : '');
          setEditActivity(typeof r.value?.activity === 'string' ? r.value.activity : '');
        }}
        onDelete={(r) => { setActionRecord(null); setDeletingRecord(r); }}
      />

      {/* 编辑心率记录 */}
      <Popup
        visible={!!editRecord}
        onMaskClick={() => setEditRecord(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '85vh', overflowY: 'auto' }}
      >
        {editRecord && (
          <div data-testid="hr-edit-popup">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>编辑心率记录</span>
              <button onClick={() => setEditRecord(null)} style={{ background: 'transparent', border: 'none', fontSize: 18, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
              {formatDateTime(editRecord.measured_at)}
            </div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>心率（bpm）</div>
              <Input
                data-testid="hr-edit-value"
                type="number"
                value={editValue}
                onChange={(v) => setEditValue(v)}
                style={{ '--font-size': '16px', padding: '10px 12px', background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' } as any}
              />
            </div>
            {meta.period && (
              <>
                <div style={{ fontSize: 13, color: '#0369a1', marginBottom: 6 }}>测量状态</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
                  {meta.period.options.map((opt) => (
                    <button
                      key={opt}
                      data-testid={`hr-edit-activity-${opt}`}
                      onClick={() => setEditActivity(opt)}
                      style={{
                        padding: '6px 14px',
                        background: editActivity === opt ? '#0ea5e9' : '#e0f2fe',
                        color: editActivity === opt ? '#fff' : '#0369a1',
                        border: 'none', borderRadius: 18, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >{opt}</button>
                  ))}
                </div>
              </>
            )}
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                data-testid="hr-edit-delete"
                onClick={() => setDeletingRecord(editRecord)}
                style={{ flex: 1, padding: '10px 0', background: '#fff', color: '#DC2626',
                  border: '1px solid #DC2626', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >删除</button>
              <button
                data-testid="hr-edit-save"
                onClick={handleEditSave}
                style={{ flex: 2, padding: '10px 0', background: '#0ea5e9', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >保存</button>
            </div>
          </div>
        )}
      </Popup>

      {/* 删除二次确认 */}
      <Popup
        visible={!!deletingRecord}
        onMaskClick={() => setDeletingRecord(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        {deletingRecord && (
          <div data-testid="hr-delete-confirm">
            <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E', marginBottom: 10 }}>确认删除</div>
            <div style={{ fontSize: 14, color: '#374151', marginBottom: 16 }}>
              确认删除这条心率记录？此操作不可撤销。
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 8 }}>
                {formatDateTime(deletingRecord.measured_at)} · {hrValueOf(deletingRecord) ?? '-'} bpm
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setDeletingRecord(null)}
                style={{ flex: 1, padding: '10px 0', background: '#fff', color: '#475569',
                  border: '1px solid #CBD5E1', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >取消</button>
              <button
                data-testid="hr-delete-confirm-btn"
                onClick={() => { handleDelete(deletingRecord); setEditRecord(null); }}
                style={{ flex: 1, padding: '10px 0', background: '#DC2626', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
              >确认删除</button>
            </div>
          </div>
        )}
      </Popup>

      {/* 数据点点击弹窗 */}
      <Popup
        visible={!!pointPopup}
        onMaskClick={() => setPointPopup(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 18 }}
      >
        {pointPopup && (() => {
          const j = judgeHeartRate(pointPopup.value);
          const pp = getHrPalette(j?.color ?? 'blue');
          return (
            <div data-testid="hr-point-popup">
              <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E', marginBottom: 10 }}>心率详情</div>
              <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 8 }}>{formatDateTime(pointPopup.measured_at)}</div>
              <div style={{ height: 1, background: '#E5E7EB', margin: '8px 0' }} />
              <DetailRow k="心率" v={pointPopup.value != null ? `${pointPopup.value} bpm` : '—'} />
              <DetailRow k="档位" v={
                <span data-testid="hr-point-level" style={{
                  padding: '2px 10px', borderRadius: 999,
                  background: pp.capsuleBg, color: pp.capsuleText, fontSize: 12, fontWeight: 700,
                }}>{pointPopup.label || '—'}</span>
              } />
              {pointPopup.activity && <DetailRow k="测量状态" v={pointPopup.activity} />}
              <DetailRow k="来源" v={formatBpSource(pointPopup.source)} />
              <Button
                block color="primary" onClick={() => setPointPopup(null)}
                style={{ '--background-color': '#0EA5E9', '--border-radius': '12px', height: 40, fontSize: 14, marginTop: 14 } as any}
              >知道了</Button>
            </div>
          );
        })()}
      </Popup>

      {/* AI 解读抽屉 */}
      <Popup
        visible={!!aiDrawer}
        onMaskClick={() => setAiDrawer(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: '70vh', overflowY: 'auto' }}
      >
        {aiDrawer && (
          <div data-testid="hr-ai-drawer">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#0C4A6E' }}>🤖 AI 解读</span>
              <button onClick={() => setAiDrawer(null)} style={{ background: 'transparent', border: 'none', fontSize: 20, color: '#9CA3AF', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 14 }}>
              {aiDrawer.mode === 'single'
                ? `基于：${latest && hrValue != null ? formatDateTime(latest.measured_at) + ' 心率 ' + hrValue + ' bpm' : '当前无记录'}`
                : `基于：${range === 'day' ? '今天' : '近 7 天'}所有心率记录`}
            </div>
            <div style={{ background: '#F8FAFC', borderRadius: 12, padding: 14, minHeight: 100, fontSize: 14, color: '#0F172A', whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {aiDrawer.loading ? '正在分析…' : aiDrawer.text}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF', textAlign: 'center' }}>
              ⚠️ AI 建议仅供参考，不能替代医生诊断
            </div>
          </div>
        )}
      </Popup>
    </div>
  );
}

// [PRD-HR-ALIGN-BP-V1 2026-06-01] 心率单线趋势图（日/周 + 数据点可点击 + 参考线 60/100）
function HrTrendChart({ points, range, onPointClick }: {
  points: { x: number; y: number; raw: MetricRecord }[];
  range: HrTrendRange;
  onPointClick: (d: HrPointDetail) => void;
}) {
  const W = 340, H = 200;
  const PAD = { top: 14, right: 18, bottom: 28, left: 32 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  const xMax = range === 'week' ? 6 : 24;
  const yMin = 40, yMax = 160;

  const xScale = (x: number) => PAD.left + (x / xMax) * cw;
  const yScale = (y: number) => PAD.top + ch - ((Math.max(yMin, Math.min(yMax, y)) - yMin) / (yMax - yMin)) * ch;

  const sorted = [...points].sort((a, b) => a.x - b.x);
  const pathD = sorted.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(' ');

  const refLines = [
    { y: 60, label: '60' },
    { y: 100, label: '100' },
  ];

  const xLabels: { x: number; lab: string }[] = range === 'week'
    ? Array.from({ length: 7 }, (_, i) => ({ x: i, lab: i === 6 ? '今' : `${6 - i}天前` }))
    : [{ x: 0, lab: '0' }, { x: 6, lab: '早' }, { x: 12, lab: '中' }, { x: 18, lab: '晚' }, { x: 23.5, lab: '夜' }];

  return (
    <svg data-testid="hr-trend-svg" width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      {[40, 70, 100, 130, 160].map(y => (
        <g key={y}>
          <line x1={PAD.left} y1={yScale(y)} x2={W - PAD.right} y2={yScale(y)} stroke="#E5E7EB" strokeWidth={0.6} />
          <text x={PAD.left - 4} y={yScale(y) + 3} textAnchor="end" fill="#9CA3AF" fontSize={9}>{y}</text>
        </g>
      ))}
      {refLines.map(l => (
        <g key={l.label}>
          <line x1={PAD.left} y1={yScale(l.y)} x2={W - PAD.right} y2={yScale(l.y)} stroke="#F97316" strokeWidth={0.8} strokeDasharray="3 3" />
          <text x={W - PAD.right + 2} y={yScale(l.y) + 3} fill="#F97316" fontSize={9}>{l.label}</text>
        </g>
      ))}
      {xLabels.map((lab, i) => (
        <text key={i} x={xScale(lab.x)} y={H - 8} textAnchor="middle" fill="#9CA3AF" fontSize={10}>{lab.lab}</text>
      ))}
      <path d={pathD} fill="none" stroke="#0EA5E9" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {sorted.map((p, i) => {
        const j = judgeHeartRate(p.y);
        const fill = j?.color === 'orange' ? '#F97316' : '#0EA5E9';
        return (
          <circle
            key={i}
            data-testid={`hr-trend-point-${i}`}
            cx={xScale(p.x)} cy={yScale(p.y)} r={4} fill={fill} stroke="#fff" strokeWidth={1.2}
            style={{ cursor: 'pointer' }}
            onClick={() => onPointClick({
              measured_at: p.raw.measured_at,
              value: p.y,
              label: j?.label || '',
              source: p.raw.source,
              activity: typeof p.raw.value?.activity === 'string' ? p.raw.value.activity : null,
            })}
          />
        );
      })}
    </svg>
  );
}

function BgMenuItem({ label, onClick, last }: { label: string; onClick: () => void; last?: boolean }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 0', borderBottom: last ? 'none' : '1px solid #F1F5F9',
        cursor: 'pointer',
      }}
    >
      <span style={{ fontSize: 14, color: '#374151' }}>{label}</span>
      <span style={{ color: '#9CA3AF' }}>›</span>
    </div>
  );
}

interface BgTrendChartProps {
  data: Record<'fasting' | 'after_meal' | 'bedtime', { x: number; y: number; raw: MetricRecord }[]>;
  range: BgTrendRange;
}

function BgTrendChart({ data, range }: BgTrendChartProps) {
  const W = 340, H = 200;
  const PAD = { top: 14, right: 14, bottom: 28, left: 36 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  const allPoints = [...data.fasting, ...data.after_meal, ...data.bedtime];
  const isEmpty = allPoints.length === 0;

  const xMax = range === 'today' ? 24 : (range === 'week' ? 6 : 29);
  const yMin = 2, yMax = 18;

  const xScale = (x: number) => PAD.left + (x / xMax) * cw;
  const yScale = (y: number) => PAD.top + ch - ((y - yMin) / (yMax - yMin)) * ch;

  const buildPath = (pts: { x: number; y: number }[]) => {
    if (pts.length === 0) return '';
    const sorted = [...pts].sort((a, b) => a.x - b.x);
    return sorted.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(' ');
  };

  const refLines: { y: number; color: string; label: string; dash?: string }[] = [
    { y: 3.9, color: '#94A3B8', label: '3.9', dash: '3 3' },
    { y: 7.8, color: '#F97316', label: '7.8', dash: '3 3' },
    { y: 11.1, color: '#EF4444', label: '11.1', dash: '3 3' },
  ];

  const xLabels: { x: number; lab: string }[] = (() => {
    if (range === 'today') {
      return [
        { x: 0, lab: '0' }, { x: 6, lab: '早' }, { x: 12, lab: '中' }, { x: 18, lab: '晚' }, { x: 23.5, lab: '夜' },
      ];
    }
    if (range === 'week') {
      return Array.from({ length: 7 }, (_, i) => ({ x: i, lab: i === 6 ? '今' : `${6 - i}天前` }));
    }
    return [{ x: 0, lab: '30天前' }, { x: 14, lab: '15天前' }, { x: 29, lab: '今' }];
  })();

  if (isEmpty) {
    return (
      <div data-testid="bg-trend-empty" style={{ padding: '30px 8px', textAlign: 'center' }}>
        <svg width="80" height="64" viewBox="0 0 80 64" style={{ display: 'block', margin: '0 auto 8px' }} aria-hidden="true">
          <path d="M10 50 Q 25 30 40 40 T 70 25" stroke="#0EA5E9" strokeWidth="2" fill="none" strokeDasharray="3 3" />
          <circle cx="40" cy="40" r="4" fill="#F97316" />
          <circle cx="22" cy="36" r="4" fill="#1E40AF" />
          <circle cx="60" cy="30" r="4" fill="#8B5CF6" />
        </svg>
        <div style={{ fontSize: 14, color: '#6B7280' }}>暂无数据，点击右上角录入</div>
      </div>
    );
  }

  return (
    <svg data-testid="bg-trend-svg" width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      {/* 网格 + Y 轴标签 */}
      {[2, 6, 10, 14, 18].map(y => (
        <g key={y}>
          <line x1={PAD.left} y1={yScale(y)} x2={W - PAD.right} y2={yScale(y)} stroke="#E5E7EB" strokeWidth={0.6} />
          <text x={PAD.left - 4} y={yScale(y) + 3} textAnchor="end" fill="#9CA3AF" fontSize={9}>{y}</text>
        </g>
      ))}
      {/* 参考线 */}
      {refLines.map((l) => (
        <g key={l.label}>
          <line x1={PAD.left} y1={yScale(l.y)} x2={W - PAD.right} y2={yScale(l.y)} stroke={l.color} strokeWidth={0.8} strokeDasharray={l.dash} />
          <text x={W - PAD.right + 2} y={yScale(l.y) + 3} fill={l.color} fontSize={9}>{l.label}</text>
        </g>
      ))}
      {/* X 轴标签 */}
      {xLabels.map((lab, i) => (
        <text key={i} x={xScale(lab.x)} y={H - 8} textAnchor="middle" fill="#9CA3AF" fontSize={10}>{lab.lab}</text>
      ))}
      {/* 三条线 */}
      <path d={buildPath(data.fasting)} fill="none" stroke="#1E40AF" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <path d={buildPath(data.after_meal)} fill="none" stroke="#F97316" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <path d={buildPath(data.bedtime)} fill="none" stroke="#8B5CF6" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {/* 数据点 */}
      {data.fasting.map((p, i) => (
        <circle key={`f${i}`} cx={xScale(p.x)} cy={yScale(p.y)} r={3} fill="#1E40AF" stroke="#fff" strokeWidth={1} />
      ))}
      {data.after_meal.map((p, i) => (
        <circle key={`a${i}`} cx={xScale(p.x)} cy={yScale(p.y)} r={3} fill="#F97316" stroke="#fff" strokeWidth={1} />
      ))}
      {data.bedtime.map((p, i) => (
        <circle key={`b${i}`} cx={xScale(p.x)} cy={yScale(p.y)} r={3} fill="#8B5CF6" stroke="#fff" strokeWidth={1} />
      ))}
    </svg>
  );
}
