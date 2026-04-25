'use client';

import React, { useEffect, useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, MedicineBoxOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { post, get } from '@/lib/api';
import { useRouter } from 'next/navigation';

const { Title, Text } = Typography;

interface CaptchaState {
  captcha_id: string;
  image_base64: string;
}

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [captcha, setCaptcha] = useState<CaptchaState | null>(null);
  const [captchaLoading, setCaptchaLoading] = useState(false);
  const router = useRouter();
  const [form] = Form.useForm();

  const refreshCaptcha = async () => {
    setCaptchaLoading(true);
    try {
      const res = await get<CaptchaState>('/api/captcha/image');
      setCaptcha(res);
      form.setFieldValue('captcha_code', '');
    } catch (err) {
      message.error('验证码加载失败，请稍后重试');
    } finally {
      setCaptchaLoading(false);
    }
  };

  useEffect(() => {
    refreshCaptcha();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onFinish = async (values: { phone: string; password: string; captcha_code: string }) => {
    if (!captcha) {
      message.warning('验证码加载中，请稍候');
      return;
    }
    setLoading(true);
    try {
      const res = await post('/api/admin/login', {
        phone: values.phone,
        password: values.password,
        captcha_id: captcha.captcha_id,
        captcha_code: values.captcha_code,
      });
      if (res.code === 0 || res.token) {
        localStorage.setItem('admin_token', res.token || res.data?.token);
        localStorage.setItem(
          'admin_user',
          JSON.stringify(res.user || res.data?.user || { name: '管理员' })
        );
        message.success('登录成功');
        if (res.must_change_password || res.user?.must_change_password) {
          router.push('/profile/change-password?force=1');
        } else {
          router.push('/dashboard');
        }
      } else {
        await refreshCaptcha();
        message.error(res.message || '登录失败');
      }
    } catch (err: any) {
      await refreshCaptcha();
      message.error(err?.response?.data?.detail || err?.response?.data?.message || '账号、密码或验证码错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Card
        style={{
          width: 420,
          borderRadius: 16,
          boxShadow: '0 8px 32px rgba(82,196,26,0.12)',
          border: 'none',
        }}
        bodyStyle={{ padding: '48px 40px 36px' }}
      >
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
          >
            <MedicineBoxOutlined style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <Title level={3} style={{ marginBottom: 4, color: '#333' }}>
            宾尼小康
          </Title>
          <Text type="secondary">AI健康管家 · 管理后台</Text>
        </div>

        <Form form={form} name="login" onFinish={onFinish} size="large" autoComplete="off">
          <Form.Item name="phone" rules={[{ required: true, message: '请输入手机号' }, { pattern: /^1\d{10}$/, message: '请输入正确的手机号' }]}>
            <Input prefix={<UserOutlined />} placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>
          <Form.Item required style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <Form.Item name="captcha_code" noStyle rules={[{ required: true, message: '请输入验证码' }, { len: 4, message: '验证码为 4 位' }]}>
                <Input
                  prefix={<SafetyCertificateOutlined />}
                  placeholder="请输入验证码"
                  maxLength={4}
                  style={{ flex: 1 }}
                />
              </Form.Item>
              <div
                onClick={refreshCaptcha}
                title="点击刷新验证码"
                style={{
                  width: 130,
                  height: 44,
                  cursor: 'pointer',
                  border: '1px solid #d9d9d9',
                  borderRadius: 8,
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: '#fafafa',
                }}
              >
                {captcha?.image_base64 ? (
                  <img
                    src={captcha.image_base64}
                    alt="验证码"
                    style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: captchaLoading ? 0.5 : 1 }}
                  />
                ) : (
                  <span style={{ color: '#999', fontSize: 12 }}>加载中...</span>
                )}
              </div>
            </div>
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block style={{ height: 44, borderRadius: 8, fontSize: 16 }}>
              登 录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
