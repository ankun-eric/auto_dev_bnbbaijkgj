'use client';

// PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）
// 商家 H5 后台登录：手机号 + 密码 + 4 位字符图形验证码（移动端自适应：屏宽 40%）

import React, { useRef, useState } from 'react';
import { Form, Input, Button, Toast } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import CaptchaImage, { type CaptchaImageRef } from '@/components/CaptchaImage';
import { saveLogin } from '../mobile-lib';

interface LoginFormValues {
  phone: string;
  password: string;
  captcha_code: string;
}

export default function MerchantMobileLoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [captchaId, setCaptchaId] = useState<string>('');
  const [form] = Form.useForm<LoginFormValues>();
  const captchaRef = useRef<CaptchaImageRef>(null);
  const captchaInputRef = useRef<any>(null);

  const handleCaptchaError = () => {
    captchaRef.current?.refresh();
    form.setFieldValue('captcha_code', '');
    setTimeout(() => captchaInputRef.current?.focus?.(), 50);
  };

  const submit = async () => {
    try {
      const values = (await form.validateFields()) as LoginFormValues;
      if (!captchaId) {
        Toast.show({ icon: 'fail', content: '验证码加载中，请稍后重试' });
        captchaRef.current?.refresh();
        return;
      }
      setLoading(true);
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
        captcha_id: captchaId,
        captcha_code: (values.captcha_code || '').trim().toUpperCase(),
      });

      const validRoles = ['owner', 'store_manager', 'verifier', 'finance', 'staff'];
      const merchantRole = res?.merchant_role;
      const hasMerchantIdentity = merchantRole && validRoles.includes(merchantRole);
      if (!res?.access_token || !hasMerchantIdentity) {
        Toast.show({
          icon: 'fail',
          content: '该账号不是商家账号，请使用商家账号登录，或联系管理员开通商家身份。',
        });
        handleCaptchaError();
        return;
      }

      saveLogin(res.access_token, {
        merchant_id: res.user_id,
        merchant_name: res.nickname || '商家',
        role: res.merchant_role,
        store_ids: (res.stores || []).map((s: any) => s.id),
        stores: (res.stores || []).map((s: any) => ({ id: s.id, name: s.store_name })),
      });
      Toast.show({ icon: 'success', content: '登录成功' });
      if (res.must_change_password) {
        router.push('/merchant/m/profile/force-change-password');
        return;
      }
      if ((res.stores || []).length <= 1) {
        router.push('/merchant/m/dashboard');
      } else {
        router.push('/merchant/m/select-store');
      }
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail;
      let msgText = '账号或密码错误';
      if (detail && typeof detail === 'object') {
        msgText = detail.msg || msgText;
      } else if (typeof detail === 'string') {
        msgText = detail;
      }
      Toast.show({ icon: 'fail', content: msgText });
      handleCaptchaError();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #e6fffb 0%, #f6ffed 100%)',
        padding: '48px 20px 20px',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div style={{ fontSize: 28, fontWeight: 600, color: '#52c41a', marginBottom: 6 }}>
          商家工作台
        </div>
        <div style={{ color: '#999', fontSize: 13 }}>宾尼小康 · 合作机构/商家登录</div>
      </div>

      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: 20,
          boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
        }}
      >
        <Form form={form} layout="vertical" mode="card" style={{ background: 'transparent' }}>
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '手机号格式错误' },
            ]}
          >
            <Input placeholder="请输入手机号" clearable type="tel" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input placeholder="请输入密码" type="password" clearable />
          </Form.Item>
          <Form.Item
            name="captcha_code"
            label="图形验证码"
            rules={[
              { required: true, message: '请输入验证码' },
              { len: 4, message: '验证码 4 位' },
            ]}
          >
            <Input
              ref={captchaInputRef}
              placeholder="请输入图中字符"
              clearable
              maxLength={4}
              style={{ textTransform: 'uppercase' }}
              onChange={(v) => {
                const up = (v || '').trim().toUpperCase().slice(0, 4);
                if (up !== v) form.setFieldValue('captcha_code', up);
              }}
            />
          </Form.Item>
        </Form>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            margin: '4px 12px 12px',
          }}
        >
          <CaptchaImage ref={captchaRef} mode="mobile" onChange={setCaptchaId} />
          <a
            onClick={(e) => {
              e.preventDefault();
              captchaRef.current?.refresh();
              form.setFieldValue('captcha_code', '');
            }}
            style={{ color: '#1890ff', fontSize: 14 }}
          >
            看不清？换一张
          </a>
        </div>

        <Button
          block
          color="primary"
          size="large"
          loading={loading}
          onClick={submit}
          style={{ marginTop: 8, height: 48, fontSize: 16 }}
        >
          登录
        </Button>

        <div style={{ textAlign: 'center', color: '#999', fontSize: 12, marginTop: 20 }}>
          非商家账号请前往 C 端小程序使用。
        </div>
      </div>

      <div style={{ textAlign: 'center', color: '#bbb', fontSize: 11, marginTop: 24 }}>
        v1.0 · 商家端移动版
      </div>
    </div>
  );
}
