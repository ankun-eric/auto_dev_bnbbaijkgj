'use client';

// [2026-04-24] 商家端移动端 H5 登录页 - PRD §4.1
// D4 三种登录方式：账号密码、短信验证码、微信授权（微信内浏览器才显示）

import React, { useState } from 'react';
import { Form, Input, Button, Tabs, Toast, Space } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { saveLogin, isWechatBrowser } from '../mobile-lib';

export default function MerchantMobileLoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'password' | 'sms'>('password');
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const submit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const res: any = await api.post('/api/merchant/auth/login', {
        phone: values.phone,
        password: mode === 'password' ? values.password : undefined,
        sms_code: mode === 'sms' ? values.sms_code : undefined,
      });
      saveLogin(res.access_token, {
        merchant_id: res.user_id,
        merchant_name: res.nickname || '商家',
        role: res.merchant_role,
        store_ids: (res.stores || []).map((s: any) => s.id),
        stores: (res.stores || []).map((s: any) => ({ id: s.id, name: s.store_name })),
      });
      Toast.show({ icon: 'success', content: '登录成功' });
      if ((res.stores || []).length <= 1) {
        router.push('/merchant/m/dashboard');
      } else {
        router.push('/merchant/m/select-store');
      }
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验错误
      const detail = e?.response?.data?.detail || e?.message || '登录失败';
      Toast.show({ icon: 'fail', content: detail });
    } finally {
      setLoading(false);
    }
  };

  const sendSms = async () => {
    Toast.show({ content: '测试环境：万能验证码 8888' });
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
        <Tabs
          activeKey={mode}
          onChange={(k) => setMode(k as any)}
          style={{ marginBottom: 8 }}
        >
          <Tabs.Tab title="账号密码" key="password" />
          <Tabs.Tab title="短信验证码" key="sms" />
        </Tabs>

        <Form
          form={form}
          layout="vertical"
          mode="card"
          style={{ background: 'transparent' }}
        >
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
          {mode === 'password' ? (
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input placeholder="请输入密码" type="password" clearable />
            </Form.Item>
          ) : (
            <Form.Item
              name="sms_code"
              label="验证码"
              rules={[{ required: true, message: '请输入验证码' }]}
              extra={
                <Button size="mini" color="primary" fill="none" onClick={sendSms}>
                  获取验证码
                </Button>
              }
            >
              <Input placeholder="测试环境：8888" clearable />
            </Form.Item>
          )}
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

        {isWechatBrowser() && (
          <Button
            block
            color="success"
            fill="outline"
            size="large"
            style={{ marginTop: 12, height: 48 }}
            onClick={() => Toast.show({ content: '微信一键登录暂未开放，请使用账号密码或验证码登录' })}
          >
            微信一键登录
          </Button>
        )}

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
