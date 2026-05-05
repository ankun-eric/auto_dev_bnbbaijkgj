'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button, Input, Toast, Checkbox, Dialog, SpinLoading } from 'antd-mobile';
import { login } from '@/lib/auth';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

interface RegisterSettings {
  enable_self_registration: boolean;
  wechat_register_mode: 'authorize_member' | 'fill_profile';
  register_page_layout: 'vertical' | 'horizontal';
  show_profile_completion_prompt: boolean;
  member_card_no_rule: 'incremental' | 'random';
}

const defaultRegisterSettings: RegisterSettings = {
  enable_self_registration: true,
  wechat_register_mode: 'authorize_member',
  register_page_layout: 'vertical',
  show_profile_completion_prompt: true,
  member_card_no_rule: 'incremental',
};

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const refParam = searchParams.get('ref') || '';
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [registerSettings, setRegisterSettings] = useState<RegisterSettings>(defaultRegisterSettings);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchLogo = async () => {
      try {
        const res: any = await api.get('/api/settings/logo');
        if (res?.data?.logo_url) {
          setLogoUrl(res.data.logo_url);
        }
      } catch {}
    };
    fetchLogo();
  }, []);

  useEffect(() => {
    const fetchRegisterSettings = async () => {
      try {
        const res = await api.get('/api/auth/register-settings');
        setRegisterSettings({ ...defaultRegisterSettings, ...res });
      } catch {
        setRegisterSettings(defaultRegisterSettings);
      } finally {
        setSettingsLoading(false);
      }
    };
    fetchRegisterSettings();
  }, []);

  const sendCode = async () => {
    if (!phone || phone.length !== 11) {
      Toast.show({ content: '请输入正确的手机号' });
      return;
    }
    setSending(true);
    try {
      await api.post('/api/auth/sms-code', { phone, type: 'login' });
      Toast.show({ content: '验证码已发送，请注意查收短信' });
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
    } catch (error: any) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;
      if (status === 429 || status === 403) {
        Toast.show({ content: detail || '发送失败，请稍后重试' });
      } else if (status === 500) {
        Toast.show({ content: '短信发送失败，请稍后重试' });
      } else {
        Toast.show({ content: detail || '发送失败，请稍后重试' });
      }
    } finally {
      setSending(false);
    }
  };

  // 真实执行登录请求（在协议已勾选/同意之后调用）
  const doLoginRequest = async () => {
    if (!phone || phone.length !== 11) {
      Toast.show({ content: '请输入正确的手机号' });
      return;
    }
    if (!code || code.length < 4) {
      Toast.show({ content: '请输入验证码' });
      return;
    }
    setSubmitting(true);
    try {
      const loginPayload: Record<string, string> = { phone, code };
      if (refParam) {
        loginPayload.referrer_no = refParam;
      }
      const res: any = await api.post('/api/auth/sms-login', loginPayload);
      login(res.access_token, res.user);
      if (res.is_new_user) {
        const cardInfo = res.user?.member_card_no
          ? `注册成功！您的会员卡号: ${res.user.member_card_no}`
          : '注册成功，欢迎加入';
        Toast.show({ content: cardInfo, duration: 3000 });
        router.replace('/health-guide');
        return;
      } else {
        Toast.show({ content: '登录成功' });
      }
      if (res.needs_profile_completion && registerSettings.show_profile_completion_prompt) {
        const shouldComplete = await Dialog.confirm({
          title: '补充会员信息',
          content: '完善基础健康信息后，可获得更精准的 AI 健康建议，是否现在去完善？',
          confirmText: '立即完善',
          cancelText: '稍后再说',
        });
        router.replace(shouldComplete ? '/health-guide' : '/home');
        return;
      }
      router.replace('/home');
    } catch (error: any) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail || '';
      if (status === 403 && detail.includes('暂未开放自助注册')) {
        Dialog.alert({
          title: '无法注册',
          content: '当前系统暂未开放自助注册，请联系管理员开通账号后再登录。',
          confirmText: '我知道了',
        });
      } else {
        Toast.show({ content: detail || '登录失败，请检查验证码' });
      }
    } finally {
      setSubmitting(false);
    }
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
      // 未勾选协议时弹出二次确认弹窗
      const confirmed = await Dialog.confirm({
        title: '为保障您的权益，请阅读并同意以下协议',
        content: (
          <div style={{ fontSize: 14, lineHeight: 1.6, color: '#555' }}>
            您需要阅读并同意
            <span style={{ color: '#2fb56a' }}>《用户服务协议》</span>
            和
            <span style={{ color: '#2fb56a' }}>《隐私政策》</span>
            后才能继续登录。
          </div>
        ),
        confirmText: '同意并登录',
        cancelText: '再看看',
      });
      if (!confirmed) {
        return;
      }
      setAgreed(true);
    }
    await doLoginRequest();
  };

  if (settingsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(180deg, #2fb56a 0%, #5cd692 100%)' }}>
        <div className="flex flex-col items-center gap-3 text-sm text-white">
          <SpinLoading color="white" />
          <span>正在加载...</span>
        </div>
      </div>
    );
  }

  const submitText = registerSettings.enable_self_registration ? '登录 / 注册' : '登录';

  return (
    <div
      className="login-page-v3"
      style={{
        minHeight: '100vh',
        background: '#f7f8fa',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 顶部 42% 屏高的绿色渐变沉浸式品牌区 */}
      <div
        className="top-brand"
        style={{
          height: '42vh',
          minHeight: '280px',
          background: 'linear-gradient(180deg, #2fb56a 0%, #5cd692 100%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 32px 56px',
          position: 'relative',
        }}
      >
        {/* 92×92 白色圆形托盘内嵌项目 LOGO */}
        <div
          className="logo-circle"
          style={{
            width: '92px',
            height: '92px',
            borderRadius: '50%',
            background: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            marginBottom: '20px',
            overflow: 'hidden',
          }}
        >
          {logoUrl ? (
            <img
              src={resolveAssetUrl(logoUrl)}
              alt="Logo"
              style={{ width: '76px', height: '76px', objectFit: 'contain', borderRadius: '50%' }}
            />
          ) : (
            <span style={{ fontSize: '40px' }}>🌿</span>
          )}
        </div>

        <h1
          style={{
            color: '#ffffff',
            fontSize: '28px',
            fontWeight: 700,
            margin: '0 0 8px',
            letterSpacing: '1px',
            textShadow: '0 2px 4px rgba(0,0,0,0.08)',
          }}
        >
          宾尼小康
        </h1>
        <p
          style={{
            color: 'rgba(255,255,255,0.92)',
            fontSize: '14px',
            margin: 0,
            letterSpacing: '0.5px',
          }}
        >
          AI 健康管家 · 您的私人健康助手
        </p>
      </div>

      {/* 表单卡片上浮 -28px，圆角 24px，覆盖在渐变下沿 */}
      <div
        className="form-card"
        style={{
          marginTop: '-28px',
          marginLeft: '20px',
          marginRight: '20px',
          background: '#ffffff',
          borderRadius: '24px',
          padding: '28px 24px 24px',
          boxShadow: '0 -4px 24px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)',
          position: 'relative',
          zIndex: 2,
        }}
      >
        <div className="w-full space-y-4">
          {/* 手机号输入 */}
          <div
            className="bg-gray-50 rounded-xl px-4 py-3 flex items-center"
            style={{ background: '#f5f7fa', borderRadius: '12px' }}
          >
            <span className="text-gray-500 mr-2" style={{ fontSize: '15px' }}>+86</span>
            <div className="w-px h-5 bg-gray-200 mr-3" />
            <Input
              placeholder="请输入手机号"
              value={phone}
              onChange={setPhone}
              type="tel"
              maxLength={11}
              style={{ '--font-size': '16px' } as React.CSSProperties}
            />
          </div>

          {/* 验证码输入 + 获取验证码按钮 */}
          <div
            className="bg-gray-50 rounded-xl px-4 py-3 flex items-center"
            style={{ background: '#f5f7fa', borderRadius: '12px' }}
          >
            <Input
              placeholder="请输入验证码"
              value={code}
              onChange={setCode}
              type="number"
              maxLength={6}
              className="flex-1"
              style={{ '--font-size': '16px' } as React.CSSProperties}
            />
            <Button
              size="small"
              disabled={countdown > 0 || sending}
              onClick={sendCode}
              style={{
                color: countdown > 0 ? '#999' : '#2fb56a',
                border: 'none',
                background: 'transparent',
                padding: '0 0 0 12px',
                fontSize: '14px',
                whiteSpace: 'nowrap',
                wordBreak: 'keep-all',
                flex: '0 0 auto',
              }}
            >
              {countdown > 0 ? `${countdown} s` : '获取验证码'}
            </Button>
          </div>

          {refParam && (
            <div className="px-1 text-xs" style={{ color: '#2fb56a' }}>
              🎉 已识别邀请码：<span className="font-medium">{refParam}</span>
            </div>
          )}

          {/* 登录按钮始终高亮可点 */}
          <Button
            block
            loading={submitting}
            onClick={handleLogin}
            style={{
              background: 'linear-gradient(135deg, #2fb56a 0%, #5cd692 100%)',
              color: '#fff',
              border: 'none',
              borderRadius: '24px',
              height: '48px',
              fontSize: '16px',
              fontWeight: 600,
              marginTop: '20px',
              boxShadow: '0 6px 16px rgba(47,181,106,0.32)',
            }}
          >
            {submitText}
          </Button>

          {/* 协议勾选行 */}
          <div className="flex items-start" style={{ marginTop: '16px' }}>
            <Checkbox
              checked={agreed}
              onChange={setAgreed}
              style={{
                '--icon-size': '16px',
                '--adm-color-primary': '#2fb56a',
              } as React.CSSProperties}
            />
            <span className="text-xs ml-2 leading-5" style={{ color: '#999' }}>
              我已阅读并同意
              <span style={{ color: '#2fb56a' }}>《用户服务协议》</span>
              和
              <span style={{ color: '#2fb56a' }}>《隐私政策》</span>
            </span>
          </div>
        </div>
      </div>

      {/* 底部留白（删除「登录即表示您将享受 AI 智能健康陪伴服务」文案） */}
      <div style={{ flex: 1, minHeight: '24px' }} />
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(180deg, #2fb56a 0%, #5cd692 100%)' }}>
        <SpinLoading color="white" />
      </div>
    }>
      <LoginContent />
    </Suspense>
  );
}
