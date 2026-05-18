'use client';

/**
 * [PRD-FAMILY-GUARDIAN-V1] 异常阈值配置 CRUD
 * 全局生效；二期切人群分级时启用 gender / age 字段。
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Collapse,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title, Text } = Typography;
const { Panel } = Collapse;

interface ThresholdRow {
  id: number;
  metric_code: string;
  metric_name: string;
  severity: string;
  lower_bound?: number | null;
  upper_bound?: number | null;
  unit?: string;
  is_active: boolean;
}

const SEVERITY_OPTIONS = [
  { value: 'critical', label: '危急', color: 'red' },
  { value: 'warning', label: '警告', color: 'orange' },
  { value: 'info', label: '提示', color: 'blue' },
];

export default function AbnormalThresholdsPage() {
  const [data, setData] = useState<ThresholdRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ThresholdRow | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items: ThresholdRow[] }>(
        '/api/admin/abnormal-thresholds',
        keyword ? { keyword } : undefined,
      );
      setData(res.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ severity: 'warning', is_active: true });
    setModalOpen(true);
  };

  const openEdit = (row: ThresholdRow) => {
    setEditing(row);
    form.setFieldsValue(row);
    setModalOpen(true);
  };

  const onSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await put(`/api/admin/abnormal-thresholds/${editing.id}`, values);
        message.success('已更新');
      } else {
        await post('/api/admin/abnormal-thresholds', values);
        message.success('已创建');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const onDelete = async (row: ThresholdRow) => {
    Modal.confirm({
      title: '删除阈值',
      content: `确定删除「${row.metric_name}」吗？`,
      onOk: async () => {
        try {
          await del(`/api/admin/abnormal-thresholds/${row.id}`);
          message.success('已删除');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const columns = [
    { title: '指标编码', dataIndex: 'metric_code', key: 'metric_code', width: 140 },
    { title: '名称', dataIndex: 'metric_name', key: 'metric_name', width: 200 },
    {
      title: '严重程度',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (v: string) => {
        const opt = SEVERITY_OPTIONS.find((x) => x.value === v);
        return opt ? <Tag color={opt.color}>{opt.label}</Tag> : v;
      },
    },
    { title: '下限', dataIndex: 'lower_bound', key: 'lower_bound', width: 100 },
    { title: '上限', dataIndex: 'upper_bound', key: 'upper_bound', width: 100 },
    { title: '单位', dataIndex: 'unit', key: 'unit', width: 100 },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => v ? <Tag color="green">生效</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, row: ThresholdRow) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)}>编辑</Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(row)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>异常阈值配置</Title>
        <Space>
          <Input.Search
            placeholder="搜索指标编码/名称"
            allowClear
            onSearch={setKeyword}
            style={{ width: 240 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增阈值</Button>
        </Space>
      </div>

      <Text type="secondary">本期所有阈值均为全局生效；二期上线人群分级时启用「高级配置」中的性别 / 年龄字段。</Text>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{ pageSize: 20 }}
        style={{ marginTop: 16 }}
      />

      <Modal
        title={editing ? '编辑阈值' : '新增阈值'}
        open={modalOpen}
        onOk={onSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="metric_code" label="指标编码" rules={[{ required: true }]}>
            <Input placeholder="如 GLU / HBA1C" />
          </Form.Item>
          <Form.Item name="metric_name" label="指标名称" rules={[{ required: true }]}>
            <Input placeholder="如 空腹血糖" />
          </Form.Item>
          <Form.Item name="severity" label="严重程度" rules={[{ required: true }]}>
            <Select options={SEVERITY_OPTIONS.map((o) => ({ value: o.value, label: o.label }))} />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="lower_bound" label="下限" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="upper_bound" label="上限" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="unit" label="单位" style={{ flex: 1 }}>
              <Input placeholder="如 mmol/L" />
            </Form.Item>
          </Space>
          <Form.Item name="is_active" label="是否生效" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>

          <Collapse>
            <Panel header="高级配置（暂不开放 - 二期人群分级）" key="adv">
              <Text type="secondary">本期所有阈值默认全局生效，gender / age 字段已在表结构中预留，二期上线后启用。</Text>
            </Panel>
          </Collapse>
        </Form>
      </Modal>
    </Card>
  );
}
