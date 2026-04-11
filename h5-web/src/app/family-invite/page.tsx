'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Toast, Button } from 'antd-mobile';
import api from '@/lib/api';

interface InvitationData {
  invite_code: string;
  qr_url: string;
  expires_at: string;
}

export default function FamilyInvitePage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-gray-400">加载中...</div>}>
      <FamilyInviteContent />
    </Suspense>
  );
}

function FamilyInviteContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const memberId = searchParams.get('member_id');

  const [loading, setLoading] = useState(true);
  const [invitation, setInvitation] = useState<InvitationData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!memberId) {
      setError('缺少成员参数');
      setLoading(false);
      return;
    }
    createInvitation();
  }, [memberId]);

  const createInvitation = async () => {
    setLoading(true);
    try {
      const res: any = await api.post('/api/family/invitation', { member_id: Number(memberId) });
      const data = res.data || res;
      setInvitation(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '生成邀请失败，请重试';
      setError(detail);
    }
    setLoading(false);
  };

  const inviteLink = invitation
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}${process.env.NEXT_PUBLIC_BASE_PATH || ''}/family-auth?code=${invitation.invite_code}`
    : '';

  const handleCopyLink = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      Toast.show({ content: '链接已复制', icon: 'success' });
    } catch {
      Toast.show({ content: '复制失败，请手动复制', icon: 'fail' });
    }
  };

  const handleSaveImage = () => {
    Toast.show({ content: '请长按图片保存到相册' });
  };

  const handleShareWechat = () => {
    Toast.show({ content: '请点击右上角"..."分享给微信好友' });
  };

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}>
      <NavBar onBack={() => router.back()} style={{ background: 'transparent' }}>
        邀请关联
      </NavBar>

      <div className="px-4 pt-2 pb-8">
        {loading ? (
          <div className="text-center py-20 text-gray-400 text-sm">正在生成邀请...</div>
        ) : error ? (
          <div className="text-center py-20">
            <div className="text-gray-400 text-sm mb-4">{error}</div>
            <Button
              size="small"
              style={{ '--border-color': '#52c41a', '--text-color': '#52c41a', borderRadius: 20 }}
              onClick={() => router.back()}
            >
              返回
            </Button>
          </div>
        ) : invitation ? (
          <>
            {/* Invitation card */}
            <div
              className="rounded-3xl overflow-hidden mx-auto"
              style={{
                maxWidth: 340,
                background: '#fff',
                boxShadow: '0 8px 32px rgba(82, 196, 26, 0.15)',
              }}
            >
              {/* Card header */}
              <div
                className="px-6 pt-8 pb-6 text-center"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              >
                <div className="text-white text-lg font-bold mb-1">家庭健康档案共管</div>
                <div className="text-white/80 text-xs">邀请您一起守护家人健康</div>
              </div>

              {/* Card body */}
              <div className="px-6 py-6">
                <div className="text-center mb-6">
                  <div className="text-sm text-gray-600 mb-4">扫描下方二维码接受邀请</div>
                  {/* QR code placeholder */}
                  <div
                    className="mx-auto flex items-center justify-center rounded-2xl"
                    style={{
                      width: 180,
                      height: 180,
                      background: '#f6ffed',
                      border: '2px dashed #b7eb8f',
                    }}
                  >
                    <div className="text-center">
                      <div className="text-4xl mb-2">📱</div>
                      <div className="text-xs text-gray-400">二维码</div>
                      <div className="text-xs text-gray-300 mt-1 break-all px-2" style={{ fontSize: 9 }}>
                        {invitation.invite_code.slice(0, 12)}...
                      </div>
                    </div>
                  </div>
                </div>

                {/* Logo area */}
                <div className="flex items-center justify-center gap-2 mb-2">
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center"
                    style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                  >
                    <span className="text-white text-xs font-bold">B</span>
                  </div>
                  <span className="text-xs text-gray-400">Bini Health</span>
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="mt-6 space-y-3" style={{ maxWidth: 340, margin: '24px auto 0' }}>
              <Button
                block
                style={{
                  background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 24,
                  height: 44,
                  fontWeight: 600,
                }}
                onClick={handleSaveImage}
              >
                保存到本地
              </Button>
              <Button
                block
                style={{
                  background: '#fff',
                  color: '#52c41a',
                  border: '1.5px solid #52c41a',
                  borderRadius: 24,
                  height: 44,
                  fontWeight: 600,
                }}
                onClick={handleCopyLink}
              >
                复制链接
              </Button>
              <Button
                block
                style={{
                  background: '#07c160',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 24,
                  height: 44,
                  fontWeight: 600,
                }}
                onClick={handleShareWechat}
              >
                分享微信好友
              </Button>
            </div>

            {/* Expiry notice */}
            <div className="text-center mt-6">
              <span className="text-xs text-gray-400">邀请有效期：24 小时</span>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
