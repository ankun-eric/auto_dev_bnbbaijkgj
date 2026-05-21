'use client';

/**
 * [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
 * [BUG-HSC-FIX-V2 2026-05-21] B-3 地毯式加固
 * [PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查结果页优化：
 *   ① 删除「答题记录」整块区域 —— 用户填的部位/症状 数十个问题列出来意义不大；
 *   ② AI 解读 / 居家建议 / 就医警示 三块统一来自后端 AI（接 LLM + 兜底模板），
 *      不再展示后端写死的常量；
 *   ③ 新增「档案已更新」黄色提示条 + 「刷新 AI 解读」按钮（A+++ 缓存失效策略）。
 *
 * 当前结果页区块（精简后）：
 *   - 顶部摘要条（subject_label + 完成时间）
 *   - 档案不足 / pending / failed / profile_outdated 状态条（按需展示）
 *   - AI 解读（Markdown 友好展示）
 *   - 居家处理建议（数组循环）
 *   - 出现以下情况请立即就医（数组循环，红色框）
 *   - 推荐商品（保留）
 *   - 底部 CTA（返回 / 找医生咨询）
 *
 * 数据源：GET /api/questionnaire/answers/{id}
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, SpinLoading, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import ErrorBoundary from '@/components/ErrorBoundary';
import api from '@/lib/api';
import { dispatchCta, shouldHideOnH5, type ResultCta } from '@/lib/cta-router';

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
  // [PRD-HSC-OPTIM-V3 2026-05-21]
  ai_status?: 'pending' | 'done' | 'failed' | string;
  ai_failed_reason?: string;
  archive_insufficient?: boolean;
  result_cta?: ResultCta | null;
  // [PRD-HSC-AI-REAL-V1 2026-05-21] A+++ 缓存失效：档案关键字段已变更
  profile_outdated?: boolean;
  ai_generated_at?: string | null;
}

type LoadState = 'loading' | 'ok' | 'notfound' | 'error';

function PageInner() {
  const params = useParams() as { id?: string };
  const id = params?.id;
  const router = useRouter();
  const [data, setData] = useState<ResultData | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  // [PRD-HSC-OPTIM-V3 2026-05-21] ai-status 轮询：理论上详情页打开时已 done，但作为兜底
  const pollTimerRef = useRef<any>(null);
  const pollStartedAtRef = useRef<number>(0);

  const stopPoll = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

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

  // [PRD-HSC-OPTIM-V3 2026-05-21] 若 ai_status=pending，按 3s 间隔轮询，最多 60s
  useEffect(() => {
    if (!id || !data) return;
    if ((data.ai_status || 'done') !== 'pending') {
      stopPoll();
      return;
    }
    if (pollTimerRef.current) return; // 已在轮询
    pollStartedAtRef.current = Date.now();
    pollTimerRef.current = setInterval(async () => {
      try {
        const st = await api.get<any>(`/api/questionnaire/answers/${id}/ai-status`);
        const s = (st?.ai_status || 'done') as string;
        if (s !== 'pending') {
          stopPoll();
          // 重新拉一次详情
          await load();
          return;
        }
        if (Date.now() - pollStartedAtRef.current > 60000) {
          stopPoll();
          // 超时，让用户看到失败提示
          setData((d) => (d ? { ...d, ai_status: 'failed', ai_failed_reason: '分析超时' } : d));
        }
      } catch {
        // 静默忽略，下一轮再尝试
      }
    }, 3000);
    return () => stopPoll();
  }, [id, data, load, stopPoll]);

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
  // [PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查结果页不再展示「答题记录」整块区域，qaList 仅做兜底引用
  const homeCareTips = Array.isArray(data.home_care_tips) ? data.home_care_tips : [];
  const redFlagSignals = Array.isArray(data.red_flag_signals) ? data.red_flag_signals : [];
  const recommendGoods = Array.isArray(data.recommend_goods) ? data.recommend_goods : [];

  // [PRD-HSC-AI-REAL-V1 2026-05-21] 触发服务端重新生成 AI 解读
  const triggerRetryAi = async (showToast: boolean = true) => {
    try {
      await api.post(`/api/questionnaire/answers/${id}/retry-ai`, {});
      if (showToast) Toast.show({ content: '已重新触发 AI 解读' });
      setData((d) => (d ? { ...d, ai_status: 'pending', profile_outdated: false } : d));
    } catch {
      if (showToast) Toast.show({ content: '触发失败，请稍后再试' });
    }
  };

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

      {/* [PRD-HSC-OPTIM-V3 2026-05-21] 档案不足提示（黄色 Tip） */}
      {data.archive_insufficient && (
        <div
          style={{
            margin: '8px 14px 0',
            padding: '10px 12px',
            background: '#FEFCE8',
            border: '1px solid #FDE68A',
            borderRadius: 10,
            fontSize: 12,
            color: '#92400E',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
          data-testid="hsc-archive-insufficient"
        >
          <span>该家人档案信息较少，建议补全档案获得更精准解读</span>
          <Button
            size="mini"
            color="warning"
            fill="outline"
            onClick={() => router.push('/health-profile')}
          >
            去补全
          </Button>
        </div>
      )}

      {/* [PRD-HSC-OPTIM-V3 2026-05-21] 分析中 / 失败 状态条（兜底） */}
      {data.ai_status === 'pending' && (
        <div
          style={{
            margin: '8px 14px 0',
            padding: '10px 12px',
            background: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: 10,
            fontSize: 12,
            color: '#1D4ED8',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
          data-testid="hsc-ai-pending"
        >
          <SpinLoading style={{ '--size': '14px' } as any} color="primary" />
          <span>AI 正在分析中，结果生成后会自动刷新…</span>
        </div>
      )}
      {data.ai_status === 'failed' && (
        <div
          style={{
            margin: '8px 14px 0',
            padding: '10px 12px',
            background: '#FEF2F2',
            border: '1px solid #FECACA',
            borderRadius: 10,
            fontSize: 12,
            color: '#B91C1C',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
          data-testid="hsc-ai-failed"
        >
          <span>AI 解读暂时失败：{data.ai_failed_reason || '请稍后重试'}</span>
          <Button size="mini" color="primary" onClick={() => triggerRetryAi(true)}>
            重试解读
          </Button>
        </div>
      )}

      {/* [PRD-HSC-AI-REAL-V1 2026-05-21] A+++ 缓存失效：档案已更新提示条 */}
      {data.profile_outdated && data.ai_status !== 'pending' && (
        <div
          style={{
            margin: '8px 14px 0',
            padding: '10px 12px',
            background: '#FEFCE8',
            border: '1px solid #FDE68A',
            borderRadius: 10,
            fontSize: 12,
            color: '#92400E',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
          data-testid="hsc-profile-outdated"
        >
          <span>您的健康档案已更新，AI 解读基于旧档案生成</span>
          <Button size="mini" color="warning" onClick={() => triggerRetryAi(true)}>
            刷新 AI 解读
          </Button>
        </div>
      )}

      {/* [PRD-HSC-AI-REAL-V1 2026-05-21] AI 解读区块（保留段落空行，简单 Markdown 友好展示） */}
      <SectionCard title="🤖 AI 解读" testid="hsc-section-ai">
        {(data.ai_full_interpretation || '').trim() ? (
          <div
            style={{
              fontSize: 13,
              color: '#1E293B',
              lineHeight: 1.75,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {data.ai_full_interpretation}
          </div>
        ) : (
          <div style={{ color: '#94A3B8', fontSize: 13 }}>
            {data.ai_status === 'pending' ? 'AI 正在为您生成个性化解读…' : '暂无 AI 解读'}
          </div>
        )}
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

      {/* B6 底部 CTA
        * [PRD-HSC-OPTIM-V3 2026-05-21]
        * - 「重新填写」改为「返回」（router.back() + history 兜底）
        * - 「找医生咨询」改为按后台配置 result_cta 动态渲染；未配置则隐藏，让「返回」占满整条
        */}
      {(() => {
        const cta = data.result_cta || null;
        const showCta = !shouldHideOnH5(cta);
        const goBack = () => {
          if (typeof window !== 'undefined' && window.history.length <= 1) {
            router.push('/ai-home');
            return;
          }
          try {
            router.back();
          } catch {
            router.push('/ai-home');
          }
        };
        return (
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
            <Button block color="default" onClick={goBack} data-testid="hsc-cta-back">
              返回
            </Button>
            {showCta && (
              <Button
                block
                color="primary"
                onClick={() => dispatchCta(cta, router)}
                data-testid="hsc-cta-consult"
              >
                {(cta && cta.text) || '找医生咨询'}
              </Button>
            )}
          </div>
        );
      })()}
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
