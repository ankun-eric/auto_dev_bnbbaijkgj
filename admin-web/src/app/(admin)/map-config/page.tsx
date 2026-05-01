'use client';

/**
 * [2026-05-01 地图配置 PRD v1.0] 地图配置（系统管理 → 地图配置）
 *
 * 单页分区布局，从上到下：
 *   ① 地图服务商（本期固定高德）
 *   ② Key 配置（Server / Web JS / H5 JS / SecurityJsCode）
 *   ③ 默认地图参数（默认城市 / 中心点 / 缩放级别）
 *   ④ 测试连接 + 最近 5 次测试记录
 *   ⑤ 底部 [保存] [取消]
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  message,
  Row,
  Select,
  Slider,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  CheckCircleTwoTone,
  CloseCircleTwoTone,
  CopyOutlined,
  EnvironmentOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  ReloadOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { get, post, put } from '@/lib/api';

const { Title, Text, Paragraph, Link: TypographyLink } = Typography;

interface MapConfigData {
  id: number | null;
  provider: string;
  server_key: string;
  web_js_key: string;
  h5_js_key: string;
  security_js_code: string;
  default_city: string;
  default_center_lng: number;
  default_center_lat: number;
  default_zoom: number;
  has_record: boolean;
  updated_at: string | null;
  updated_by: number | null;
}

interface TestSubResult {
  status: 'ok' | 'fail';
  detail: string;
}

interface TestResponse {
  server: TestSubResult;
  web: TestSubResult;
  h5: TestSubResult;
  overall_pass: boolean;
  tested_at: string;
}

interface TestLogItem {
  id: number;
  operator_name: string | null;
  server_status: string;
  web_status: string;
  h5_status: string;
  overall_pass: boolean;
  created_at: string;
}

const STATUS_OK_ICON = <CheckCircleTwoTone twoToneColor="#52c41a" />;
const STATUS_FAIL_ICON = <CloseCircleTwoTone twoToneColor="#ff4d4f" />;

export default function MapConfigPage() {
  const [form] = Form.useForm<MapConfigData>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [hasRecord, setHasRecord] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResponse | null>(null);
  const [logs, setLogs] = useState<TestLogItem[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await get<MapConfigData>('/api/admin/map-config');
      form.setFieldsValue({
        provider: data.provider || 'amap',
        server_key: data.server_key || '',
        web_js_key: data.web_js_key || '',
        h5_js_key: data.h5_js_key || '',
        security_js_code: data.security_js_code || '',
        default_city: data.default_city || '北京',
        default_center_lng: Number(data.default_center_lng) || 116.397428,
        default_center_lat: Number(data.default_center_lat) || 39.90923,
        default_zoom: Number(data.default_zoom) || 12,
      });
      setHasRecord(!!data.has_record);
      setUpdatedAt(data.updated_at);
    } catch (e) {
      message.error('加载地图配置失败，请刷新重试');
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async () => {
    setLogsLoading(true);
    try {
      const data = await get<{ items: TestLogItem[] }>(
        '/api/admin/map-config/test-logs',
        { limit: 5 },
      );
      setLogs(data.items || []);
    } catch {
      // ignore
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
    loadLogs();
  }, []);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await put<MapConfigData>('/api/admin/map-config', values);
      message.success('地图配置已保存，全系统已生效。已打开的页面刷新后生效');
      await loadConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || '保存失败，请重试';
      message.error(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await post<TestResponse>('/api/admin/map-config/test');
      setTestResult(res);
      if (res.overall_pass) {
        message.success('全部 Key 测试通过');
      } else {
        message.warning('部分 Key 测试未通过，请查看下方结果');
      }
      await loadLogs();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '测试连接失败');
    } finally {
      setTesting(false);
    }
  };

  const copyDomain = async (which: 'web' | 'h5') => {
    try {
      // 优先使用浏览器当前域名
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const domain = origin || (await get<{ web_admin_origin: string }>(
        '/api/admin/map-config/copy-domain',
      )).web_admin_origin;
      if (!domain) {
        message.error('无法获取当前域名');
        return;
      }
      await navigator.clipboard?.writeText(domain);
      message.success(
        `${which === 'web' ? '管理后台' : 'H5 端'}域名已复制：${domain}，请到高德开放平台控制台粘贴配置白名单`,
      );
    } catch {
      message.error('复制失败，请手动复制地址栏域名');
    }
  };

  const renderTestRow = (label: string, sub: TestSubResult | undefined) => {
    if (!sub) return null;
    return (
      <div style={{ marginBottom: 6 }}>
        <Space>
          {sub.status === 'ok' ? STATUS_OK_ICON : STATUS_FAIL_ICON}
          <Text strong>{label}：</Text>
          <Text type={sub.status === 'ok' ? 'success' : 'danger'}>{sub.detail}</Text>
        </Space>
      </div>
    );
  };

  const logColumns = useMemo(
    () => [
      {
        title: '时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 180,
        render: (v: string) =>
          v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '-',
      },
      { title: '操作人', dataIndex: 'operator_name', key: 'operator_name', width: 140, render: (v: string) => v || '-' },
      {
        title: 'Server',
        dataIndex: 'server_status',
        key: 'server_status',
        width: 90,
        render: (v: string) => (v === 'ok' ? <Tag color="success">通过</Tag> : <Tag color="error">失败</Tag>),
      },
      {
        title: 'Web',
        dataIndex: 'web_status',
        key: 'web_status',
        width: 90,
        render: (v: string) => (v === 'ok' ? <Tag color="success">通过</Tag> : <Tag color="error">失败</Tag>),
      },
      {
        title: 'H5',
        dataIndex: 'h5_status',
        key: 'h5_status',
        width: 90,
        render: (v: string) => (v === 'ok' ? <Tag color="success">通过</Tag> : <Tag color="error">失败</Tag>),
      },
      {
        title: '整体',
        dataIndex: 'overall_pass',
        key: 'overall_pass',
        width: 90,
        render: (v: boolean) => (v ? <Tag color="success">通过</Tag> : <Tag color="default">未通过</Tag>),
      },
    ],
    [],
  );

  return (
    <Spin spinning={loading}>
      <div style={{ maxWidth: 960 }}>
        <Title level={3} style={{ marginBottom: 4 }}>
          <EnvironmentOutlined /> 地图配置
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          统一管理高德地图所有 Key 与默认参数。保存后全系统立即生效，无需重启。
          {hasRecord
            ? ` 当前正在使用数据库配置${updatedAt ? `（更新于 ${new Date(updatedAt).toLocaleString('zh-CN', { hour12: false })}）` : ''}。`
            : ' 当前尚未保存过配置，系统正在使用环境变量兜底，保存后将自动切换到数据库配置。'}
        </Paragraph>

        <Form form={form} layout="vertical" autoComplete="off">
          {/* ───── 区块 ① 地图服务商 ───── */}
          <Card
            title={<><EnvironmentOutlined /> 区块 ① 地图服务商</>}
            size="small"
            style={{ marginBottom: 16 }}
          >
            <Form.Item label="服务商" name="provider" initialValue="amap">
              <Select
                options={[{ value: 'amap', label: '高德地图' }]}
                style={{ maxWidth: 320 }}
                disabled
              />
            </Form.Item>
            <Text type="secondary" style={{ fontSize: 12 }}>
              本期固定为「高德地图」，后续可扩展百度地图、腾讯地图等多供应商。
            </Text>
          </Card>

          {/* ───── 区块 ② Key 配置 ───── */}
          <Card title={<>区块 ② Key 配置</>} size="small" style={{ marginBottom: 16 }}>
            <Form.Item
              label="Server Key（服务端用）"
              name="server_key"
              rules={[{ required: true, message: '请填写 Server Key' }]}
              extra={<Text type="secondary" style={{ fontSize: 12 }}>用于后端调用高德开放接口（地理编码、POI 搜索、静态地图等）。</Text>}
            >
              <Input placeholder="请输入高德 Web 服务 Key" allowClear maxLength={64} />
            </Form.Item>

            <Form.Item
              label={
                <Space>
                  <span>Web JS Key（管理后台用）</span>
                  <Tooltip title="复制当前管理后台域名，用于到高德开放平台配置 JS API 域名白名单">
                    <Button
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => copyDomain('web')}
                    >
                      复制当前管理后台域名
                    </Button>
                  </Tooltip>
                </Space>
              }
              name="web_js_key"
              rules={[{ required: true, message: '请填写 Web JS Key' }]}
              extra={
                <Text type="warning" style={{ fontSize: 12 }}>
                  ⚠ 此 Key 会下发到浏览器，请到{' '}
                  <TypographyLink href="https://console.amap.com/dev/key/app" target="_blank" rel="noopener">
                    高德开放平台控制台
                  </TypographyLink>{' '}
                  为该 Key 配置「域名白名单」，否则 Web 端会报 USERKEY_PLAT_NOMATCH。
                </Text>
              }
            >
              <Input placeholder="请输入高德 Web JS API Key" allowClear maxLength={64} />
            </Form.Item>

            <Form.Item
              label={
                <Space>
                  <span>H5 JS Key（用户端 H5 / APP / 小程序用）</span>
                  <Tooltip title="复制当前 H5 端域名，用于到高德开放平台配置 JS API 域名白名单">
                    <Button
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => copyDomain('h5')}
                    >
                      复制当前 H5 端域名
                    </Button>
                  </Tooltip>
                </Space>
              }
              name="h5_js_key"
              rules={[{ required: true, message: '请填写 H5 JS Key' }]}
              extra={
                <Text type="warning" style={{ fontSize: 12 }}>
                  ⚠ 此 Key 会下发到 H5 / APP / 小程序，请到高德开放平台控制台为该 Key 配置「域名白名单」。
                </Text>
              }
            >
              <Input placeholder="请输入高德 H5 / APP / 小程序 JS API Key" allowClear maxLength={64} />
            </Form.Item>

            <Form.Item
              label="安全密钥 SecurityJsCode"
              name="security_js_code"
              extra={<Text type="secondary" style={{ fontSize: 12 }}>与 Server Key 配套使用，仅在后端持有，不会下发到客户端。</Text>}
            >
              <Input placeholder="（可选）请输入高德安全密钥" allowClear maxLength={64} />
            </Form.Item>
          </Card>

          {/* ───── 区块 ③ 默认地图参数 ───── */}
          <Card title={<>区块 ③ 默认地图参数</>} size="small" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="默认城市" name="default_city" initialValue="北京">
                  <Input placeholder="如 北京" allowClear maxLength={50} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="默认缩放级别（3-18）"
                  name="default_zoom"
                  initialValue={12}
                  rules={[{ required: true, message: '请输入缩放级别' }]}
                >
                  <Slider min={3} max={18} marks={{ 3: '3', 12: '12', 18: '18' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="默认中心点经度"
                  name="default_center_lng"
                  initialValue={116.397428}
                  rules={[
                    { required: true, message: '请输入经度' },
                    {
                      validator: (_, v) =>
                        v >= -180 && v <= 180
                          ? Promise.resolve()
                          : Promise.reject(new Error('经度需在 -180 到 180 之间')),
                    },
                  ]}
                >
                  <InputNumber style={{ width: '100%' }} step={0.000001} precision={6} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="默认中心点纬度"
                  name="default_center_lat"
                  initialValue={39.90923}
                  rules={[
                    { required: true, message: '请输入纬度' },
                    {
                      validator: (_, v) =>
                        v >= -90 && v <= 90
                          ? Promise.resolve()
                          : Promise.reject(new Error('纬度需在 -90 到 90 之间')),
                    },
                  ]}
                >
                  <InputNumber style={{ width: '100%' }} step={0.000001} precision={6} />
                </Form.Item>
              </Col>
            </Row>
            <Text type="secondary" style={{ fontSize: 12 }}>
              用途：新建门店、用户端预约下单等场景打开地图时的默认定位。
            </Text>
          </Card>

          {/* ───── 区块 ④ 测试连接 + 历史 ───── */}
          <Card
            title={
              <Space>
                <ExperimentOutlined /> 区块 ④ 测试连接
              </Space>
            }
            size="small"
            style={{ marginBottom: 16 }}
            extra={
              <Space>
                <Button
                  type="primary"
                  icon={<ExperimentOutlined />}
                  loading={testing}
                  onClick={handleTest}
                >
                  测试连接
                </Button>
                <Tooltip title="刷新最近 5 次测试记录">
                  <Button icon={<ReloadOutlined />} onClick={loadLogs} />
                </Tooltip>
              </Space>
            }
          >
            {testing && (
              <Alert
                message="正在逐项检测 Server / Web / H5 三个 Key，单项最长等待 10 秒…"
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
            )}
            {testResult && (
              <Card
                size="small"
                style={{ marginBottom: 12, background: testResult.overall_pass ? '#f6ffed' : '#fff7e6' }}
              >
                <Text strong style={{ marginRight: 8 }}>
                  本次测试结果：
                </Text>
                {testResult.overall_pass ? (
                  <Tag color="success">全部通过</Tag>
                ) : (
                  <Tag color="warning">部分失败</Tag>
                )}
                <Divider style={{ margin: '8px 0' }} />
                {renderTestRow('Server Key（地理编码）', testResult.server)}
                {renderTestRow('Web JS Key（脚本加载）', testResult.web)}
                {renderTestRow('H5 JS Key（脚本加载）', testResult.h5)}
              </Card>
            )}

            <Divider orientation="left" plain style={{ margin: '8px 0 12px' }}>
              <HistoryOutlined /> 最近 5 次测试记录
            </Divider>
            <Table
              size="small"
              rowKey="id"
              loading={logsLoading}
              columns={logColumns as any}
              dataSource={logs}
              pagination={false}
              locale={{ emptyText: '暂无测试记录，点击右上角「测试连接」开始第一次自检' }}
            />
          </Card>

          {/* ───── 底部操作 ───── */}
          <Card size="small" style={{ marginBottom: 32 }}>
            <Space>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                loading={saving}
                onClick={handleSave}
                size="large"
              >
                保存
              </Button>
              <Button onClick={() => loadConfig()} disabled={saving} size="large">
                取消（恢复为已保存值）
              </Button>
            </Space>
            <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}>
              💡 提示：保存成功后，所有使用高德地图的位置（管理后台门店选址、用户端预约下单选门店、APP/小程序门店详情等）将立即使用新配置。
              已打开的页面/APP 因浏览器或客户端缓存，可能仍在使用旧 Key，刷新或重启后生效。
            </Paragraph>
          </Card>
        </Form>
      </div>
    </Spin>
  );
}
