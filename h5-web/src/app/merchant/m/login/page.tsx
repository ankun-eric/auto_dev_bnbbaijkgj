'use client';

// [PRD V1.0 §M7 + Bug 修复 V1.0 / 2026-04-25]
// 商家 H5 登录页：手机号 + 密码 + 滑块拼图验证码
// 已用 SliderCaptcha 组件替代旧字符验证码。

import React, { useState } from 'react';
import { Form, Input, Button, Toast } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import SliderCaptcha from '@/components/SliderCaptcha';
import { saveLogin } from '../mobile-lib';

export default function MerchantMobileLoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string>('');
  const [captchaResetKey, setCaptchaResetKey] = useState<number>(0);
  const [form] = Form.useForm();

  const submit = async () => {
    try {
      const values = await form.validateFields();
      if (!captchaToken) {
        Toast.show({ icon: 'fail', content: '请先完成滑块验证' });
        return;
      }
      setLoading(true);
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
        captcha_token: captchaToken,
      });

      const validRoles = ['owner', 'store_manager', 'verifier', 'finance', 'staff'];
      const merchantRole = res?.merchant_role;
      const hasMerchantIdentity = merchantRole && validRoles.includes(merchantRole);
      if (!res?.access_token || !hasMerchantIdentity) {
        Toast.show({
          icon: 'fail',
          content: '该账号不是商家账号，请使用商家账号登录，或联系管理员开通商家身份。',
        });
        setCaptchaToken('');
        setCaptchaResetKey((k) => k + 1);
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
      const detail = e?.response?.data?.detail || e?.message || '登录失败';
      Toast.show({ icon: 'fail', content: detail });
      setCaptchaToken('');
      setCaptchaResetKey((k) => k + 1);
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
          <Form.Item label="滑块验证">
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <SliderCaptcha
                key={captchaResetKey}
                apiClient={api as any}
                mode="mobile"
                onSuccess={(tok) => setCaptchaToken(tok)}
                onReset={() => setCaptchaToken('')}
              />
            </div>
          </Form.Item>
        </Form>

        <Button
          block
          color="primary"
          size="large"
          loading={loading}
          onClick={submit}
          style={{ marginTop: 20, height: 48, fontSize: 16 }}
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
