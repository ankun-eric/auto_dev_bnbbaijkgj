'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ImageViewer, ActionSheet, SpinLoading } from 'antd-mobile';
import type { Action } from 'antd-mobile/es/components/action-sheet';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';

interface ReportDetail {
  id: number;
  name: string;
  report_date: string;
  source_type: string;
  ai_summary: string;
  ai_interpretation: string;
  images: string[];
  indicators: Indicator[];
  created_at: string;
}

interface Indicator {
  name: string;
  value: string;
  unit: string;
  reference_range: string;
  status: 'normal' | 'high' | 'low' | 'abnormal';
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

export default function ReportDetailPage() {
  const router = useRouter();
  const params = useParams();
  const reportId = params?.id as string;

  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [imageViewerVisible, setImageViewerVisible] = useState(false);
  const [imageViewerIndex, setImageViewerIndex] = useState(0);
  const [shareVisible, setShareVisible] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchReport = useCallback(async () => {
    if (!reportId) return;
    setLoading(true);
    setError(false);
    try {
      const res: any = await api.get(`/api/report-history/${reportId}`);
      const data = res.data || res;
      setReport({
        id: data.id,
        name: data.report_name || '未命名报告',
        report_date: data.report_date || '',
        source_type: data.source_type || '体检报告',
        ai_summary: data.ai_summary || '',
        ai_interpretation: data.ai_interpretation || '',
        images: Array.isArray(data.original_images) ? data.original_images : [],
        indicators: Array.isArray(data.indicators_data) ? data.indicators_data : [],
        created_at: data.created_at || '',
      });
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const handleShare = async (shareType: string) => {
    setShareVisible(false);
    try {
      const res: any = await api.post('/api/report-history/share', {
        report_history_id: Number(reportId),
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
        report_history_id: Number(reportId),
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

  const sourceLabel = (type: string) => {
    if (type === 'comparison' || type === 'compare') return '对比报告';
    return '体检报告';
  };

  const sourceStyle = (type: string): React.CSSProperties => {
    if (type === 'comparison' || type === 'compare') {
      return { background: '#EFF6FF', color: '#0284C7', border: '1px solid #BAE6FD' };
    }
    return { background: '#F3F4F6', color: '#6B7280', border: '1px solid #E5E7EB' };
  };

  const statusIcon = (status: string) => {
    if (status === 'high') return '↑';
    if (status === 'low') return '↓';
    return '';
  };

  const statusColor = (status: string) => {
    if (status === 'high' || status === 'low' || status === 'abnormal') return '#EF4444';
    return '#374151';
  };

  if (loading) {
    return (
      <div style={{ background: '#F0F9FF', minHeight: '100vh' }}>
        <div style={{ background: 'linear-gradient(180deg, #0284C7, #0EA5E9)' }}>
          <GreenNavBar>报告详情</GreenNavBar>
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
          <GreenNavBar>报告详情</GreenNavBar>
        </div>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>😕</div>
          <div style={{ color: '#9CA3AF', fontSize: 15, marginBottom: 16 }}>加载失败</div>
          <button
            onClick={fetchReport}
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

  return (
    <div style={{ background: '#F0F9FF', minHeight: '100vh', paddingBottom: 100 }}>
      {/* Nav */}
      <div style={{ position: 'sticky', top: 0, zIndex: 60, background: 'linear-gradient(180deg, #0284C7, #0EA5E9)' }}>
        <GreenNavBar>报告详情</GreenNavBar>
      </div>

      {/* Basic Info */}
      <div style={{ padding: '12px 16px' }}>
        <div style={{
          background: '#fff',
          borderRadius: 16,
          padding: 16,
          boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 17, fontWeight: 700, color: '#1F2937', flex: 1 }}>{report.name}</span>
            <span style={{
              fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 10, whiteSpace: 'nowrap',
              ...sourceStyle(report.source_type),
            }}>
              {sourceLabel(report.source_type)}
            </span>
          </div>
          <div style={{ fontSize: 13, color: '#9CA3AF' }}>
            {report.report_date}
          </div>
        </div>
      </div>

      {/* Report Images */}
      {report.images.length > 0 && (
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{
            background: '#fff',
            borderRadius: 16,
            padding: 16,
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
            background: '#fff',
            borderRadius: 16,
            padding: 16,
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
            background: '#fff',
            borderRadius: 16,
            padding: 16,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E', marginBottom: 12 }}>关键指标</div>

            {/* Table Header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: 4,
              padding: '8px 0',
              borderBottom: '2px solid #E5E7EB',
            }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280' }}>指标名称</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', textAlign: 'center' }}>数值</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', textAlign: 'right' }}>参考范围</span>
            </div>

            {/* Table Rows */}
            {report.indicators.map((ind, idx) => {
              const isAbnormal = ind.status !== 'normal';
              return (
                <div
                  key={idx}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr 1fr',
                    gap: 4,
                    padding: '10px 0',
                    borderBottom: '1px solid #F3F4F6',
                    background: isAbnormal ? '#FEF2F2' : 'transparent',
                    marginLeft: -8,
                    marginRight: -8,
                    paddingLeft: 8,
                    paddingRight: 8,
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
          onClick={() => router.push(`/report-history?pre_selected=${report.id}`)}
          style={{
            flex: 1,
            height: 40,
            borderRadius: 20,
            border: '1px solid #0284C7',
            background: '#fff',
            color: '#0284C7',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >对比另一份报告</button>
        <button
          onClick={() => setShareVisible(true)}
          style={{
            flex: 1,
            height: 40,
            borderRadius: 20,
            border: 'none',
            background: 'linear-gradient(135deg, #0284C7, #0EA5E9)',
            color: '#fff',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >分享</button>
        <button
          onClick={handleSaveMedical}
          disabled={saving}
          style={{
            flex: 1,
            height: 40,
            borderRadius: 20,
            border: 'none',
            background: saving ? '#93C5FD' : '#10B981',
            color: '#fff',
            fontSize: 13,
            fontWeight: 600,
            cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >{saving ? '保存中…' : '存到就医资料'}</button>
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
