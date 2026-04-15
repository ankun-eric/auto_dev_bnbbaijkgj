'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Button, Toast, SpinLoading } from 'antd-mobile';
import { QRCodeSVG } from 'qrcode.react';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';

interface ShareLinkResponse {
  share_link: string;
  user_no: string;
}

export default function InvitePage() {
  const router = useRouter();
  const { isLoggedIn, loading: authLoading } = useAuth();
  const [shareData, setShareData] = useState<ShareLinkResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!isLoggedIn) {
      router.replace('/login');
      return;
    }

    const fetchShareLink = async () => {
      try {
        const res = await api.get('/api/users/share-link') as any;
        setShareData(res);
      } catch {
        Toast.show({ content: '获取分享链接失败', icon: 'fail' });
      } finally {
        setLoading(false);
      }
    };
    fetchShareLink();
  }, [authLoading, isLoggedIn, router]);

  const handleCopy = () => {
    if (!shareData?.share_link) return;
    navigator.clipboard.writeText(shareData.share_link).then(() => {
      Toast.show({ content: '已复制', icon: 'success' });
    }).catch(() => {
      Toast.show({ content: '复制失败' });
    });
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <SpinLoading color="primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(180deg, #e8fce8 0%, #ffffff 40%)' }}>
      <NavBar onBack={() => router.back()} style={{ '--border-bottom': 'none', background: 'transparent' }}>
        邀请好友
      </NavBar>

      <div className="px-6 pt-4 pb-10 flex flex-col items-center">
        <div className="w-20 h-20 rounded-full flex items-center justify-center mb-4"
          style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
          <span className="text-4xl">🎁</span>
        </div>

        <h2 className="text-xl font-bold mb-1" style={{ color: '#333' }}>邀请好友一起体验</h2>
        <p className="text-sm text-gray-400 mb-6">扫描二维码或分享链接邀请好友一起体验</p>

        <div className="bg-white rounded-2xl p-6 shadow-sm w-full max-w-sm flex flex-col items-center">
          {shareData?.share_link && (
            <div className="p-4 bg-white rounded-xl border border-gray-100">
              <QRCodeSVG
                value={shareData.share_link}
                size={180}
                level="M"
                fgColor="#333"
                imageSettings={{
                  src: '',
                  height: 0,
                  width: 0,
                  excavate: false,
                }}
              />
            </div>
          )}

          {shareData?.user_no && (
            <div className="mt-4 text-sm text-gray-500">
              我的邀请码：<span className="font-bold" style={{ color: '#52c41a' }}>{shareData.user_no}</span>
            </div>
          )}

          <Button
            block
            onClick={handleCopy}
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: '24px',
              height: '44px',
              fontSize: '15px',
              fontWeight: 600,
              marginTop: '24px',
            }}
          >
            复制分享链接
          </Button>
        </div>

        <div className="mt-8 w-full max-w-sm">
          <h3 className="text-sm font-medium text-gray-600 mb-3">邀请说明</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <div className="flex items-start gap-2">
              <span style={{ color: '#52c41a' }}>1.</span>
              <span>将二维码或链接分享给好友</span>
            </div>
            <div className="flex items-start gap-2">
              <span style={{ color: '#52c41a' }}>2.</span>
              <span>好友通过链接注册成为会员</span>
            </div>
            <div className="flex items-start gap-2">
              <span style={{ color: '#52c41a' }}>3.</span>
              <span>邀请成功后双方均可获得奖励</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
