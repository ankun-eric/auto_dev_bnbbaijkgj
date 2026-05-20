'use client';

/**
 * [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
 * [BUG-HSC-FIX-V2 2026-05-21] B-3 地毯式加固：
 *   1) 所有 data.xxx.length / .map 加 ?? [] 空值兜底，杜绝硬解引用
 *   2) 顶层 ErrorBoundary 包裹，单点崩溃不再触发 Next.js 全局白屏
 *   3) <img> onError 兜底，单张图片失败不影响整页
 *   4) 接口 404/500 时显示"结果不存在/加载失败"友好页
 *   5) 渲染 B-2 subject 信息（家人档案场景）
 *
 * 健康自查结果详情页（6 区块）：
 *   B1 答题记录
 *   B2 AI 解读
 *   B3 居家处理建议
 *   B4 就医警示（红色框）
 *   B5 推荐商品
 *   B6 底部 CTA（找医生咨询 / 重新填写）
 *
 * 数据源：GET /api/questionnaire/answers/{id}
 */

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, SpinLoading, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import ErrorBoundary from '@/components/ErrorBoundary';
import api from '@/lib/api';

interface QAItem {
  question_id: number;
  sort_order: number;
  title: string;
  subtitle?: string | null;
  dimension?: string | null;
  value: any;
  value_display: string;
}

interface ResultData {
  answer_id: number;
  template_id: number;
  template_code: string;
  template_name: string;
  created_at: string | null;
  completed_at: string | null;
  qa_list: QAItem[];
  classification_name?: string | null;
  classification_code?: string | null;
  key_summary: string;
  ai_conclusion: string;
  ai_full_interpretation: string;
  home_care_tips: string[];
  red_flag_signals: string[];
  recommend_goods: Array<{
    id?: number;
    sku_id?: number;
    name?: string;
    title?: string;
    image?: string | null;
    cover_image?: string | null;
    price?: number | string | null;
    [k: string]: any;
  }>;
  // [BUG-HSC-FIX-V2 2026-05-21]
  subject_kind?: 'self' | 'family' | string;
  subject_name?: string;
  subject_relation?: string;
  subject_label?: string;
}

type LoadState = 'loading' | 'ok' | 'notfound' | 'error';

function PageInner() {
  const params = useParams() as { id?: string };
  const id = params?.id;
  const router = useRouter();
  const [data, setData] = useState<ResultData | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('loading');

  const load = useCallback(async () => {
    if (!id) {
      setLoadState('notfound');
      return;
    }
    setLoadState('loading');
    try {
      const res = await api.get<ResultData>(`/api/questionnaire/answers/${id}`);
      setData((res as ResultData) || null);
      setLoadState('ok');
    } catch (e: any) {
      // eslint-disable-next-line no-console
      console.warn('[hsc-result] load failed', e);
      const status = e?.response?.status || e?.status;
      if (status === 404) {
        setLoadState('notfound');
      } else {
        setLoadState('error');
        try {
          Toast.show({ content: '结果加载失败，请稍后再试' });
        } catch {
          /* noop */
        }
      }
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loadState === 'loading') {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#F5F7FB',
        }}
      >
        <SpinLoading color="primary" />
      </div>
    );
  }

  if (loadState === 'notfound' || !data) {
    return (
      <div style={{ minHeight: '100vh', background: '#F5F7FB' }}>
        <GreenNavBar back={() => router.back()}>健康自查结果</GreenNavBar>
        <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>📭</div>
          <div style={{ fontSize: 14 }}>该结果不存在或已被删除</div>
        </div>
      </div>
    );
  }

  if (loadState === 'error') {
    return (
      <div style={{ minHeight: '100vh', background: '#F5F7FB' }}>
        <GreenNavBar back={() => router.back()}>健康自查结果</GreenNavBar>
        <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>⚠️</div>
          <div style={{ fontSize: 14, marginBottom: 16 }}>结果暂不可查看，请稍后再试</div>
          <Button color="primary" onClick={load}>
            重新加载
          </Button>
        </div>
      </div>
    );
  }

  // [BUG-HSC-FIX-V2] 全部访问都加 ?? [] 兜底，避免运行时硬解引用崩溃
  const qaList = Array.isArray(data.qa_list) ? data.qa_list : [];
  const homeCareTips = Array.isArray(data.home_care_tips) ? data.home_care_tips : [];
  const redFlagSignals = Array.isArray(data.red_flag_signals) ? data.red_flag_signals : [];
  const recommendGoods = Array.isArray(data.recommend_goods) ? data.recommend_goods : [];

  const completedAt = data.completed_at
    ? new Date(data.completed_at).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  // [BUG-HSC-FIX-V2] B-2 subject 标签
  const subjectLabel = data.subject_label
    ? data.subject_label
    : data.subject_kind === 'family' && data.subject_name
    ? data.subject_relation
      ? `${data.subject_name}（${data.subject_relation}）`
      : data.subject_name
    : '本人';

  return (
    <div
      style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 88 }}
      data-testid="hsc-result-page"
    >
      <GreenNavBar back={() => router.back()}>健康自查结果</GreenNavBar>

      {/* 顶部摘要条 */}
      <div
        style={{
          margin: '12px 14px 0',
          padding: '14px 16px',
          background: 'linear-gradient(135deg, #0EA5E9 0%, #38BDF8 100%)',
          borderRadius: 14,
          color: '#FFF',
          boxShadow: '0 4px 16px rgba(14,165,233,0.18)',
        }}
        data-testid="hsc-result-summary"
      >
        <div style={{ fontSize: 14, opacity: 0.85, marginBottom: 4 }}>🩺 健康自查报告</div>
        <div style={{ fontSize: 16, fontWeight: 700, lineHeight: 1.5 }}>
          {data.ai_conclusion || '已完成本次健康自查'}
        </div>
        <div style={{ fontSize: 12, opacity: 0.85, marginTop: 6 }} data-testid="hsc-subject-label">
          本次回答结合 {subjectLabel} 的健康档案
        </div>
        {completedAt && (
          <div style={{ fontSize: 12, opacity: 0.85, marginTop: 4 }}>完成时间：{completedAt}</div>
        )}
      </div>

      {/* B1 答题记录 */}
      <SectionCard title="📝 您的答题记录" testid="hsc-section-qa">
        {qaList.length === 0 ? (
          <div style={{ color: '#94A3B8', fontSize: 13 }}>无答题记录</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {qaList.map((qa, idx) => (
              <div
                key={qa.question_id ?? idx}
                style={{
                  borderBottom: idx === qaList.length - 1 ? 'none' : '1px dashed #E2E8F0',
                  paddingBottom: 8,
                }}
              >
                <div style={{ fontSize: 13, color: '#0F172A', fontWeight: 600, marginBottom: 4 }}>
                  Q{idx + 1}. {qa.title || '—'}
                </div>
                <div style={{ fontSize: 13, color: '#334155' }}>
                  答：{qa.value_display || <span style={{ color: '#94A3B8' }}>—</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* B2 AI 解读 */}
      <SectionCard title="🤖 AI 解读" testid="hsc-section-ai">
        <div style={{ fontSize: 13, color: '#1E293B', lineHeight: 1.7 }}>
          {data.ai_full_interpretation || '—'}
        </div>
        {data.key_summary && (
          <div
            style={{
              marginTop: 10,
              padding: '8px 10px',
              background: '#F0F9FF',
              border: '1px solid #BAE6FD',
              borderRadius: 8,
              fontSize: 12,
              color: '#0369A1',
            }}
          >
            📌 关键症状：{data.key_summary}
          </div>
        )}
      </SectionCard>

      {/* B3 居家处理建议 */}
      <SectionCard title="🏠 居家处理建议" testid="hsc-section-home-care">
        {homeCareTips.length > 0 ? (
          <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: '#1E293B', lineHeight: 1.7 }}>
            {homeCareTips.map((tip, idx) => (
              <li key={idx}>{tip}</li>
            ))}
          </ol>
        ) : (
          <div style={{ color: '#94A3B8', fontSize: 13 }}>暂无居家建议</div>
        )}
      </SectionCard>

      {/* B4 就医警示（红色框） */}
      <div
        style={{
          margin: '12px 14px 0',
          padding: '14px 16px',
          background: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: 14,
        }}
        data-testid="hsc-section-red-flag"
      >
        <div style={{ fontSize: 15, fontWeight: 700, color: '#DC2626', marginBottom: 8 }}>
          ⚠️ 出现以下情况请立即就医
        </div>
        {redFlagSignals.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#991B1B', lineHeight: 1.7 }}>
            {redFlagSignals.map((s, idx) => (
              <li key={idx}>{s}</li>
            ))}
          </ul>
        ) : (
          <div style={{ color: '#991B1B', fontSize: 13 }}>暂无红线信号</div>
        )}
      </div>

      {/* B5 推荐商品 */}
      {recommendGoods.length > 0 && (
        <SectionCard title="🎁 为您推荐" testid="hsc-section-recommend">
          <div
            style={{
              display: 'flex',
              gap: 12,
              overflowX: 'auto',
              paddingBottom: 4,
              WebkitOverflowScrolling: 'touch',
            }}
          >
            {recommendGoods.slice(0, 6).map((g, idx) => {
              const cover = (g?.cover_image || g?.image || '') as string;
              const name = (g?.name || g?.title || '推荐商品') as string;
              const price = g?.price ?? '';
              const validCover =
                typeof cover === 'string' && (cover.startsWith('http') || cover.startsWith('/'));
              return (
                <div
                  key={g?.sku_id || g?.id || idx}
                  style={{
                    flex: '0 0 auto',
                    width: 140,
                    background: '#FFF',
                    border: '1px solid #E2E8F0',
                    borderRadius: 10,
                    overflow: 'hidden',
                  }}
                >
                  {validCover ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={cover}
                      alt={name}
                      onError={(e) => {
                        try {
                          (e.currentTarget as HTMLImageElement).style.display = 'none';
                        } catch {
                          /* noop */
                        }
                      }}
                      style={{ width: '100%', height: 100, objectFit: 'cover', display: 'block' }}
                    />
                  ) : (
                    <div
                      style={{
                        width: '100%',
                        height: 100,
                        background: '#F1F5F9',
                        color: '#94A3B8',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 12,
                      }}
                    >
                      暂无图片
                    </div>
                  )}
                  <div style={{ padding: 8 }}>
                    <div
                      style={{
                        fontSize: 12,
                        color: '#1E293B',
                        lineHeight: 1.4,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {name}
                    </div>
                    {price !== '' && price !== null && price !== undefined && (
                      <div style={{ fontSize: 13, color: '#DC2626', fontWeight: 700, marginTop: 4 }}>
                        ¥{price}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}

      {/* B6 底部 CTA */}
      <div
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          padding: '10px 14px calc(10px + env(safe-area-inset-bottom))',
          background: '#FFF',
          borderTop: '1px solid #E2E8F0',
          display: 'flex',
          gap: 10,
          zIndex: 50,
        }}
        data-testid="hsc-result-cta"
      >
        <Button
          block
          color="default"
          onClick={() => {
            router.push('/ai-home');
          }}
          data-testid="hsc-cta-restart"
        >
          重新填写
        </Button>
        <Button
          block
          color="primary"
          onClick={() => {
            router.push('/services/category/consult');
          }}
          data-testid="hsc-cta-consult"
        >
          找医生咨询
        </Button>
      </div>
    </div>
  );
}

export default function HealthSelfCheckResultPage() {
  return (
    <ErrorBoundary>
      <PageInner />
    </ErrorBoundary>
  );
}

function SectionCard({
  title,
  children,
  testid,
}: {
  title: string;
  children: React.ReactNode;
  testid?: string;
}) {
  return (
    <div
      style={{
        margin: '12px 14px 0',
        padding: '14px 16px',
        background: '#FFF',
        border: '1px solid #E2E8F0',
        borderRadius: 14,
        boxShadow: '0 1px 3px rgba(15,23,42,0.04)',
      }}
      data-testid={testid}
    >
      <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', marginBottom: 10 }}>
        {title}
      </div>
      {children}
    </div>
  );
}
