'use client';

import { useEffect, useState, Suspense, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast, SpinLoading } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import { login } from '@/lib/auth';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
import styles from './login.module.css';

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

// 协议二次确认弹窗（居中）
function AgreementDialog(props: {
  visible: boolean;
  onAgree: () => void;
  onReject: () => void;
  onOpenAgreement: (type: 'service' | 'privacy') => void;
}) {
  if (!props.visible) return null;
  return (
    <div className={styles.dialogMask} role="dialog" aria-modal="true">
      <div className={styles.dialogCard}>
        <div className={styles.dialogTitle}>服务协议及隐私保护</div>
        <div className={styles.dialogBody}>
          请您阅读并同意
          <span
            className={styles.agreementLink}
            onClick={() => props.onOpenAgreement('service')}
          >
            《用户服务协议》
          </span>
          和
          <span
            className={styles.agreementLink}
            onClick={() => props.onOpenAgreement('privacy')}
          >
            《隐私政策》
          </span>
          后才能继续登录。
        </div>
        <div className={styles.dialogActions}>
          <button
            type="button"
            className={`${styles.dialogBtn} ${styles.dialogBtnReject}`}
            onClick={props.onReject}
          >
            不同意
          </button>
          <button
            type="button"
            className={`${styles.dialogBtn} ${styles.dialogBtnAgree}`}
            onClick={props.onAgree}
          >
            同意
          </button>
        </div>
      </div>
    </div>
  );
}

// 协议详情半屏抽屉
function AgreementDrawer(props: {
  visible: boolean;
  type: 'service' | 'privacy';
  onClose: () => void;
}) {
  if (!props.visible) return null;
  const title = props.type === 'service' ? '用户服务协议' : '隐私政策';
  const url = props.type === 'service' ? '/legal/service-agreement' : '/legal/privacy-policy';
  return (
    <div
      className={styles.drawerMask}
      onClick={(e) => {
        if (e.target === e.currentTarget) props.onClose();
      }}
    >
      <div className={styles.drawer}>
        <div className={styles.drawerHandle} onClick={props.onClose}>
          <div className={styles.drawerHandleBar} />
        </div>
        <div className={styles.drawerHeader}>
          <span className={styles.drawerTitle}>{title}</span>
          <button
            type="button"
            className={styles.drawerCloseBtn}
            aria-label="关闭"
            onClick={props.onClose}
          >
            ×
          </button>
        </div>
        <div className={styles.drawerBody}>
          <iframe className={styles.drawerIframe} src={url} title={title} />
        </div>
      </div>
    </div>
  );
}

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
  const [agreementDialogVisible, setAgreementDialogVisible] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerType, setDrawerType] = useState<'service' | 'privacy'>('service');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const sendCode = async () => {
    if (!phone || phone.length !== 11) {
      showToast('请输入正确的手机号', 'warning');
      return;
    }
    setSending(true);
    try {
      await api.post('/api/auth/sms-code', { phone, type: 'login' });
      showToast('验证码已发送，请注意查收短信');
      setCountdown(60);
      timerRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            if (timerRef.current) clearInterval(timerRef.current);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      showToast(detail || '发送失败，请稍后重试', 'fail');
    } finally {
      setSending(false);
    }
  };

  const doLoginRequest = async () => {
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
        showToast('登录成功');
      }
      if (res.needs_profile_completion && registerSettings.show_profile_completion_prompt) {
        router.replace('/health-guide');
        return;
      }
      // [PRD-AI-HOME-V1 2026-05-19] 登录成功默认落地由 /home（菜单首页）改为 /ai-home（AI 首页）
      router.replace('/ai-home');
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '';
      showToast(detail || '登录失败，请检查验证码', 'fail');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = () => {
    if (!phone || phone.length !== 11) {
      showToast('请输入正确的手机号', 'warning');
      return;
    }
    if (!code || code.length < 4) {
      showToast('请输入验证码', 'warning');
      return;
    }
    if (!agreed) {
      setAgreementDialogVisible(true);
      return;
    }
    void doLoginRequest();
  };

  const handleDialogAgree = async () => {
    setAgreementDialogVisible(false);
    setAgreed(true);
    await doLoginRequest();
  };

  const handleDialogReject = () => {
    setAgreementDialogVisible(false);
  };

  const handleOpenAgreement = (type: 'service' | 'privacy') => {
    setDrawerType(type);
    setDrawerVisible(true);
  };

  if (settingsLoading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: 'linear-gradient(180deg, #4AD97A 0%, #0EA5E9 100%)' }}
      >
        <div className="flex flex-col items-center gap-3 text-sm text-white">
          <SpinLoading color="white" />
          <span>正在加载...</span>
        </div>
      </div>
    );
  }

  const submitText = registerSettings.enable_self_registration ? '登录 / 注册' : '登录';
  const submitDisabled = !phone || phone.length !== 11 || !code || code.length < 4;

  return (
    <div className={styles.page}>
      {/* 上半绿色渐变品牌区 */}
      <div className={styles.topBrand}>
        <div className={styles.logoCircle}>
          {logoUrl ? (
            <img
              src={resolveAssetUrl(logoUrl)}
              alt="宾尼小康 LOGO"
              className={styles.logoImg}
            />
          ) : (
            <span className={styles.logoFallback}>🌿</span>
          )}
        </div>
        <h1 className={styles.brandTitle}>宾尼小康</h1>
        <p className={styles.brandSubtitle}>AI 健康管家 · 您的私人健康助手</p>
      </div>

      {/* 白色卡片：上浮 -28px，圆角 24px */}
      <div className={styles.cardWrap}>
        <div className={styles.formGroup}>
          {/* 手机号输入 */}
          <label className={styles.inputBox}>
            <span className={styles.phonePrefix}>+86</span>
            <span className={styles.divider} />
            <input
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              maxLength={11}
              placeholder="请输入手机号"
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/[^\d]/g, ''))}
            />
          </label>

          {/* 验证码 + 获取验证码 */}
          <label className={styles.inputBox}>
            <input
              type="tel"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="请输入验证码"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/[^\d]/g, ''))}
            />
            <button
              type="button"
              className={styles.codeBtn}
              disabled={countdown > 0 || sending}
              onClick={sendCode}
            >
              {countdown > 0 ? `${countdown} s` : '获取验证码'}
            </button>
          </label>

          {refParam && (
            <p className={styles.referrerHint}>
              🎉 已识别邀请码：<strong>{refParam}</strong>
            </p>
          )}

          {/* 登录按钮：手机号或验证码为空时置灰 */}
          <button
            type="button"
            className={`${styles.submitBtn} ${submitDisabled ? styles.submitBtnDisabled : ''}`}
            disabled={submitDisabled || submitting}
            onClick={handleSubmit}
            aria-label={submitText}
          >
            {submitting ? '登录中...' : submitText}
          </button>

          {/* 协议勾选 */}
          <div className={styles.agreementRow}>
            <span
              className={`${styles.checkbox} ${agreed ? styles.checkboxChecked : ''}`}
              onClick={() => setAgreed(!agreed)}
              role="checkbox"
              aria-checked={agreed}
            >
              {agreed && <span className={styles.checkMark}>✓</span>}
            </span>
            <span className={styles.agreementText}>
              我已阅读并同意
              <span
                className={styles.agreementLink}
                onClick={() => handleOpenAgreement('service')}
              >
                《用户服务协议》
              </span>
              和
              <span
                className={styles.agreementLink}
                onClick={() => handleOpenAgreement('privacy')}
              >
                《隐私政策》
              </span>
            </span>
          </div>
        </div>
      </div>

      <AgreementDialog
        visible={agreementDialogVisible}
        onAgree={handleDialogAgree}
        onReject={handleDialogReject}
        onOpenAgreement={handleOpenAgreement}
      />

      <AgreementDrawer
        visible={drawerVisible}
        type={drawerType}
        onClose={() => setDrawerVisible(false)}
      />
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div
          className="min-h-screen flex items-center justify-center"
          style={{ background: 'linear-gradient(180deg, #4AD97A 0%, #0EA5E9 100%)' }}
        >
          <SpinLoading color="white" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
