'use client';

import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Typography, Alert } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { put } from '@/lib/api';
import { useRouter, useSearchParams } from 'next/navigation';

const { Title } = Typography;

const STRONG_REGEX = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

export default function AdminChangePasswordPage() {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const router = useRouter();
  const params = useSearchParams();
  const force = params?.get('force') === '1';

  useEffect(() => {
    if (force) {
      message.warning('您的密码需要修改后方可继续使用系统');
    }
  }, [force]);

  const onFinish = async (values: { old_password: string; new_password: string; confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致');
      return;
    }
    if (!STRONG_REGEX.test(values.new_password)) {
      message.error('新密码至少 8 位，且需包含字母和数字');
      return;
    }
    setLoading(true);
    try {
      await put('/api/admin/password', values);
      message.success('密码修改成功，请重新登录');
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      setTimeout(() => router.push('/login'), 600);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '修改失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        修改密码
      </Title>
      <Card style={{ maxWidth: 560 }}>
        {force && (
          <Alert
            type="warning"
            message="为账号安全，您必须先修改密码"
            description="您的密码已被超级管理员重置或为首次登录，请立即修改后再继续使用。"
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}
        <Form form={form} layout="vertical" onFinish={onFinish} autoComplete="off">
          <Form.Item
            name="old_password"
            label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入原密码" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { pattern: STRONG_REGEX, message: '新密码至少 8 位，且需包含字母和数字' },
            ]}
            hasFeedback
          >
            <Input.Password prefix={<LockOutlined />} placeholder="至少 8 位，必须含字母和数字" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) return Promise.resolve();
                  return Promise.reject(new Error('两次输入的新密码不一致'));
                },
              }),
            ]}
            hasFeedback
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入新密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              提交修改
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
