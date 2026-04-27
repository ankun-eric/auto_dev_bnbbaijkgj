'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, List, Dialog, Toast, Button, Input } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';

export default function AccountSecurityPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [wechatBound, setWechatBound] = useState(false);
  const [showDeactivate, setShowDeactivate] = useState(false);
  const [deactivateStep, setDeactivateStep] = useState<'notice' | 'verify'>('notice');
  const [verifyCode, setVerifyCode] = useState('');
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    api.get('/api/user/security-info').then((res: any) => {
      const data = res.data || res;
      setWechatBound(!!data.wechat_bound);
    }).catch(() => {});
  }, []);

  const maskedPhone = () => {
    const phone = user?.phone || '';
    if (phone.length >= 7) return phone.slice(0, 3) + '****' + phone.slice(-4);
    return phone || '未绑定';
  };

  const sendCode = async () => {
    try {
      await api.post('/api/user/send-deactivate-code');
      setCountdown(60);
      const timer = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) { clearInterval(timer); return 0; }
          return prev - 1;
        });
      }, 1000);
    } catch {
      Toast.show({ content: '发送失败', icon: 'fail' });
    }
  };

  const handleDeactivate = async () => {
    if (!verifyCode) { Toast.show({ content: '请输入验证码' }); return; }
    try {
      await api.post('/api/user/deactivate', { code: verifyCode });
      Toast.show({ content: '账号已注销' });
      localStorage.clear();
      router.replace('/login');
    } catch {
      Toast.show({ content: '注销失败', icon: 'fail' });
    }
  };

  const handleWechatToggle = async () => {
    if (wechatBound) {
      const ok = await Dialog.confirm({ content: '确定解绑微信吗？' });
      if (!ok) return;
      try {
        await api.post('/api/user/unbind-wechat');
        setWechatBound(false);
        Toast.show({ content: '已解绑', icon: 'success' });
      } catch {
        Toast.show({ content: '解绑失败', icon: 'fail' });
      }
    } else {
      Toast.show({ content: '请在微信中完成绑定' });
    }
  };

  return (
    <div className="min-h-screen" style={{ background: THEME.background }}>
      <NavBar
        onBack={() => router.back()}
        style={{ background: THEME.cardBg, '--border-bottom': `1px solid ${THEME.divider}` } as React.CSSProperties}
      >
        <span style={{ color: THEME.textPrimary, fontWeight: 600 }}>账号安全</span>
      </NavBar>

      <div className="pt-2">
        <List style={{ '--border-top': 'none' } as React.CSSProperties}>
          <List.Item extra={maskedPhone()} arrow onClick={() => router.push('/change-phone')}>
            手机号
          </List.Item>
          <List.Item arrow onClick={() => router.push('/change-password')}>
            登录密码
          </List.Item>
          <List.Item
            extra={wechatBound ? '已绑定' : '未绑定'}
            arrow
            onClick={handleWechatToggle}
          >
            微信绑定
          </List.Item>
        </List>

        <div className="px-4 mt-8">
          <Button
            block
            onClick={() => { setShowDeactivate(true); setDeactivateStep('notice'); }}
            style={{
              color: THEME.textSecondary,
              borderColor: THEME.divider,
              borderRadius: 24,
              height: 44,
              background: 'transparent',
              fontSize: 14,
            }}
          >
            账号注销
          </Button>
        </div>
      </div>

      {/* Deactivate dialog */}
      {showDeactivate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowDeactivate(false)} />
          <div
            className="relative rounded-2xl p-5 mx-6"
            style={{ background: THEME.cardBg, maxWidth: 360, width: '100%' }}
          >
            {deactivateStep === 'notice' ? (
              <>
                <div className="text-base font-bold mb-3" style={{ color: THEME.textPrimary }}>账号注销须知</div>
                <div className="text-sm mb-4 space-y-2" style={{ color: THEME.textSecondary }}>
                  <p>• 注销后账号数据将被永久删除，无法恢复</p>
                  <p>• 注销后该手机号将无法用于注册新账号（90天内）</p>
                  <p>• 未完成的订单、未使用的优惠券将作废</p>
                  <p>• 健康档案数据将被永久清除</p>
                </div>
                <div className="flex gap-3">
                  <Button block style={{ borderRadius: 20 }} onClick={() => setShowDeactivate(false)}>取消</Button>
                  <Button
                    block
                    style={{ borderRadius: 20, background: '#FF4D4F', color: '#fff', border: 'none' }}
                    onClick={() => setDeactivateStep('verify')}
                  >
                    继续注销
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="text-base font-bold mb-3" style={{ color: THEME.textPrimary }}>验证身份</div>
                <div className="text-sm mb-4" style={{ color: THEME.textSecondary }}>
                  验证码将发送到 {maskedPhone()}
                </div>
                <div className="flex gap-2 mb-4">
                  <Input
                    placeholder="输入验证码"
                    value={verifyCode}
                    onChange={setVerifyCode}
                    style={{ '--font-size': '16px', flex: 1 }}
                  />
                  <Button
                    size="small"
                    disabled={countdown > 0}
                    style={{ borderRadius: 20, color: THEME.primary, borderColor: THEME.primary, flexShrink: 0 }}
                    onClick={sendCode}
                  >
                    {countdown > 0 ? `${countdown}s` : '获取验证码'}
                  </Button>
                </div>
                <div className="flex gap-3">
                  <Button block style={{ borderRadius: 20 }} onClick={() => setShowDeactivate(false)}>取消</Button>
                  <Button
                    block
                    style={{ borderRadius: 20, background: '#FF4D4F', color: '#fff', border: 'none' }}
                    onClick={handleDeactivate}
                  >
                    确认注销
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
