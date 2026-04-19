'use client';

import { useState, useEffect, useMemo, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast, SpinLoading } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

/* ───── types ───── */

interface IndicatorDiff {
  name: string;
  previousValue: string;
  currentValue: string;
  unit: string;
  change: string;
  direction: 'better' | 'worse' | 'unchanged' | 'new' | 'same';
  previousRiskLevel: number;
  currentRiskLevel: number;
  suggestion: string;
}

interface ScoreDiff {
  previousScore: number | null;
  currentScore: number | null;
  diff: number | null;
  comment: string | null;
}

interface CompareResult {
  aiSummary: string;
  scoreDiff: ScoreDiff | null;
  indicators: IndicatorDiff[];
  disclaimer: string;
}

type FilterType = 'all' | 'better' | 'worse' | 'new_abnormal';

const RISK_COLORS: Record<number, string> = {
  1: '#1B8C3D',
  2: '#4CAF50',
  3: '#FFC107',
  4: '#FF9800',
  5: '#F44336',
};

const DIRECTION_MAP: Record<string, { label: string; color: string; arrow: string }> = {
  better: { label: '变好', color: '#4CAF50', arrow: '↓' },
  worse: { label: '变差', color: '#F44336', arrow: '↑' },
  unchanged: { label: '持平', color: '#999', arrow: '→' },
  same: { label: '持平', color: '#999', arrow: '→' },
  new: { label: '新增', color: '#FF9800', arrow: '★' },
};

const FILTERS: { key: FilterType; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'better', label: '变好' },
  { key: 'worse', label: '变差' },
  { key: 'new_abnormal', label: '新增异常' },
];

function ComparePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const id1 = searchParams.get('id1');
  const id2 = searchParams.get('id2');

  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>('all');

  const fetchCompare = useCallback(async () => {
    if (!id1 || !id2) return;
    setLoading(true);
    try {
      const res: any = await api.post('/api/report/compare', {
        report_id_1: Number(id1),
        report_id_2: Number(id2),
      });
      const data = res.data || res;
      setResult(data);
    } catch {
      Toast.show({ content: '对比分析失败，请重试' });
    } finally {
      setLoading(false);
    }
  }, [id1, id2]);

  useEffect(() => {
    fetchCompare();
  }, [fetchCompare]);

  const filteredIndicators = useMemo(() => {
    if (!result) return [];
    return result.indicators.filter((ind) => {
      if (filter === 'all') return true;
      if (filter === 'better') return ind.direction === 'better';
      if (filter === 'worse') return ind.direction === 'worse';
      if (filter === 'new_abnormal') return ind.direction === 'new' || (ind.currentRiskLevel >= 3 && ind.previousRiskLevel < 3);
      return true;
    });
  }, [result, filter]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#1890ff' }} />
          <p className="text-sm text-gray-400 mt-4">正在对比分析中…</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>
          报告对比
        </GreenNavBar>
        <div className="flex items-center justify-center pt-20">
          <p className="text-gray-400">对比分析失败</p>
        </div>
      </div>
    );
  }

  const { scoreDiff, aiSummary, indicators, disclaimer } = result;
  const diffPositive = (scoreDiff?.diff ?? 0) > 0;
  const diffColor = (scoreDiff?.diff ?? 0) > 0 ? '#4CAF50' : (scoreDiff?.diff ?? 0) < 0 ? '#F44336' : '#999';

  return (
    <div className="min-h-screen bg-gray-50 pb-8">
      <GreenNavBar>
        报告对比
      </GreenNavBar>

      {/* AI Summary */}
      <div className="mx-4 mt-3">
        <div
          className="rounded-2xl p-4"
          style={{ background: 'linear-gradient(135deg, #1890ff, #096dd9)' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center">
              <span className="text-white text-[10px] font-bold">AI</span>
            </div>
            <span className="text-white font-medium text-sm">对比分析总结</span>
          </div>
          <p className="text-white/90 text-sm leading-relaxed">{aiSummary}</p>
        </div>
      </div>

      {/* Score Comparison */}
      {scoreDiff && (
        <div className="mx-4 mt-4">
          <div
            className="bg-white rounded-2xl p-5 flex items-center justify-center gap-4"
            style={{ border: '1px solid #f0f0f0' }}
          >
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">上次评分</p>
              <p className="text-3xl font-bold text-gray-400">{scoreDiff.previousScore}</p>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-2xl">→</span>
              <span
                className="text-sm font-bold mt-1"
                style={{ color: diffColor }}
              >
                {diffPositive ? '↑' : (scoreDiff.diff ?? 0) < 0 ? '↓' : '→'}
                {Math.abs(scoreDiff.diff ?? 0)}分
              </span>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">本次评分</p>
              <p className="text-3xl font-bold" style={{ color: diffColor }}>
                {scoreDiff.currentScore}
              </p>
            </div>
          </div>
          {scoreDiff.comment && (
            <p className="text-xs text-gray-500 text-center mt-2">{scoreDiff.comment}</p>
          )}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="px-4 mt-5 flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => {
          const active = filter === f.key;
          const count =
            f.key === 'all'
              ? indicators.length
              : indicators.filter((ind) => {
                  if (f.key === 'better') return ind.direction === 'better';
                  if (f.key === 'worse') return ind.direction === 'worse';
                  if (f.key === 'new_abnormal') return ind.direction === 'new' || (ind.currentRiskLevel >= 3 && ind.previousRiskLevel < 3);
                  return false;
                }).length;
          return (
            <button
              key={f.key}
              className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap flex-shrink-0 transition-colors"
              style={{
                background: active ? '#1890ff' : '#f5f5f5',
                color: active ? '#fff' : '#666',
              }}
              onClick={() => setFilter(f.key)}
            >
              {f.label}({count})
            </button>
          );
        })}
      </div>

      {/* Indicator Comparison List */}
      <div className="px-4 mt-4 space-y-3">
        {filteredIndicators.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">该类别暂无指标</div>
        ) : (
          filteredIndicators.map((ind, idx) => {
            const dir = DIRECTION_MAP[ind.direction] || DIRECTION_MAP.unchanged;
            return (
              <div
                key={idx}
                className="bg-white rounded-xl p-4"
                style={{ border: '1px solid #f0f0f0', boxShadow: '0 1px 4px rgba(0,0,0,0.04)' }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-gray-800">{ind.name}</span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ background: `${dir.color}18`, color: dir.color }}
                  >
                    {dir.arrow} {dir.label}
                  </span>
                </div>

                {/* Values comparison */}
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex-1 text-center rounded-lg py-2" style={{ background: '#fafafa' }}>
                    <p className="text-xs text-gray-400">上次</p>
                    <p
                      className="text-base font-bold mt-0.5"
                      style={{ color: RISK_COLORS[ind.previousRiskLevel] || '#333' }}
                    >
                      {ind.previousValue || '-'}
                    </p>
                  </div>
                  <span className="text-gray-300">→</span>
                  <div className="flex-1 text-center rounded-lg py-2" style={{ background: '#fafafa' }}>
                    <p className="text-xs text-gray-400">本次</p>
                    <p
                      className="text-base font-bold mt-0.5"
                      style={{ color: RISK_COLORS[ind.currentRiskLevel] || '#333' }}
                    >
                      {ind.currentValue}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-400">变化</p>
                    <p className="text-sm font-bold mt-0.5" style={{ color: dir.color }}>
                      {ind.change}{ind.unit ? ` ${ind.unit}` : ''}
                    </p>
                  </div>
                </div>

                {/* Suggestion */}
                {ind.suggestion && (
                  <div
                    className="mt-2 pt-2 border-t border-gray-50 rounded-lg px-3 py-2"
                    style={{ background: '#f8f9fa' }}
                  >
                    <p className="text-xs text-gray-500 leading-relaxed">💡 {ind.suggestion}</p>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Disclaimer */}
      {disclaimer && (
        <div className="px-4 mt-5">
          <div className="rounded-xl bg-amber-50 p-3">
            <p className="text-xs text-amber-700 leading-relaxed">⚠️ {disclaimer}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#1890ff' }} />
        </div>
      }
    >
      <ComparePageInner />
    </Suspense>
  );
}
