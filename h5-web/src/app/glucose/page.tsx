'use client';

/**
 * [PRD-GLUCOSE-V1 2026-05-30] 血糖管理模块（H5 单页 SPA-Tab 结构）
 *
 * 页面结构（顶部 Tab 切换）：
 *   - 首页（趋势缩略 + 最近一次 + 警示条 + 录入入口）
 *   - 录入页（场景四选一 + 数值 + 备注，触发危象强弹窗）
 *   - 历史
 *   - 趋势（7/30/90 天 + 分场景）
 *   - 预警（危象事件列表 + 确认）
 *   - AI 建议
 *
 * 复用：
 *   - `/lib/api`  统一带 token 请求
 *   - `/components/GreenNavBar`  顶部绿色导航条（项目通用）
 *   - `/lib/toast-unified`  统一 Toast
 *
 * 与「健康档案 - 血压 Tab」保持视觉一致（11 级天蓝 + 病历卡风格）。
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Popup, Input, Button, TextArea } from 'antd-mobile';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';

// ─── 主题 ─────────────────────────────────────────────────────────
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
  ok: '#16A34A',
  warn: '#F59E0B',
  bad: '#EF4444',
  badDeep: '#B91C1C',
};

// ─── 场景与档位 ───────────────────────────────────────────────────
const SCENE_OPTIONS = [
  { value: 1, label: '空腹', tip: '至少 8 小时未进食' },
  { value: 2, label: '餐后 2h', tip: '从第一口饭算起 2 小时' },
  { value: 3, label: '随机', tip: '任意时间测量' },
  { value: 4, label: '睡前', tip: '入睡前 30 分钟内' },
];

const LEVEL_COLORS: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: '#FEE2E2', text: T.badDeep, label: '严重偏低' },
  2: { bg: '#FEF3C7', text: '#92400E', label: '偏低' },
  3: { bg: '#DCFCE7', text: '#166534', label: '正常' },
  4: { bg: '#FEF3C7', text: '#92400E', label: '偏高' },
  5: { bg: '#FEE2E2', text: T.bad, label: '严重偏高' },
};

// ─── 类型 ─────────────────────────────────────────────────────────
interface GlucoseRecord {
  id: number;
  user_id: number;
  value: number;
  scene: number;
  scene_label: string;
  level: number;
  level_label: string;
  level_color: string;
  is_crisis: number;
  crisis_label: string;
  measure_time: string;
  note?: string | null;
  create_time: string;
}

interface AlertItem {
  id: number;
  record_id: number;
  alert_type: number;
  alert_label: string;
  push_status: number;
  guardian_confirmed: number;
  create_time: string;
  value: number | null;
  scene: number | null;
  scene_label: string;
  measure_time: string;
}

interface SaveAlert {
  must_popup: boolean;
  alert_id: number;
  alert_type: number;
  alert_label: string;
  title: string;
  message: string;
  guardian_notified: boolean;
}

interface StatsResp {
  range_days: number;
  count: number;
  avg: number | null;
  max: number | null;
  min: number | null;
  abnormal_count: number;
  target_rate: number | null;
  trend: { date: string; avg: number | null; count: number }[];
  distribution: Record<string, number>;
}

interface AiAdviceResp {
  period_days: number;
  summary_lines: string[];
  trend_lines: string[];
  advice_lines: string[];
  disclaimer: string;
}

interface ReminderConfig {
  breakfast?: string | null;
  lunch?: string | null;
  dinner?: string | null;
  enabled: boolean;
}

// ─── 工具 ─────────────────────────────────────────────────────────
function unwrap<T>(res: unknown): T {
  // 项目里 api 的封装有时返回 { data } 有时直接返回数据
  const r: any = res;
  return (r && r.data !== undefined ? r.data : r) as T;
}

function MedicalCard({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: '#fff',
        borderLeft: `3px solid ${T.brand400}`,
        borderRadius: 16,
        padding: 16,
        boxShadow: '0 4px 16px rgba(56, 189, 248, 0.08)',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ─── Tab 定义 ──────────────────────────────────────────────────────
type TabKey = 'home' | 'add' | 'history' | 'trend' | 'alerts' | 'ai' | 'report';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'home', label: '首页' },
  { key: 'add', label: '录入' },
  { key: 'history', label: '历史' },
  { key: 'trend', label: '趋势' },
  { key: 'alerts', label: '预警' },
  { key: 'ai', label: 'AI 建议' },
  { key: 'report', label: '报告' },
];

// ─── 主页面 ───────────────────────────────────────────────────────
export default function GlucosePage() {
  const router = useRouter();
  const [tab, setTab] = useState<TabKey>('home');

  // 首页 / 趋势 / 历史共享：最近列表 + 7 天统计
  const [records, setRecords] = useState<GlucoseRecord[]>([]);
  const [stats7, setStats7] = useState<StatsResp | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 危象强弹窗
  const [crisisPopup, setCrisisPopup] = useState<SaveAlert | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rRes, sRes, aRes] = await Promise.all([
        api.get('/api/glucose-v1/records?days=90&page=1&size=20'),
        api.get('/api/glucose-v1/stats?days=7'),
        api.get('/api/glucose-v1/alerts?days=30&page=1&size=20'),
      ]);
      setRecords(unwrap<{ items: GlucoseRecord[] }>(rRes).items || []);
      setStats7(unwrap<StatsResp>(sRes));
      setAlerts(unwrap<{ items: AlertItem[] }>(aRes).items || []);
    } catch (e) {
      // 静默
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // 未确认危象事件计数
  const pendingAlerts = useMemo(
    () => alerts.filter((a) => !a.guardian_confirmed && (a.alert_type === 1 || a.alert_type === 2)),
    [alerts],
  );

  return (
    <div style={{ background: T.brand50, minHeight: '100vh', paddingBottom: 80 }}>
      <GreenNavBar>血糖管理</GreenNavBar>

      {/* 顶部 Tab 切换 */}
      <div
        data-testid="glucose-tabs"
        style={{
          display: 'flex',
          overflowX: 'auto',
          gap: 6,
          padding: '10px 12px',
          background: '#fff',
          borderBottom: `1px solid ${T.brand100}`,
          position: 'sticky',
          top: 0,
          zIndex: 5,
        }}
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`glucose-tab-${t.key}`}
            data-active={tab === t.key ? 'true' : 'false'}
            onClick={() => setTab(t.key)}
            style={{
              flexShrink: 0,
              padding: '6px 14px',
              borderRadius: 999,
              border: 'none',
              background: tab === t.key ? T.brand500 : T.brand100,
              color: tab === t.key ? '#fff' : T.brand700,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'home' && (
        <HomeTab
          records={records}
          stats={stats7}
          pendingAlerts={pendingAlerts}
          onGoAdd={() => setTab('add')}
          onGoAlerts={() => setTab('alerts')}
          onGoTrend={() => setTab('trend')}
          onGoReport={() => setTab('report')}
        />
      )}
      {tab === 'add' && (
        <AddTab
          onSaved={async (alertPayload) => {
            await fetchAll();
            if (alertPayload && alertPayload.must_popup) {
              setCrisisPopup(alertPayload);
            } else if (alertPayload) {
              showToast(alertPayload.title, 'success');
              setTab('home');
            } else {
              showToast('已保存', 'success');
              setTab('home');
            }
          }}
        />
      )}
      {tab === 'history' && <HistoryTab records={records} onChanged={fetchAll} />}
      {tab === 'trend' && <TrendTab />}
      {tab === 'alerts' && <AlertsTab alerts={alerts} onConfirmed={fetchAll} />}
      {tab === 'ai' && <AiTab />}
      {tab === 'report' && <ReportTab />}

      <CrisisPopup detail={crisisPopup} onClose={() => {
        setCrisisPopup(null);
        setTab('home');
      }} />
    </div>
  );
}

// ─── 首页 Tab ─────────────────────────────────────────────────────
function HomeTab(props: {
  records: GlucoseRecord[];
  stats: StatsResp | null;
  pendingAlerts: AlertItem[];
  onGoAdd: () => void;
  onGoAlerts: () => void;
  onGoTrend: () => void;
  onGoReport: () => void;
}) {
  const { records, stats, pendingAlerts, onGoAdd, onGoAlerts, onGoTrend, onGoReport } = props;
  const latest = records[0];
  const level = latest ? LEVEL_COLORS[latest.level] : null;

  return (
    <div style={{ padding: '12px' }}>
      {/* 危象警示条 */}
      {pendingAlerts.length > 0 && (
        <div
          data-testid="glucose-alert-banner"
          onClick={onGoAlerts}
          style={{
            background: T.bad,
            color: '#fff',
            padding: '10px 14px',
            borderRadius: 10,
            marginBottom: 12,
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>⚠️ 检测到 {pendingAlerts.length} 次血糖异常事件，点击查看</span>
          <span style={{ fontSize: 16 }}>→</span>
        </div>
      )}

      {/* 最近一次卡片 */}
      <MedicalCard style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: 13, color: T.brand800 }}>最近一次</div>
            <div style={{ marginTop: 6 }}>
              {latest ? (
                <>
                  <span data-testid="glucose-latest-value" style={{ fontSize: 36, fontWeight: 800, color: T.brand700 }}>
                    {latest.value}
                  </span>
                  <span style={{ fontSize: 14, color: T.brand800, marginLeft: 4 }}>mmol/L</span>
                </>
              ) : (
                <span style={{ fontSize: 14, color: T.brand800 }}>尚无记录</span>
              )}
            </div>
            {latest && (
              <div style={{ fontSize: 12, color: T.brand600, marginTop: 6 }}>
                {latest.scene_label} · {latest.measure_time.slice(5, 16)}
              </div>
            )}
          </div>
          {level && (
            <span
              data-testid="glucose-latest-level"
              style={{
                padding: '4px 12px',
                borderRadius: 999,
                background: level.bg,
                color: level.text,
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {level.label}
            </span>
          )}
        </div>
      </MedicalCard>

      {/* 7 天关键统计 */}
      <MedicalCard style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>近 7 天</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          <StatCell label="平均" value={stats?.avg ?? '—'} />
          <StatCell label="最高" value={stats?.max ?? '—'} />
          <StatCell label="最低" value={stats?.min ?? '—'} />
          <StatCell label="异常次数" value={stats?.abnormal_count ?? 0} />
        </div>
        {/* 趋势缩略 */}
        {stats && stats.trend.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <TinyTrendChart trend={stats.trend} />
          </div>
        )}
      </MedicalCard>

      {/* 快捷入口 */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 8 }}>
        <button
          data-testid="glucose-quick-add"
          onClick={onGoAdd}
          style={{
            padding: '12px 0',
            background: T.brand500,
            color: '#fff',
            border: 'none',
            borderRadius: 12,
            fontSize: 15,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >+ 录入血糖</button>
        <QuickBtn label="趋势" onClick={onGoTrend} />
        <QuickBtn label="预警" onClick={onGoAlerts} />
        <QuickBtn label="报告" onClick={onGoReport} />
      </div>
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: any }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: T.brand700 }}>{value}</div>
      <div style={{ fontSize: 11, color: T.brand600, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function QuickBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '12px 0',
        background: '#fff',
        color: T.brand700,
        border: `1px solid ${T.brand300}`,
        borderRadius: 12,
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >{label}</button>
  );
}

function TinyTrendChart({ trend }: { trend: { date: string; avg: number | null }[] }) {
  const values = trend.map((d) => d.avg);
  const validVals = values.filter((v): v is number => v != null);
  if (validVals.length === 0) {
    return <div style={{ fontSize: 12, color: T.brand600, textAlign: 'center' }}>暂无近 7 天数据</div>;
  }
  const min = Math.min(...validVals, 3);
  const max = Math.max(...validVals, 10);
  const range = max - min || 1;
  const W = 320, H = 60;
  const n = values.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} data-testid="glucose-tiny-trend">
      {/* 正常区间背景 3.9-7.8 */}
      <rect x={0} y={H - ((7.8 - min) / range) * H} width={W}
            height={Math.max(((7.8 - 3.9) / range) * H, 0)}
            fill="#DCFCE7" opacity={0.4} />
      <polyline
        points={values.map((v, i) => {
          if (v == null) return '';
          const x = (i / Math.max(n - 1, 1)) * W;
          const y = H - ((v - min) / range) * H;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).filter(Boolean).join(' ')}
        fill="none"
        stroke={T.brand500}
        strokeWidth={2}
      />
      {values.map((v, i) => v != null ? (
        <circle key={i}
                cx={(i / Math.max(n - 1, 1)) * W}
                cy={H - ((v - min) / range) * H}
                r={3} fill={T.brand500} />
      ) : null)}
    </svg>
  );
}

// ─── 录入 Tab ─────────────────────────────────────────────────────
function AddTab({ onSaved }: { onSaved: (alert: SaveAlert | null) => void }) {
  const [value, setValue] = useState('');
  const [scene, setScene] = useState<number>(() => recommendScene());
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  function recommendScene(): number {
    const h = new Date().getHours();
    if (h < 9) return 1;          // 空腹
    if (h >= 9 && h < 14) return 2; // 餐后2h
    if (h >= 21) return 4;          // 睡前
    return 3;                        // 随机
  }

  const handleSave = async () => {
    const v = Number(value);
    if (!value || Number.isNaN(v)) {
      showToast('请填写测量值', 'fail');
      return;
    }
    if (v < 0.5 || v > 35.0) {
      showToast('数值不在合理范围（0.5~35.0）', 'fail');
      return;
    }
    setSaving(true);
    try {
      const res: any = await api.post('/api/glucose-v1/records', {
        value: Math.round(v * 10) / 10,
        scene,
        note: note.trim() || null,
      });
      const data = unwrap<{ record: GlucoseRecord; alert: SaveAlert | null }>(res);
      onSaved(data.alert);
    } catch {
      showToast('保存失败，请重试', 'fail');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: 12 }}>
      <MedicalCard>
        <div style={{ fontSize: 16, fontWeight: 600, color: T.brand700, marginBottom: 12 }}>录入血糖</div>

        {/* 测量值 */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: T.brand800, marginBottom: 6 }}>测量值（mmol/L）</div>
          <Input
            data-testid="glucose-input-value"
            type="number"
            placeholder="请输入 0.5 ~ 35.0"
            value={value}
            onChange={setValue}
            style={{
              '--font-size': '20px',
              padding: '12px 14px',
              background: T.brand50,
              borderRadius: 10,
              border: `1px solid ${T.brand200}`,
            } as any}
          />
        </div>

        {/* 场景四选一 */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: T.brand800, marginBottom: 6 }}>测量场景</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {SCENE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                data-testid={`glucose-scene-${opt.value}`}
                data-active={scene === opt.value ? 'true' : 'false'}
                onClick={() => setScene(opt.value)}
                style={{
                  padding: '10px 0',
                  background: scene === opt.value ? T.brand500 : T.brand100,
                  color: scene === opt.value ? '#fff' : T.brand700,
                  border: 'none',
                  borderRadius: 10,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >{opt.label}</button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: T.brand600, marginTop: 4 }}>
            {SCENE_OPTIONS.find((o) => o.value === scene)?.tip}
          </div>
        </div>

        {/* 备注 */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: T.brand800, marginBottom: 6 }}>备注（选填）</div>
          <TextArea
            data-testid="glucose-input-note"
            placeholder="今天吃了什么 / 运动情况等，200 字以内"
            value={note}
            onChange={setNote}
            maxLength={200}
            rows={3}
            style={{
              '--font-size': '14px',
              padding: '10px 12px',
              background: T.brand50,
              borderRadius: 10,
              border: `1px solid ${T.brand200}`,
            } as any}
          />
        </div>

        <Button
          block color="primary"
          loading={saving}
          onClick={handleSave}
          data-testid="glucose-save-btn"
          style={{
            '--background-color': T.brand500,
            '--border-radius': '12px',
            height: 48,
            fontSize: 16,
            fontWeight: 600,
          } as any}
        >保存</Button>
      </MedicalCard>

      {/* 五档阈值速查表 */}
      <MedicalCard style={{ marginTop: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>五档阈值速查（mmol/L）</div>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: T.brand600 }}>
              <th style={{ textAlign: 'left', padding: '4px 0' }}>档位</th>
              <th>空腹</th>
              <th>餐后2h/随机/睡前</th>
            </tr>
          </thead>
          <tbody>
            {[
              { l: '严重偏低', a: '<2.8', b: '<2.8', c: '#FEE2E2' },
              { l: '偏低', a: '2.8 ~ 3.9', b: '2.8 ~ 3.9', c: '#FEF3C7' },
              { l: '正常', a: '3.9 ~ 6.1', b: '3.9 ~ 7.8', c: '#DCFCE7' },
              { l: '偏高', a: '6.1 ~ 7.0', b: '7.8 ~ 11.1', c: '#FEF3C7' },
              { l: '严重偏高', a: '≥ 7.0', b: '≥ 11.1', c: '#FEE2E2' },
            ].map((r) => (
              <tr key={r.l} style={{ background: r.c }}>
                <td style={{ padding: '4px 6px', fontWeight: 600 }}>{r.l}</td>
                <td style={{ textAlign: 'center' }}>{r.a}</td>
                <td style={{ textAlign: 'center' }}>{r.b}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ fontSize: 11, color: T.bad, marginTop: 6 }}>
          ⚠️ 数值 ≥ 16.7 触发高糖危象 / 数值 &lt; 2.8 触发低糖危象（不分场景）
        </div>
      </MedicalCard>
    </div>
  );
}

// ─── 历史 Tab ─────────────────────────────────────────────────────
function HistoryTab({ records, onChanged }: { records: GlucoseRecord[]; onChanged: () => void }) {
  const [filterScene, setFilterScene] = useState<number | null>(null);
  const filtered = useMemo(
    () => records.filter((r) => filterScene === null || r.scene === filterScene),
    [records, filterScene],
  );

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除这条记录吗？')) return;
    try {
      await api.delete(`/api/glucose-v1/records/${id}`);
      showToast('已删除', 'success');
      onChanged();
    } catch {
      showToast('删除失败', 'fail');
    }
  };

  return (
    <div style={{ padding: 12 }}>
      {/* 场景筛选 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto' }}>
        <FilterChip label="全部" active={filterScene === null} onClick={() => setFilterScene(null)} />
        {SCENE_OPTIONS.map((s) => (
          <FilterChip key={s.value} label={s.label}
                      active={filterScene === s.value}
                      onClick={() => setFilterScene(s.value)} />
        ))}
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: T.brand600 }}>暂无记录</div>
      ) : (
        <MedicalCard>
          {filtered.map((r) => {
            const lc = LEVEL_COLORS[r.level];
            return (
              <div
                key={r.id}
                data-testid={`glucose-history-row-${r.id}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 0',
                  borderBottom: `1px solid ${T.brand100}`,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontSize: 18, fontWeight: 700, color: T.brand700 }}>{r.value}</span>
                    <span style={{ fontSize: 12, color: T.brand600 }}>mmol/L</span>
                    {r.is_crisis > 0 && (
                      <span style={{
                        fontSize: 10, padding: '2px 6px', borderRadius: 8,
                        background: T.badDeep, color: '#fff', fontWeight: 700,
                      }}>{r.crisis_label}</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: T.brand600, marginTop: 2 }}>
                    {r.scene_label} · {r.measure_time.slice(5, 16)}
                  </div>
                  {r.note && <div style={{ fontSize: 12, color: T.brand800, marginTop: 2 }}>📝 {r.note}</div>}
                </div>
                <span style={{
                  padding: '3px 10px', borderRadius: 999,
                  background: lc.bg, color: lc.text,
                  fontSize: 11, fontWeight: 700,
                  marginRight: 8,
                }}>{lc.label}</span>
                <button
                  onClick={() => handleDelete(r.id)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: T.bad,
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                >删除</button>
              </div>
            );
          })}
        </MedicalCard>
      )}
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '6px 14px',
        background: active ? T.brand500 : T.brand100,
        color: active ? '#fff' : T.brand700,
        border: 'none',
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        flexShrink: 0,
      }}
    >{label}</button>
  );
}

// ─── 趋势 Tab ─────────────────────────────────────────────────────
function TrendTab() {
  const [days, setDays] = useState<number>(7);
  const [scene, setScene] = useState<number | null>(null);
  const [stats, setStats] = useState<StatsResp | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: string[] = [`days=${days}`];
      if (scene != null) params.push(`scene=${scene}`);
      const res = await api.get(`/api/glucose-v1/stats?${params.join('&')}`);
      setStats(unwrap<StatsResp>(res));
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [days, scene]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: 12 }}>
      {/* 时间范围 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        {[7, 30, 90].map((d) => (
          <FilterChip key={d} label={`${d} 天`} active={days === d} onClick={() => setDays(d)} />
        ))}
      </div>
      {/* 场景 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto' }}>
        <FilterChip label="全部场景" active={scene === null} onClick={() => setScene(null)} />
        {SCENE_OPTIONS.map((s) => (
          <FilterChip key={s.value} label={s.label}
                      active={scene === s.value}
                      onClick={() => setScene(s.value)} />
        ))}
      </div>

      {!stats || stats.count === 0 ? (
        <MedicalCard><div style={{ textAlign: 'center', padding: 24, color: T.brand600 }}>暂无数据</div></MedicalCard>
      ) : (
        <>
          {/* 关键指标 */}
          <MedicalCard style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>关键指标</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              <StatCell label="平均" value={stats.avg ?? '—'} />
              <StatCell label="最高" value={stats.max ?? '—'} />
              <StatCell label="最低" value={stats.min ?? '—'} />
              <StatCell label="测量次数" value={stats.count} />
              <StatCell label="异常次数" value={stats.abnormal_count} />
              <StatCell label="达标率"
                        value={stats.target_rate != null ? `${Math.round(stats.target_rate * 100)}%` : '—'} />
            </div>
          </MedicalCard>

          {/* 折线图 */}
          <MedicalCard style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>趋势曲线</div>
            <TrendLineChart trend={stats.trend} />
          </MedicalCard>

          {/* 五档分布 */}
          <MedicalCard>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>五档分布</div>
            {Object.entries(stats.distribution).map(([k, v]) => {
              const pct = stats.count > 0 ? Math.round((v / stats.count) * 100) : 0;
              const color = k.includes('严重') ? T.bad : k.includes('正常') ? T.ok : T.warn;
              return (
                <div key={k} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: T.brand800 }}>
                    <span>{k}</span><span>{v} 次（{pct}%）</span>
                  </div>
                  <div style={{ height: 6, background: T.brand100, borderRadius: 3, marginTop: 4 }}>
                    <div style={{ height: '100%', background: color, borderRadius: 3, width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </MedicalCard>
        </>
      )}
    </div>
  );
}

function TrendLineChart({ trend }: { trend: { date: string; avg: number | null }[] }) {
  const values = trend.map((d) => d.avg);
  const valid = values.filter((v): v is number => v != null);
  if (valid.length === 0) return <div style={{ color: T.brand600, textAlign: 'center', padding: 16 }}>暂无趋势</div>;
  const min = Math.min(...valid, 3);
  const max = Math.max(...valid, 12);
  const range = max - min || 1;
  const W = 340, H = 180;
  const PAD = { l: 28, r: 10, t: 12, b: 24 };
  const cw = W - PAD.l - PAD.r;
  const ch = H - PAD.t - PAD.b;
  const n = values.length;

  const yScale = (v: number) => PAD.t + ch - ((v - min) / range) * ch;
  const xScale = (i: number) => PAD.l + (i / Math.max(n - 1, 1)) * cw;

  // 正常区间 3.9 - 7.8
  const yNormalHi = Math.max(yScale(7.8), PAD.t);
  const yNormalLo = Math.min(yScale(3.9), PAD.t + ch);

  // 折线
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

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" data-testid="glucose-trend-line">
      {/* 正常区间背景 */}
      <rect x={PAD.l} y={yNormalHi} width={cw} height={Math.max(yNormalLo - yNormalHi, 0)}
            fill="#DCFCE7" opacity={0.55} />
      {/* 参考线 11.1 + 危象 16.7 */}
      {[7.8, 11.1, 16.7].map((v) => v >= min && v <= max ? (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={yScale(v)} y2={yScale(v)}
                stroke={v === 16.7 ? T.bad : T.warn}
                strokeWidth={0.8} strokeDasharray="4 3" />
          <text x={W - PAD.r} y={yScale(v) - 2} textAnchor="end" fontSize={9}
                fill={v === 16.7 ? T.bad : T.warn}>{v}</text>
        </g>
      ) : null)}
      {/* 折线 */}
      <path d={segs.join(' ')} fill="none" stroke={T.brand500} strokeWidth={2} />
      {/* 数据点 */}
      {values.map((v, i) => v != null ? (
        <circle key={i} cx={xScale(i)} cy={yScale(v)} r={3} fill={T.brand500} />
      ) : null)}
      {/* X 轴稀疏标签 */}
      {[0, Math.floor(n / 2), n - 1].map((i) => {
        if (i < 0 || i >= n) return null;
        const d = trend[i]?.date || '';
        return (
          <text key={i} x={xScale(i)} y={H - 6} fontSize={9} textAnchor="middle" fill={T.brand600}>
            {d.slice(5)}
          </text>
        );
      })}
    </svg>
  );
}

// ─── 预警 Tab ─────────────────────────────────────────────────────
function AlertsTab({ alerts, onConfirmed }: { alerts: AlertItem[]; onConfirmed: () => void }) {
  const handleConfirm = async (id: number) => {
    try {
      await api.post(`/api/glucose-v1/alerts/${id}/confirm`);
      showToast('已标记处理', 'success');
      onConfirmed();
    } catch {
      showToast('操作失败', 'fail');
    }
  };

  return (
    <div style={{ padding: 12 }}>
      {alerts.length === 0 ? (
        <MedicalCard>
          <div style={{ textAlign: 'center', padding: 30, color: T.brand600 }}>暂无预警事件 🎉</div>
        </MedicalCard>
      ) : (
        <MedicalCard>
          {alerts.map((a) => (
            <div key={a.id} data-testid={`glucose-alert-${a.id}`}
                 style={{
                   borderBottom: `1px solid ${T.brand100}`,
                   padding: '12px 0',
                 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: T.bad }}>
                    {a.alert_label}
                    {a.value != null && <span style={{ marginLeft: 8 }}>{a.value} mmol/L</span>}
                  </div>
                  <div style={{ fontSize: 12, color: T.brand600, marginTop: 4 }}>
                    {a.scene_label && `${a.scene_label} · `}
                    {a.measure_time.slice(5, 16) || a.create_time.slice(5, 16)}
                  </div>
                  <div style={{ fontSize: 12, color: T.brand800, marginTop: 4 }}>
                    推送状态：{a.push_status === 1 ? '✅ 已推送' : a.push_status === 2 ? '❌ 推送失败' : '⏳ 待推送'}
                  </div>
                </div>
                {a.guardian_confirmed ? (
                  <span style={{
                    padding: '4px 10px', borderRadius: 999,
                    background: T.brand100, color: T.brand700,
                    fontSize: 11, fontWeight: 700,
                  }}>已处理</span>
                ) : (
                  <button onClick={() => handleConfirm(a.id)}
                          style={{
                            padding: '4px 10px', borderRadius: 8,
                            background: T.brand500, color: '#fff',
                            border: 'none', fontSize: 12, fontWeight: 600,
                            cursor: 'pointer',
                          }}>标记已处理</button>
                )}
              </div>
            </div>
          ))}
        </MedicalCard>
      )}
    </div>
  );
}

// ─── AI 建议 Tab ──────────────────────────────────────────────────
function AiTab() {
  const [advice, setAdvice] = useState<AiAdviceResp | null>(null);
  const [days, setDays] = useState<number>(30);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/glucose-v1/ai-advice?days=${days}`);
      setAdvice(unwrap<AiAdviceResp>(res));
    } catch {
      setAdvice(null);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {[7, 30, 90].map((d) => (
          <FilterChip key={d} label={`${d} 天`} active={days === d} onClick={() => setDays(d)} />
        ))}
      </div>
      {loading && <div style={{ textAlign: 'center', padding: 24, color: T.brand600 }}>分析中…</div>}
      {advice && (
        <>
          <MedicalCard style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: T.brand700, marginBottom: 8 }}>📊 概况</div>
            {advice.summary_lines.map((s, i) => (
              <div key={i} style={{ fontSize: 13, color: T.brand800, marginBottom: 4 }}>• {s}</div>
            ))}
          </MedicalCard>

          <MedicalCard style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: T.brand700, marginBottom: 8 }}>📈 趋势观察</div>
            {advice.trend_lines.map((s, i) => (
              <div key={i} style={{ fontSize: 13, color: T.brand800, marginBottom: 4 }}>• {s}</div>
            ))}
          </MedicalCard>

          <MedicalCard style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: T.brand700, marginBottom: 8 }}>💡 个性化建议</div>
            {advice.advice_lines.map((s, i) => (
              <div key={i} style={{ fontSize: 13, color: T.brand800, marginBottom: 6 }}>{i + 1}. {s}</div>
            ))}
          </MedicalCard>

          <div data-testid="glucose-ai-disclaimer"
               style={{
                 marginTop: 12, padding: 10, borderRadius: 8,
                 background: '#FEF3C7', color: '#92400E',
                 fontSize: 12, fontWeight: 600, textAlign: 'center',
               }}>
            ⚠️ {advice.disclaimer}
          </div>
        </>
      )}
    </div>
  );
}

// ─── 报告 Tab ────────────────────────────────────────────────────
function ReportTab() {
  const [days, setDays] = useState<number>(30);
  const [report, setReport] = useState<any>(null);
  const [reminder, setReminder] = useState<ReminderConfig | null>(null);
  const [savingReminder, setSavingReminder] = useState(false);

  const loadReport = useCallback(async () => {
    try {
      const res = await api.get(`/api/glucose-v1/report?days=${days}`);
      setReport(unwrap<any>(res));
    } catch { /* 静默 */ }
  }, [days]);

  const loadReminder = useCallback(async () => {
    try {
      const res = await api.get('/api/glucose-v1/reminder');
      setReminder(unwrap<ReminderConfig>(res));
    } catch { /* 静默 */ }
  }, []);

  useEffect(() => { loadReport(); }, [loadReport]);
  useEffect(() => { loadReminder(); }, [loadReminder]);

  const handleSaveReminder = async () => {
    if (!reminder) return;
    setSavingReminder(true);
    try {
      await api.put('/api/glucose-v1/reminder', reminder);
      showToast('已保存提醒设置', 'success');
    } catch {
      showToast('保存失败', 'fail');
    } finally {
      setSavingReminder(false);
    }
  };

  return (
    <div style={{ padding: 12 }}>
      {/* 报告内容预览 */}
      <MedicalCard style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: T.brand700, marginBottom: 8 }}>📄 血糖管理报告</div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
          {[7, 30, 90].map((d) => (
            <FilterChip key={d} label={`${d} 天`} active={days === d} onClick={() => setDays(d)} />
          ))}
        </div>
        {report && (
          <div style={{ fontSize: 13, color: T.brand800, lineHeight: 1.7 }}>
            <div>· 生成时间：{report.generated_at}</div>
            <div>· 数据范围：近 {report.period_days} 天</div>
            <div>· 测量总次数：{report.stats?.count ?? 0}</div>
            <div>· 平均血糖：{report.stats?.avg ?? '—'} mmol/L</div>
            <div>· 异常次数：{report.stats?.abnormal_count ?? 0}</div>
            <div style={{ marginTop: 8, fontSize: 11, color: T.brand600 }}>
              分享链接有效期 {report.share_valid_days} 天（请向医生发送系统内置短链）
            </div>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button
            onClick={() => showToast('正在准备下载，请稍候…（PDF 模块敬请期待）', 'success')}
            style={{
              flex: 1, padding: '10px 0', background: T.brand500, color: '#fff',
              border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}
          >下载 PDF</button>
          <button
            onClick={() => navigator.clipboard?.writeText(window.location.origin + (report?.share_url || ''))}
            style={{
              flex: 1, padding: '10px 0', background: '#fff', color: T.brand700,
              border: `1px solid ${T.brand300}`, borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}
          >复制分享链接</button>
        </div>
      </MedicalCard>

      {/* 餐后 2h 提醒设置 */}
      <MedicalCard>
        <div style={{ fontSize: 14, fontWeight: 700, color: T.brand700, marginBottom: 8 }}>⏰ 餐后 2 小时提醒</div>
        {reminder && (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'flex', alignItems: 'center', fontSize: 14, color: T.brand800 }}>
                <input
                  type="checkbox"
                  checked={reminder.enabled}
                  onChange={(e) => setReminder({ ...reminder, enabled: e.target.checked })}
                  style={{ marginRight: 8 }}
                />
                开启提醒
              </label>
            </div>
            {[
              { k: 'breakfast', label: '早餐时间' },
              { k: 'lunch', label: '午餐时间' },
              { k: 'dinner', label: '晚餐时间' },
            ].map(({ k, label }) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ width: 96, fontSize: 13, color: T.brand800 }}>{label}</span>
                <input
                  type="time"
                  value={(reminder as any)[k] || ''}
                  onChange={(e) => setReminder({ ...reminder, [k]: e.target.value })}
                  style={{
                    padding: '6px 10px',
                    border: `1px solid ${T.brand200}`,
                    borderRadius: 8,
                    fontSize: 14,
                  }}
                />
              </div>
            ))}
            <Button
              block color="primary" loading={savingReminder} onClick={handleSaveReminder}
              style={{
                '--background-color': T.brand500, '--border-radius': '10px',
                height: 40, fontSize: 14, marginTop: 8,
              } as any}
            >保存提醒设置</Button>
          </>
        )}
        <div style={{ fontSize: 11, color: T.brand600, marginTop: 8 }}>
          ℹ️ 餐后 2 小时由浏览器/APP 本地定时器触发，需保持页面打开或安装 APP。
        </div>
      </MedicalCard>
    </div>
  );
}

// ─── 危象强弹窗 ──────────────────────────────────────────────────
function CrisisPopup({ detail, onClose }: { detail: SaveAlert | null; onClose: () => void }) {
  return (
    <Popup
      visible={!!detail}
      // 不提供 onMaskClick：必须点击「我知道了」才能关闭（PRD §3.5）
      bodyStyle={{
        borderTopLeftRadius: 16,
        borderTopRightRadius: 16,
        padding: 24,
      }}
      closeOnMaskClick={false}
      showCloseButton={false}
    >
      {detail && (
        <div data-testid="glucose-crisis-popup">
          <div style={{ fontSize: 22, fontWeight: 800, color: T.bad, textAlign: 'center', marginBottom: 12 }}>
            ⚠️ {detail.title}
          </div>
          <div style={{
            background: '#FEF2F2',
            borderRadius: 12,
            padding: 16,
            marginBottom: 16,
            fontSize: 14,
            color: T.badDeep,
            lineHeight: 1.7,
          }}>
            {detail.message}
          </div>
          {detail.guardian_notified && (
            <div style={{ fontSize: 12, color: T.brand600, textAlign: 'center', marginBottom: 16 }}>
              ✅ 已自动通知您的守护人
            </div>
          )}
          <Button
            block color="danger"
            data-testid="glucose-crisis-confirm"
            onClick={onClose}
            style={{
              '--background-color': T.bad, '--border-radius': '12px',
              height: 48, fontSize: 16, fontWeight: 700,
            } as any}
          >我知道了</Button>
        </div>
      )}
    </Popup>
  );
}
