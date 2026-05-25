'use client';

/**
 * [守护人体系 PRD v1.2 §12.3] 紧急呼叫触发源管理
 * 初始 4 种内置（健康数据异常 / 烟雾报警器 / 水位报警器 / 紧急呼叫器），可启停但不可删；
 * 运营可新增触发源。
 */
import React, { useEffect, useState } from 'react';
import {
  Table, Tag, Input, Space, Card, Typography, message,
  Button, Modal, Form, Switch, InputNumber, Popconfirm,
} from 'antd';
import { get, post, put, del } from '@/lib/api';

const { Title, Paragraph } = Typography;

interface EmergencySource {
  id: number;
  source_code: string;
  source_name: string;
  description?: string;
  is_enabled: boolean;
  is_builtin: boolean;
  trigger_condition?: string;
  applicable_device_type?: string;
  sort_order: number;
  created_at?: string;
}

export default function EmergencySourcesPage() {
  const [data, setData] = useState<EmergencySource[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<EmergencySource | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res: any = await get('/api/admin/emergency-sources');
      setData(res?.items || res?.data?.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const openAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_enabled: true, sort_order: 100 });
    setModalOpen(true);
  };

  const openEdit = (rec: EmergencySource) => {
    setEditing(rec);
    form.setFieldsValue(rec);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const vals = await form.validateFields();
      if (editing) {
        await put(`/api/admin/emergency-sources/${editing.id}`, vals);
        message.success('已更新');
      } else {
        await post('/api/admin/emergency-sources', vals);
        message.success('已新增');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const handleToggle = async (rec: EmergencySource, checked: boolean) => {
    try {
      await put(`/api/admin/emergency-sources/${rec.id}`, { is_enabled: checked });
      message.success('已更新');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (rec: EmergencySource) => {
    try {
      await del(`/api/admin/emergency-sources/${rec.id}`);
      message.success('已删除');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '触发源编码', dataIndex: 'source_code', width: 180,
      render: (v: string, rec: EmergencySource) => (
        <span>{v}{rec.is_builtin && <Tag color='blue' style={{ marginLeft: 8 }}>内置</Tag>}</span>
      ) },
    { title: '名称', dataIndex: 'source_name', width: 160 },
    { title: '描述', dataIndex: 'description' },
    { title: '适用设备', dataIndex: 'applicable_device_type', width: 120 },
    { title: '启用', dataIndex: 'is_enabled', width: 80,
      render: (v: boolean, rec: EmergencySource) =>
        <Switch checked={v} onChange={(c) => handleToggle(rec, c)} /> },
    { title: '排序', dataIndex: 'sort_order', width: 80 },
    {
      title: '操作', width: 160, fixed: 'right' as const,
      render: (_: any, rec: EmergencySource) => (
        <Space>
          <Button size='small' onClick={() => openEdit(rec)}>编辑</Button>
          {!rec.is_builtin && (
            <Popconfirm title='确认删除该触发源？' onConfirm={() => handleDelete(rec)}>
              <Button size='small' danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Title level={3}>紧急呼叫触发源管理</Title>
        <Paragraph type='secondary'>
          管理紧急 AI 呼叫的触发源。初始内置 4 种（健康数据异常 / 烟雾报警器 / 水位报警器 / 紧急呼叫器），
          仅可启停不可删除；运营可自由扩展新触发源（如燃气报警器、跌倒检测手环等）。
        </Paragraph>
        <Space style={{ marginBottom: 16 }}>
          <Button type='primary' onClick={openAdd}>新增触发源</Button>
          <Button onClick={fetchData}>刷新</Button>
        </Space>

        <Table
          rowKey='id'
          dataSource={data}
          columns={columns}
          loading={loading}
          pagination={false}
          scroll={{ x: 1100 }}
        />
      </Card>

      <Modal
        title={editing ? '编辑触发源' : '新增触发源'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        destroyOnClose
        width={600}
      >
        <Form form={form} layout='vertical'>
          <Form.Item
            label='触发源编码'
            name='source_code'
            rules={[{ required: true, message: '请输入编码' }]}
            extra='唯一标识，建议小写英文+下划线，如 gas_alarm'
          >
            <Input disabled={!!editing?.is_builtin} placeholder='如 gas_alarm' />
          </Form.Item>
          <Form.Item label='触发源名称' name='source_name' rules={[{ required: true }]}>
            <Input disabled={!!editing?.is_builtin} placeholder='如 燃气报警器' />
          </Form.Item>
          <Form.Item label='描述' name='description'>
            <Input.TextArea rows={2} disabled={!!editing?.is_builtin} placeholder='触发源详细说明' />
          </Form.Item>
          <Form.Item label='适用设备类型' name='applicable_device_type'>
            <Input disabled={!!editing?.is_builtin} placeholder='如 wifi-gas-sensor' />
          </Form.Item>
          <Form.Item label='触发条件配置（JSON）' name='trigger_condition'>
            <Input.TextArea rows={2} disabled={!!editing?.is_builtin}
              placeholder='可选，JSON 格式描述阈值等' />
          </Form.Item>
          <Form.Item label='排序' name='sort_order' initialValue={100}>
            <InputNumber min={0} max={9999} />
          </Form.Item>
          <Form.Item label='启用' name='is_enabled' valuePropName='checked'>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
