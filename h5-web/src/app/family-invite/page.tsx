'use client';

/**
 * [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版]
 * 二维码邀请页 —— 单一职责：只为指定成员（member_id）生成二维码。
 *
 * 与历史版本的区别（按需求"删兜底、没 id 直接报错"）：
 *   1. 删除「无 member_id 时渲染姓名+关系表单 + 就地建档案」的整套兜底（含
 *      handleInviteSubmit、createInvitation 中 relationOverride/nicknameOverride/
 *      nickname/relation_type 等无 id 分支）。
 *   2. 删除本页的「完善本人资料抽屉」逻辑：完善档案拦截已前移到
 *      「点新增咨询人 / 添加成员」那一刻（ConsultTargetPicker / 健康档案页）。
 *      本页只管「给指定成员出二维码」这一件事。
 *   3. 没带 member_id → 页面正中显示红字错误：
 *      "⚠️ 缺少成员信息，无法生成邀请，请从成员档案进入"。
 *
 * 本次不动：布局、二维码、三个 emoji 标签、按钮配色（两个实心蓝 + 一个微信绿）、
 * 文案（"邀请 TA 加入我的健康守护" / "邀请 24 小时内有效"）。
 */

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import { QRCodeCanvas } from 'qrcode.react';
import api from '@/lib/api';

interface InvitationData {
  invite_code: string;
  qr_url: string;
  qr_content_url?: string;
  expires_at: string;
}

export default function FamilyInvitePage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>加载中...</div>}>
      <FamilyInviteContent />
    </Suspense>
  );
}

function FamilyInviteContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const memberId = searchParams.get('member_id');

  const [loading, setLoading] = useState(false);
  const [invitation, setInvitation] = useState<InvitationData | null>(null);
  const [error, setError] = useState('');
  const [memberName, setMemberName] = useState<string>('');

  const THEME = {
    gradientStart: '#0EA5E9',
    gradientEnd: '#38BDF8',
  };

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版]
  // 有 member_id 才请求邀请码；没有 → 不发任何请求，下面直接渲染红字错误。
  useEffect(() => {
    if (!memberId) return;
    createInvitation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberId]);

  useEffect(() => {
    if (!memberId) return;
    (async () => {
      try {
        const res: any = await api.get('/api/family/members');
        const data = res.data || res;
        const items: any[] = Array.isArray(data.items) ? data.items : [];
        const m = items.find((x: any) => String(x.id) === memberId);
        if (m) setMemberName(m.nickname || m.name || '');
      } catch {}
    })();
  }, [memberId]);

  const createInvitation = async () => {
    if (!memberId) return;
    setLoading(true);
    setError('');
    try {
      const res: any = await api.post('/api/family/invitation', {
        member_id: Number(memberId),
      });
      const data = res.data || res;
      setInvitation(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '生成邀请失败，请重试';
      setError(typeof detail === 'string' ? detail : '生成邀请失败，请重试');
      showToast(typeof detail === 'string' ? detail : '生成邀请失败，请重试', 'fail');
    }
    setLoading(false);
  };

  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const inviteLink = invitation
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}${basePath}/family-auth?code=${invitation.invite_code}`
    : '';

  const qrContentUrl = invitation
    ? (invitation.qr_content_url || inviteLink)
    : '';

  const qrCanvasRef = useRef<HTMLDivElement>(null);

  const handleCopyLink = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      showToast('链接已复制');
    } catch {
      showToast('复制失败，请手动复制', 'fail');
    }
  };

  const handleSaveImage = useCallback(() => {
    const canvas = qrCanvasRef.current?.querySelector('canvas');
    if (!canvas) {
      showToast('二维码未生成', 'fail');
      return;
    }
    try {
      const url = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `bini-health-invite-${invitation?.invite_code?.slice(0, 8) || 'qr'}.png`;
      link.href = url;
      link.click();
      showToast('图片已保存');
    } catch {
      showToast('保存失败，请截图保存', 'fail');
    }
  }, [invitation]);

  const handleShareWechat = () => {
    showToast('请点击右上角"..."分享给微信好友');
  };

  return (
    <div style={{ background: '#F0F5FF', minHeight: '100vh', paddingBottom: 40 }}>
      {/* Nav bar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: '#fff',
        boxShadow: '0 2px 8px rgba(14,165,233,0.3)',
      }}>
        <button
          onClick={() => router.back()}
          style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 18 }}
        >←</button>
        <span style={{ flex: 1, fontSize: 17, fontWeight: 700, textAlign: 'center' }}>邀请 TA 加入我的健康守护</span>
        <span style={{ width: 36 }} />
      </div>

      {/* Brand bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '12px 16px', background: '#fff', gap: 8,
      }}>
        <span style={{ fontSize: 22 }}>🌿</span>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#333' }}>宾尼小康AI健康管家</span>
      </div>

      <div style={{ padding: '16px 16px' }}>
        {/* [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版]
            没带 member_id：页面正中红字错误，不再弹旧表单、不再就地建档案。 */}
        {!memberId ? (
          <div
            data-testid="family-invite-missing-member"
            style={{
              background: '#FFFFFF',
              borderRadius: 16,
              padding: '48px 24px',
              textAlign: 'center',
              boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
              marginTop: 32,
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
            <div
              style={{
                color: '#DC2626',
                fontSize: 15,
                fontWeight: 600,
                lineHeight: 1.7,
              }}
            >
              ⚠️ 缺少成员信息，无法生成邀请，请从成员档案进入
            </div>
          </div>
        ) : loading ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在生成邀请…</div>
        ) : error ? (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '40px 20px',
            textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 14, color: '#6B7280', marginBottom: 16 }}>{error}</div>
            <button
              onClick={() => createInvitation()}
              style={{
                padding: '10px 24px', borderRadius: 20,
                background: THEME.gradientStart, color: '#fff',
                border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >重新生成</button>
          </div>
        ) : invitation ? (
          <>
            {/* Gradient Card */}
            <div style={{
              background: '#fff', borderRadius: 20, overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(14,165,233,0.12)',
              maxWidth: 360, margin: '0 auto',
            }}>
              {/* Card Header */}
              <div style={{
                background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                padding: '24px 20px 18px', textAlign: 'center', color: '#fff',
              }}>
                <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 10 }}>邀请 TA 加入我的健康守护</div>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {[
                    { icon: '📋', text: '档案管理' },
                    { icon: '💊', text: '用药提醒' },
                    { icon: '🔔', text: '异常提醒' },
                  ].map((tag) => (
                    <span key={tag.text} style={{
                      background: 'rgba(255,255,255,0.22)',
                      padding: '4px 12px', borderRadius: 14,
                      fontSize: 12, fontWeight: 500, color: '#fff',
                    }}>{tag.icon} {tag.text}</span>
                  ))}
                </div>
              </div>

              {/* Card Body */}
              <div style={{ padding: '20px 24px 24px', textAlign: 'center' }}>
                <div
                  ref={qrCanvasRef}
                  style={{
                    display: 'inline-flex', padding: 10, borderRadius: 14,
                    border: '2px solid #E0F2FE', background: '#fff',
                  }}
                >
                  <QRCodeCanvas
                    value={qrContentUrl}
                    size={164}
                    level="M"
                    includeMargin={false}
                    bgColor="#ffffff"
                    fgColor="#333333"
                  />
                </div>

                <div style={{ marginTop: 14, fontSize: 12, color: '#9CA3AF' }}>
                  邀请 24 小时内有效
                </div>

                <div style={{
                  marginTop: 10, padding: '8px 14px', borderRadius: 10,
                  background: '#F0F9FF', fontSize: 13, color: '#0369A1',
                }}>
                  {memberName
                    ? `🔗 将绑定到「${memberName}」的档案`
                    : '让 TA 扫码或打开链接，确认后就能加入啦'}
                </div>

                {/* [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 按钮配色：
                    - 保存到本地 / 复制链接 = 实心主色蓝渐变
                    - 转发微信好友 = 微信绿 #07c160 */}
                <div style={{ marginTop: 18 }}>
                  <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
                    <button
                      onClick={handleSaveImage}
                      style={{
                        flex: 1, padding: '12px 0', borderRadius: 22,
                        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                        color: '#fff', border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >保存到本地</button>
                    <button
                      onClick={handleCopyLink}
                      style={{
                        flex: 1, padding: '12px 0', borderRadius: 22,
                        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                        color: '#fff', border: 'none',
                        fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >复制链接</button>
                  </div>
                  <button
                    onClick={handleShareWechat}
                    style={{
                      width: '100%', padding: '12px 0', borderRadius: 22,
                      background: '#07c160', color: '#fff',
                      border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                    }}
                  >转发微信好友</button>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
