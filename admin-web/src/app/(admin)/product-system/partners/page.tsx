'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Tag, message, Typography, Popconfirm,
  Switch, Drawer, Row, Col, Statistic, Card,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, EyeOutlined, CopyOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title, Paragraph, Text } = Typography;

interface Partner {
  id: number;
  name: string;
  contact: string | null;
  api_key: string;
  api_secret?: string;
  status: string;
  notes: string | null;
  created_at: string;
}

export default function PartnersPage() {
  const [items, setItems] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Partner | null>(null);
  const [secretModal, setSecretModal] = useState<{ open: boolean; key?: string; secret?: string; name?: string }>({ open: false });
  const [form] = Form.useForm();

  // 对账抽屉
  const [reconVisible, setReconVisible] = useState(false);
  const [reconLoading, setReconLoading] = useState(false);
  const [reconData, setReconData] = useState<any>(null);
  const [reconPartner, setReconPartner] = useState<Partner | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await get('/api/admin/partners');
      setItems(res?.items || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: 'active' });
    setModal(true);
  };
  const handleEdit = (r: Partner) => {
    setEditing(r);
    form.setFieldsValue(r);
    setModal(true);
  };
  const handleSubmit = async () => {
    try {
      const v = await form.validateFields();
      if (editing) {
        await put(`/api/admin/partners/${editing.id}`, v);
        message.success('更新成功');
      } else {
        const res: any = await post('/api/admin/partners', v);
        message.success('创建成功');
        if (res?.api_secret) {
          setSecretModal({ open: true, key: res.api_key, secret: res.api_secret, name: res.name });
        }
      }
      setModal(false);
      fetchData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };
  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/partners/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };
  const handleRegen = async (r: Partner) => {
    try {
      const res: any = await post(`/api/admin/partners/${r.id}/regenerate-key`);
      setSecretModal({ open: true, key: res.api_key, secret: res.api_secret, name: r.name });
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '重置失败');
    }
  };
  const openRecon = async (r: Partner) => {
    setReconPartner(r);
    setReconVisible(true);
    setReconLoading(true);
    try {
      const res: any = await get(`/api/admin/partners/${r.id}/reconciliation`);
      setReconData(res || {});
    } catch (err: any) {
      setReconData({});
      message.error(err?.response?.data?.detail || '加载对账失败');
    } finally {
      setReconLoading(false);
    }
  };

  const copyText = (txt: string) => {
    navigator.clipboard.writeText(txt).then(() => message.success('已复制'));
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '合作方名称', dataIndex: 'name', width: 180 },
    { title: '联系人', dataIndex: 'contact', width: 140, render: (v: string) => v || '-' },
    {
      title: 'API Key', dataIndex: 'api_key', width: 280,
      render: (v: string) => (
        <Space>
          <Text code>{v}</Text>
          <Button size="small" type="link" icon={<CopyOutlined />} onClick={() => copyText(v)} />
        </Space>
      ),
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag>,
    },
    { title: '备注', dataIndex: 'notes', render: (v: string) => v || '-' },
    {
      title: '操作', key: 'a', width: 320, fixed: 'right' as const,
      render: (_: any, r: Partner) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r)}>编辑</Button>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openRecon(r)}>对账</Button>
          <Popconfirm title="重置后旧 Secret 立即失效，确定？" onConfirm={() => handleRegen(r)}>
            <Button type="link" size="small" icon={<ReloadOutlined />}>重置 Key</Button>
          </Popconfirm>
          <Popconfirm title="删除该合作方？" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>合作方管理（C+ 第三方接入）</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增合作方</Button>
      </div>
      <Table columns={columns} dataSource={items} rowKey="id" loading={loading} scroll={{ x: 1200 }} />

      <Modal title={editing ? '编辑合作方' : '新增合作方'} open={modal}
        onOk={handleSubmit} onCancel={() => setModal(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item label="合作方名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="联系人/电话" name="contact"><Input /></Form.Item>
          <Form.Item label="状态" name="status" valuePropName="checked"
            getValueProps={(v) => ({ checked: v === 'active' })}
            getValueFromEvent={(c: boolean) => c ? 'active' : 'inactive'}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
          <Form.Item label="备注" name="notes"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      {/* Secret 一次性展示 */}
      <Modal title="⚠️ API 密钥（仅本次显示）" open={secretModal.open}
        onCancel={() => setSecretModal({ open: false })} footer={null} width={600}>
        <Paragraph type="warning">请立即复制 Secret 并安全保存，关闭窗口后将无法再次查看完整 Secret。</Paragraph>
        <p><b>合作方：</b>{secretModal.name}</p>
        <p><b>API Key：</b><Text code copyable>{secretModal.key}</Text></p>
        <p><b>API Secret：</b><Text code copyable>{secretModal.secret}</Text></p>
      </Modal>

      {/* 对账 */}
      <Drawer title={`对账：${reconPartner?.name || ''}`} width={760}
        open={reconVisible} onClose={() => setReconVisible(false)}>
        {reconLoading ? <p>加载中…</p> : (
          <Row gutter={16}>
            <Col span={8}><Card><Statistic title="生成兑换码总数" value={reconData?.total_codes || 0} /></Card></Col>
            <Col span={8}><Card><Statistic title="已售出" value={reconData?.sold_codes || 0} /></Card></Col>
            <Col span={8}><Card><Statistic title="已核销" value={reconData?.used_codes || 0} /></Card></Col>
            <Col span={8} style={{ marginTop: 16 }}><Card><Statistic title="作废" value={reconData?.disabled_codes || 0} /></Card></Col>
            <Col span={8} style={{ marginTop: 16 }}><Card><Statistic title="待售" value={reconData?.available_codes || 0} /></Card></Col>
            <Col span={8} style={{ marginTop: 16 }}><Card><Statistic title="批次数量" value={reconData?.batch_count || 0} /></Card></Col>
          </Row>
        )}
      </Drawer>
    </div>
  );
}
