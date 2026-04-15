'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Toast, Dialog } from 'antd-mobile';
import api from '@/lib/api';

/* ───── types ───── */

interface ItemDetail {
  explanation: string;
  possibleCauses: string;
  dietAdvice: string;
  exerciseAdvice: string;
  lifestyleAdvice: string;
  recheckAdvice: string;
  medicalAdvice: string;
}

interface IndicatorItem {
  name: string;
  value: string;
  unit: string;
  referenceRange: string;
  riskLevel: number;
  riskName: string;
  detail?: ItemDetail;
}

interface Category {
  name: string;
  emoji: string;
  items: IndicatorItem[];
}

interface HealthScore {
  score: number;
  level: string;
  comment: string;
}

interface Summary {
  totalItems: number;
  abnormalCount: number;
  excellentCount: number;
  normalCount: number;
}

interface AnalysisResult {
  report_id: number;
  status: string;
  healthScore: HealthScore;
  summary: Summary;
  categories: Category[];
  disclaimer: string;
}

interface ReportListItem {
  id: number;
  created_at: string;
  health_score?: number;
}

/* ───── constants ───── */

const RISK_MAP: Record<number, { name: string; color: string; emoji: string }> = {
  1: { name: '优秀', color: '#1B8C3D', emoji: '✅' },
  2: { name: '正常', color: '#4CAF50', emoji: '🟢' },
  3: { name: '轻度异常', color: '#FFC107', emoji: '⚠️' },
  4: { name: '中度异常', color: '#FF9800', emoji: '🔶' },
  5: { name: '严重异常', color: '#F44336', emoji: '🔴' },
};

const SCORE_COLOR_RANGES = [
  { min: 90, max: 100, color: '#0D7A3E' },
  { min: 75, max: 89, color: '#4CAF50' },
  { min: 60, max: 74, color: '#FFC107' },
  { min: 40, max: 59, color: '#FF9800' },
  { min: 0, max: 39, color: '#F44336' },
];

const LOADING_MESSAGES = [
  '🔬 AI 正在分析您的指标…',
  '📊 正在评估各项指标的风险等级…',
  '📝 正在生成个性化健康建议…',
  '✅ 分析完成！',
];

const BASE_SHARE_URL =
  'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/shared/report';

function getScoreColor(score: number): string {
  for (const r of SCORE_COLOR_RANGES) {
    if (score >= r.min && score <= r.max) return r.color;
  }
  return '#F44336';
}

function getRisk(level: number) {
  return RISK_MAP[level] || RISK_MAP[2];
}

/* ───── SVG Gauge ───── */

function ScoreGauge({ score, comment }: { score: number; comment: string }) {
  const color = getScoreColor(score);
  const radius = 80;
  const stroke = 10;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * 0.75;
  const offset = arc - (score / 100) * arc;

  return (
    <div className="flex flex-col items-center pt-6 pb-4">
      <svg width="200" height="170" viewBox="0 0 200 200">
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          stroke="#f0f0f0"
          strokeWidth={stroke}
          strokeDasharray={`${arc} ${circumference}`}
          strokeDashoffset="0"
          strokeLinecap="round"
          transform="rotate(135 100 100)"
        />
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={`${arc} ${circumference}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(135 100 100)"
          style={{ transition: 'stroke-dashoffset 1s ease-out, stroke 0.5s' }}
        />
        <text
          x="100"
          y="95"
          textAnchor="middle"
          dominantBaseline="central"
          style={{ fontSize: 44, fontWeight: 700, fill: color }}
        >
          {score}
        </text>
        <text
          x="100"
          y="130"
          textAnchor="middle"
          style={{ fontSize: 13, fill: '#999' }}
        >
          健康评分
        </text>
      </svg>
      <p className="text-sm text-gray-600 mt-1 text-center px-6 leading-relaxed">{comment}</p>
    </div>
  );
}

/* ───── Detail section labels ───── */

const DETAIL_SECTIONS: { key: keyof ItemDetail; emoji: string; label: string }[] = [
  { key: 'explanation', emoji: '📖', label: '指标含义' },
  { key: 'possibleCauses', emoji: '🔍', label: '可能原因' },
  { key: 'dietAdvice', emoji: '🥗', label: '饮食建议' },
  { key: 'exerciseAdvice', emoji: '🏃', label: '运动建议' },
  { key: 'lifestyleAdvice', emoji: '🌙', label: '生活习惯' },
  { key: 'recheckAdvice', emoji: '🔄', label: '复查建议' },
  { key: 'medicalAdvice', emoji: '🏥', label: '就医指引' },
];

/* ───── Indicator Card ───── */

function IndicatorCard({ item }: { item: IndicatorItem }) {
  const isAbnormal = item.riskLevel >= 3;
  const [expanded, setExpanded] = useState(isAbnormal);
  const risk = getRisk(item.riskLevel);
  const hasDetail = item.detail && Object.values(item.detail).some((v) => v);

  return (
    <div
      className="bg-white rounded-xl p-4 mb-3"
      style={{
        border: `1px solid ${isAbnormal ? risk.color + '40' : '#f0f0f0'}`,
        boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
      }}
    >
      {/* header row */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <span className="text-sm font-semibold text-gray-800">{item.name}</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-bold" style={{ color: risk.color }}>
              {item.value}
            </span>
            <span className="text-xs text-gray-400">{item.unit}</span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">参考范围：{item.referenceRange}</p>
        </div>
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 flex items-center gap-0.5"
          style={{ background: `${risk.color}18`, color: risk.color }}
        >
          {risk.emoji} {item.riskName || risk.name}
        </span>
      </div>

      {/* collapsible detail */}
      {hasDetail && (
        <>
          <button
            className="w-full text-xs text-gray-400 mt-3 flex items-center justify-center gap-1"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? '收起详情' : '展开详情'}
            <span
              className="inline-block transition-transform"
              style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              ▾
            </span>
          </button>
          {expanded && item.detail && (
            <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
              {DETAIL_SECTIONS.map(({ key, emoji, label }) => {
                const text = item.detail![key];
                if (!text) return null;
                return (
                  <div key={key}>
                    <p className="text-xs font-medium text-gray-600 mb-0.5">
                      {emoji} {label}
                    </p>
                    <p className="text-xs text-gray-500 leading-relaxed">{text}</p>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ───── Progressive Loading ───── */

function ProgressiveLoading() {
  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIdx((prev) => (prev < LOADING_MESSAGES.length - 1 ? prev + 1 : prev));
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  const progress = ((msgIdx + 1) / LOADING_MESSAGES.length) * 100;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center px-8 w-full max-w-xs">
        <div className="relative mx-auto mb-6">
          <svg width="80" height="80" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="34" fill="none" stroke="#f0f0f0" strokeWidth="6" />
            <circle
              cx="40"
              cy="40"
              r="34"
              fill="none"
              stroke="#52c41a"
              strokeWidth="6"
              strokeDasharray={`${2 * Math.PI * 34}`}
              strokeDashoffset={`${2 * Math.PI * 34 * (1 - progress / 100)}`}
              strokeLinecap="round"
              transform="rotate(-90 40 40)"
              style={{ transition: 'stroke-dashoffset 0.6s ease-out' }}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-green-600">
            {Math.round(progress)}%
          </span>
        </div>
        <div className="space-y-2">
          {LOADING_MESSAGES.map((msg, i) => (
            <p
              key={i}
              className="text-sm transition-all duration-500"
              style={{
                color: i === msgIdx ? '#333' : i < msgIdx ? '#bbb' : '#e0e0e0',
                fontWeight: i === msgIdx ? 600 : 400,
                transform: i === msgIdx ? 'scale(1.05)' : 'scale(1)',
              }}
            >
              {msg}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ───── Main page ───── */

export default function ResultPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasHistory, setHasHistory] = useState(false);
  const [prevReportId, setPrevReportId] = useState<number | null>(null);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [shareLinkVisible, setShareLinkVisible] = useState(false);

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.post('/api/report/analyze', { report_id: Number(id) });
      const data = res.data || res;
      setResult(data);
    } catch (err: any) {
      const status = err?.response?.status || err?.status;
      if (status === 404) {
        Toast.show({ content: '报告不存在或尚未生成，请返回重试' });
      } else {
        Toast.show({ content: '分析失败，请重试' });
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  const fetchHistory = useCallback(async () => {
    try {
      const res: any = await api.get('/api/report/list', { params: { page: 1, page_size: 50 } });
      const data = res.data || res;
      const items: ReportListItem[] = data.items || data.list || [];
      const currentIdx = items.findIndex((r) => r.id === Number(id));
      if (currentIdx >= 0 && items.length > 1) {
        setHasHistory(true);
        const prev = items.find((r, i) => i !== currentIdx);
        if (prev) setPrevReportId(prev.id);
      }
    } catch {
      /* ignore */
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    fetchAnalysis();
    fetchHistory();
  }, [id, fetchAnalysis, fetchHistory]);

  const handleShare = async () => {
    setShareLoading(true);
    try {
      const res: any = await api.post(`/api/report/${id}/share`);
      const data = res.data || res;
      const token = data.share_token || data.token;
      if (!token) {
        Toast.show({ content: '生成分享链接失败' });
        return;
      }
      const url = `${BASE_SHARE_URL}/${token}`;
      setShareLink(url);
      setShareLinkVisible(true);
    } catch {
      Toast.show({ content: '生成分享链接失败' });
    } finally {
      setShareLoading(false);
    }
  };

  const handleCopyFromDialog = async () => {
    try {
      await navigator.clipboard.writeText(shareLink);
      Toast.show({ icon: 'success', content: '链接已复制' });
    } catch {
      Toast.show({ content: '复制失败' });
    }
  };

  const expandedCategories = useMemo(() => {
    if (!result) return new Set<string>();
    return new Set(result.categories.map((c) => c.name));
  }, [result]);

  if (loading) return <ProgressiveLoading />;

  if (!result) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
          解读结果
        </NavBar>
        <div className="flex items-center justify-center pt-20">
          <p className="text-gray-400">加载失败</p>
        </div>
      </div>
    );
  }

  const { healthScore, summary, categories, disclaimer } = result;

  return (
    <div className="min-h-screen bg-gray-50 pb-8">
      {/* NavBar */}
      <NavBar
        onBack={() => router.back()}
        right={
          <button
            className="text-sm font-medium"
            style={{ color: '#52c41a' }}
            onClick={handleShare}
            disabled={shareLoading}
          >
            分享
          </button>
        }
        style={{ background: '#fff' }}
      >
        解读结果
      </NavBar>

      {/* ─── Zone 1: Health Score Gauge ─── */}
      <div
        className="mx-4 mt-3 rounded-2xl overflow-hidden"
        style={{
          background: 'linear-gradient(180deg, #f8fdf5 0%, #ffffff 100%)',
          border: '1px solid #e8f5e0',
        }}
      >
        <ScoreGauge score={healthScore.score} comment={healthScore.comment} />
      </div>

      {/* ─── Zone 2: Summary Cards ─── */}
      <div className="px-4 mt-4 grid grid-cols-3 gap-3">
        <div className="bg-white rounded-xl p-3 text-center" style={{ border: '1px solid #f0f0f0' }}>
          <p className="text-2xl font-bold text-gray-800">{summary.totalItems}</p>
          <p className="text-xs text-gray-400 mt-1">共检测项</p>
        </div>
        <div className="bg-white rounded-xl p-3 text-center" style={{ border: '1px solid #ffccc7' }}>
          <p className="text-2xl font-bold" style={{ color: '#F44336' }}>
            {summary.abnormalCount}
          </p>
          <p className="text-xs mt-1" style={{ color: '#F44336' }}>
            项异常
          </p>
        </div>
        <div className="bg-white rounded-xl p-3 text-center" style={{ border: '1px solid #b7eb8f' }}>
          <p className="text-2xl font-bold" style={{ color: '#1B8C3D' }}>
            {summary.excellentCount}
          </p>
          <p className="text-xs mt-1" style={{ color: '#1B8C3D' }}>
            项优秀
          </p>
        </div>
      </div>

      {/* ─── Zone 3: Categorized Indicators ─── */}
      <div className="px-4 mt-5">
        <div className="flex items-center gap-2 mb-3">
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
          >
            <span className="text-white text-[10px] font-bold">AI</span>
          </div>
          <span className="font-semibold text-base text-gray-800">分类指标详细解读</span>
        </div>

        {categories.map((cat) => (
          <CategorySection key={cat.name} category={cat} defaultOpen={expandedCategories.has(cat.name)} />
        ))}
      </div>

      {/* ─── Zone 4: Compare Entry ─── */}
      {hasHistory && prevReportId && (
        <div className="px-4 mt-5">
          <button
            className="w-full py-3 rounded-xl text-sm font-medium text-white flex items-center justify-center gap-2"
            style={{ background: 'linear-gradient(135deg, #1890ff, #096dd9)' }}
            onClick={() => router.push(`/checkup/compare?id1=${prevReportId}&id2=${id}`)}
          >
            📊 与上次报告对比
          </button>
        </div>
      )}

      {/* ─── Disclaimer ─── */}
      {disclaimer && (
        <div className="px-4 mt-5">
          <div className="rounded-xl bg-amber-50 p-3">
            <p className="text-xs text-amber-700 leading-relaxed">⚠️ {disclaimer}</p>
          </div>
        </div>
      )}

      {/* Share dialog */}
      <Dialog
        visible={shareLinkVisible}
        title="分享链接"
        content={
          <div>
            <div
              className="rounded-lg p-3 mt-2 break-all text-xs text-gray-600"
              style={{ background: '#f5f5f5' }}
            >
              {shareLink}
            </div>
            <button
              onClick={handleCopyFromDialog}
              className="mt-3 w-full py-2.5 rounded-xl text-sm font-medium text-white"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            >
              复制链接
            </button>
          </div>
        }
        closeOnMaskClick
        onClose={() => setShareLinkVisible(false)}
        actions={[]}
      />
    </div>
  );
}

/* ───── Category Section with collapse ───── */

function CategorySection({ category, defaultOpen }: { category: Category; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const abnormalCount = category.items.filter((i) => i.riskLevel >= 3).length;

  return (
    <div className="mb-4">
      <button
        className="w-full flex items-center justify-between py-2"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{category.emoji}</span>
          <span className="font-medium text-sm text-gray-800">{category.name}</span>
          {abnormalCount > 0 && (
            <span
              className="text-xs px-1.5 py-0.5 rounded-full"
              style={{ background: '#FFF1F0', color: '#F44336' }}
            >
              {abnormalCount}项异常
            </span>
          )}
        </div>
        <span
          className="text-gray-400 text-xs transition-transform"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          ▾
        </span>
      </button>
      {open && (
        <div>
          {category.items.map((item, idx) => (
            <IndicatorCard key={idx} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
