'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { ImageViewer, SpinLoading } from 'antd-mobile';
import api from '@/lib/api';

interface SharedReport {
  id: number;
  name: string;
  report_date: string;
  source_type: string;
  ai_summary: string;
  ai_interpretation: string;
  images: string[];
  indicators: Indicator[];
  comparison?: ComparisonData | null;
}

interface Indicator {
  name: string;
  value: string;
  unit: string;
  reference_range: string;
  status: 'normal' | 'high' | 'low' | 'abnormal';
}

interface ComparisonData {
  report_a: { name: string; report_date: string };
  report_b: { name: string; report_date: string };
  indicator_changes: {
    name: string;
    value_a: string;
    value_b: string;
    unit: string;
    change_direction: 'improved' | 'worsened' | 'unchanged' | 'new';
    change_description: string;
  }[];
  health_advice: string;
  risk_warnings: { title: string; description: string; level: string }[];
}

function simpleMarkdown(text: string): string {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:15px;font-weight:700;color:#0C4A6E;margin:16px 0 8px">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:16px;font-weight:700;color:#0C4A6E;margin:16px 0 8px">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 style="font-size:17px;font-weight:700;color:#0C4A6E;margin:16px 0 8px">$1</h1>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/\n/g, '<br/>');
  return html;
}

export default function SharedReportPage() {
  const params = useParams();
  const shareToken = params?.token as string;

  const [report, setReport] = useState<SharedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [imageViewerVisible, setImageViewerVisible] = useState(false);
  const [imageViewerIndex, setImageViewerIndex] = useState(0);

  const fetchShared = useCallback(async () => {
    if (!shareToken) return;
    setLoading(true);
    setError(false);
    try {
      const res: any = await api.get(`/api/report-history/shared/${shareToken}`);
      const data = res.data || res;
      const cc = data.comparison_content || null;
      setReport({
        id: data.id,
        name: data.report_name || '分享报告',
        report_date: data.report_date || '',
        source_type: data.source_type || '体检报告',
        ai_summary: data.ai_summary || '',
        ai_interpretation: data.ai_interpretation || '',
        images: Array.isArray(data.original_images) ? data.original_images : [],
        indicators: Array.isArray(data.indicators_data) ? data.indicators_data : [],
        comparison: cc ? {
          report_a: { name: cc.report_a_name || '报告A', report_date: cc.report_a_date || '' },
          report_b: { name: cc.report_b_name || '报告B', report_date: cc.report_b_date || '' },
          indicator_changes: cc.indicator_changes || [],
          health_advice: cc.health_advice || '',
          risk_warnings: cc.risk_warnings || [],
        } : null,
      });
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [shareToken]);

  useEffect(() => { fetchShared(); }, [fetchShared]);

  const statusIcon = (status: string) => {
    if (status === 'high') return '↑';
    if (status === 'low') return '↓';
    return '';
  };

  const statusColor = (status: string) => {
    if (status === 'high' || status === 'low' || status === 'abnormal') return '#EF4444';
    return '#374151';
  };

  const changeColor = (dir: string) => {
    if (dir === 'improved') return '#10B981';
    if (dir === 'worsened') return '#EF4444';
    return '#6B7280';
  };

  const changeIcon = (dir: string) => {
    if (dir === 'improved') return '✓ 改善';
    if (dir === 'worsened') return '✗ 恶化';
    if (dir === 'new') return '新增';
    return '—';
  };

  if (loading) {
    return (
      <div style={{ background: '#F0F9FF', minHeight: '100vh' }}>
        <div style={{
          background: 'linear-gradient(180deg, #0284C7, #0EA5E9)',
          padding: '14px 16px',
          textAlign: 'center',
        }}>
          <span style={{ color: '#fff', fontWeight: 600, fontSize: 17 }}>健康报告</span>
        </div>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <SpinLoading color="#0284C7" style={{ fontSize: 28 }} />
          <div style={{ color: '#9CA3AF', fontSize: 14, marginTop: 12 }}>加载中…</div>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div style={{ background: '#F0F9FF', minHeight: '100vh' }}>
        <div style={{
          background: 'linear-gradient(180deg, #0284C7, #0EA5E9)',
          padding: '14px 16px',
          textAlign: 'center',
        }}>
          <span style={{ color: '#fff', fontWeight: 600, fontSize: 17 }}>健康报告</span>
        </div>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>😕</div>
          <div style={{ color: '#9CA3AF', fontSize: 15, marginBottom: 8 }}>报告不存在或链接已过期</div>
          <button
            onClick={fetchShared}
            style={{
              padding: '10px 24px', borderRadius: 20, border: 'none',
              background: 'linear-gradient(135deg, #0284C7, #0EA5E9)', color: '#fff',
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}
          >重新加载</button>
        </div>
      </div>
    );
  }

  const isComparison = !!report.comparison;

  return (
    <div style={{ background: '#F0F9FF', minHeight: '100vh', paddingBottom: 40 }}>
      {/* Header (no back button for shared) */}
      <div style={{
        background: 'linear-gradient(180deg, #0284C7, #0EA5E9)',
        padding: '14px 16px',
        textAlign: 'center',
      }}>
        <span style={{ color: '#fff', fontWeight: 600, fontSize: 17 }}>
          {isComparison ? '对比分析报告' : '健康报告'}
        </span>
      </div>

      {/* Shared badge */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '8px 12px', background: '#EFF6FF', borderRadius: 8,
          border: '1px solid #BAE6FD',
        }}>
          <span style={{ fontSize: 14 }}>🔗</span>
          <span style={{ fontSize: 12, color: '#0284C7' }}>分享的健康报告（只读）</span>
        </div>
      </div>

      {/* For comparison reports */}
      {isComparison && report.comparison && (
        <>
          {/* Compared Reports Info */}
          <div style={{ padding: '12px 16px' }}>
            <div style={{
              background: '#fff', borderRadius: 16, padding: 16,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              display: 'flex', gap: 12,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>报告 A</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {report.comparison.report_a.name}
                </div>
                <div style={{ fontSize: 12, color: '#9CA3AF' }}>{report.comparison.report_a.report_date}</div>
              </div>
              <div style={{ width: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <span style={{ fontSize: 18, color: '#0284C7' }}>⇄</span>
              </div>
              <div style={{ flex: 1, textAlign: 'right' }}>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>报告 B</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {report.comparison.report_b.name}
                </div>
                <div style={{ fontSize: 12, color: '#9CA3AF' }}>{report.comparison.report_b.report_date}</div>
              </div>
            </div>
          </div>

          {/* Indicator Changes */}
          {report.comparison.indicator_changes.length > 0 && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{
                background: '#fff', borderRadius: 16, padding: 16,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E', marginBottom: 12 }}>指标变化详情</div>
                <div style={{
                  display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 0.8fr',
                  gap: 4, padding: '8px 0', borderBottom: '2px solid #E5E7EB',
                }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280' }}>指标</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textAlign: 'center' }}>报告A</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textAlign: 'center' }}>报告B</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textAlign: 'right' }}>变化</span>
                </div>
                {report.comparison.indicator_changes.map((change, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 0.8fr',
                      gap: 4, padding: '10px 0', borderBottom: '1px solid #F3F4F6', alignItems: 'center',
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 13, color: '#374151', fontWeight: 500 }}>{change.name}</span>
                      {change.unit && <span style={{ fontSize: 10, color: '#9CA3AF', marginLeft: 2 }}>({change.unit})</span>}
                    </div>
                    <span style={{ fontSize: 13, color: '#6B7280', textAlign: 'center' }}>{change.value_a || '—'}</span>
                    <span style={{ fontSize: 13, color: '#6B7280', textAlign: 'center' }}>{change.value_b || '—'}</span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, textAlign: 'right',
                      color: changeColor(change.change_direction),
                    }}>
                      {changeIcon(change.change_direction)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Health Advice */}
          {report.comparison.health_advice && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{
                background: '#fff', borderRadius: 16, padding: 16,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>💡</span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E' }}>综合健康建议</span>
                </div>
                <div
                  style={{ fontSize: 14, color: '#374151', lineHeight: 1.7 }}
                  dangerouslySetInnerHTML={{ __html: simpleMarkdown(report.comparison.health_advice) }}
                />
              </div>
            </div>
          )}

          {/* Risk Warnings */}
          {report.comparison.risk_warnings.length > 0 && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{
                background: '#fff', borderRadius: 16, padding: 16,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>⚠️</span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E' }}>风险预警</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {report.comparison.risk_warnings.map((w, idx) => {
                    const levelColors: Record<string, { bg: string; border: string; text: string }> = {
                      high: { bg: '#FEF2F2', border: '#FECACA', text: '#DC2626' },
                      medium: { bg: '#FFFBEB', border: '#FDE68A', text: '#D97706' },
                      low: { bg: '#F0FDF4', border: '#BBF7D0', text: '#16A34A' },
                    };
                    const c = levelColors[w.level] || levelColors.low;
                    return (
                      <div key={idx} style={{
                        background: c.bg, border: `1px solid ${c.border}`,
                        borderRadius: 12, padding: '12px 14px',
                      }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: c.text, marginBottom: 6 }}>{w.title}</div>
                        <div style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.5 }}>{w.description}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* For regular reports */}
      {!isComparison && (
        <>
          {/* Basic Info */}
          <div style={{ padding: '12px 16px' }}>
            <div style={{
              background: '#fff', borderRadius: 16, padding: 16,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{ fontSize: 17, fontWeight: 700, color: '#1F2937', marginBottom: 8 }}>{report.name}</div>
              <div style={{ fontSize: 13, color: '#9CA3AF' }}>{report.report_date}</div>
            </div>
          </div>

          {/* Images */}
          {report.images.length > 0 && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{
                background: '#fff', borderRadius: 16, padding: 16,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E', marginBottom: 12 }}>报告原图</div>
                <div style={{ display: 'flex', gap: 8, overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                  {report.images.map((img, idx) => (
                    <img
                      key={idx}
                      src={img}
                      alt={`报告图片${idx + 1}`}
                      onClick={() => { setImageViewerIndex(idx); setImageViewerVisible(true); }}
                      style={{
                        width: 120, height: 160, objectFit: 'cover', borderRadius: 8,
                        cursor: 'pointer', flexShrink: 0, border: '1px solid #E5E7EB',
                      }}
                    />
                  ))}
                </div>
              </div>
              <ImageViewer.Multi
                images={report.images}
                visible={imageViewerVisible}
                defaultIndex={imageViewerIndex}
                onClose={() => setImageViewerVisible(false)}
              />
            </div>
          )}

          {/* AI Interpretation */}
          {report.ai_interpretation && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{
                background: '#fff', borderRadius: 16, padding: 16,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>🤖</span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E' }}>AI 解读摘要</span>
                </div>
                <div
                  style={{ fontSize: 14, color: '#374151', lineHeight: 1.7 }}
                  dangerouslySetInnerHTML={{ __html: simpleMarkdown(report.ai_interpretation) }}
                />
              </div>
            </div>
          )}

          {/* Indicators Table */}
          {report.indicators.length > 0 && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{
                background: '#fff', borderRadius: 16, padding: 16,
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E', marginBottom: 12 }}>关键指标</div>
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
                  gap: 4, padding: '8px 0', borderBottom: '2px solid #E5E7EB',
                }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280' }}>指标名称</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', textAlign: 'center' }}>数值</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', textAlign: 'right' }}>参考范围</span>
                </div>
                {report.indicators.map((ind, idx) => {
                  const isAbnormal = ind.status !== 'normal';
                  return (
                    <div
                      key={idx}
                      style={{
                        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
                        gap: 4, padding: '10px 0', borderBottom: '1px solid #F3F4F6',
                        background: isAbnormal ? '#FEF2F2' : 'transparent',
                        marginLeft: -8, marginRight: -8, paddingLeft: 8, paddingRight: 8,
                        borderRadius: isAbnormal ? 6 : 0,
                      }}
                    >
                      <span style={{ fontSize: 13, color: statusColor(ind.status), fontWeight: isAbnormal ? 600 : 400 }}>
                        {ind.name}
                      </span>
                      <span style={{ fontSize: 13, color: statusColor(ind.status), fontWeight: isAbnormal ? 700 : 500, textAlign: 'center' }}>
                        {ind.value}{ind.unit ? ` ${ind.unit}` : ''}
                        {statusIcon(ind.status) && (
                          <span style={{ color: '#EF4444', marginLeft: 2, fontWeight: 700 }}>
                            {statusIcon(ind.status)}
                          </span>
                        )}
                      </span>
                      <span style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'right' }}>
                        {ind.reference_range}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Branding Footer */}
      <div style={{ textAlign: 'center', padding: '24px 0 16px' }}>
        <div style={{ fontSize: 12, color: '#9CA3AF' }}>由 宾尼小康 提供健康分析服务</div>
      </div>
    </div>
  );
}
