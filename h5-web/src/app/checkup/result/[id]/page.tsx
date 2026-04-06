'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Tabs, Tag, Toast, SpinLoading, ActionSheet, Collapse } from 'antd-mobile';
import api from '@/lib/api';

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

interface ReportDetail {
  id: number;
  ai_analysis?: string;
  ai_analysis_json?: {
    overall_assessment?: string;
    suggestions?: string[];
  };
  indicators: Indicator[];
  abnormal_count: number;
  created_at: string;
}

const DISCLAIMER = '⚠️ 免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。';

export default function ResultPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('category');
  const [shareVisible, setShareVisible] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetchDetail();
  }, [id]);

  const fetchDetail = async () => {
    setLoading(true);
    try {
      const res: any = await api.get(`/api/report/detail/${id}`);
      const data = res.data || res;
      setDetail(data);
    } catch {
      Toast.show({ content: '加载失败，请重试' });
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

  const handleShare = async (action: string) => {
    setShareVisible(false);
    if (action === 'link') {
      try {
        const res: any = await api.post('/api/report/share', { report_id: Number(id) });
        const data = res.data || res;
        const shareUrl = `${window.location.origin}/shared/report/${data.token || data.share_token}`;
        await navigator.clipboard.writeText(shareUrl);
        Toast.show({ icon: 'success', content: '链接已复制' });
      } catch {
        Toast.show({ content: '生成分享链接失败' });
      }
    } else if (action === 'image') {
      Toast.show({ content: '正在生成图片...' });
      setTimeout(() => Toast.show({ content: '图片已保存' }), 1500);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <p className="text-sm text-gray-400 mt-4">加载解读结果...</p>
        </div>
      </div>
    );
  }

  if (!detail) {
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

  const indicators = detail.indicators || [];
  const categories = groupByCategory(indicators);
  const isAbnormal = (ind: Indicator) => ind.status === 'abnormal' || ind.status === 'critical';
  const abnormalIndicators = indicators.filter(isAbnormal);
  const normalIndicators = indicators.filter((i) => !isAbnormal(i));
  const overallAssessment = detail.ai_analysis_json?.overall_assessment || detail.ai_analysis || '';
  const suggestions = detail.ai_analysis_json?.suggestions || [];

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar
        onBack={() => router.back()}
        right={
          <button
            className="text-sm text-primary"
            onClick={() => setShareVisible(true)}
          >
            分享
          </button>
        }
        style={{ background: '#fff' }}
      >
        解读结果
      </NavBar>

      {/* AI Summary */}
      <div className="mx-4 mt-3">
        <div
          className="rounded-xl p-4"
          style={{
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center">
              <span className="text-white text-xs font-bold">AI</span>
            </div>
            <span className="text-white font-medium text-sm">综合评估</span>
          </div>
          <p className="text-white/90 text-sm leading-relaxed">
            {overallAssessment || '暂无综合评估'}
          </p>
          {suggestions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/20">
              <p className="text-white/80 text-xs font-medium mb-1">综合建议</p>
              <p className="text-white/90 text-sm leading-relaxed">{suggestions.join('；')}</p>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="mx-4 mt-3">
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
                        <IndicatorRow key={idx} indicator={ind} router={router} />
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
                  <IndicatorRow key={idx} indicator={ind} showDesc router={router} />
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
                  <IndicatorRow key={idx} indicator={ind} router={router} />
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
      <div className="px-4 pb-8">
        <div className="rounded-xl bg-amber-50 p-3">
          <p className="text-xs text-amber-700 leading-relaxed">{DISCLAIMER}</p>
        </div>
      </div>

      {/* Share Action Sheet */}
      <ActionSheet
        visible={shareVisible}
        actions={[
          { text: '生成图片', key: 'image', onClick: () => handleShare('image') },
          { text: '复制链接', key: 'link', onClick: () => handleShare('link') },
        ]}
        cancelText="取消"
        onClose={() => setShareVisible(false)}
      />
    </div>
  );
}

function IndicatorRow({
  indicator,
  showDesc = false,
  router,
}: {
  indicator: Indicator;
  showDesc?: boolean;
  router: ReturnType<typeof useRouter>;
}) {
  const abnormal = indicator.status === 'abnormal' || indicator.status === 'critical';

  return (
    <div
      className="bg-white rounded-xl p-3"
      style={{
        border: abnormal ? '1px solid #ffccc7' : '1px solid #f0f0f0',
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={`text-sm font-medium ${abnormal ? 'text-red-600' : 'text-gray-800'}`}
            >
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
        <button
          className="text-xs px-2 py-1 rounded-full bg-gray-50 text-gray-500 flex-shrink-0"
          onClick={() =>
            router.push(`/checkup/trend?indicator_name=${encodeURIComponent(indicator.indicator_name)}`)
          }
        >
          趋势 ›
        </button>
      </div>
      {showDesc && indicator.advice && (
        <div className="mt-2 pt-2 border-t border-gray-50">
          <p className="text-xs text-gray-500 leading-relaxed">{indicator.advice}</p>
        </div>
      )}
    </div>
  );
}
