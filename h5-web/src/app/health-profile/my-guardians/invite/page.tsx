'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import { QRCodeCanvas } from 'qrcode.react';
import api from '@/lib/api';

interface InviteData {
  invite_code: string;
  qr_url: string;
  expires_at: string;
  max_uses?: number;
  used_count?: number;
}

function InvitePageInner() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [invite, setInvite] = useState<InviteData | null>(null);
  const [error, setError] = useState('');

  const createInvite = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res: any = await api.post('/api/reverse-guardian/invite');
      const data = res.data || res;
      setInvite(data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '生成邀请失败';
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    createInvite();
  }, [createInvite]);

  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const inviteLink = invite
    ? (invite.qr_url || `${typeof window !== 'undefined' ? window.location.origin : ''}${basePath}/family-auth?code=${invite.invite_code}&type=reverse`)
    : '';

  const qrContentUrl = inviteLink;
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
      link.download = `bini-health-guardian-invite-${invite?.invite_code?.slice(0, 8) || 'qr'}.png`;
      link.href = url;
      link.click();
      showToast('图片已保存');
    } catch {
      showToast('保存失败，请截图保存', 'fail');
    }
  }, [invite]);

  const handleShareWechat = () => {
    showToast('请点击右上角"..."分享给微信好友');
  };

  const THEME = {
    gradientStart: '#4CAF50',
    gradientEnd: '#66BB6A',
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
        boxShadow: '0 2px 8px rgba(76,175,80,0.3)',
      }}>
        <button
          onClick={() => router.back()}
          style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 18 }}
        >←</button>
        <span style={{ flex: 1, fontSize: 17, fontWeight: 700, textAlign: 'center' }}>邀请 TA 守护我的健康</span>
        <span style={{ width: 36 }} />
      </div>

      <div style={{ padding: '16px 16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在生成邀请…</div>
        ) : error ? (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '40px 20px',
            textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 14, color: '#6B7280', marginBottom: 16 }}>{error}</div>
            <button
              onClick={createInvite}
              style={{
                padding: '10px 24px', borderRadius: 20,
                background: THEME.gradientStart, color: '#fff',
                border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >重新生成</button>
          </div>
        ) : invite ? (
          <>
            {/* Gradient Card */}
            <div style={{
              background: '#fff', borderRadius: 20, overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(76,175,80,0.12)',
              maxWidth: 360, margin: '0 auto',
            }}>
              {/* Card Header */}
              <div style={{
                background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                padding: '24px 20px 18px', textAlign: 'center', color: '#fff',
              }}>
                <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 10 }}>邀请 TA 守护我的健康</div>
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
                    border: '2px solid #E8F5E9', background: '#fff',
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
                  邀请有效期：24小时
                </div>

                <div style={{
                  marginTop: 10, padding: '8px 14px', borderRadius: 10,
                  background: '#F0FDF4', fontSize: 13, color: '#166534',
                }}>
                  💚 让 TA 随时关注我的健康
                </div>

                {/* Buttons */}
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
                        background: '#fff', color: THEME.gradientStart,
                        border: `1.5px solid ${THEME.gradientStart}`,
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

export default function InviteGuardianPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <InvitePageInner />
    </Suspense>
  );
}
