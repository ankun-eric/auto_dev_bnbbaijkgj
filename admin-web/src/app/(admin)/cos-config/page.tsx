'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Form, Input, Button, Switch, Select, Table, Tabs, Space,
  Statistic, Row, Col, Tag, Image, message, Spin, Popconfirm, Modal,
} from 'antd';
import {
  SaveOutlined, ApiOutlined, DeleteOutlined, EyeOutlined,
  CloudOutlined, FileOutlined, PieChartOutlined,
} from '@ant-design/icons';
import { get, put, post, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

interface CosConfig {
  id: number;
  secret_id: string;
  secret_key_masked: string;
  bucket: string;
  region: string;
  image_prefix: string;
  video_prefix: string;
  file_prefix: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface CosFile {
  id: number;
  file_key: string;
  file_url: string;
  file_type: string | null;
  file_size: number | null;
  original_name: string | null;
  module: string | null;
  ref_id: number | null;
  created_at: string;
}

interface CosUsage {
  total_files: number;
  total_size: number;
  total_size_mb: number;
  by_type: Record<string, { count: number; size: number }>;
}

const REGIONS = [
  { label: '北京 (ap-beijing)', value: 'ap-beijing' },
  { label: '上海 (ap-shanghai)', value: 'ap-shanghai' },
  { label: '广州 (ap-guangzhou)', value: 'ap-guangzhou' },
  { label: '成都 (ap-chengdu)', value: 'ap-chengdu' },
  { label: '重庆 (ap-chongqing)', value: 'ap-chongqing' },
  { label: '南京 (ap-nanjing)', value: 'ap-nanjing' },
  { label: '香港 (ap-hongkong)', value: 'ap-hongkong' },
  { label: '新加坡 (ap-singapore)', value: 'ap-singapore' },
];

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${units[i]}`;
}

function isImageFile(type: string): boolean {
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(type.toLowerCase());
}

export default function CosConfigPage() {
  const [activeTab, setActiveTab] = useState('config');

  // Config tab
  const [configForm] = Form.useForm();
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [cosEnabled, setCosEnabled] = useState(false);
  const [hasSecretKey, setHasSecretKey] = useState(false);

  // Files tab
  const [files, setFiles] = useState<CosFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesPagination, setFilesPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [fileTypeFilter, setFileTypeFilter] = useState<string | undefined>(undefined);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Usage tab
  const [usage, setUsage] = useState<CosUsage>({ total_files: 0, total_size: 0, total_size_mb: 0, by_type: {} });
  const [usageLoading, setUsageLoading] = useState(false);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res = await get<CosConfig>('/api/admin/cos/config');
      setCosEnabled(!!res.is_active);
      setHasSecretKey(!!res.secret_key_masked);
      configForm.setFieldsValue({
        secret_id: res.secret_id || '',
        bucket: res.bucket || '',
        region: res.region || '',
        image_prefix: res.image_prefix || 'images/',
        video_prefix: res.video_prefix || 'videos/',
        file_prefix: res.file_prefix || 'files/',
      });
    } catch {
      // not configured yet
    } finally {
      setConfigLoading(false);
    }
  }, [configForm]);

  const fetchFiles = useCallback(async (page = 1, pageSize = 20) => {
    setFilesLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (fileTypeFilter) params.module = fileTypeFilter;
      const res = await get<{ items: CosFile[]; total: number; page: number; page_size: number }>('/api/admin/cos/files', params);
      setFiles(res.items || []);
      setFilesPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取文件列表失败');
    } finally {
      setFilesLoading(false);
    }
  }, [fileTypeFilter]);

  const fetchUsage = useCallback(async () => {
    setUsageLoading(true);
    try {
      const res = await get<CosUsage>('/api/admin/cos/usage');
      setUsage(res);
    } catch {
      // ignore
    } finally {
      setUsageLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (activeTab === 'files') fetchFiles();
  }, [activeTab, fetchFiles]);

  useEffect(() => {
    if (activeTab === 'usage') fetchUsage();
  }, [activeTab, fetchUsage]);

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      const payload: Record<string, any> = { ...values, is_active: cosEnabled };
      if (!payload.secret_key) delete payload.secret_key;
      await put('/api/admin/cos/config', payload);
      message.success('存储配置保存成功');
      fetchConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setConfigSaving(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      setTesting(true);
      setTestResult(null);
      const res = await post<{ success: boolean; message: string }>('/api/admin/cos/test', {});
      setTestResult({ success: res.success, message: res.message || '连接成功' });
      if (res.success) message.success('连接测试成功');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '连接失败';
      setTestResult({ success: false, message: typeof msg === 'string' ? msg : '连接失败' });
    } finally {
      setTesting(false);
    }
  };

  const handleDeleteFile = async (fileKey: string) => {
    try {
      await del(`/api/admin/cos/files?file_key=${encodeURIComponent(fileKey)}`);
      message.success('文件删除成功');
      fetchFiles(filesPagination.current, filesPagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '删除失败';
      message.error(typeof detail === 'string' ? detail : '删除失败');
    }
  };

  const fileColumns = [
    {
      title: '文件名',
      dataIndex: 'original_name',
      key: 'original_name',
      ellipsis: true,
      render: (v: string | null, record: CosFile) => (
        <Space>
          {record.file_type && isImageFile(record.file_type) && record.file_url && (
            <Image
              src={record.file_url}
              width={32}
              height={32}
              style={{ objectFit: 'cover', borderRadius: 4 }}
              preview={false}
            />
          )}
          <span>{v || record.file_key}</span>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 100,
      render: (v: string | null) => v ? <Tag>{v.toUpperCase()}</Tag> : '-',
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 120,
      render: (v: number | null) => v != null ? formatFileSize(v) : '-',
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: CosFile) => (
        <Space>
          {record.file_type && isImageFile(record.file_type) && record.file_url && (
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setPreviewUrl(record.file_url)}>
              预览
            </Button>
          )}
          <Popconfirm title="确定删除此文件？" onConfirm={() => handleDeleteFile(record.file_key)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const usageTypeColumns = [
    { title: '文件类型', dataIndex: 'type', key: 'type', render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
    { title: '文件数量', dataIndex: 'count', key: 'count', width: 120 },
    { title: '占用空间', dataIndex: 'size', key: 'size', width: 140, render: (v: number) => formatFileSize(v) },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>存储配置</Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'config',
            label: <Space><CloudOutlined />存储配置</Space>,
            children: (
              <Spin spinning={configLoading}>
                <Card style={{ borderRadius: 12, maxWidth: 640 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
                    <Title level={5} style={{ margin: 0 }}>腾讯云COS配置</Title>
                    <Switch
                      checked={cosEnabled}
                      onChange={setCosEnabled}
                      checkedChildren="启用"
                      unCheckedChildren="禁用"
                    />
                  </div>
                  <Form form={configForm} layout="vertical">
                    <Form.Item label="SecretId" name="secret_id" rules={[{ required: true, message: '请输入SecretId' }]}>
                      <Input placeholder="请输入SecretId" />
                    </Form.Item>
                    <Form.Item label="SecretKey" name="secret_key">
                      <Input.Password placeholder={hasSecretKey ? '已设置（重新输入将覆盖）' : '未设置'} />
                    </Form.Item>
                    <Form.Item label="Bucket" name="bucket" rules={[{ required: true, message: '请输入Bucket名称' }]}>
                      <Input placeholder="请输入Bucket名称，如 my-bucket-1250000000" />
                    </Form.Item>
                    <Form.Item label="Region" name="region" rules={[{ required: true, message: '请选择Region' }]}>
                      <Select options={REGIONS} placeholder="请选择地域" />
                    </Form.Item>
                    <Form.Item label="图片路径前缀" name="image_prefix">
                      <Input placeholder="images/" />
                    </Form.Item>
                    <Form.Item label="视频路径前缀" name="video_prefix">
                      <Input placeholder="videos/" />
                    </Form.Item>
                    <Form.Item label="文件路径前缀" name="file_prefix">
                      <Input placeholder="files/" />
                    </Form.Item>
                    <Form.Item>
                      <Space>
                        <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveConfig} loading={configSaving}>
                          保存配置
                        </Button>
                        <Button icon={<ApiOutlined />} onClick={handleTestConnection} loading={testing}>
                          测试连接
                        </Button>
                      </Space>
                    </Form.Item>
                  </Form>
                  {testResult && (
                    <div style={{
                      marginTop: 12,
                      padding: 12,
                      borderRadius: 8,
                      background: testResult.success ? '#f6ffed' : '#fff2f0',
                      border: `1px solid ${testResult.success ? '#b7eb8f' : '#ffa39e'}`,
                    }}>
                      <Text type={testResult.success ? 'success' : 'danger'}>{testResult.message}</Text>
                    </div>
                  )}
                </Card>
              </Spin>
            ),
          },
          {
            key: 'files',
            label: <Space><FileOutlined />文件管理</Space>,
            children: (
              <div>
                <Space style={{ marginBottom: 16 }}>
                  <Select
                    placeholder="模块"
                    value={fileTypeFilter}
                    onChange={setFileTypeFilter}
                    allowClear
                    style={{ width: 140 }}
                    options={[
                      { label: '全部', value: '' },
                      { label: '图片', value: 'image' },
                      { label: '视频', value: 'video' },
                      { label: '文件', value: 'file' },
                    ]}
                  />
                  <Button type="primary" onClick={() => fetchFiles(1, filesPagination.pageSize)}>查询</Button>
                </Space>
                <Table
                  columns={fileColumns}
                  dataSource={files}
                  rowKey="file_key"
                  loading={filesLoading}
                  pagination={{
                    current: filesPagination.current,
                    pageSize: filesPagination.pageSize,
                    total: filesPagination.total,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page, pageSize) => fetchFiles(page, pageSize),
                  }}
                  scroll={{ x: 700 }}
                />
                <Modal open={!!previewUrl} onCancel={() => setPreviewUrl(null)} footer={null} width={640}>
                  {previewUrl && <Image src={previewUrl} width="100%" preview={false} />}
                </Modal>
              </div>
            ),
          },
          {
            key: 'usage',
            label: <Space><PieChartOutlined />用量统计</Space>,
            children: (
              <Spin spinning={usageLoading}>
                <Row gutter={16} style={{ marginBottom: 24 }}>
                  <Col span={12}>
                    <Card>
                      <Statistic title="总存储用量" value={`${usage.total_size_mb} MB`} prefix={<CloudOutlined />} />
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card>
                      <Statistic title="文件总数" value={usage.total_files} prefix={<FileOutlined />} />
                    </Card>
                  </Col>
                </Row>
                <Card title="按类型统计" style={{ borderRadius: 12 }}>
                  <Table
                    columns={usageTypeColumns}
                    dataSource={Object.entries(usage.by_type).map(([type, data]) => ({ type, count: data.count, size: data.size }))}
                    rowKey="type"
                    pagination={false}
                  />
                </Card>
              </Spin>
            ),
          },
        ]}
      />
    </div>
  );
}
