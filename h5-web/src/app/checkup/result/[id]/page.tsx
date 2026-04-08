'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Toast, SpinLoading, Collapse, Dialog } from 'antd-mobile';
import api from '@/lib/api';

interface AiItem {
  name: string;
  value: string;
  unit: string;
  reference: string;
  status: string;
  suggestion?: string;
}

interface AiCategory {
  name: string;
  items: AiItem[];
}

interface AiAnalysisJson {
  summary?: string;
  categories?: AiCategory[];
  abnormal_items?: string[];
}

interface ReportDetail {
  id: number;
  ai_analysis?: string;
  ai_analysis_json?: AiAnalysisJson | string;
  created_at: string;
}

const DISCLAIMER =
  '⚠️ 免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。';

const BASE_SHARE_URL =
  'https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/shared/report';

function getStatusColor(status: string): string {
  if (status === '偏高' || status === 'high' || status === 'critical') return '#FF4D4F';
  if (status === '偏低' || status === 'low') return '#FAAD14';
  if (status === '正常' || status === 'normal') return '#52C41A';
  return '#FF4D4F';
}

function isAbnormalStatus(status: string): boolean {
  return status !== '正常' && status !== 'normal' && status !== '';
}

export default function ResultPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [shareLinkVisible, setShareLinkVisible] = useState(false);

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

  const parseAiJson = (detail: ReportDetail): AiAnalysisJson | null => {
    if (!detail.ai_analysis_json) return null;
    if (typeof detail.ai_analysis_json === 'string') {
      try {
        return JSON.parse(detail.ai_analysis_json);
      } catch {
        return null;
      }
    }
    return detail.ai_analysis_json as AiAnalysisJson;
  };

  const getShareToken = async (): Promise<string | null> => {
    try {
      const res: any = await api.post(`/api/report/${id}/share`);
      const data = res.data || res;
      return data.share_token || data.token || null;
    } catch {
      return null;
    }
  };

  const handleShareLink = async () => {
    setShareLoading(true);
    try {
      const token = await getShareToken();
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

  const handleCopyShareLink = async () => {
    setShareLoading(true);
    try {
      const token = await getShareToken();
      if (!token) {
        Toast.show({ content: '生成分享链接失败' });
        return;
      }
      const url = `${BASE_SHARE_URL}/${token}`;
      await navigator.clipboard.writeText(url);
      Toast.show({ icon: 'success', content: '链接已复制到剪贴板' });
    } catch {
      Toast.show({ content: '复制失败，请重试' });
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

  const aiJson = parseAiJson(detail);
  const categories = aiJson?.categories || [];
  const summary = aiJson?.summary || detail.ai_analysis || '';

  const allAbnormalItems: AiItem[] = [];
  categories.forEach((cat) => {
    cat.items.forEach((item) => {
      if (isAbnormalStatus(item.status)) {
        allAbnormalItems.push(item);
      }
    });
  });

  const hasAiData = categories.length > 0;

  return (
    <div className="min-h-screen bg-gray-50 pb-32">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        解读结果
      </NavBar>

      {/* 区域1：异常汇总卡片区 */}
      <div className="px-4 pt-3">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-1 h-5 rounded-full" style={{ background: '#FF4D4F' }} />
          <span className="font-semibold text-base text-gray-800">
            异常指标（{allAbnormalItems.length}项）
          </span>
        </div>

        {allAbnormalItems.length === 0 ? (
          <div
            className="rounded-xl p-4 flex items-center gap-3"
            style={{ background: '#F6FFED', border: '1px solid #B7EB8F' }}
          >
            <span className="text-2xl">✅</span>
            <div>
              <p className="font-medium text-sm" style={{ color: '#52C41A' }}>
                所有指标均在正常范围内
              </p>
              {!hasAiData && (
                <p className="text-xs text-gray-400 mt-0.5">暂无AI结构化解读数据</p>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {allAbnormalItems.map((item, idx) => {
              const color = getStatusColor(item.status);
              const isBgRed = item.status === '偏高' || item.status === 'high' || item.status === 'critical';
              return (
                <div
                  key={idx}
                  className="rounded-xl p-4 bg-white"
                  style={{
                    border: `1px solid ${isBgRed ? '#FFCCC7' : '#FFE58F'}`,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <span className="text-base font-bold text-gray-800">{item.name}</span>
                      <div className="flex items-baseline gap-1 mt-1">
                        <span className="text-xl font-bold" style={{ color }}>
                          {item.value}
                        </span>
                        <span className="text-xs text-gray-400">{item.unit}</span>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">正常范围：{item.reference}</p>
                    </div>
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0"
                      style={{ background: `${color}18`, color }}
                    >
                      {item.status}
                    </span>
                  </div>
                  {item.suggestion && (
                    <div
                      className="mt-3 pt-3 rounded-lg px-3 py-2"
                      style={{ background: `${color}08`, borderTop: `1px solid ${color}20` }}
                    >
                      <p className="text-xs leading-relaxed" style={{ color: '#555' }}>
                        💡 {item.suggestion}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 区域2：分类详情区 */}
      {hasAiData && (
        <div className="px-4 mt-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1 h-5 rounded-full bg-blue-400" />
            <span className="font-semibold text-base text-gray-800">分类详情</span>
          </div>

          <Collapse defaultActiveKey={categories.map((c) => c.name)}>
            {categories.map((cat) => {
              const abnCount = cat.items.filter((i) => isAbnormalStatus(i.status)).length;
              return (
                <Collapse.Panel
                  key={cat.name}
                  title={
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{cat.name}</span>
                      {abnCount > 0 && (
                        <span
                          className="text-xs px-1.5 py-0.5 rounded-full"
                          style={{ background: '#FFF1F0', color: '#FF4D4F' }}
                        >
                          {abnCount}项异常
                        </span>
                      )}
                    </div>
                  }
                >
                  <div className="space-y-1">
                    {cat.items.map((item, idx) => {
                      const abnormal = isAbnormalStatus(item.status);
                      const color = abnormal ? getStatusColor(item.status) : '#52C41A';
                      return (
                        <div
                          key={idx}
                          className="flex items-center py-2 border-b last:border-b-0"
                          style={{ borderColor: '#f5f5f5' }}
                        >
                          <span
                            className="flex-1 text-sm"
                            style={{ color: abnormal ? '#333' : '#555' }}
                          >
                            {item.name}
                          </span>
                          <span
                            className="text-sm font-semibold mx-2"
                            style={{ color: abnormal ? getStatusColor(item.status) : '#333' }}
                          >
                            {item.value}
                            <span className="text-xs font-normal text-gray-400 ml-0.5">
                              {item.unit}
                            </span>
                          </span>
                          <span className="text-xs text-gray-400 mr-2 hidden sm:inline">
                            {item.reference}
                          </span>
                          <span
                            className="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                            style={{ background: `${color}18`, color }}
                          >
                            {item.status || '正常'}
                          </span>
                          <button
                            className="ml-2 text-xs text-gray-400 flex-shrink-0"
                            onClick={() =>
                              router.push(
                                `/checkup/trend?indicator_name=${encodeURIComponent(item.name)}`
                              )
                            }
                          >
                            趋势›
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </Collapse.Panel>
              );
            })}
          </Collapse>
        </div>
      )}

      {/* 区域3：综合建议区 */}
      <div className="px-4 mt-5">
        <div className="flex items-center gap-2 mb-3">
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
          >
            <span className="text-white text-[10px] font-bold">AI</span>
          </div>
          <span className="font-semibold text-base text-gray-800">综合健康建议</span>
        </div>

        <div className="rounded-xl bg-white p-4" style={{ border: '1px solid #f0f0f0' }}>
          {summary ? (
            <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">{summary}</p>
          ) : (
            <p className="text-sm text-gray-400">暂无综合建议</p>
          )}
        </div>

        <div className="rounded-xl bg-amber-50 p-3 mt-3">
          <p className="text-xs text-amber-700 leading-relaxed">{DISCLAIMER}</p>
        </div>
      </div>

      {/* 分享按钮区 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-3 safe-area-bottom">
        <div className="flex gap-3">
          <button
            onClick={handleShareLink}
            disabled={shareLoading}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium"
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              opacity: shareLoading ? 0.7 : 1,
            }}
          >
            生成图片分享
          </button>
          <button
            onClick={handleCopyShareLink}
            disabled={shareLoading}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium"
            style={{
              background: '#f5f5f5',
              color: '#555',
              border: '1px solid #e8e8e8',
              opacity: shareLoading ? 0.7 : 1,
            }}
          >
            复制分享链接
          </button>
        </div>
      </div>

      {/* 分享链接对话框 */}
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
