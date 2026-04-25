'use client';

// [Bug 修复 V1.0 / 2026-04-25] admin 登录页：手机号 + 密码 + 滑块拼图验证码
// 旧字符验证码已替换为滑块拼图（SliderCaptcha 组件 + captcha_token）。

import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import { post } from '@/lib/api';
import { sliderApiClient } from '@/lib/captcha';
import { useRouter } from 'next/navigation';
import SliderCaptcha from '@/components/SliderCaptcha';

const { Title, Text } = Typography;

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string>('');
  const [captchaResetKey, setCaptchaResetKey] = useState<number>(0);
  const router = useRouter();
  const [form] = Form.useForm();

  const onFinish = async (values: { phone: string; password: string }) => {
    if (!captchaToken) {
      message.warning('请先完成滑块验证');
      return;
    }
    setLoading(true);
    try {
      const res = await post('/api/admin/login', {
        phone: values.phone,
        password: values.password,
        captcha_token: captchaToken,
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
        setCaptchaToken('');
        setCaptchaResetKey((k) => k + 1);
        message.error(res.message || '登录失败');
      }
    } catch (err: any) {
      setCaptchaToken('');
      setCaptchaResetKey((k) => k + 1);
      message.error(
        err?.response?.data?.detail || err?.response?.data?.message || '账号、密码或验证码错误'
      );
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
          <Text type="secondary">AI健康管家 · 管理后台</Text>
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
          <Form.Item required style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <SliderCaptcha
                key={captchaResetKey}
                apiClient={sliderApiClient}
                mode="pc"
                onSuccess={(tok) => setCaptchaToken(tok)}
                onReset={() => setCaptchaToken('')}
              />
            </div>
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
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
