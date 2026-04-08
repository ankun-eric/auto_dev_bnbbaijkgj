'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Modal, Form, message, Tag, Switch,
  Radio, Popconfirm, Select,
} from 'antd';
import {
  SearchOutlined, PlusOutlined, EditOutlined, DeleteOutlined, ImportOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface BlockWord {
  id: number;
  keyword: string;
  block_mode: string;
  tip_content: string | null;
  is_active: boolean;
  created_at: string;
}

interface ListResponse {
  items: BlockWord[];
  total: number;
  page: number;
  page_size: number;
}

const BLOCK_MODE_OPTIONS = [
  { label: '完全屏蔽', value: 'full' },
  { label: '替换提示', value: 'tip' },
];

const blockModeLabel = (val: string) => {
  const found = BLOCK_MODE_OPTIONS.find((o) => o.value === val);
  return found ? found.label : val;
};

export default function BlockWordsPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<BlockWord[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [keyword, setKeyword] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<BlockWord | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [blockMode, setBlockMode] = useState('full');

  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchForm] = Form.useForm();
  const [batchSaving, setBatchSaving] = useState(false);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get<ListResponse>('/api/admin/search/block-words', {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
      });
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取屏蔽词列表失败');
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

  const handleOpenModal = (record?: BlockWord) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        keyword: record.keyword,
        block_mode: record.block_mode,
        tip_content: record.tip_content || '',
        is_active: record.is_active,
      });
      setBlockMode(record.block_mode);
    } else {
      form.setFieldsValue({ block_mode: 'full', is_active: true });
      setBlockMode('full');
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        ...values,
        tip_content: values.block_mode === 'tip' ? (values.tip_content || '') : null,
      };
      if (editing) {
        await put(`/api/admin/search/block-words/${editing.id}`, payload);
        message.success('更新成功');
      } else {
        await post('/api/admin/search/block-words', payload);
        message.success('新增成功');
      }
      setModalOpen(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/search/block-words/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '删除失败';
      message.error(typeof detail === 'string' ? detail : '删除失败');
    }
  };

  const handleBatchImport = async () => {
    try {
      const values = await batchForm.validateFields();
      const words = (values.words_text as string)
        .split('\n')
        .map((w) => w.trim())
        .filter(Boolean);
      if (words.length === 0) {
        message.warning('请输入至少一个屏蔽词');
        return;
      }
      setBatchSaving(true);
      await post('/api/admin/search/block-words/batch', {
        keywords: words,
        block_mode: values.block_mode,
      });
      message.success(`成功导入 ${words.length} 个屏蔽词`);
      setBatchModalOpen(false);
      batchForm.resetFields();
      fetchData(1, pagination.pageSize);
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '导入失败';
      message.error(typeof detail === 'string' ? detail : '导入失败');
    } finally {
      setBatchSaving(false);
    }
  };

  const columns = [
    {
      title: '词条',
      dataIndex: 'keyword',
      key: 'keyword',
    },
    {
      title: '屏蔽模式',
      dataIndex: 'block_mode',
      key: 'block_mode',
      width: 120,
      render: (v: string) => (
        <Tag color={v === 'full' ? 'red' : 'orange'}>{blockModeLabel(v)}</Tag>
      ),
    },
    {
      title: '提示文案',
      dataIndex: 'tip_content',
      key: 'tip_content',
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    {
      title: '启用状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: BlockWord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该屏蔽词？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>搜索屏蔽词管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索屏蔽词"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 240 }}
          allowClear
        />
        <Button type="primary" onClick={handleSearch}>搜索</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增屏蔽词
        </Button>
        <Button icon={<ImportOutlined />} onClick={() => { batchForm.resetFields(); batchForm.setFieldsValue({ block_mode: 'full' }); setBatchModalOpen(true); }}>
          批量导入
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
      />

      <Modal
        title={editing ? '编辑屏蔽词' : '新增屏蔽词'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="词条"
            name="keyword"
            rules={[{ required: true, message: '请输入屏蔽词' }]}
          >
            <Input placeholder="请输入屏蔽词" />
          </Form.Item>
          <Form.Item
            label="屏蔽模式"
            name="block_mode"
            rules={[{ required: true, message: '请选择屏蔽模式' }]}
          >
            <Radio.Group
              options={BLOCK_MODE_OPTIONS}
              onChange={(e) => setBlockMode(e.target.value)}
            />
          </Form.Item>
          {blockMode === 'tip' && (
            <Form.Item label="替换提示文案" name="tip_content">
              <TextArea rows={3} placeholder="请输入替换后的提示文案" />
            </Form.Item>
          )}
          <Form.Item label="启用状态" name="is_active" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量导入屏蔽词"
        open={batchModalOpen}
        onOk={handleBatchImport}
        onCancel={() => setBatchModalOpen(false)}
        confirmLoading={batchSaving}
        destroyOnClose
      >
        <Form form={batchForm} layout="vertical" style={{ marginTop: 16 }} initialValues={{ block_mode: 'full' }}>
          <Form.Item
            label="屏蔽词列表（一行一个）"
            name="words_text"
            rules={[{ required: true, message: '请输入屏蔽词' }]}
          >
            <TextArea rows={8} placeholder="请粘贴屏蔽词，一行一个" />
          </Form.Item>
          <Form.Item
            label="屏蔽模式"
            name="block_mode"
            rules={[{ required: true, message: '请选择屏蔽模式' }]}
          >
            <Radio.Group options={BLOCK_MODE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
