'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Toast, Checkbox, Space, Dialog, SpinLoading } from 'antd-mobile';
import { login } from '@/lib/auth';
import api from '@/lib/api';

interface RegisterSettings {
  enable_self_registration: boolean;
  wechat_register_mode: 'authorize_member' | 'fill_profile';
  douyin_register_mode: 'authorize_member' | 'fill_profile';
  register_page_layout: 'vertical' | 'horizontal';
  show_profile_completion_prompt: boolean;
  member_card_no_rule: 'incremental' | 'random';
}

const defaultRegisterSettings: RegisterSettings = {
  enable_self_registration: true,
  wechat_register_mode: 'authorize_member',
  douyin_register_mode: 'authorize_member',
  register_page_layout: 'vertical',
  show_profile_completion_prompt: true,
  member_card_no_rule: 'incremental',
};

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [registerSettings, setRegisterSettings] = useState<RegisterSettings>(defaultRegisterSettings);

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
    } catch (error: any) {
      Toast.show({ content: error?.response?.data?.detail || '发送失败，请稍后重试' });
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
      if (res.is_new_user) {
        const cardInfo = res.user?.member_card_no
          ? `注册成功！您的会员卡号: ${res.user.member_card_no}`
          : '注册成功，欢迎加入';
        Toast.show({ content: cardInfo, duration: 3000 });
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
        router.replace(shouldComplete ? '/health-profile' : '/home');
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

  const showChannelHint = async (channel: 'wechat' | 'douyin') => {
    const isWechat = channel === 'wechat';
    const channelLabel = isWechat ? '微信' : '抖音';
    const registerMode = isWechat
      ? registerSettings.wechat_register_mode
      : registerSettings.douyin_register_mode;

    if (!registerSettings.enable_self_registration) {
      await Dialog.alert({
        title: `${channelLabel}注册已关闭`,
        content: '当前系统未开放自助注册，请联系管理员开通账号后使用手机号验证码登录。',
        confirmText: '我知道了',
      });
      return;
    }

    if (registerMode === 'authorize_member') {
      await Dialog.alert({
        title: `${channelLabel}授权即会员`,
        content: `当前策略为“授权即会员”。在对应${channelLabel}客户端完成授权后，可直接成为会员；当前 H5 页面仍可使用手机号验证码继续登录。`,
        confirmText: '知道了',
      });
      return;
    }

    await Dialog.alert({
      title: `${channelLabel}需填写注册信息`,
      content: `当前策略为“填写注册信息”。在对应${channelLabel}客户端授权后，还需要补充手机号等注册资料；当前 H5 页面可先通过手机号验证码完成登录。`,
      confirmText: '去登录',
    });
  };

  if (settingsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(180deg, #e8fce8 0%, #ffffff 40%)' }}>
        <div className="flex flex-col items-center gap-3 text-sm text-gray-400">
          <SpinLoading color="primary" />
          <span>正在加载注册设置...</span>
        </div>
      </div>
    );
  }

  const isHorizontal = registerSettings.register_page_layout === 'horizontal';
  const submitText = registerSettings.enable_self_registration ? '登录 / 注册' : '登录';
  const helperText = registerSettings.enable_self_registration
    ? '未注册手机号验证后将自动创建会员'
    : '当前未开放自助注册，仅支持已注册账号登录';
  const profilePromptText = registerSettings.show_profile_completion_prompt
    ? '首次注册后，如资料不完整，系统会提醒补充会员信息。'
    : '首次注册后将直接进入首页，不额外弹出资料补充提醒。';
  const channelItems = [
    {
      key: 'wechat' as const,
      icon: '💬',
      label: '微信',
      desc: registerSettings.wechat_register_mode === 'authorize_member' ? '授权即会员' : '授权后填写注册信息',
      bg: '#f6ffed',
    },
    {
      key: 'douyin' as const,
      icon: '🎵',
      label: '抖音',
      desc: registerSettings.douyin_register_mode === 'authorize_member' ? '授权即会员' : '授权后填写注册信息',
      bg: '#fff1f0',
    },
  ];

  return (
    <div
      className={`min-h-screen flex flex-col ${isHorizontal ? 'md:flex-row' : ''} transition-all duration-500 ease-in-out`}
      style={{ background: 'linear-gradient(180deg, #e8fce8 0%, #ffffff 40%)' }}
    >
      <div className={`flex flex-col items-center transition-all duration-500 ease-in-out ${isHorizontal ? 'flex-1 pt-20 px-8 md:flex-none md:justify-center md:px-6 md:w-2/5 md:pt-0' : 'flex-1 pt-20 px-8'}`}>
        <div className="w-20 h-20 rounded-full flex items-center justify-center mb-4"
          style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
          <span className="text-white text-4xl">🌿</span>
        </div>
        <h1 className="text-2xl font-bold mb-1" style={{ color: '#52c41a' }}>宾尼小康</h1>
        <p className="text-gray-400 text-sm mb-10">AI健康管家 · 您的私人健康助手</p>
      </div>

      <div className={`transition-all duration-500 ease-in-out ${isHorizontal ? 'px-8 pb-10 md:w-3/5 md:flex md:items-center' : 'px-8 pb-10'}`}>
        <div className="w-full space-y-4 max-w-xl mx-auto">
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

          <div className="space-y-1 px-1">
            <div className="text-xs text-gray-400">{helperText}</div>
            <div className="text-xs text-gray-300">{profilePromptText}</div>
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
            {submitText}
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

      <div className={`text-center py-6 transition-all duration-500 ease-in-out ${isHorizontal ? 'md:absolute md:bottom-0 md:right-0 md:left-0' : ''}`}>
        <Space direction="vertical" align="center">
          <span className="text-xs text-gray-300">其他登录方式</span>
          <div className="flex flex-wrap justify-center gap-3">
            {channelItems.map((item) => (
              <div
                key={item.key}
                className="rounded-2xl px-4 py-3 min-w-[140px] text-left"
                style={{ background: item.bg }}
                onClick={() => showChannelHint(item.key)}
              >
                <div className="flex items-center justify-center gap-2 text-base">
                  <span>{item.icon}</span>
                  <span className="font-medium text-gray-700">{item.label}</span>
                </div>
                <div className="mt-1 text-[11px] text-gray-400">{item.desc}</div>
              </div>
            ))}
          </div>
        </Space>
      </div>
    </div>
  );
}
