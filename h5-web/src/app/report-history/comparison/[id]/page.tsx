'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ActionSheet, SpinLoading } from 'antd-mobile';
import type { Action } from 'antd-mobile/es/components/action-sheet';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';

interface ComparisonReport {
  id: number;
  report_a: { id: number; name: string; report_date: string };
  report_b: { id: number; name: string; report_date: string };
  indicator_changes: IndicatorChange[];
  health_advice: string;
  risk_warnings: RiskWarning[];
  created_at: string;
}

interface IndicatorChange {
  name: string;
  value_a: string;
  value_b: string;
  unit: string;
  change_direction: 'improved' | 'worsened' | 'unchanged' | 'new';
  change_description: string;
}

interface RiskWarning {
  title: string;
  description: string;
  level: 'high' | 'medium' | 'low';
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

export default function ComparisonDetailPage() {
  const router = useRouter();
  const params = useParams();
  const comparisonId = params?.id as string;

  const [report, setReport] = useState<ComparisonReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [shareVisible, setShareVisible] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchComparison = useCallback(async () => {
    if (!comparisonId) return;
    setLoading(true);
    setError(false);
    try {
      const res: any = await api.get(`/api/report-history/comparison/${comparisonId}`);
      const data = res.data || res;
      const content = data.comparison_content || {};
      setReport({
        id: data.id,
        report_a: data.report_a_info ? { id: data.report_a_info.id || 0, name: data.report_a_info.report_name || '报告A', report_date: data.report_a_info.report_date || '' } : { id: 0, name: '报告A', report_date: '' },
        report_b: data.report_b_info ? { id: data.report_b_info.id || 0, name: data.report_b_info.report_name || '报告B', report_date: data.report_b_info.report_date || '' } : { id: 0, name: '报告B', report_date: '' },
        indicator_changes: Array.isArray(content.indicator_changes) ? content.indicator_changes : [],
        health_advice: content.health_advice || '',
        risk_warnings: Array.isArray(content.risk_warnings) ? content.risk_warnings : [],
        created_at: data.created_at || '',
      });
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [comparisonId]);

  useEffect(() => { fetchComparison(); }, [fetchComparison]);

  const handleShare = async (shareType: string) => {
    setShareVisible(false);
    try {
      const res: any = await api.post('/api/report-history/share', {
        report_history_id: Number(comparisonId),
        share_type: shareType,
      });
      const data = res.data || res;
      if (data?.share_url || data?.share_token) {
        const url = data.share_url || `${window.location.origin}/report-history/shared/${data.share_token}`;
        await navigator.clipboard?.writeText(url);
        showToast('分享链接已复制');
      } else {
        showToast('分享成功');
      }
    } catch {
      showToast('分享失败', 'fail');
    }
  };

  const handleSaveMedical = async () => {
    setSaving(true);
    try {
      await api.post('/api/report-history/save-medical', {
        report_history_id: Number(comparisonId),
      });
      showToast('已保存到就医资料');
    } catch {
      showToast('保存失败', 'fail');
    } finally {
      setSaving(false);
    }
  };

  const shareActions: Action[] = [
    { text: '复制链接', key: 'link', onClick: () => handleShare('link') },
    { text: '微信好友', key: 'wechat', onClick: () => handleShare('wechat') },
    { text: '朋友圈', key: 'moments', onClick: () => handleShare('moments') },
  ];

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

  const riskLevelColor = (level: string) => {
    if (level === 'high') return { bg: '#FEF2F2', border: '#FECACA', text: '#DC2626' };
    if (level === 'medium') return { bg: '#FFFBEB', border: '#FDE68A', text: '#D97706' };
    return { bg: '#F0FDF4', border: '#BBF7D0', text: '#16A34A' };
  };

  const riskLevelLabel = (level: string) => {
    if (level === 'high') return '高风险';
    if (level === 'medium') return '中风险';
    return '低风险';
  };

  if (loading) {
    return (
      <div style={{ background: '#F0F9FF', minHeight: '100vh' }}>
        <div style={{ background: 'linear-gradient(180deg, #0284C7, #0EA5E9)' }}>
          <GreenNavBar>对比分析报告</GreenNavBar>
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
        <div style={{ background: 'linear-gradient(180deg, #0284C7, #0EA5E9)' }}>
          <GreenNavBar>对比分析报告</GreenNavBar>
        </div>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>😕</div>
          <div style={{ color: '#9CA3AF', fontSize: 15, marginBottom: 16 }}>加载失败</div>
          <button
            onClick={fetchComparison}
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

  const improvedCount = report.indicator_changes.filter((c) => c.change_direction === 'improved').length;
  const worsenedCount = report.indicator_changes.filter((c) => c.change_direction === 'worsened').length;

  return (
    <div style={{ background: '#F0F9FF', minHeight: '100vh', paddingBottom: 80 }}>
      {/* Nav */}
      <div style={{ position: 'sticky', top: 0, zIndex: 60, background: 'linear-gradient(180deg, #0284C7, #0EA5E9)' }}>
        <GreenNavBar>对比分析报告</GreenNavBar>
      </div>

      {/* Compared Reports Info */}
      <div style={{ padding: '12px 16px' }}>
        <div style={{
          background: '#fff',
          borderRadius: 16,
          padding: 16,
          boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          display: 'flex',
          gap: 12,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>报告 A</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {report.report_a.name}
            </div>
            <div style={{ fontSize: 12, color: '#9CA3AF' }}>{report.report_a.report_date}</div>
          </div>
          <div style={{
            width: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <span style={{ fontSize: 18, color: '#0284C7' }}>⇄</span>
          </div>
          <div style={{ flex: 1, textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>报告 B</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {report.report_b.name}
            </div>
            <div style={{ fontSize: 12, color: '#9CA3AF' }}>{report.report_b.report_date}</div>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div style={{ padding: '0 16px 12px', display: 'flex', gap: 10 }}>
        <div style={{
          flex: 1, background: '#F0FDF4', borderRadius: 12, padding: '12px 14px',
          textAlign: 'center', border: '1px solid #BBF7D0',
        }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#10B981' }}>{improvedCount}</div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>改善指标</div>
        </div>
        <div style={{
          flex: 1, background: '#FEF2F2', borderRadius: 12, padding: '12px 14px',
          textAlign: 'center', border: '1px solid #FECACA',
        }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#EF4444' }}>{worsenedCount}</div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>恶化指标</div>
        </div>
        <div style={{
          flex: 1, background: '#F3F4F6', borderRadius: 12, padding: '12px 14px',
          textAlign: 'center', border: '1px solid #E5E7EB',
        }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#6B7280' }}>
            {report.indicator_changes.length - improvedCount - worsenedCount}
          </div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>不变/新增</div>
        </div>
      </div>

      {/* Indicator Changes */}
      {report.indicator_changes.length > 0 && (
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{
            background: '#fff',
            borderRadius: 16,
            padding: 16,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E', marginBottom: 12 }}>指标变化详情</div>

            {/* Header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1.2fr 1fr 1fr 0.8fr',
              gap: 4,
              padding: '8px 0',
              borderBottom: '2px solid #E5E7EB',
            }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280' }}>指标</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textAlign: 'center' }}>报告A</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textAlign: 'center' }}>报告B</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textAlign: 'right' }}>变化</span>
            </div>

            {report.indicator_changes.map((change, idx) => (
              <div
                key={idx}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.2fr 1fr 1fr 0.8fr',
                  gap: 4,
                  padding: '10px 0',
                  borderBottom: '1px solid #F3F4F6',
                  alignItems: 'center',
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
      {report.health_advice && (
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{
            background: '#fff',
            borderRadius: 16,
            padding: 16,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
              <span style={{ fontSize: 18 }}>💡</span>
              <span style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E' }}>综合健康建议</span>
            </div>
            <div
              style={{ fontSize: 14, color: '#374151', lineHeight: 1.7 }}
              dangerouslySetInnerHTML={{ __html: simpleMarkdown(report.health_advice) }}
            />
          </div>
        </div>
      )}

      {/* Risk Warnings */}
      {report.risk_warnings.length > 0 && (
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{
            background: '#fff',
            borderRadius: 16,
            padding: 16,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
              <span style={{ fontSize: 18 }}>⚠️</span>
              <span style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E' }}>风险预警</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {report.risk_warnings.map((warning, idx) => {
                const colors = riskLevelColor(warning.level);
                return (
                  <div
                    key={idx}
                    style={{
                      background: colors.bg,
                      border: `1px solid ${colors.border}`,
                      borderRadius: 12,
                      padding: '12px 14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>{warning.title}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '1px 6px',
                        borderRadius: 6, background: colors.text, color: '#fff',
                      }}>
                        {riskLevelLabel(warning.level)}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.5 }}>
                      {warning.description}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Bottom Actions */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        background: '#fff',
        borderTop: '1px solid #E5E7EB',
        padding: '10px 16px',
        zIndex: 50,
        display: 'flex',
        gap: 10,
      }}>
        <button
          onClick={() => setShareVisible(true)}
          style={{
            flex: 1,
            height: 44,
            borderRadius: 22,
            border: 'none',
            background: 'linear-gradient(135deg, #0284C7, #0EA5E9)',
            color: '#fff',
            fontSize: 15,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >分享</button>
        <button
          onClick={handleSaveMedical}
          disabled={saving}
          style={{
            flex: 1,
            height: 44,
            borderRadius: 22,
            border: 'none',
            background: saving ? '#93C5FD' : '#10B981',
            color: '#fff',
            fontSize: 15,
            fontWeight: 600,
            cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >{saving ? '保存中…' : '保存到就医资料'}</button>
      </div>

      {/* Share Action Sheet */}
      <ActionSheet
        visible={shareVisible}
        actions={shareActions}
        onClose={() => setShareVisible(false)}
        cancelText="取消"
      />
    </div>
  );
}
