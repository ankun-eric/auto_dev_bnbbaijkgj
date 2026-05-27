'use client';

/**
 * [PRD-HOME-SAFETY-V1 2026-05-27] 智能硬件绑定 · 居家安全设备 v1.0
 * 管理后台 · 紧急呼叫触发源管理 - 居家安全设备
 *
 * 4 个 Tab：
 *  1. 设备类型字典（只读展示）
 *  2. 设备绑定流水
 *  3. 报警记录流水
 *  4. 回调地址配置（保存 + 连通性测试 + 推送上游）
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Tabs,
  Table,
  Tag,
  Button,
  Form,
  Input,
  message,
  Space,
  Card,
  Typography,
  Descriptions,
} from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { get, put, post } from '@/lib/api';
import { formatDateTime } from '@/lib/datetime';

const { Title, Paragraph, Text } = Typography;

const DEVICE_COLOR: Record<number, string> = { 1: 'red', 2: 'orange', 7: 'gold' };

function deviceTag(t: number, label?: string) {
  return <Tag color={DEVICE_COLOR[t] || 'default'}>{label || `type=${t}`}</Tag>;
}

function StatusYN({ v }: { v: number }) {
  if (v === 1) return <Tag color="success">成功</Tag>;
  if (v === 2) return <Tag color="error">失败</Tag>;
  if (v === 3) return <Tag color="default">已发起待回调</Tag>;
  return <Tag color="default">未发</Tag>;
}

function DictTab() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await get('/api/admin/home_safety/dict/device_types');
      setItems(data.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card>
      <Title level={4}>设备类型字典</Title>
      <Paragraph type="secondary">三类居家安全设备的名称、颜色等级、通知文案与 AI 话术模板（本期为只读展示）。</Paragraph>
      <Table
        rowKey="device_type"
        loading={loading}
        dataSource={items}
        pagination={false}
        columns={[
          {
            title: '上游类型码',
            dataIndex: 'device_type',
            width: 100,
            render: (v: number, r: any) => deviceTag(v, `type=${v}`),
          },
          { title: '平台设备名', dataIndex: 'device_type_label', width: 180 },
          {
            title: '颜色等级',
            dataIndex: 'color',
            width: 100,
            render: (v: string) => <Tag color={v === 'red' ? 'red' : v === 'orange' ? 'orange' : 'gold'}>{v}</Tag>,
          },
          { title: '通知标题模板', dataIndex: 'title_template' },
          { title: 'AI 话术模板', dataIndex: 'ai_script_template' },
          {
            title: '启用',
            dataIndex: 'enabled',
            width: 80,
            render: (v: boolean) => (v ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>),
          },
        ]}
      />
    </Card>
  );
}

function BindingsTab() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await get('/api/admin/home_safety/bindings');
      setItems(data.items || []);
    } catch (e: any) {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card
      title="设备绑定流水"
      extra={<Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>}
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1200 }}
        columns={[
          { title: '流水 ID', dataIndex: 'id', width: 80 },
          {
            title: '设备类型',
            dataIndex: 'device_type',
            width: 160,
            render: (v: number, r: any) => deviceTag(v, r.device_type_label),
          },
          { title: '网关 SN', dataIndex: 'gateway_sn', width: 140 },
          { title: '设备 SN', dataIndex: 'device_sn', width: 120 },
          { title: '绑定用户', dataIndex: 'user_id', width: 100 },
          {
            title: '操作类型',
            dataIndex: 'status',
            width: 100,
            render: (v: number, r: any) =>
              v === 1 ? <Tag color="success">绑定</Tag> : <Tag color="default">解绑</Tag>,
          },
          {
            title: '校验结果',
            dataIndex: 'verify_status',
            width: 110,
            render: (v: number) =>
              v === 1 ? <Tag color="success">通过</Tag> : v === 2 ? <Tag color="error">未通过</Tag> : <Tag>未校验</Tag>,
          },
          { title: '绑定时间', dataIndex: 'bound_at', width: 180, render: (v: string) => formatDateTime(v) },
          { title: '解绑时间', dataIndex: 'unbound_at', width: 180, render: (v: string) => formatDateTime(v) },
        ]}
      />
    </Card>
  );
}

function AlarmsTab() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await get('/api/admin/home_safety/alarms');
      setItems(data.items || []);
    } catch (e: any) {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card
      title="报警记录流水"
      extra={<Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>}
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1600 }}
        columns={[
          { title: '报警 ID', dataIndex: 'id', width: 80 },
          { title: '设备 SN', dataIndex: 'device_sn', width: 120 },
          {
            title: '设备类型',
            dataIndex: 'device_type',
            width: 160,
            render: (v: number, r: any) => deviceTag(v, r.device_type_label),
          },
          { title: '上报时间', dataIndex: 'alarm_at', width: 180, render: (v: string) => formatDateTime(v) },
          { title: '接收时间', dataIndex: 'received_at', width: 180, render: (v: string) => formatDateTime(v) },
          { title: '关联用户', dataIndex: 'user_id', width: 100 },
          {
            title: '站内',
            dataIndex: 'notify_inapp',
            width: 80,
            render: (v: number) => <StatusYN v={v} />,
          },
          {
            title: '小程序',
            dataIndex: 'notify_mp',
            width: 80,
            render: (v: number) => <StatusYN v={v} />,
          },
          {
            title: '短信',
            dataIndex: 'notify_sms',
            width: 80,
            render: (v: number) => <StatusYN v={v} />,
          },
          {
            title: 'AI 外呼',
            dataIndex: 'notify_ai_call',
            width: 130,
            render: (v: number) => (
              <Tag color={v === 2 ? 'green' : v === 3 ? 'red' : v === 1 ? 'blue' : 'default'}>
                {v === 0 ? '未发起' : v === 1 ? '已发起待回调' : v === 2 ? '成功' : '失败'}
              </Tag>
            ),
          },
          {
            title: '合并次数',
            dataIndex: 'dedupe_count',
            width: 100,
            render: (v: number) => (v > 1 ? <Tag color="purple">合并 {v} 次</Tag> : <span>1</span>),
          },
          {
            title: '处置',
            dataIndex: 'handle_status',
            width: 100,
            render: (v: number, r: any) =>
              v === 1 ? <Tag color="success">已处置</Tag> : r.read_status ? <Tag>已读</Tag> : <Tag color="warning">未读</Tag>,
          },
          { title: '处置备注', dataIndex: 'handle_note', width: 200, ellipsis: true },
        ]}
      />
    </Card>
  );
}

function CallbackConfigTab() {
  const [form] = Form.useForm();
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    try {
      const d: any = await get('/api/admin/home_safety/callback_config');
      setData(d);
      form.setFieldsValue({
        org_id: d.org_id || '',
        callback_url: d.callback_url || '',
        auth_token: d.auth_token || '',
        upstream_base_url: d.upstream_base_url || '',
      });
    } catch (e: any) {
      message.error('加载失败');
    }
  }, [form]);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    const values = await form.validateFields();
    setLoading(true);
    try {
      await put('/api/admin/home_safety/callback_config', values);
      message.success('保存成功');
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setLoading(false);
    }
  };

  const onTest = async () => {
    setTesting(true);
    try {
      const r: any = await post('/api/admin/home_safety/callback_config/test', {});
      message.success(r.result || '测试成功');
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '测试失败');
    } finally {
      setTesting(false);
    }
  };

  const onPush = async () => {
    try {
      await post('/api/admin/home_safety/callback_config/push_upstream', {});
      message.success('已推送给上游');
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '推送失败');
    }
  };

  return (
    <Card title="回调地址配置（全平台 1 套）">
      <Form layout="vertical" form={form} style={{ maxWidth: 600 }}>
        <Form.Item label="机构 ID（= 平台 ID）" name="org_id">
          <Input placeholder="例如：platform" />
        </Form.Item>
        <Form.Item label="回调地址 URL（我方对外暴露）" name="callback_url">
          <Input placeholder="https://newbb.test.bangbangvip.com/.../callback/home_safety/alarm" />
        </Form.Item>
        <Form.Item label="鉴权 Token" name="auth_token">
          <Input placeholder="bearer token" />
        </Form.Item>
        <Form.Item label="上游基础 URL" name="upstream_base_url">
          <Input placeholder="https://upstream.example.com" />
        </Form.Item>
        <Space>
          <Button type="primary" loading={loading} onClick={onSave}>
            保存
          </Button>
          <Button onClick={onTest} loading={testing}>
            测试连通性
          </Button>
          <Button onClick={onPush}>把配置推送给上游</Button>
        </Space>
      </Form>
      <Descriptions style={{ marginTop: 24 }} bordered column={1} size="small">
        <Descriptions.Item label="上次保存时间">{formatDateTime(data.updated_at)}</Descriptions.Item>
        <Descriptions.Item label="上次推送上游时间">{formatDateTime(data.last_pushed_at)}</Descriptions.Item>
        <Descriptions.Item label="上次测试时间">{formatDateTime(data.last_test_at)}</Descriptions.Item>
        <Descriptions.Item label="上次测试结果">{data.last_test_result || '-'}</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}

export default function HomeSafetyPage() {
  return (
    <div style={{ padding: 16 }}>
      <Title level={3} style={{ marginBottom: 16 }}>
        居家安全设备管理（紧急呼叫器 / 烟雾报警器 / 水位报警器）
      </Title>
      <Tabs
        items={[
          { key: 'dict', label: '设备类型字典', children: <DictTab /> },
          { key: 'bindings', label: '设备绑定流水', children: <BindingsTab /> },
          { key: 'alarms', label: '报警记录流水', children: <AlarmsTab /> },
          { key: 'cb', label: '回调地址配置', children: <CallbackConfigTab /> },
        ]}
      />
    </div>
  );
}
