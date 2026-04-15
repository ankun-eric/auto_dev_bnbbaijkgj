'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Typography, Card, Form, Input, InputNumber, Button, Switch, Select, Table, Tabs,
  Space, Statistic, Tag, message, Spin, Progress, Checkbox, Alert,
} from 'antd';
import {
  SaveOutlined, ApiOutlined, CloudOutlined, FileOutlined,
  SyncOutlined, RocketOutlined, ReloadOutlined, ScanOutlined,
} from '@ant-design/icons';
import { get, put, post } from '@/lib/api';

const { Title, Text } = Typography;

interface CosConfig {
  id: number;
  secret_id: string;
  secret_key_masked: string;
  bucket: string;
  region: string;
  path_prefix: string;
  cdn_domain: string | null;
  cdn_protocol: string;
  is_active: boolean;
  test_passed: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface UploadLimit {
  module: string;
  module_name: string;
  max_size_mb: number;
}

interface MigrationScanItem {
  module: string;
  module_name: string;
  file_count: number;
  total_size: number;
  total_size_display: string;
}

interface MigrationProgress {
  task_id: number;
  status: string;
  total_files: number;
  migrated_count: number;
  failed_count: number;
  skipped_count: number;
  current_file: string | null;
  progress_percent: number;
  estimated_remaining_seconds: number | null;
  started_at: string | null;
  failed_items: { original_url: string; error_message: string | null }[];
}

const REGIONS = [
  { label: '北京 (ap-beijing)', value: 'ap-beijing' },
  { label: '上海 (ap-shanghai)', value: 'ap-shanghai' },
  { label: '广州 (ap-guangzhou)', value: 'ap-guangzhou' },
  { label: '成都 (ap-chengdu)', value: 'ap-chengdu' },
  { label: '重庆 (ap-chongqing)', value: 'ap-chongqing' },
  { label: '南京 (ap-nanjing)', value: 'ap-nanjing' },
  { label: '香港 (ap-hongkong)', value: 'ap-hongkong' },
];

const CDN_PROTOCOLS = [
  { label: 'HTTPS', value: 'https' },
  { label: 'HTTP', value: 'http' },
];

const DEFAULT_UPLOAD_LIMITS: UploadLimit[] = [
  { module: 'avatar', module_name: '用户头像', max_size_mb: 2 },
  { module: 'health_record_image', module_name: '健康记录图片', max_size_mb: 10 },
  { module: 'health_record_video', module_name: '健康记录视频', max_size_mb: 100 },
  { module: 'brand_logo', module_name: '品牌LOGO', max_size_mb: 2 },
  { module: 'banner', module_name: '轮播图/广告图', max_size_mb: 5 },
  { module: 'report', module_name: '体检报告图片', max_size_mb: 10 },
  { module: 'other', module_name: '其他文件', max_size_mb: 50 },
];

export default function CosConfigPage() {
  const [activeTab, setActiveTab] = useState('config');

  const [configForm] = Form.useForm();
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testPassed, setTestPassed] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [cosEnabled, setCosEnabled] = useState(false);
  const [hasSecretKey, setHasSecretKey] = useState(false);

  const [uploadLimits, setUploadLimits] = useState<UploadLimit[]>(DEFAULT_UPLOAD_LIMITS);
  const [limitsLoading, setLimitsLoading] = useState(false);
  const [limitsSaving, setLimitsSaving] = useState(false);

  const [scanLoading, setScanLoading] = useState(false);
  const [scanResult, setScanResult] = useState<MigrationScanItem[]>([]);
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [migrating, setMigrating] = useState(false);
  const [migrationTaskId, setMigrationTaskId] = useState<string | null>(null);
  const [migrationProgress, setMigrationProgress] = useState<MigrationProgress | null>(null);
  const [retrying, setRetrying] = useState(false);
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [totalFiles, setTotalFiles] = useState(0);
  const [filesLoading, setFilesLoading] = useState(false);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res = await get<CosConfig>('/api/admin/cos/config');
      setCosEnabled(!!res.is_active);
      setHasSecretKey(!!res.secret_key_masked);
      setTestPassed(!!res.test_passed);
      configForm.setFieldsValue({
        secret_id: res.secret_id || '',
        bucket: res.bucket || '',
        region: res.region || '',
        path_prefix: res.path_prefix || '',
        cdn_domain: res.cdn_domain || '',
        cdn_protocol: res.cdn_protocol || 'https',
      });
    } catch {
      // not configured yet
    } finally {
      setConfigLoading(false);
    }
  }, [configForm]);

  const fetchUploadLimits = useCallback(async () => {
    setLimitsLoading(true);
    try {
      const res = await get<{ items: UploadLimit[] }>('/api/admin/cos/upload-limits');
      const items = res?.items;
      if (items && items.length > 0) {
        setUploadLimits(items);
      }
    } catch {
      // use defaults
    } finally {
      setLimitsLoading(false);
    }
  }, []);

  const fetchUsage = useCallback(async () => {
    setFilesLoading(true);
    try {
      const res = await get<{ total_files: number }>('/api/admin/cos/usage');
      setTotalFiles(res.total_files || 0);
    } catch {
      // ignore
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchUploadLimits();
  }, [fetchConfig, fetchUploadLimits]);

  useEffect(() => {
    if (activeTab === 'files') fetchUsage();
  }, [activeTab, fetchUsage]);

  useEffect(() => {
    return () => {
      if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    };
  }, []);

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      const payload: Record<string, any> = {
        secret_id: values.secret_id,
        bucket: values.bucket,
        region: values.region,
        path_prefix: values.path_prefix || '',
        cdn_domain: values.cdn_domain || '',
        cdn_protocol: values.cdn_protocol || 'https',
        is_active: cosEnabled,
      };
      if (values.secret_key) payload.secret_key = values.secret_key;
      await put('/api/admin/cos/config', payload);
      message.success('存储配置保存成功');
      setTestPassed(false);
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
      if (res.success) {
        setTestPassed(true);
        message.success('连接测试成功');
      } else {
        setTestPassed(false);
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '连接失败';
      setTestResult({ success: false, message: typeof msg === 'string' ? msg : '连接失败' });
      setTestPassed(false);
    } finally {
      setTesting(false);
    }
  };

  const handleSaveUploadLimits = async () => {
    for (const item of uploadLimits) {
      if (item.max_size_mb <= 0 || item.max_size_mb > 1024) {
        message.error(`${item.module_name} 的限制值必须大于 0 且不超过 1024 MB`);
        return;
      }
    }
    setLimitsSaving(true);
    try {
      await put('/api/admin/cos/upload-limits', {
        items: uploadLimits.map((item) => ({ module: item.module, max_size_mb: item.max_size_mb })),
      });
      message.success('上传限制配置保存成功');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setLimitsSaving(false);
    }
  };

  const handleScanMigration = async () => {
    setScanLoading(true);
    setScanResult([]);
    setSelectedModules([]);
    try {
      const res = await post<{ groups: MigrationScanItem[]; total_files: number; total_size: number; total_size_display: string }>('/api/admin/cos/migration/scan', {});
      const groups = res?.groups || [];
      setScanResult(groups);
      if (groups.length > 0) {
        setSelectedModules(groups.map((item) => item.module));
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '扫描失败';
      message.error(typeof detail === 'string' ? detail : '扫描失败');
    } finally {
      setScanLoading(false);
    }
  };

  const startProgressPolling = useCallback((taskId: string) => {
    if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    progressTimerRef.current = setInterval(async () => {
      try {
        const res = await get<MigrationProgress>('/api/admin/cos/migration/progress', { task_id: taskId });
        setMigrationProgress(res);
        if (res.status === 'completed' || res.status === 'failed') {
          if (progressTimerRef.current) clearInterval(progressTimerRef.current);
          progressTimerRef.current = null;
          setMigrating(false);
          if (res.status === 'completed' && res.failed_count === 0) {
            message.success('数据迁移完成');
          } else if (res.status === 'completed' && res.failed_count > 0) {
            message.warning(`迁移完成，${res.failed_count} 个文件失败`);
          } else {
            message.error('迁移任务异常终止');
          }
        }
      } catch {
        // keep polling
      }
    }, 3000);
  }, []);

  const handleStartMigration = async () => {
    if (selectedModules.length === 0) {
      message.warning('请至少选择一个模块');
      return;
    }
    setMigrating(true);
    setMigrationProgress(null);
    try {
      const res = await post<{ task_id: number; status: string; total_files: number; message: string }>('/api/admin/cos/migration/start', { modules: selectedModules });
      const taskId = String(res.task_id);
      setMigrationTaskId(taskId);
      startProgressPolling(taskId);
    } catch (e: any) {
      setMigrating(false);
      const detail = e?.response?.data?.detail || e?.message || '启动迁移失败';
      message.error(typeof detail === 'string' ? detail : '启动迁移失败');
    }
  };

  const handleRetryFailed = async () => {
    if (!migrationTaskId) return;
    setRetrying(true);
    try {
      await post('/api/admin/cos/migration/retry', null, { params: { task_id: migrationTaskId } });
      setMigrating(true);
      startProgressPolling(migrationTaskId);
      message.info('正在重试失败文件...');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '重试失败';
      message.error(typeof detail === 'string' ? detail : '重试失败');
    } finally {
      setRetrying(false);
    }
  };

  const updateLimitValue = (module: string, value: number | null) => {
    setUploadLimits((prev) =>
      prev.map((item) => (item.module === module ? { ...item, max_size_mb: value ?? 0 } : item))
    );
  };

  const scanColumns = [
    {
      title: (
        <Checkbox
          checked={scanResult.length > 0 && selectedModules.length === scanResult.length}
          indeterminate={selectedModules.length > 0 && selectedModules.length < scanResult.length}
          onChange={(e) => {
            setSelectedModules(e.target.checked ? scanResult.map((item) => item.module) : []);
          }}
        />
      ),
      dataIndex: 'module',
      key: 'select',
      width: 50,
      render: (_: any, record: MigrationScanItem) => (
        <Checkbox
          checked={selectedModules.includes(record.module)}
          onChange={(e) => {
            setSelectedModules((prev) =>
              e.target.checked ? [...prev, record.module] : prev.filter((m) => m !== record.module)
            );
          }}
        />
      ),
    },
    { title: '模块名称', dataIndex: 'module_name', key: 'module_name' },
    { title: '文件数', dataIndex: 'file_count', key: 'file_count', width: 100 },
    { title: '总大小', dataIndex: 'total_size_display', key: 'total_size_display', width: 120 },
  ];

  const failedFileColumns = [
    { title: '文件', dataIndex: 'original_url', key: 'original_url', ellipsis: true },
    { title: '错误原因', dataIndex: 'error_message', key: 'error_message', ellipsis: true },
  ];

  const renderConfigTab = () => (
    <Spin spinning={configLoading}>
      <div className="flex flex-col gap-6">
        {/* 区块一：COS基础配置 */}
        <Card title="COS基础配置" style={{ borderRadius: 12 }}>
          <Form form={configForm} layout="vertical" style={{ maxWidth: 560 }}>
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
            <Form.Item label="统一路径前缀" name="path_prefix">
              <Input placeholder="非必填，如 bini-health/" />
            </Form.Item>
            <Form.Item label="启用COS" valuePropName="checked">
              <Switch
                checked={cosEnabled}
                onChange={setCosEnabled}
                disabled={!testPassed && !cosEnabled}
                checkedChildren="启用"
                unCheckedChildren="禁用"
              />
              {!testPassed && !cosEnabled && (
                <Text type="secondary" className="ml-2 text-xs">请先测试连接通过后再启用</Text>
              )}
            </Form.Item>
          </Form>
        </Card>

        {/* 区块二：CDN加速配置 */}
        <Card title="CDN加速配置" style={{ borderRadius: 12 }}>
          <Form form={configForm} layout="vertical" style={{ maxWidth: 560 }}>
            <Form.Item label="CDN域名" name="cdn_domain">
              <Input placeholder="非必填，如 cdn.example.com" />
            </Form.Item>
            <Form.Item label="CDN协议" name="cdn_protocol" initialValue="https">
              <Select options={CDN_PROTOCOLS} placeholder="请选择协议" />
            </Form.Item>
          </Form>
        </Card>

        {/* 区块三：上传限制配置 */}
        <Card
          title="上传限制配置"
          style={{ borderRadius: 12 }}
          extra={
            <Button
              type="primary"
              size="small"
              icon={<SaveOutlined />}
              loading={limitsSaving}
              onClick={handleSaveUploadLimits}
            >
              保存上传限制
            </Button>
          }
        >
          <Spin spinning={limitsLoading}>
            <div className="flex flex-col gap-3" style={{ maxWidth: 480 }}>
              {uploadLimits.map((item) => (
                <div key={item.module} className="flex items-center justify-between">
                  <Text style={{ width: 140 }}>{item.module_name}</Text>
                  <Space>
                    <InputNumber
                      min={1}
                      max={1024}
                      value={item.max_size_mb}
                      onChange={(val) => updateLimitValue(item.module, val)}
                      addonAfter="MB"
                      style={{ width: 160 }}
                    />
                  </Space>
                </div>
              ))}
              <Text type="secondary" className="text-xs mt-1">限制范围：1 ~ 1024 MB</Text>
            </div>
          </Spin>
        </Card>

        {/* 区块四：操作区 */}
        <Card title="操作" style={{ borderRadius: 12 }}>
          <Space size="middle">
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveConfig} loading={configSaving}>
              保存配置
            </Button>
            <Button icon={<ApiOutlined />} onClick={handleTestConnection} loading={testing}>
              测试连接
            </Button>
          </Space>
          {testResult && (
            <Alert
              className="mt-4"
              type={testResult.success ? 'success' : 'error'}
              showIcon
              message={testResult.message}
              style={{ maxWidth: 560 }}
            />
          )}
        </Card>

        {/* 区块五：数据迁移 */}
        <Card title="数据迁移" style={{ borderRadius: 12 }}>
          <div className="flex flex-col gap-4">
            <div>
              <Button
                icon={<ScanOutlined />}
                onClick={handleScanMigration}
                loading={scanLoading}
              >
                扫描待迁移文件
              </Button>
            </div>

            {scanResult.length > 0 && (
              <>
                <Table
                  columns={scanColumns}
                  dataSource={scanResult}
                  rowKey="module"
                  pagination={false}
                  size="small"
                  style={{ maxWidth: 600 }}
                />
                <div>
                  <Button
                    type="primary"
                    icon={<RocketOutlined />}
                    onClick={handleStartMigration}
                    loading={migrating}
                    disabled={selectedModules.length === 0}
                  >
                    开始迁移
                  </Button>
                </div>
              </>
            )}

            {migrationProgress && (
              <Card size="small" style={{ maxWidth: 600, background: '#fafafa' }}>
                <div className="flex flex-col gap-3">
                  <Progress
                    percent={migrationProgress.progress_percent}
                    status={
                      migrationProgress.status === 'completed'
                        ? (migrationProgress.failed_count > 0 ? 'exception' : 'success')
                        : migrationProgress.status === 'failed'
                          ? 'exception'
                          : 'active'
                    }
                  />
                  <div className="flex gap-6 flex-wrap">
                    <Text>总数: <Text strong>{migrationProgress.total_files}</Text></Text>
                    <Text>成功: <Text strong type="success">{migrationProgress.migrated_count}</Text></Text>
                    <Text>失败: <Text strong type="danger">{migrationProgress.failed_count}</Text></Text>
                    {migrationProgress.skipped_count > 0 && (
                      <Text>跳过: <Text strong>{migrationProgress.skipped_count}</Text></Text>
                    )}
                  </div>
                  {migrationProgress.status === 'migrating' && migrationProgress.current_file && (
                    <Text type="secondary" className="text-xs" ellipsis>
                      <SyncOutlined spin className="mr-1" />
                      当前: {migrationProgress.current_file}
                    </Text>
                  )}
                  {migrationProgress.status === 'migrating' && migrationProgress.estimated_remaining_seconds != null && (
                    <Text type="secondary" className="text-xs">
                      预计剩余: {migrationProgress.estimated_remaining_seconds}秒
                    </Text>
                  )}
                  {migrationProgress.status !== 'migrating' && migrationProgress.status !== 'scanning' && (
                    <Tag color={migrationProgress.status === 'completed' && migrationProgress.failed_count === 0 ? 'green' : 'red'}>
                      {migrationProgress.status === 'completed' ? '迁移完成' : '迁移异常'}
                    </Tag>
                  )}

                  {migrationProgress.failed_count > 0 && migrationProgress.failed_items?.length > 0 && (
                    <>
                      <Table
                        columns={failedFileColumns}
                        dataSource={migrationProgress.failed_items}
                        rowKey="original_url"
                        pagination={false}
                        size="small"
                        scroll={{ y: 200 }}
                      />
                      <div>
                        <Button
                          icon={<ReloadOutlined />}
                          onClick={handleRetryFailed}
                          loading={retrying}
                          danger
                        >
                          重试失败文件
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </Card>
            )}
          </div>
        </Card>
      </div>
    </Spin>
  );

  const renderFilesTab = () => (
    <Spin spinning={filesLoading}>
      <div className="flex items-center justify-center" style={{ minHeight: 320 }}>
        <Card style={{ borderRadius: 16, textAlign: 'center', padding: '40px 60px' }}>
          <Statistic
            title="总文件数"
            value={totalFiles}
            prefix={<FileOutlined />}
            valueStyle={{ fontSize: 48, fontWeight: 700 }}
          />
          <Text type="secondary" className="block mt-4">
            数据来源：基于数据库统计，不消耗COS API流量
          </Text>
        </Card>
      </div>
    </Spin>
  );

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
            children: renderConfigTab(),
          },
          {
            key: 'files',
            label: <Space><FileOutlined />文件管理</Space>,
            children: renderFilesTab(),
          },
        ]}
      />
    </div>
  );
}
