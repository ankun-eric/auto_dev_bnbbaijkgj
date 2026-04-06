'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { SpinLoading, Tag, Collapse, Tabs } from 'antd-mobile';
import axios from 'axios';

interface Indicator {
  id: number;
  indicator_name: string;
  value: string;
  unit: string;
  reference_range: string;
  status: string;
  category?: string;
  advice?: string;
}

interface SharedReport {
  ai_analysis?: string;
  ai_analysis_json?: {
    overall_assessment?: string;
    suggestions?: string[];
  };
  indicators: Indicator[];
  abnormal_count: number;
  disclaimer?: string;
  expired?: boolean;
}

const DISCLAIMER = '⚠️ 免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。';
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default function SharedReportPage() {
  const params = useParams();
  const token = params.token as string;
  const [report, setReport] = useState<SharedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('category');

  useEffect(() => {
    if (!token) return;
    fetchSharedReport();
  }, [token]);

  const fetchSharedReport = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${basePath}/api/report/share/${token}`);
      const data = res.data;
      if (data.expired) {
        setError('链接已过期');
        return;
      }
      setReport(data);
    } catch (err: any) {
      if (err?.response?.status === 404 || err?.response?.status === 410) {
        setError('链接已过期');
      } else {
        setError('加载失败，请稍后重试');
      }
    } finally {
      setLoading(false);
    }
  };

  const groupByCategory = (indicators: Indicator[]): Record<string, Indicator[]> => {
    const groups: Record<string, Indicator[]> = {};
    indicators.forEach((ind) => {
      const cat = ind.category || '其他';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(ind);
    });
    return groups;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <p className="text-sm text-gray-400 mt-4">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center px-6">
          <div className="text-5xl mb-4">⏰</div>
          <p className="text-base text-gray-500">{error}</p>
          <p className="text-xs text-gray-300 mt-3">请联系分享者重新生成链接</p>
        </div>
      </div>
    );
  }

  if (!report) return null;

  const indicators = report.indicators || [];
  const categories = groupByCategory(indicators);
  const isAbnormal = (ind: Indicator) => ind.status === 'abnormal' || ind.status === 'critical';
  const abnormalIndicators = indicators.filter(isAbnormal);
  const normalIndicators = indicators.filter((i) => !isAbnormal(i));
  const overallAssessment = report.ai_analysis_json?.overall_assessment || report.ai_analysis || '';
  const suggestions = report.ai_analysis_json?.suggestions || [];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div
        className="px-4 py-5"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-sm font-bold">AI</span>
          </div>
          <div>
            <h1 className="text-white font-bold text-base">体检报告解读</h1>
            <p className="text-white/70 text-xs mt-0.5">
              AI智能解读
            </p>
          </div>
        </div>
      </div>

      {/* AI Summary */}
      <div className="mx-4 mt-3">
        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            >
              <span className="text-white text-[10px] font-bold">AI</span>
            </div>
            <span className="text-sm font-medium text-gray-800">综合评估</span>
          </div>
          <p className="text-sm text-gray-600 leading-relaxed">
            {overallAssessment || '暂无综合评估'}
          </p>
          {suggestions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-xs font-medium text-gray-500 mb-1">综合建议</p>
              <p className="text-sm text-gray-600 leading-relaxed">{suggestions.join('；')}</p>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="mx-4 mt-1">
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{
            '--title-font-size': '14px',
            '--active-title-color': '#52c41a',
            '--active-line-color': '#52c41a',
          }}
        >
          <Tabs.Tab title="按分类" key="category" />
          <Tabs.Tab title="异常优先" key="abnormal" />
        </Tabs>
      </div>

      {/* Category view */}
      {activeTab === 'category' && (
        <div className="px-4 mt-2 pb-4">
          {Object.entries(categories).length > 0 ? (
            <Collapse defaultActiveKey={Object.keys(categories)}>
              {Object.entries(categories).map(([cat, items]) => {
                const abnCount = items.filter((i) => i.status === 'abnormal' || i.status === 'critical').length;
                return (
                  <Collapse.Panel
                    key={cat}
                    title={
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{cat}</span>
                        {abnCount > 0 && (
                          <Tag
                            style={{
                              '--background-color': '#f5222d15',
                              '--text-color': '#f5222d',
                              '--border-color': 'transparent',
                              fontSize: 10,
                            }}
                          >
                            {abnCount}项异常
                          </Tag>
                        )}
                      </div>
                    }
                  >
                    <div className="space-y-2">
                      {items.map((ind, idx) => (
                        <SharedIndicatorRow key={idx} indicator={ind} />
                      ))}
                    </div>
                  </Collapse.Panel>
                );
              })}
            </Collapse>
          ) : (
            <div className="text-center text-gray-400 py-8 text-sm">暂无指标数据</div>
          )}
        </div>
      )}

      {/* Abnormal first view */}
      {activeTab === 'abnormal' && (
        <div className="px-4 mt-2 pb-4">
          {abnormalIndicators.length > 0 && (
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1 h-4 rounded-full bg-red-500" />
                <span className="text-sm font-medium text-gray-800">
                  异常指标 ({abnormalIndicators.length})
                </span>
              </div>
              <div className="space-y-2">
                {abnormalIndicators.map((ind, idx) => (
                  <SharedIndicatorRow key={idx} indicator={ind} showDesc />
                ))}
              </div>
            </div>
          )}
          {normalIndicators.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1 h-4 rounded-full bg-green-500" />
                <span className="text-sm font-medium text-gray-800">
                  正常指标 ({normalIndicators.length})
                </span>
              </div>
              <div className="space-y-2">
                {normalIndicators.map((ind, idx) => (
                  <SharedIndicatorRow key={idx} indicator={ind} />
                ))}
              </div>
            </div>
          )}
          {indicators.length === 0 && (
            <div className="text-center text-gray-400 py-8 text-sm">暂无指标数据</div>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <div className="px-4 pb-4">
        <div className="rounded-xl bg-amber-50 p-3">
          <p className="text-xs text-amber-700 leading-relaxed">{DISCLAIMER}</p>
        </div>
      </div>

      {/* Brand footer */}
      <div className="border-t border-gray-100 bg-white px-4 py-4 text-center">
        <div className="flex items-center justify-center gap-2">
          <span className="text-lg">🌿</span>
          <span
            className="font-bold text-sm"
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            宾尼小康 AI健康管家
          </span>
        </div>
        <p className="text-[11px] text-gray-300 mt-1">
          此为分享内容，仅供参考，不构成医疗建议
        </p>
      </div>
    </div>
  );
}

function SharedIndicatorRow({
  indicator,
  showDesc = false,
}: {
  indicator: Indicator;
  showDesc?: boolean;
}) {
  const abnormal = indicator.status === 'abnormal' || indicator.status === 'critical';

  return (
    <div
      className="bg-white rounded-xl p-3"
      style={{ border: abnormal ? '1px solid #ffccc7' : '1px solid #f0f0f0' }}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-medium ${abnormal ? 'text-red-600' : 'text-gray-800'}`}>
              {indicator.indicator_name}
            </span>
            {abnormal && (
              <Tag
                style={{
                  '--background-color': '#f5222d15',
                  '--text-color': '#f5222d',
                  '--border-color': 'transparent',
                  fontSize: 10,
                  padding: '0 4px',
                }}
              >
                {indicator.status === 'critical' ? '危急' : '异常'}
              </Tag>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-base font-bold ${abnormal ? 'text-red-600' : 'text-gray-800'}`}>
              {indicator.value}
            </span>
            <span className="text-xs text-gray-400">{indicator.unit}</span>
          </div>
          <div className="text-xs text-gray-400 mt-0.5">参考范围: {indicator.reference_range}</div>
        </div>
      </div>
      {showDesc && indicator.advice && (
        <div className="mt-2 pt-2 border-t border-gray-50">
          <p className="text-xs text-gray-500 leading-relaxed">{indicator.advice}</p>
        </div>
      )}
    </div>
  );
}
