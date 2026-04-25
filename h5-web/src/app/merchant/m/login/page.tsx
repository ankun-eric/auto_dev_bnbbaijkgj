'use client';

// [PRD V1.0 §M7] 商家 H5 登录页：手机号 + 密码 + 图形验证码
// 已删除「短信验证码」Tab、「忘记密码」入口和「微信一键登录」入口。
// 登录成功若返回 must_change_password=true，跳转 /merchant/m/profile/force-change-password。

import React, { useEffect, useState } from 'react';
import { Form, Input, Button, Toast } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { fetchCaptchaImage } from '@/lib/captcha';
import { saveLogin } from '../mobile-lib';

export default function MerchantMobileLoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [captchaId, setCaptchaId] = useState('');
  const [captchaImg, setCaptchaImg] = useState('');
  const [form] = Form.useForm();

  const refreshCaptcha = async () => {
    try {
      const data = await fetchCaptchaImage();
      setCaptchaId(data.captcha_id);
      setCaptchaImg(data.image_base64);
    } catch {
      Toast.show({ icon: 'fail', content: '验证码加载失败' });
    }
  };

  useEffect(() => {
    refreshCaptcha();
  }, []);

  const submit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
        captcha_id: captchaId,
        captcha_code: values.captcha_code,
      });

      const validRoles = ['owner', 'store_manager', 'verifier', 'finance', 'staff'];
      const merchantRole = res?.merchant_role;
      const hasMerchantIdentity = merchantRole && validRoles.includes(merchantRole);
      if (!res?.access_token || !hasMerchantIdentity) {
        Toast.show({
          icon: 'fail',
          content: '该账号不是商家账号，请使用商家账号登录，或联系管理员开通商家身份。',
        });
        refreshCaptcha();
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
      refreshCaptcha();
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
            rules={[{ required: true, message: '请输入图形验证码' }]}
            extra={
              <div
                onClick={refreshCaptcha}
                style={{
                  width: 110,
                  height: 36,
                  borderRadius: 6,
                  border: '1px solid #eee',
                  overflow: 'hidden',
                  cursor: 'pointer',
                  background: '#fafafa',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {captchaImg ? (
                  <img
                    src={captchaImg}
                    alt="验证码"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <span style={{ fontSize: 12, color: '#999' }}>加载中</span>
                )}
              </div>
            }
          >
            <Input placeholder="请输入验证码" clearable maxLength={6} />
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
