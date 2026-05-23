'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { SpinLoading } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';

interface Indicator {
  name: string;
  value: string;
  unit: string;
  status: 'normal' | 'high' | 'low';
  reference: string;
}

interface ReportDetail {
  id: number;
  title: string;
  date: string;
  memberName: string;
  aiSummary: string;
  indicators: Indicator[];
}

const fallbackReport: ReportDetail = {
  id: 1,
  title: '年度健康体检报告',
  date: '2026-05-20',
  memberName: '张三',
  aiSummary:
    '整体健康状况良好。血常规各项指标基本正常，肝功能和肾功能均在正常范围内。建议关注血脂偏高的情况，适当调整饮食结构，减少高脂肪食物摄入，增加有氧运动频率。维生素D水平偏低，建议适当补充并增加户外活动时间。',
  indicators: [
    { name: '空腹血糖', value: '5.2', unit: 'mmol/L', status: 'normal', reference: '3.9-6.1' },
    { name: '总胆固醇', value: '6.8', unit: 'mmol/L', status: 'high', reference: '2.8-5.2' },
    { name: '甘油三酯', value: '1.5', unit: 'mmol/L', status: 'normal', reference: '0.56-1.7' },
    { name: '血红蛋白', value: '108', unit: 'g/L', status: 'low', reference: '115-150' },
    { name: '白细胞计数', value: '6.5', unit: '×10⁹/L', status: 'normal', reference: '3.5-9.5' },
    { name: '维生素D', value: '18', unit: 'ng/mL', status: 'low', reference: '30-100' },
    { name: '尿酸', value: '380', unit: 'μmol/L', status: 'normal', reference: '155-428' },
    { name: '肌酐', value: '72', unit: 'μmol/L', status: 'normal', reference: '44-97' },
  ],
};

const STATUS_COLOR: Record<string, string> = {
  normal: '#10B981',
  high: '#EF4444',
  low: '#F59E0B',
};

const STATUS_LABEL: Record<string, string> = {
  normal: '正常',
  high: '偏高',
  low: '偏低',
};

export default function CheckupResultPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      try {
        const res: any = await api.get(`/api/checkup/reports/${id}`);
        const data = res?.data || res;

        if (data?.interpret_session_id && !data?.indicators) {
          router.replace(`/chat/${data.interpret_session_id}?type=report_interpret`);
          return;
        }

        if (!cancelled) {
          setReport({ ...fallbackReport, ...data, id });
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setReport({ ...fallbackReport, id });
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [id, router]);

  const handleShare = useCallback(() => {
    showToast('分享功能开发中');
  }, []);

  const handleAiInterpret = useCallback(() => {
    router.push(`/chat/new?type=report_interpret&report_id=${id}`);
  }, [id, router]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <SpinLoading color="primary" style={{ '--size': '40px' } as any} />
        <div style={{ fontSize: 14, color: '#666' }}>正在加载报告...</div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div style={{ minHeight: '100vh', background: '#F5F5F5', paddingBottom: 80 }}>
      {/* 英雄区 */}
      <div style={{ background: '#F0F9FF', padding: '0 0 24px 0', position: 'relative' }}>
        {/* 顶栏 */}
        <div style={{
          display: 'flex', alignItems: 'center', height: 48,
          paddingTop: 'env(safe-area-inset-top)', padding: '0 16px',
        }}>
          <div onClick={() => router.back()} style={{ cursor: 'pointer', fontSize: 20, color: '#1F2937' }}>←</div>
          <div style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 700, color: '#1F2937' }}>报告详情</div>
          <div style={{ width: 20 }} />
        </div>

        <div style={{ padding: '24px 20px 0', minHeight: 140 }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#1F2937', marginBottom: 8 }}>{report.title}</div>
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 4 }}>体检人：{report.memberName}</div>
          <div style={{ fontSize: 13, color: '#6B7280' }}>报告日期：{report.date}</div>
        </div>
      </div>

      {/* AI 综合解读卡 */}
      <div style={{ padding: '16px 16px 0' }}>
        <div style={{
          background: '#fff', borderRadius: 16, padding: '16px 16px 16px 19px',
          borderLeft: '3px solid #38BDF8', boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#1F2937', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🤖</span> AI 综合解读
          </div>
          <div style={{ fontSize: 14, color: '#374151', lineHeight: 1.6 }}>{report.aiSummary}</div>
        </div>
      </div>

      {/* 指标列表 */}
      <div style={{ padding: '16px 16px 0' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#1F2937', marginBottom: 12 }}>检查指标</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {report.indicators.map((item, i) => (
            <div
              key={i}
              style={{
                background: '#fff', borderRadius: 12, padding: '14px 16px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: 14, color: '#374151', fontWeight: 500 }}>{item.name}</div>
                <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>参考范围：{item.reference} {item.unit}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: STATUS_COLOR[item.status] }}>
                  {item.value}
                  <span style={{ fontSize: 12, fontWeight: 400, marginLeft: 2 }}>{item.unit}</span>
                </div>
                <div style={{
                  fontSize: 12, color: STATUS_COLOR[item.status], marginTop: 2,
                  fontWeight: 500,
                }}>
                  {STATUS_LABEL[item.status]}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 底栏双按钮 */}
      <div style={{
        position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 750, background: '#fff',
        borderTop: '1px solid #E5E7EB',
        padding: '12px 16px calc(12px + env(safe-area-inset-bottom))',
        display: 'flex', gap: 12,
      }}>
        <button
          type="button"
          onClick={handleShare}
          style={{
            flex: 1, height: 48, borderRadius: 12,
            background: '#fff', color: '#0284C7',
            border: '1px solid #0284C7', fontSize: 15, fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          分享给家人
        </button>
        <button
          type="button"
          onClick={handleAiInterpret}
          style={{
            flex: 1, height: 48, borderRadius: 12,
            background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
            color: '#fff', border: 'none', fontSize: 15, fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          AI 深度解读
        </button>
      </div>
    </div>
  );
}
