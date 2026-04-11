'use client';

import React, { useState, useCallback, useRef } from 'react';
import { Form, Input, Select, Button, Card, Typography, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface UserOption {
  label: string;
  value: number;
}

export default function SendMessagePage() {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [userOptions, setUserOptions] = useState<UserOption[]>([]);
  const [userSearching, setUserSearching] = useState(false);
  const fetchRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const searchUsers = useCallback((keyword: string) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!keyword || keyword.length < 1) {
      setUserOptions([]);
      return;
    }
    timerRef.current = setTimeout(async () => {
      fetchRef.current += 1;
      const fetchId = fetchRef.current;
      setUserSearching(true);
      try {
        const res = await get<{
          items?: Array<Record<string, unknown>>;
          list?: Array<Record<string, unknown>>;
        }>('/api/admin/users', { keyword, page: 1, page_size: 20 });
        if (fetchId !== fetchRef.current) return;
        const items = res.items ?? res.list ?? [];
        setUserOptions(
          items.map((u) => ({
            label: `${u.nickname || u.name || '未知用户'} (${u.phone || '-'})`,
            value: Number(u.id),
          }))
        );
      } catch {
        if (fetchId === fetchRef.current) setUserOptions([]);
      } finally {
        if (fetchId === fetchRef.current) setUserSearching(false);
      }
    }, 400);
  }, []);

  const handleSubmit = async (values: {
    recipient_user_ids: number[];
    message_type: string;
    title: string;
    content: string;
  }) => {
    setSubmitting(true);
    try {
      await post('/api/admin/messages', {
        recipient_user_ids: values.recipient_user_ids,
        message_type: values.message_type,
        title: values.title,
        content: values.content,
      });
      message.success('消息发送成功');
      form.resetFields();
      setUserOptions([]);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string; detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.response?.data?.message || err?.message || '发送失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>发送系统消息</Title>

      <Card bordered={false} style={{ maxWidth: 720 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          requiredMark="optional"
        >
          <Form.Item
            label="接收对象"
            name="recipient_user_ids"
            rules={[{ required: true, message: '请选择接收用户' }]}
          >
            <Select
              mode="multiple"
              placeholder="搜索用户姓名或手机号"
              filterOption={false}
              showSearch
              onSearch={searchUsers}
              loading={userSearching}
              options={userOptions}
              notFoundContent={userSearching ? '搜索中...' : '请输入关键词搜索'}
              allowClear
            />
          </Form.Item>

          <Form.Item
            label="消息类型"
            name="message_type"
            rules={[{ required: true, message: '请选择消息类型' }]}
          >
            <Select
              placeholder="请选择消息类型"
              options={[
                { label: '系统通知', value: 'system_notice' },
                { label: '运营活动', value: 'operation_activity' },
                { label: '维护通知', value: 'maintenance' },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="消息标题"
            name="title"
            rules={[{ required: true, message: '请输入消息标题' }]}
          >
            <Input placeholder="请输入消息标题" maxLength={100} showCount />
          </Form.Item>

          <Form.Item
            label="消息内容"
            name="content"
            rules={[{ required: true, message: '请输入消息内容' }]}
          >
            <TextArea
              placeholder="请输入消息内容"
              rows={6}
              maxLength={2000}
              showCount
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              icon={<SendOutlined />}
              size="large"
            >
              发送消息
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
