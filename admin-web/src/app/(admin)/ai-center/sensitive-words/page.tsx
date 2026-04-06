'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Modal, Form, message, Popconfirm,
} from 'antd';
import { SearchOutlined, PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface SensitiveWord {
  id: number;
  sensitive_word: string;
  replacement_word: string;
  created_at: string;
}

interface ListResponse {
  items: SensitiveWord[];
  total: number;
  page: number;
  page_size: number;
}

export default function SensitiveWordsPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<SensitiveWord[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [keyword, setKeyword] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SensitiveWord | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get<ListResponse>('/api/admin/ai-center/sensitive-words', {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
      });
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取敏感词列表失败');
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

  const handleOpenModal = (record?: SensitiveWord) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        sensitive_word: record.sensitive_word,
        replacement_word: record.replacement_word,
      });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (editing) {
        await put(`/api/admin/ai-center/sensitive-words/${editing.id}`, values);
        message.success('更新成功');
      } else {
        await post('/api/admin/ai-center/sensitive-words', values);
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

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该敏感词吗？删除后不可恢复。',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await del(`/api/admin/ai-center/sensitive-words/${id}`);
          message.success('删除成功');
          fetchData(pagination.current, pagination.pageSize);
        } catch (e: any) {
          const detail = e?.response?.data?.detail || e?.message || '删除失败';
          message.error(typeof detail === 'string' ? detail : '删除失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '序号',
      key: 'index',
      width: 70,
      render: (_: any, __: any, index: number) =>
        (pagination.current - 1) * pagination.pageSize + index + 1,
    },
    {
      title: '敏感词',
      dataIndex: 'sensitive_word',
      key: 'sensitive_word',
    },
    {
      title: '替换词',
      dataIndex: 'replacement_word',
      key: 'replacement_word',
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
      render: (_: any, record: SensitiveWord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>敏感词管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索敏感词"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 240 }}
          allowClear
        />
        <Button type="primary" onClick={handleSearch}>搜索</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增敏感词
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
        title={editing ? '编辑敏感词' : '新增敏感词'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="敏感词"
            name="sensitive_word"
            rules={[{ required: true, message: '请输入敏感词' }]}
          >
            <Input placeholder="请输入敏感词" />
          </Form.Item>
          <Form.Item
            label="替换词"
            name="replacement_word"
            rules={[{ required: true, message: '请输入替换词' }]}
          >
            <Input placeholder="请输入替换词" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
