'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Avatar, Button, SpinLoading, Image, Toast } from 'antd-mobile';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';

interface QRCodeData {
  token: string;
  expires_at: string;
  user_id: number;
}

export default function MemberCardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [qrData, setQrData] = useState<QRCodeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [countdown, setCountdown] = useState(60);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchQRCode = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/member/qrcode');
      const data = res.data || res;
      setQrData(data);
      setCountdown(60);
    } catch {
      Toast.show({ content: '获取二维码失败' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQRCode();
  }, [fetchQRCode]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);

    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          fetchQRCode();
          return 60;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [fetchQRCode]);

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(180deg, #52c41a, #13c2c2 60%, #f5f5f5)' }}>
      <NavBar
        onBack={() => router.back()}
        style={{ background: 'transparent', color: '#fff' }}
      >
        会员卡
      </NavBar>

      <div className="px-6 pt-4">
        <div
          className="rounded-2xl p-6 text-center"
          style={{
            background: 'rgba(255,255,255,0.95)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
          }}
        >
          <Avatar
            src={user?.avatar || ''}
            style={{
              '--size': '72px',
              '--border-radius': '50%',
              border: '3px solid #52c41a',
              margin: '0 auto',
            }}
          />
          <div className="text-lg font-bold mt-3">{user?.nickname || '用户'}</div>
          {user?.user_no && (
            <div className="text-xs text-gray-400 mt-1">会员号：{user.user_no}</div>
          )}

          <div className="my-6">
            {loading ? (
              <div className="flex items-center justify-center py-10">
                <SpinLoading color="primary" />
              </div>
            ) : qrData ? (
              <div className="flex flex-col items-center">
                <Image
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrData.token)}`}
                  width={200}
                  height={200}
                  fit="contain"
                  style={{ borderRadius: 8 }}
                />
              </div>
            ) : (
              <div className="text-gray-400 py-10">二维码加载失败</div>
            )}
          </div>

          <div className="text-sm text-gray-500">
            <span className="text-primary font-medium">{countdown}s</span> 后自动刷新
          </div>

          <Button
            size="small"
            onClick={fetchQRCode}
            style={{
              marginTop: 12,
              borderRadius: 20,
              color: '#52c41a',
              borderColor: '#52c41a',
            }}
          >
            手动刷新
          </Button>

          <div className="text-xs text-gray-400 mt-4">
            请向工作人员出示此二维码完成到店签到或核销
          </div>
        </div>
      </div>
    </div>
  );
}
