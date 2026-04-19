'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, SpinLoading, Toast, ProgressBar } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface DayData {
  date: string;
  rate: number;
}

interface PlanRank {
  name: string;
  rate: number;
  color: string;
}

interface Statistics {
  today_completed: number;
  today_total: number;
  streak_days: number;
  weekly_data: DayData[];
  monthly_data: DayData[];
  plan_ranks: PlanRank[];
}

const RANK_COLORS = ['#52c41a', '#1890ff', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#faad14'];

/**
 * 月视图平滑曲线 + 渐变面积填充折线图（v6 新增）
 * - 容器固定 160px 高度，无拉伸
 * - 仅标记最高点（绿▲）和最低点（橙▼）
 */
function SmoothLineChart({ data }: { data: DayData[] }) {
  const W = 320; // 视口宽度（viewBox），保持比例
  const H = 160;
  const padX = 8;
  const padTop = 18;
  const padBottom = 22;

  if (!data || data.length === 0) {
    return <div className="text-center text-gray-400 text-sm py-8">暂无数据</div>;
  }

  const n = data.length;
  const usableW = W - padX * 2;
  const usableH = H - padTop - padBottom;
  const stepX = n > 1 ? usableW / (n - 1) : usableW;
  const maxR = Math.max(100, ...data.map((d) => d.rate));
  const points = data.map((d, i) => ({
    x: padX + i * stepX,
    y: padTop + (1 - d.rate / maxR) * usableH,
    rate: d.rate,
    date: d.date,
  }));

  // Catmull-Rom -> Bezier 平滑曲线
  const linePath = points.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const p0 = points[i - 1];
    const p2 = points[i + 1] || p;
    const p_1 = points[i - 2] || p0;
    const c1x = p0.x + (p.x - p_1.x) / 6;
    const c1y = p0.y + (p.y - p_1.y) / 6;
    const c2x = p.x - (p2.x - p0.x) / 6;
    const c2y = p.y - (p2.y - p0.y) / 6;
    return `${acc} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p.x} ${p.y}`;
  }, '');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${H - padBottom} L ${points[0].x} ${H - padBottom} Z`;

  // 找最高点 / 最低点（多点同值取首个）
  let maxIdx = 0;
  let minIdx = 0;
  data.forEach((d, i) => {
    if (d.rate > data[maxIdx].rate) maxIdx = i;
    if (d.rate < data[minIdx].rate) minIdx = i;
  });
  const maxPoint = points[maxIdx];
  const minPoint = points[minIdx];

  const xLabels = data
    .map((d, i) => ({ x: padX + i * stepX, label: d.date.slice(-2), idx: i }))
    .filter((it) => it.idx === 0 || it.idx === n - 1 || it.idx % 5 === 0);

  return (
    <div style={{ width: '100%', height: 160, position: 'relative' }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height: '100%', display: 'block' }}
      >
        <defs>
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#52c41a" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#52c41a" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {/* 背景网格线 */}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => (
          <line
            key={r}
            x1={padX}
            x2={W - padX}
            y1={padTop + r * usableH}
            y2={padTop + r * usableH}
            stroke="#f0f0f0"
            strokeWidth="0.5"
          />
        ))}
        {/* 渐变面积 */}
        <path d={areaPath} fill="url(#areaGradient)" />
        {/* 平滑曲线 */}
        <path d={linePath} fill="none" stroke="#52c41a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        {/* 最高点：绿▲ */}
        <g>
          <polygon
            points={`${maxPoint.x},${maxPoint.y - 7} ${maxPoint.x - 5},${maxPoint.y + 1} ${maxPoint.x + 5},${maxPoint.y + 1}`}
            fill="#52c41a"
          />
          <text
            x={maxPoint.x}
            y={maxPoint.y - 10}
            textAnchor="middle"
            style={{ fontSize: 9, fill: '#52c41a', fontWeight: 600 }}
          >
            {Math.round(maxPoint.rate)}%
          </text>
        </g>
        {/* 最低点：橙▼ */}
        {minIdx !== maxIdx && (
          <g>
            <polygon
              points={`${minPoint.x},${minPoint.y + 7} ${minPoint.x - 5},${minPoint.y - 1} ${minPoint.x + 5},${minPoint.y - 1}`}
              fill="#fa8c16"
            />
            <text
              x={minPoint.x}
              y={minPoint.y + 16}
              textAnchor="middle"
              style={{ fontSize: 9, fill: '#fa8c16', fontWeight: 600 }}
            >
              {Math.round(minPoint.rate)}%
            </text>
          </g>
        )}
        {/* X 轴标签 */}
        {xLabels.map((it) => (
          <text
            key={it.idx}
            x={it.x}
            y={H - 6}
            textAnchor="middle"
            style={{ fontSize: 9, fill: '#999' }}
          >
            {it.label}
          </text>
        ))}
      </svg>
    </div>
  );
}

export default function StatisticsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Statistics | null>(null);
  const [timeRange, setTimeRange] = useState<'week' | 'month'>('week');

  useEffect(() => {
    const mapDayData = (items: any[], rates: number[] | null): DayData[] =>
      (items || []).map((d: any, i: number) => ({
        date: d.date || '',
        rate: rates && rates[i] != null ? rates[i] : (d.rate ?? d.count ?? 0),
      }));

    const fetchData = async () => {
      try {
        const res: any = await api.get('/api/health-plan/statistics');
        const raw = res.data || res;
        setStats({
          today_completed: raw.today_completed ?? 0,
          today_total: raw.today_total ?? 0,
          streak_days: raw.streak_days ?? raw.consecutive_days ?? 0,
          weekly_data: mapDayData(raw.weekly_data, raw.weekly_rates),
          monthly_data: mapDayData(raw.monthly_data, raw.monthly_rates),
          plan_ranks: (raw.plan_rankings || []).map((p: any, i: number) => ({
            name: p.plan_name || p.name || `计划${i + 1}`,
            rate: p.completion_rate ?? p.rate ?? 0,
            color: p.color || RANK_COLORS[i % RANK_COLORS.length],
          })),
        });
      } catch {
        setStats({
          today_completed: 0,
          today_total: 0,
          streak_days: 0,
          weekly_data: [],
          monthly_data: [],
          plan_ranks: [],
        });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>打卡统计</GreenNavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!stats) return null;

  const todayRate = stats.today_total > 0
    ? Math.round((stats.today_completed / stats.today_total) * 100)
    : 0;

  const chartData = timeRange === 'week' ? stats.weekly_data : stats.monthly_data;
  const maxRate = chartData.length > 0 ? Math.max(...chartData.map((d) => d.rate), 1) : 100;

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <GreenNavBar>打卡统计</GreenNavBar>

      <div className="px-4 py-5" style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
        <div className="flex items-center justify-around text-white">
          <div className="text-center">
            <div className="relative w-20 h-20 mx-auto mb-2">
              <svg viewBox="0 0 100 100" className="w-full h-full" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="8" />
                <circle
                  cx="50" cy="50" r="42"
                  fill="none" stroke="#fff" strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${(todayRate / 100) * 264} 264`}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold">{todayRate}%</span>
              </div>
            </div>
            <div className="text-xs opacity-80">今日完成</div>
            <div className="text-sm font-medium">{stats.today_completed}/{stats.today_total}</div>
          </div>
          <div className="text-center">
            <div className="w-20 h-20 mx-auto mb-2 flex items-center justify-center">
              <div>
                <div className="text-3xl font-bold">{stats.streak_days}</div>
                <div className="text-xs opacity-80">天</div>
              </div>
            </div>
            <div className="text-xs opacity-80">连续打卡</div>
            <div className="text-sm font-medium">🔥 继续加油</div>
          </div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        {chartData.length > 0 && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-around text-center">
              <div>
                <div className="text-lg font-bold" style={{ color: '#52c41a' }}>
                  {chartData.length > 0
                    ? Math.round(chartData.reduce((sum, d) => sum + d.rate, 0) / chartData.length)
                    : 0}%
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {timeRange === 'week' ? '本周' : '本月'}平均完成率
                </div>
              </div>
              <div style={{ width: 1, height: 30, background: '#f0f0f0' }} />
              <div>
                <div className="text-lg font-bold" style={{ color: '#1890ff' }}>
                  {chartData.filter((d) => d.rate >= 100).length}
                </div>
                <div className="text-xs text-gray-400 mt-1">全部完成天数</div>
              </div>
              <div style={{ width: 1, height: 30, background: '#f0f0f0' }} />
              <div>
                <div className="text-lg font-bold" style={{ color: '#fa8c16' }}>
                  {Math.max(...chartData.map((d) => d.rate), 0)}%
                </div>
                <div className="text-xs text-gray-400 mt-1">最高完成率</div>
              </div>
            </div>
          </Card>
        )}

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex items-center justify-between mb-4">
            <div className="section-title mb-0">完成率趋势</div>
            <div className="flex gap-1">
              {(['week', 'month'] as const).map((r) => (
                <div
                  key={r}
                  onClick={() => setTimeRange(r)}
                  className="px-3 py-1 rounded-full text-xs cursor-pointer"
                  style={{
                    background: timeRange === r ? '#52c41a15' : '#f5f5f5',
                    color: timeRange === r ? '#52c41a' : '#999',
                    fontWeight: timeRange === r ? 600 : 400,
                  }}
                >
                  {r === 'week' ? '周' : '月'}
                </div>
              ))}
            </div>
          </div>

          {chartData.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-8">暂无数据</div>
          ) : timeRange === 'week' ? (
            // 周视图：保持柱状图
            <div>
              <div className="flex items-end gap-1" style={{ height: 160 }}>
                {chartData.map((d, i) => {
                  const h = maxRate > 0 ? (d.rate / maxRate) * 100 : 0;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center">
                      <div className="text-xs text-gray-400 mb-1">{d.rate}%</div>
                      <div
                        className="w-full rounded-t-md"
                        style={{
                          height: `${Math.max(h, 2)}%`,
                          background: d.rate >= 80
                            ? 'linear-gradient(180deg, #52c41a, #73d13d)'
                            : d.rate >= 50
                            ? 'linear-gradient(180deg, #faad14, #ffc53d)'
                            : 'linear-gradient(180deg, #ff7a45, #ffa39e)',
                          minHeight: 4,
                          transition: 'height 0.3s ease',
                        }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-1 mt-1">
                {chartData.map((d, i) => {
                  const WEEKDAY_NAMES = ['日', '一', '二', '三', '四', '五', '六'];
                  let label = d.date.slice(-2);
                  try {
                    const dayOfWeek = new Date(d.date).getDay();
                    label = WEEKDAY_NAMES[dayOfWeek] || d.date.slice(-2);
                  } catch {/* keep */}
                  return (
                    <div key={i} className="flex-1 text-center text-xs text-gray-400" style={{ fontSize: 10 }}>
                      {label}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            // 月视图：平滑曲线 + 渐变面积填充 + 标记最高/最低
            <SmoothLineChart data={chartData} />
          )}
        </Card>

        <Card style={{ borderRadius: 12 }}>
          <div className="section-title">各计划完成率</div>
          {(!stats.plan_ranks || stats.plan_ranks.length === 0) ? (
            <div className="text-center text-gray-400 text-sm py-4">暂无数据</div>
          ) : (
            stats.plan_ranks.map((plan, idx) => (
              <div key={idx} className="mb-4 last:mb-0">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center">
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white mr-2"
                      style={{ background: RANK_COLORS[idx % RANK_COLORS.length] }}
                    >
                      {idx + 1}
                    </span>
                    <span className="text-sm">{plan.name}</span>
                  </div>
                  <span className="text-sm font-medium" style={{ color: RANK_COLORS[idx % RANK_COLORS.length] }}>
                    {plan.rate}%
                  </span>
                </div>
                <ProgressBar
                  percent={plan.rate}
                  style={{
                    '--track-width': '6px',
                    '--fill-color': RANK_COLORS[idx % RANK_COLORS.length],
                  }}
                />
              </div>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}
