'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Toast, Checkbox, Space } from 'antd-mobile';
import { login } from '@/lib/auth';
import api from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const sendCode = async () => {
    if (!phone || phone.length !== 11) {
      Toast.show({ content: '请输入正确的手机号' });
      return;
    }
    setSending(true);
    try {
      await api.post('/api/auth/sms-code', { phone, type: 'login' });
      Toast.show({ content: '验证码已发送' });
      setCountdown(60);
      const timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch {
      Toast.show({ content: '发送失败，请稍后重试' });
    }
    setSending(false);
  };

  const handleLogin = async () => {
    if (!phone || phone.length !== 11) {
      Toast.show({ content: '请输入正确的手机号' });
      return;
    }
    if (!code || code.length < 4) {
      Toast.show({ content: '请输入验证码' });
      return;
    }
    if (!agreed) {
      Toast.show({ content: '请同意用户协议和隐私政策' });
      return;
    }
    setSubmitting(true);
    try {
      const res: any = await api.post('/api/auth/sms-login', { phone, code });
      login(res.access_token, res.user);
      Toast.show({ content: '登录成功' });
      router.replace('/home');
    } catch {
      Toast.show({ content: '登录失败，请检查验证码' });
    }
    setSubmitting(false);
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(180deg, #e8fce8 0%, #ffffff 40%)' }}>
      <div className="flex-1 flex flex-col items-center pt-20 px-8">
        <div className="w-20 h-20 rounded-full flex items-center justify-center mb-4"
          style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
          <span className="text-white text-4xl">🌿</span>
        </div>
        <h1 className="text-2xl font-bold mb-1" style={{ color: '#52c41a' }}>宾尼小康</h1>
        <p className="text-gray-400 text-sm mb-10">AI健康管家 · 您的私人健康助手</p>

        <div className="w-full space-y-4">
          <div className="bg-gray-50 rounded-xl px-4 py-3 flex items-center">
            <span className="text-gray-400 mr-2">+86</span>
            <div className="w-px h-5 bg-gray-200 mr-3" />
            <Input
              placeholder="请输入手机号"
              value={phone}
              onChange={setPhone}
              type="tel"
              maxLength={11}
              style={{ '--font-size': '16px' }}
            />
          </div>

          <div className="bg-gray-50 rounded-xl px-4 py-3 flex items-center">
            <Input
              placeholder="请输入验证码"
              value={code}
              onChange={setCode}
              type="number"
              maxLength={6}
              className="flex-1"
              style={{ '--font-size': '16px' }}
            />
            <Button
              size="small"
              disabled={countdown > 0 || sending}
              onClick={sendCode}
              style={{
                color: countdown > 0 ? '#999' : '#52c41a',
                border: 'none',
                background: 'transparent',
                padding: '0 0 0 12px',
                fontSize: '14px',
              }}
            >
              {countdown > 0 ? `${countdown}s后重发` : '获取验证码'}
            </Button>
          </div>

          <Button
            block
            loading={submitting}
            onClick={handleLogin}
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: '24px',
              height: '48px',
              fontSize: '16px',
              fontWeight: 600,
              marginTop: '24px',
            }}
          >
            登录 / 注册
          </Button>

          <div className="flex items-start mt-4">
            <Checkbox
              checked={agreed}
              onChange={setAgreed}
              style={{
                '--icon-size': '16px',
                '--adm-color-primary': '#52c41a',
              }}
            />
            <span className="text-xs text-gray-400 ml-2 leading-5">
              我已阅读并同意
              <span className="text-primary">《用户服务协议》</span>
              和
              <span className="text-primary">《隐私政策》</span>
            </span>
          </div>
        </div>
      </div>

      <div className="text-center py-6">
        <Space direction="vertical" align="center">
          <span className="text-xs text-gray-300">其他登录方式</span>
          <Space>
            <div className="w-10 h-10 rounded-full bg-green-50 flex items-center justify-center text-xl">💬</div>
            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-xl">📱</div>
          </Space>
        </Space>
      </div>
    </div>
  );
}
