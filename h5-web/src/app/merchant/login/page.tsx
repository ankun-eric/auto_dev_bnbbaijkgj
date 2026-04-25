'use client';

// PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）
// 商家 PC 后台登录：手机号 + 密码 + 4 位字符图形验证码
// 验证码图片 160×60，可点击刷新；提交失败后自动刷新 + 清空输入框 + 焦点回到验证码

import React, { useRef, useState } from 'react';
import { Card, Form, Input, Button, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import CaptchaImage, { type CaptchaImageRef } from '@/components/CaptchaImage';
import { saveLogin } from '../lib';

const { Title, Text } = Typography;

interface LoginFormValues {
  phone: string;
  password: string;
  captcha_code: string;
}

export default function MerchantLoginPage() {
  const [loading, setLoading] = useState(false);
  const [captchaId, setCaptchaId] = useState<string>('');
  const router = useRouter();
  const [form] = Form.useForm<LoginFormValues>();
  const captchaRef = useRef<CaptchaImageRef>(null);
  const captchaInputRef = useRef<any>(null);

  const handleCaptchaError = () => {
    captchaRef.current?.refresh();
    form.setFieldsValue({ captcha_code: '' });
    setTimeout(() => captchaInputRef.current?.focus?.(), 50);
  };

  const submit = async (values: LoginFormValues) => {
    if (!captchaId) {
      message.warning('验证码加载中，请稍后重试');
      captchaRef.current?.refresh();
      return;
    }
    setLoading(true);
    try {
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: values.password,
        captcha_id: captchaId,
        captcha_code: (values.captcha_code || '').trim().toUpperCase(),
      });
      saveLogin(res.access_token, {
        merchant_id: res.user_id,
        merchant_name: res.nickname || '商家',
        role: res.merchant_role,
        store_ids: (res.stores || []).map((s: any) => s.id),
        stores: (res.stores || []).map((s: any) => ({ id: s.id, name: s.store_name })),
      });
      message.success('登录成功');
      if (res.must_change_password) {
        router.push('/merchant/m/profile/force-change-password');
        return;
      }
      if ((res.stores || []).length <= 1) {
        router.push('/merchant/dashboard');
      } else {
        router.push('/merchant/select-store');
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let msgText = '账号或密码错误';
      if (detail && typeof detail === 'object') {
        msgText = detail.msg || msgText;
      } else if (typeof detail === 'string') {
        msgText = detail;
      }
      message.error(msgText);
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
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 6px 24px rgba(0,0,0,0.08)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ color: '#52c41a', marginBottom: 4 }}>
            商家/机构工作台
          </Title>
          <Text type="secondary">宾尼小康 · 合作机构/商家登录</Text>
        </div>
        <Form form={form} layout="vertical" onFinish={submit} autoComplete="off">
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '手机号格式错误' },
            ]}
          >
            <Input prefix={<UserOutlined />} size="large" placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} size="large" placeholder="请输入密码" />
          </Form.Item>
          <Form.Item label="图形验证码" required style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
              <Form.Item
                name="captcha_code"
                noStyle
                rules={[
                  { required: true, message: '请输入验证码' },
                  { len: 4, message: '验证码 4 位' },
                ]}
                normalize={(v) => (v || '').trim().toUpperCase().slice(0, 4)}
              >
                <Input
                  ref={captchaInputRef}
                  prefix={<SafetyOutlined />}
                  size="large"
                  placeholder="验证码"
                  maxLength={4}
                  autoComplete="off"
                  style={{ flex: 1, textTransform: 'uppercase' }}
                />
              </Form.Item>
              <CaptchaImage ref={captchaRef} mode="pc" onChange={setCaptchaId} />
            </div>
            <div style={{ textAlign: 'right', marginTop: 4 }}>
              <a
                onClick={(e) => {
                  e.preventDefault();
                  captchaRef.current?.refresh();
                  form.setFieldsValue({ captcha_code: '' });
                }}
                style={{ color: '#1890ff', fontSize: 12 }}
              >
                看不清？换一张
              </a>
            </div>
          </Form.Item>
          <Form.Item style={{ marginTop: 12 }}>
            <Button block size="large" type="primary" htmlType="submit" loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: 'center', color: '#999', fontSize: 12 }}>
          非商家账号请前往 C 端小程序使用普通功能。
        </div>
      </Card>
    </div>
  );
}
