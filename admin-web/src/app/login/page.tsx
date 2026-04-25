'use client';

// PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）
// 平台管理后台登录：手机号 + 密码 + 4 位字符图形验证码
// 验证码 160×60，可点击刷新；提交失败后自动刷新并清空输入框，焦点回到验证码输入框

import React, { useRef, useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, MedicineBoxOutlined, SafetyOutlined } from '@ant-design/icons';
import { post } from '@/lib/api';
import { useRouter } from 'next/navigation';
import CaptchaImage, { type CaptchaImageRef } from '@/components/CaptchaImage';

const { Title, Text } = Typography;

interface LoginFormValues {
  phone: string;
  password: string;
  captcha_code: string;
}

export default function LoginPage() {
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

  const onFinish = async (values: LoginFormValues) => {
    if (!captchaId) {
      message.warning('验证码加载中，请稍后重试');
      captchaRef.current?.refresh();
      return;
    }
    setLoading(true);
    try {
      const res = await post('/api/admin/login', {
        phone: values.phone,
        password: values.password,
        captcha_id: captchaId,
        captcha_code: (values.captcha_code || '').trim().toUpperCase(),
      });
      if (res.token || res.access_token) {
        localStorage.setItem('admin_token', res.token || res.access_token);
        localStorage.setItem(
          'admin_user',
          JSON.stringify(res.user || { name: '管理员' })
        );
        message.success('登录成功');
        if (res.must_change_password || res.user?.must_change_password) {
          router.push('/profile/change-password?force=1');
        } else {
          router.push('/dashboard');
        }
      } else {
        handleCaptchaError();
        message.error(res.message || res.msg || '登录失败');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      // 业务码：40101/40102/40103=验证码相关；40121/40122=账号相关；40129=锁定
      let msgText = '账号或密码错误';
      if (detail && typeof detail === 'object') {
        msgText = detail.msg || msgText;
      } else if (typeof detail === 'string') {
        msgText = detail;
      }
      handleCaptchaError();
      message.error(msgText);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Card
        style={{
          width: 460,
          borderRadius: 16,
          boxShadow: '0 8px 32px rgba(82,196,26,0.12)',
          border: 'none',
        }}
        bodyStyle={{ padding: '40px 36px 32px' }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
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
          <Text type="secondary">AI健康管家 · 平台管理后台</Text>
        </div>

        <Form form={form} name="login" onFinish={onFinish} size="large" autoComplete="off">
          <Form.Item
            name="phone"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 8 }}>
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
                  placeholder="验证码"
                  maxLength={4}
                  autoComplete="off"
                  style={{ flex: 1, textTransform: 'uppercase' }}
                />
              </Form.Item>
              <CaptchaImage ref={captchaRef} onChange={setCaptchaId} />
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
          <Form.Item style={{ marginBottom: 0, marginTop: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, borderRadius: 8, fontSize: 16 }}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
