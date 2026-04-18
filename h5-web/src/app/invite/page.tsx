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

interface InviteStatsItem {
  user_id: number;
  user_no?: string;
  phone?: string;
  nickname?: string;
  registered_at: string;
  points_awarded: number;
}

interface InviteStats {
  total_invited: number;
  total_points_earned: number;
  items: InviteStatsItem[];
}

export default function InvitePage() {
  const router = useRouter();
  const { isLoggedIn, loading: authLoading } = useAuth();
  const [shareData, setShareData] = useState<ShareLinkResponse | null>(null);
  const [stats, setStats] = useState<InviteStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!isLoggedIn) {
      router.replace('/login');
      return;
    }

    const fetchAll = async () => {
      try {
        const [linkRes, statsRes]: any[] = await Promise.allSettled([
          api.get('/api/users/share-link'),
          api.get('/api/users/invite-stats', { params: { page: 1, page_size: 50 } }),
        ]);
        if (linkRes.status === 'fulfilled') {
          setShareData(linkRes.value?.data || linkRes.value);
        } else {
          Toast.show({ content: '获取分享链接失败', icon: 'fail' });
        }
        if (statsRes.status === 'fulfilled') {
          const d = statsRes.value?.data || statsRes.value || {};
          setStats({
            total_invited: d?.total_invited ?? 0,
            total_points_earned: d?.total_points_earned ?? 0,
            items: d?.items || [],
          });
        }
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
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

        <div className="mt-8 w-full max-w-sm">
          <h3 className="text-sm font-medium text-gray-600 mb-3">我的邀请战绩</h3>
          <div className="bg-white rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-around mb-3 pb-3 border-b border-gray-100">
              <div className="text-center">
                <div className="text-xs text-gray-400">累计邀请</div>
                <div className="text-xl font-bold" style={{ color: '#52c41a' }}>
                  {stats?.total_invited ?? 0}
                </div>
              </div>
              <div className="w-px h-8 bg-gray-100" />
              <div className="text-center">
                <div className="text-xs text-gray-400">累计获得</div>
                <div className="text-xl font-bold" style={{ color: '#fa8c16' }}>
                  {stats?.total_points_earned ?? 0}
                </div>
                <div className="text-xs text-gray-400">积分</div>
              </div>
            </div>
            {stats && stats.items.length > 0 ? (
              <div className="space-y-2">
                {stats.items.map((it) => (
                  <div key={it.user_id} className="flex items-center justify-between text-xs">
                    <div className="flex-1">
                      <div className="text-gray-700">
                        {it.nickname || it.phone || it.user_no || `用户${it.user_id}`}
                      </div>
                      <div className="text-gray-400 text-[10px]">
                        {it.registered_at?.replace('T', ' ').slice(0, 16)}
                      </div>
                    </div>
                    <span style={{ color: '#52c41a' }} className="font-medium">
                      +{it.points_awarded}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-xs text-gray-400 py-3">
                还没有邀请记录，快去分享吧
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
