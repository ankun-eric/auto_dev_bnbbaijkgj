'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Tag, Modal, Form, Select,
  Radio, Switch, message, Popconfirm, Breadcrumb, Upload, Spin,
} from 'antd';
import type { UploadFile } from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined,
  ImportOutlined, InboxOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload } from '@/lib/api';
import { useRouter, useParams } from 'next/navigation';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { Dragger } = Upload;

interface KnowledgeEntry {
  id: number;
  kb_id: number;
  type: 'qa' | 'doc';
  title?: string;
  question?: string;
  content_json?: any;
  keywords: string[];
  display_mode: string;
  status: string;
  hit_count: number;
  last_hit_at?: string;
  created_at: string;
  updated_at?: string;
}

interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
}

interface ListResponse {
  items: KnowledgeEntry[];
  total: number;
  page: number;
  page_size: number;
}

export default function KnowledgeEntriesPage() {
  const router = useRouter();
  const params = useParams();
  const kbId = params.id as string;

  const [kbInfo, setKbInfo] = useState<KnowledgeBase | null>(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<KnowledgeEntry[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const [keyword, setKeyword] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState<string | undefined>(undefined);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeEntry | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const entryType = Form.useWatch('type', form);

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importMode, setImportMode] = useState<'file' | 'url'>('file');
  const [importUrl, setImportUrl] = useState('');
  const [importFileList, setImportFileList] = useState<UploadFile[]>([]);
  const [importing, setImporting] = useState(false);

  const fetchKbInfo = useCallback(async () => {
    try {
      const res = await get<{ items: KnowledgeBase[] }>('/api/admin/knowledge-bases', { page: 1, page_size: 100 });
      const kb = (res.items || []).find((item: KnowledgeBase) => String(item.id) === kbId);
      if (kb) setKbInfo(kb);
    } catch {
      // ignore
    }
  }, [kbId]);

  const fetchData = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const p: Record<string, any> = { page, page_size: pageSize };
      if (keyword) p.keyword = keyword;
      if (typeFilter) p.entry_type = typeFilter;
      if (statusFilter) p.status = statusFilter;
      if (sortBy) p.sort_by = sortBy;
      const res = await get<ListResponse>(`/api/admin/knowledge-bases/${kbId}/entries`, p);
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取条目列表失败');
    } finally {
      setLoading(false);
    }
  }, [kbId, keyword, typeFilter, statusFilter, sortBy]);

  useEffect(() => {
    fetchKbInfo();
  }, [fetchKbInfo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenModal = (record?: KnowledgeEntry) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      const cj = record.content_json;
      let answer = '';
      let content = '';
      if (typeof cj === 'string') {
        answer = cj;
        content = cj;
      } else if (cj && typeof cj === 'object') {
        answer = cj.text || cj.answer || cj.body || '';
        content = cj.text || cj.body || cj.content || '';
      }
      form.setFieldsValue({
        type: record.type,
        question: record.question || '',
        answer,
        title: record.title || '',
        content,
        keywords: record.keywords || [],
        display_mode: record.display_mode || 'direct',
      });
    } else {
      form.setFieldsValue({ type: 'qa', display_mode: 'direct' });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload: Record<string, any> = {
        type: values.type,
        question: values.question,
        title: values.title,
        keywords: values.keywords,
        display_mode: values.display_mode,
      };
      if (values.type === 'qa' && values.answer) {
        payload.content_json = { text: values.answer };
      } else if (values.type === 'doc' && values.content) {
        payload.content_json = { text: values.content };
      }
      if (editing) {
        await put(`/api/admin/knowledge-bases/${kbId}/entries/${editing.id}`, payload);
        message.success('条目更新成功');
      } else {
        await post(`/api/admin/knowledge-bases/${kbId}/entries`, payload);
        message.success('条目创建成功');
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

  const handleToggleStatus = async (record: KnowledgeEntry) => {
    try {
      const newStatus = record.status === 'active' ? 'inactive' : 'active';
      await put(`/api/admin/knowledge-bases/${kbId}/entries/${record.id}`, {
        status: newStatus,
      });
      message.success(newStatus === 'active' ? '已启用' : '已禁用');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '操作失败';
      message.error(typeof detail === 'string' ? detail : '操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/knowledge-bases/${kbId}/entries/${id}`);
      message.success('条目删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '删除失败';
      message.error(typeof detail === 'string' ? detail : '删除失败');
    }
  };

  const handleImport = async () => {
    setImporting(true);
    try {
      if (importMode === 'file' && importFileList.length > 0) {
        const file = importFileList[0]?.originFileObj;
        if (file) {
          const text = await file.text();
          let entries: any[] = [];
          try {
            const parsed = JSON.parse(text);
            entries = Array.isArray(parsed) ? parsed : parsed.entries || [];
          } catch {
            message.error('文件格式不正确，请使用JSON格式');
            setImporting(false);
            return;
          }
          await post('/api/admin/knowledge-bases/import', {
            kb_id: Number(kbId),
            source_type: 'excel',
            entries,
          });
          message.success('文件导入成功');
        }
      } else if (importMode === 'url' && importUrl) {
        await post('/api/admin/knowledge-bases/import', {
          kb_id: Number(kbId),
          source_type: 'url',
          entries: [],
        });
        message.success('URL导入任务已提交');
      } else {
        message.warning('请上传文件或输入URL');
        setImporting(false);
        return;
      }
      setImportModalOpen(false);
      setImportFileList([]);
      setImportUrl('');
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '导入失败';
      message.error(typeof detail === 'string' ? detail : '导入失败');
    } finally {
      setImporting(false);
    }
  };

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleReset = () => {
    setKeyword('');
    setTypeFilter(undefined);
    setStatusFilter(undefined);
    setSortBy(undefined);
  };

  const columns = [
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 90,
      render: (v: string) => <Tag color={v === 'qa' ? 'blue' : 'purple'}>{v === 'qa' ? 'Q&A' : v === 'doc' ? '文档' : v}</Tag>,
    },
    {
      title: '标题/问题',
      key: 'title',
      ellipsis: true,
      render: (_: any, record: KnowledgeEntry) => record.question || record.title || '-',
    },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      width: 200,
      render: (v: string[]) =>
        Array.isArray(v) && v.length > 0
          ? v.map((k) => <Tag key={k} style={{ marginBottom: 2 }}>{k}</Tag>)
          : '-',
    },
    {
      title: '展示方式',
      dataIndex: 'display_mode',
      key: 'display_mode',
      width: 120,
      render: (v: string) => v === 'ai_rewrite' ? 'AI改写' : '直接展示',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'default'}>{v === 'active' ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '命中次数',
      dataIndex: 'hit_count',
      key: 'hit_count',
      width: 100,
      sorter: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: KnowledgeEntry) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Button type="link" size="small" onClick={() => handleToggleStatus(record)}>
            {record.status === 'active' ? '禁用' : '启用'}
          </Button>
          <Popconfirm title="确定删除此条目？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <a onClick={() => router.push('/knowledge')}>知识库管理</a> },
          { title: kbInfo?.name || '知识库' },
          { title: '条目管理' },
        ]}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => router.push('/knowledge')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>{kbInfo?.name || '知识库'} - 条目管理</Title>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索关键词"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="条目类型"
          value={typeFilter}
          onChange={setTypeFilter}
          allowClear
          style={{ width: 120 }}
          options={[
            { label: '全部', value: '' },
            { label: 'Q&A', value: 'qa' },
            { label: '文档', value: 'doc' },
          ]}
        />
        <Select
          placeholder="状态"
          value={statusFilter}
          onChange={setStatusFilter}
          allowClear
          style={{ width: 120 }}
          options={[
            { label: '全部', value: '' },
            { label: '启用', value: 'active' },
            { label: '禁用', value: 'inactive' },
          ]}
        />
        <Select
          placeholder="排序"
          value={sortBy}
          onChange={setSortBy}
          allowClear
          style={{ width: 140 }}
          options={[
            { label: '默认排序', value: '' },
            { label: '命中次数↓', value: 'hit_count' },
          ]}
        />
        <Button type="primary" onClick={handleSearch}>搜索</Button>
        <Button onClick={() => { handleReset(); setTimeout(() => fetchData(1, pagination.pageSize), 0); }}>重置</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>新增条目</Button>
        <Button icon={<ImportOutlined />} onClick={() => setImportModalOpen(true)}>批量导入</Button>
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
        scroll={{ x: 1000 }}
      />

      <Modal
        title={editing ? '编辑条目' : '新增条目'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={720}
      >
        <Form form={form} layout="vertical" initialValues={{ type: 'qa', display_mode: 'direct' }}>
          <Form.Item label="条目类型" name="type" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio.Button value="qa">Q&A</Radio.Button>
              <Radio.Button value="doc">文档段落</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {entryType === 'qa' ? (
            <>
              <Form.Item label="问题" name="question" rules={[{ required: true, message: '请输入问题' }]}>
                <Input placeholder="请输入问题" />
              </Form.Item>
              <Form.Item label="答案" name="answer" rules={[{ required: true, message: '请输入答案' }]}>
                <Input.TextArea rows={5} placeholder="请输入答案内容" />
              </Form.Item>
            </>
          ) : (
            <>
              <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
                <Input placeholder="请输入标题" />
              </Form.Item>
              <Form.Item label="正文" name="content" rules={[{ required: true, message: '请输入正文' }]}>
                <Input.TextArea rows={6} placeholder="请输入正文内容" />
              </Form.Item>
            </>
          )}

          <Form.Item label="关键词/标签" name="keywords">
            <Select mode="tags" placeholder="输入关键词后按回车添加" />
          </Form.Item>

          <Form.Item label="展示方式" name="display_mode">
            <Radio.Group>
              <Radio value="direct">直接展示</Radio>
              <Radio value="ai_rewrite">AI改写后展示</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量导入"
        open={importModalOpen}
        onOk={handleImport}
        onCancel={() => { setImportModalOpen(false); setImportFileList([]); setImportUrl(''); }}
        confirmLoading={importing}
        destroyOnClose
        width={560}
      >
        <Radio.Group
          value={importMode}
          onChange={(e) => setImportMode(e.target.value)}
          style={{ marginBottom: 16 }}
        >
          <Radio.Button value="file">上传文件</Radio.Button>
          <Radio.Button value="url">输入URL</Radio.Button>
        </Radio.Group>

        {importMode === 'file' ? (
          <Dragger
            fileList={importFileList}
            beforeUpload={() => false}
            onChange={({ fileList }) => setImportFileList(fileList.slice(-1))}
            accept=".xlsx,.xls,.csv,.json,.txt,.md"
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">支持 xlsx、csv、json、txt、md 格式</p>
          </Dragger>
        ) : (
          <Input
            placeholder="请输入文件URL地址"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
          />
        )}
      </Modal>
    </div>
  );
}
