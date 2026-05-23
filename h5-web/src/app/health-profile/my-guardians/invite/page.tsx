'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';
import { QRCodeCanvas } from 'qrcode.react';

interface InviteData {
  invite_code: string;
  qr_url: string;
  expires_at: string;
  max_uses?: number;
  used_count?: number;
}

const T = {
  brand500: BH_TOKENS.brand500,
  brand600: BH_TOKENS.brand600,
  textPrimary: BH_TOKENS.textPrimary,
  textSecondary: BH_TOKENS.textSecondary,
};

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

  const handleCopyLink = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      showToast('链接已复制');
    } catch {
      showToast('复制失败，请手动复制', 'fail');
    }
  };

  const handleShare = () => {
    if (navigator.share && inviteLink) {
      navigator.share({
        title: '邀请你守护我的健康',
        text: '我邀请你守护我的健康，点击链接接受邀请',
        url: inviteLink,
      }).catch(() => {});
    } else {
      handleCopyLink();
    }
  };

  const formatExpiry = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = d.getTime() - now.getTime();
      const diffH = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffH > 24) return `${Math.floor(diffH / 24)}天${diffH % 24}小时`;
      if (diffH > 0) return `${diffH}小时`;
      const diffM = Math.floor(diffMs / (1000 * 60));
      return diffM > 0 ? `${diffM}分钟` : '即将过期';
    } catch {
      return '24小时';
    }
  };

  return (
    <div style={{ background: 'linear-gradient(160deg, #E8F5E9 0%, #E8F4FF 100%)', minHeight: '100vh', paddingBottom: 40 }}>
      <GreenNavBar>邀请别人守护我</GreenNavBar>

      <div style={{ padding: '12px 16px' }}>
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
                background: T.brand500, color: '#fff',
                border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >重新生成</button>
          </div>
        ) : invite ? (
          <>
            <div style={{
              background: '#fff', borderRadius: 20, overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(56,189,248,0.12)',
              maxWidth: 340, margin: '0 auto',
            }}>
              <div style={{
                background: 'linear-gradient(135deg, #4CAF50, #66BB6A)',
                padding: '28px 24px 20px', textAlign: 'center', color: '#fff',
              }}>
                <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>邀请守护我的健康</div>
                <div style={{ fontSize: 13, opacity: 0.9 }}>扫描二维码或复制链接接受邀请</div>
              </div>

              <div style={{ padding: '24px', textAlign: 'center' }}>
                <div style={{
                  display: 'inline-flex', padding: 12, borderRadius: 16,
                  border: '2px solid #E8F5E9', background: '#fff',
                }}>
                  <QRCodeCanvas
                    value={qrContentUrl}
                    size={164}
                    level="M"
                    includeMargin={false}
                    bgColor="#ffffff"
                    fgColor="#333333"
                  />
                </div>

                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
                  <div style={{ fontSize: 12, color: T.textSecondary }}>
                    有效期: {formatExpiry(invite.expires_at)}
                  </div>
                  {invite.used_count != null && (
                    <div style={{ fontSize: 12, color: T.textSecondary }}>
                      已使用: {invite.used_count}{invite.max_uses ? ` / ${invite.max_uses}` : ''} 次
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div style={{ maxWidth: 340, margin: '20px auto 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <button
                onClick={handleCopyLink}
                style={{
                  width: '100%', padding: '14px 0', borderRadius: 24,
                  background: T.brand500, color: '#fff',
                  border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}
              >复制邀请链接</button>
              <button
                onClick={handleShare}
                style={{
                  width: '100%', padding: '14px 0', borderRadius: 24,
                  background: '#07c160', color: '#fff',
                  border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}
              >分享给好友</button>
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
