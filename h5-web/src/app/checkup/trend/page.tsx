'use client';

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';

interface TrendPoint {
  date: string;
  value: number;
}

interface TrendDataRaw {
  indicator_name: string;
  unit?: string;
  reference_range?: string;
  data_points: {
    report_id: number;
    report_date?: string;
    value?: string;
    status: string;
    created_at: string;
  }[];
}

interface TrendData {
  indicator_name: string;
  unit: string;
  normal_min: number;
  normal_max: number;
  data_points: TrendPoint[];
}

function parseReferenceRange(ref: string | null | undefined): { min: number; max: number } | null {
  if (!ref) return null;
  const match = ref.match(/([\d.]+)\s*[-~～]\s*([\d.]+)/);
  if (match) return { min: parseFloat(match[1]), max: parseFloat(match[2]) };
  return null;
}

function transformTrendData(raw: TrendDataRaw): TrendData {
  const range = parseReferenceRange(raw.reference_range);
  const pts = raw.data_points
    .filter((p) => p.value != null && p.value !== '')
    .map((p) => ({
      date: p.report_date || p.created_at?.substring(0, 10) || '',
      value: parseFloat(p.value!),
    }));
  return {
    indicator_name: raw.indicator_name,
    unit: raw.unit || '',
    normal_min: range?.min ?? 0,
    normal_max: range?.max ?? 0,
    data_points: pts,
  };
}

export default function TrendPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <p className="text-sm text-gray-400 mt-4">加载趋势数据...</p>
        </div>
      </div>
    }>
      <TrendPageContent />
    </Suspense>
  );
}

function TrendPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const indicatorName = searchParams.get('indicator_name') || '';
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [trendData, setTrendData] = useState<TrendData | null>(null);
  const [analysis, setAnalysis] = useState('');
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  useEffect(() => {
    if (!indicatorName) return;
    fetchData();
  }, [indicatorName]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res: any = await api.get(`/api/report/trend/${encodeURIComponent(indicatorName)}`);
      const raw: TrendDataRaw = res.data || res;
      setTrendData(transformTrendData(raw));
    } catch {
      Toast.show({ content: '加载趋势数据失败' });
    } finally {
      setLoading(false);
    }

    setAnalysisLoading(true);
    try {
      const res: any = await api.post('/api/report/trend/analysis', {
        indicator_name: indicatorName,
      });
      const data = res.data || res;
      setAnalysis(data.analysis || data.content || '');
    } catch {
      // ignore
    } finally {
      setAnalysisLoading(false);
    }
  };

  const drawChart = useCallback(() => {
    if (!canvasRef.current || !containerRef.current || !trendData) return;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    const dpr = window.devicePixelRatio || 1;
    const width = container.clientWidth;
    const height = 240;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const padding = { top: 20, right: 20, bottom: 40, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const points = trendData.data_points;
    if (points.length === 0) return;

    const values = points.map((p) => p.value);
    const allValues = [...values, trendData.normal_min, trendData.normal_max];
    const minVal = Math.min(...allValues) * 0.9;
    const maxVal = Math.max(...allValues) * 1.1;
    const valRange = maxVal - minVal || 1;

    const toX = (i: number) => padding.left + (chartW / Math.max(points.length - 1, 1)) * i;
    const toY = (v: number) => padding.top + chartH - ((v - minVal) / valRange) * chartH;

    // Background
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, width, height);

    // Normal range band
    const normalTop = toY(trendData.normal_max);
    const normalBottom = toY(trendData.normal_min);
    ctx.fillStyle = 'rgba(82, 196, 26, 0.08)';
    ctx.fillRect(padding.left, normalTop, chartW, normalBottom - normalTop);

    // Normal range dashed lines
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#52c41a';
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.4;

    ctx.beginPath();
    ctx.moveTo(padding.left, normalTop);
    ctx.lineTo(padding.left + chartW, normalTop);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(padding.left, normalBottom);
    ctx.lineTo(padding.left + chartW, normalBottom);
    ctx.stroke();

    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    // Normal range labels
    ctx.fillStyle = '#52c41a';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`${trendData.normal_max}`, padding.left - 4, normalTop + 4);
    ctx.fillText(`${trendData.normal_min}`, padding.left - 4, normalBottom + 4);

    // Grid lines
    ctx.strokeStyle = '#f0f0f0';
    ctx.lineWidth = 0.5;
    const gridCount = 4;
    for (let i = 0; i <= gridCount; i++) {
      const y = padding.top + (chartH / gridCount) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartW, y);
      ctx.stroke();
    }

    // Line
    ctx.beginPath();
    ctx.strokeStyle = '#1890ff';
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    points.forEach((p, i) => {
      const x = toX(i);
      const y = toY(p.value);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Gradient fill under line
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
    gradient.addColorStop(0, 'rgba(24, 144, 255, 0.15)');
    gradient.addColorStop(1, 'rgba(24, 144, 255, 0)');

    ctx.beginPath();
    points.forEach((p, i) => {
      const x = toX(i);
      const y = toY(p.value);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineTo(toX(points.length - 1), padding.top + chartH);
    ctx.lineTo(toX(0), padding.top + chartH);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Data points
    points.forEach((p, i) => {
      const x = toX(i);
      const y = toY(p.value);
      const isAbnormal = p.value < trendData.normal_min || p.value > trendData.normal_max;

      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fillStyle = isAbnormal ? '#f5222d' : '#1890ff';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Value label
      ctx.fillStyle = isAbnormal ? '#f5222d' : '#333';
      ctx.font = `${isAbnormal ? 'bold ' : ''}11px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(String(p.value), x, y - 10);
    });

    // X-axis labels
    ctx.fillStyle = '#999';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    points.forEach((p, i) => {
      const x = toX(i);
      const label = formatShortDate(p.date);
      ctx.fillText(label, x, height - padding.bottom + 16);
    });

    // Legend
    ctx.font = '10px sans-serif';
    const legendY = height - 6;
    ctx.fillStyle = 'rgba(82, 196, 26, 0.3)';
    ctx.fillRect(padding.left, legendY - 8, 12, 8);
    ctx.fillStyle = '#999';
    ctx.textAlign = 'left';
    ctx.fillText('正常范围', padding.left + 16, legendY);

    ctx.beginPath();
    ctx.arc(padding.left + 90, legendY - 4, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#f5222d';
    ctx.fill();
    ctx.fillStyle = '#999';
    ctx.fillText('超标', padding.left + 98, legendY);
  }, [trendData]);

  useEffect(() => {
    drawChart();
    const handleResize = () => drawChart();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [drawChart]);

  const formatShortDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <p className="text-sm text-gray-400 mt-4">加载趋势数据...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        {indicatorName || '指标趋势'}
      </NavBar>

      <div className="px-4 pt-4">
        {/* Chart header */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div className="section-title mb-0">{indicatorName}</div>
            {trendData && (
              <span className="text-xs text-gray-400">
                单位: {trendData.unit}
              </span>
            )}
          </div>

          {trendData && trendData.data_points.length > 0 ? (
            <div ref={containerRef}>
              <canvas ref={canvasRef} />
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400 text-sm">
              暂无历史趋势数据
            </div>
          )}

          {trendData && (
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-50">
              <div className="text-xs text-gray-400">
                正常范围: {trendData.normal_min} - {trendData.normal_max} {trendData.unit}
              </div>
              <div className="text-xs text-gray-400">
                共 {trendData.data_points.length} 次记录
              </div>
            </div>
          )}
        </div>

        {/* AI trend analysis */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            >
              <span className="text-white text-[10px] font-bold">AI</span>
            </div>
            <span className="section-title mb-0">趋势分析</span>
          </div>

          {analysisLoading ? (
            <div className="flex items-center justify-center py-6">
              <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' }} />
              <span className="text-sm text-gray-400 ml-2">AI分析中...</span>
            </div>
          ) : analysis ? (
            <div className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
              {analysis}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              暂无趋势分析
            </div>
          )}
        </div>

        <div className="h-6" />
      </div>
    </div>
  );
}
