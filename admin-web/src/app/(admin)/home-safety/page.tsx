'use client';

/**
 * [PRD-HOME-SAFETY-V1 2026-05-27 / PRD-HOME-SAFETY-V2 2026-05-27]
 * 智能硬件绑定 · 居家安全设备 v1.0 + 外部 API 对接 v2
 * 管理后台 · 紧急呼叫触发源管理 - 居家安全设备
 *
 * 4 个 Tab：
 *  1. 设备类型字典（只读展示）
 *  2. 设备绑定流水
 *  3. 报警记录流水（v2: 新增 网关 SN / 厂商消息 ID / AI 外呼状态 三列）
 *  4. 回调地址配置（v2: 字段拆分 + 二次确认弹窗 + Token 密文 + 推送历史 + 未保存提示）
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
  Modal,
  Tooltip,
  Alert,
  Drawer,
  DatePicker,
  Select,
  Spin,
} from 'antd';
import { ReloadOutlined, EyeOutlined, EyeInvisibleOutlined, SaveOutlined, SendOutlined, AuditOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
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
            render: (v: number, r: any) => {
              // [PRD-HOME-SAFETY-V2] AI 外呼降级显示
              const status = r.notify_ai_call_status;
              const reason = r.notify_ai_call_fail_reason;
              if (status === 'failed') {
                return (
                  <Tooltip title={reason || '未知原因'}>
                    <Tag color="red">失败</Tag>
                  </Tooltip>
                );
              }
              if (status === 'success') return <Tag color="green">成功</Tag>;
              return (
                <Tag color={v === 2 ? 'green' : v === 3 ? 'red' : v === 1 ? 'blue' : 'default'}>
                  {v === 0 ? '未发起' : v === 1 ? '已发起待回调' : v === 2 ? '成功' : '失败'}
                </Tag>
              );
            },
          },
          // [PRD-HOME-SAFETY-V2 2026-05-27] 新增列：网关 SN
          {
            title: '网关 SN',
            dataIndex: 'gw_id',
            width: 140,
            render: (v: string) => v || '-',
          },
          // [PRD-HOME-SAFETY-V2 2026-05-27] 新增列：厂商消息 ID
          {
            title: '厂商消息 ID',
            dataIndex: 'vendor_msg_id',
            width: 200,
            ellipsis: true,
            render: (v: string) => v || '-',
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

// [PRD-HOME-SAFETY-V2 2026-05-27] 回调地址配置 Tab v2
const FIXED_CALLBACK_PATH = '/api/home_safety/callback/alarm';

function buildFullUrl(base?: string, path?: string) {
  const b = (base || '').trim().replace(/\/+$/, '');
  let p = (path || '').trim();
  if (p && !p.startsWith('/')) p = '/' + p;
  if (!b && !p) return '';
  return `${b}${p}`;
}

function CallbackConfigTab() {
  const [form] = Form.useForm();
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [previewUpstream, setPreviewUpstream] = useState('');
  const [previewCallback, setPreviewCallback] = useState('');

  const recalcPreviews = useCallback(() => {
    const v = form.getFieldsValue();
    setPreviewUpstream(buildFullUrl(v.upstream_base_url, v.upstream_path));
    setPreviewCallback(buildFullUrl(v.callback_domain, FIXED_CALLBACK_PATH));
  }, [form]);

  const load = useCallback(async () => {
    try {
      const d: any = await get('/api/admin/home_safety/callback_config');
      setData(d);
      form.setFieldsValue({
        org_id: d.org_id || '',
        upstream_base_url: d.upstream_base_url || '',
        upstream_path: d.upstream_path || '/treatment/api/setMsgCallBackUrl',
        auth_token: d.auth_token || '',
        callback_domain: d.callback_domain || '',
      });
      setTimeout(recalcPreviews, 0);
      setDirty(false);
    } catch (e: any) {
      message.error('加载失败');
    }
  }, [form, recalcPreviews]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const r: any = await get('/api/admin/home_safety/callback_config/push_history?limit=3');
      setHistory(r.items || []);
    } catch (e) {
      // 加载失败不阻塞主流程
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadHistory();
  }, [load, loadHistory]);

  // [F6] 未保存离开提示：监听 beforeunload
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = '您有未保存的修改，确认离开吗？';
      return e.returnValue;
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const onFormChange = () => {
    setDirty(true);
    recalcPreviews();
  };

  const onSave = async () => {
    const values = await form.validateFields();
    setLoading(true);
    try {
      // [F2] 仅写本地，不调上游
      await put('/api/admin/home_safety/callback_config', {
        org_id: values.org_id,
        upstream_base_url: values.upstream_base_url,
        upstream_path: values.upstream_path,
        auth_token: values.auth_token,
        callback_domain: values.callback_domain,
      });
      message.success('保存成功');
      setDirty(false);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setLoading(false);
    }
  };

  // [BUGFIX V2-REVISION 修复 3] 真正执行推送
  const doPush = async () => {
    setPushing(true);
    try {
      const r: any = await post('/api/admin/home_safety/callback_config/push_upstream', {});
      if (r.status === 'success') {
        message.success('推送成功');
      } else {
        message.error(r.message || '推送失败');
      }
      load();
      loadHistory();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '推送失败');
    } finally {
      setPushing(false);
    }
  };

  // [F3 + BUGFIX V2-REVISION] 推送到上游 - 先自检再二次确认弹窗
  const onPush = async () => {
    if (dirty) {
      Modal.warning({ title: '请先保存', content: '您有未保存的修改，请先点击「保存配置」后再推送。' });
      return;
    }
    const fullUpstream = data.full_upstream_url || buildFullUrl(data.upstream_base_url, data.upstream_path);
    const fullCallback = data.full_callback_url || buildFullUrl(data.callback_domain, data.callback_path || FIXED_CALLBACK_PATH);
    if (!fullUpstream || !fullCallback || !data.org_id) {
      Modal.error({ title: '配置不完整', content: '请确认上游完整 URL、回调完整 URL、机构 ID 均已填写并保存。' });
      return;
    }

    // [BUGFIX V2-REVISION 修复 3] 第一步：执行自检
    const precheckMsg = message.loading('正在执行回调地址自检（5 项）...', 0);
    let precheck: any = null;
    try {
      precheck = await post('/api/admin/home_safety/callback_config/precheck', {});
    } catch (e: any) {
      precheckMsg();
      message.error('自检失败：' + (e?.response?.data?.detail || '未知错误'));
      return;
    }
    precheckMsg();

    const checks: any[] = precheck?.checks || [];
    const blocked = !!precheck?.blocked;

    // 渲染自检结果列表
    const checkIcon = (s: string) => (s === 'pass' ? '✅' : s === 'warn' ? '⚠️' : '❌');
    const checkColor = (s: string) => (s === 'pass' ? '#52c41a' : s === 'warn' ? '#faad14' : '#ff4d4f');

    Modal.confirm({
      width: 640,
      icon: <SafetyCertificateOutlined />,
      title: '回调地址自检结果',
      content: (
        <div>
          <div style={{ marginBottom: 8, color: '#666' }}>{precheck?.summary || ''}</div>
          <ul style={{ margin: '8px 0 16px 0', paddingLeft: 16 }}>
            {checks.map((c: any, i: number) => (
              <li key={i} style={{ color: checkColor(c.status), marginBottom: 4 }}>
                <span>{checkIcon(c.status)} </span>
                <strong>{c.name}</strong>
                {c.detail ? <span style={{ color: '#888', marginLeft: 8 }}>— {c.detail}</span> : null}
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 12 }}><strong>完整推送内容：</strong></p>
          <p style={{ wordBreak: 'break-all', color: '#1677ff', margin: '4px 0' }}>
            上游 URL: {fullUpstream}
          </p>
          <p style={{ wordBreak: 'break-all', color: '#52c41a', margin: '4px 0' }}>
            回调 URL: {fullCallback}
          </p>
          {blocked && (
            <p style={{ color: '#ff4d4f' }}>
              ❌ 自检发现阻断错误（如 URL 格式不合法），请修正后再尝试推送。
            </p>
          )}
          {!blocked && checks.some((c: any) => c.status === 'warn') && (
            <p style={{ color: '#fa541c' }}>
              ⚠️ 自检存在告警项，可能影响实际链路。如确认无误，可点击「仍要推送」。
            </p>
          )}
          <p style={{ color: '#fa541c', marginTop: 8 }}>
            ⚠️ 厂商对同一机构(deptId)只保留 1 个回调地址，本次操作将<strong>覆盖</strong>上一次的设置。
          </p>
        </div>
      ),
      okText: precheck?.success ? '自检通过，确认推送' : '仍要推送',
      cancelText: '取消',
      okButtonProps: { danger: blocked, disabled: blocked },
      onOk: async () => {
        if (blocked) return;
        await doPush();
      },
    });
  };

  return (
    <Card title="回调地址配置">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="本页用于配置和推送「我方接收告警的回调地址」给设备厂商云端"
        description="厂商对同一个机构(deptId)只保留 1 个回调地址，再次推送即覆盖。保存与推送分离，保存仅写本地，推送才会真实调用上游。"
      />
      <Form
        layout="vertical"
        form={form}
        style={{ maxWidth: 720 }}
        onValuesChange={onFormChange}
      >
        <Typography.Title level={5} style={{ marginBottom: 8 }}>上游接口参数</Typography.Title>
        <Form.Item
          label="上游基础地址"
          name="upstream_base_url"
          rules={[{ required: true, message: '请填写上游基础地址' }]}
        >
          <Input placeholder="http://119.3.169.29" />
        </Form.Item>
        <Form.Item
          label="上游接口路径"
          name="upstream_path"
          rules={[{ required: true, message: '请填写上游接口路径' }]}
        >
          <Input placeholder="/treatment/api/setMsgCallBackUrl" />
        </Form.Item>
        <Form.Item label="完整上游 URL（自动拼接）">
          <Input value={previewUpstream} readOnly style={{ background: '#f5f5f5' }} />
        </Form.Item>
        <Form.Item
          label="机构 ID（deptId）"
          name="org_id"
          rules={[{ required: true, message: '请填写机构 ID' }]}
        >
          <Input placeholder="your_dept_id" />
        </Form.Item>
        <Form.Item
          label="鉴权 Token"
          name="auth_token"
          rules={[{ required: true, message: '请填写鉴权 Token' }]}
        >
          <Input.Password
            placeholder="eyJh****IUzI"
            visibilityToggle={{
              visible: showToken,
              onVisibleChange: setShowToken,
            }}
            iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
          />
        </Form.Item>

        <Typography.Title level={5} style={{ marginTop: 16, marginBottom: 8 }}>我方回调地址</Typography.Title>
        <Form.Item
          label="回调域名"
          name="callback_domain"
          rules={[{ required: true, message: '请填写回调域名' }]}
        >
          <Input placeholder="https://your-domain.com" />
        </Form.Item>
        <Form.Item label="回调路径（固定）">
          <Input value={FIXED_CALLBACK_PATH} readOnly style={{ background: '#f5f5f5' }} />
        </Form.Item>
        <Form.Item label="完整回调 URL（自动拼接）">
          <Input value={previewCallback} readOnly style={{ background: '#f5f5f5' }} />
        </Form.Item>

        <Space>
          <Button icon={<SaveOutlined />} type="primary" loading={loading} onClick={onSave}>
            保存配置
          </Button>
          <Button icon={<SendOutlined />} type="default" danger loading={pushing} onClick={onPush}>
            推送到上游
          </Button>
          {dirty && <Tag color="orange">有未保存的修改</Tag>}
        </Space>
      </Form>

      <Typography.Title level={5} style={{ marginTop: 24 }}>最近一次推送结果</Typography.Title>
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="推送时间">{formatDateTime(data.last_pushed_at)}</Descriptions.Item>
        <Descriptions.Item label="推送状态">
          {data.last_push_status === 'success' ? (
            <Tag color="success">✅ 成功</Tag>
          ) : data.last_push_status === 'fail' ? (
            <Tag color="error">❌ 失败</Tag>
          ) : (
            '-'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="推送 URL">{data.last_push_url || '-'}</Descriptions.Item>
        <Descriptions.Item label={
          <Tooltip title="上游真实返回的 code，原样透传，不做任何二次转译">
            上游返回码 <span style={{color: '#999'}}>ⓘ</span>
          </Tooltip>
        }>
          {data.last_push_code ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label="上游消息">{data.last_push_message || '-'}</Descriptions.Item>
        <Descriptions.Item label={
          <Tooltip title="后端如何判定本次推送的成功/失败：HTTP 状态、code 白名单、message 白名单的命中情况">
            判定依据 <span style={{color: '#999'}}>ⓘ</span>
          </Tooltip>
        }>
          <span style={{ color: '#666', fontSize: 12 }}>
            {data.last_push_judge_basis || '-'}
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="上游原始响应">
          {data.last_push_raw ? (
            <pre style={{ maxHeight: 200, overflow: 'auto', background: '#fafafa', padding: 8, margin: 0 }}>
              {data.last_push_raw}
            </pre>
          ) : (
            '-'
          )}
        </Descriptions.Item>
      </Descriptions>

      <Typography.Title level={5} style={{ marginTop: 24 }}>
        推送历史（最近 3 次）
        <Button
          size="small"
          icon={<ReloadOutlined />}
          style={{ marginLeft: 12 }}
          onClick={loadHistory}
          loading={historyLoading}
        >
          刷新
        </Button>
      </Typography.Title>
      <Table
        rowKey="id"
        loading={historyLoading}
        dataSource={history}
        pagination={false}
        size="small"
        columns={[
          { title: '时间', dataIndex: 'pushed_at', width: 180, render: (v: string) => formatDateTime(v) },
          { title: '推送 URL', dataIndex: 'pushed_url', ellipsis: true },
          { title: '操作人', dataIndex: 'operator_username', width: 120 },
          {
            title: '状态',
            dataIndex: 'status',
            width: 90,
            render: (v: string) =>
              v === 'success' ? <Tag color="success">✅ 成功</Tag> : <Tag color="error">❌ 失败</Tag>,
          },
          { title: '上游消息', dataIndex: 'upstream_message', ellipsis: true },
        ]}
      />
    </Card>
  );
}

// ────────── [BUGFIX V2-REVISION 2026-05-28] Tab5：回调原始记录 ──────────
const PARSE_STATUS_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'ok', label: '✅ 成功' },
  { value: 'pending', label: '⏳ 处理中' },
  { value: 'duplicate', label: '🔁 重复' },
  { value: 'unbound', label: '🚫 未绑定' },
  { value: 'unsupported_type', label: '⚠️ 类型不支持' },
  { value: 'unknown_devtype', label: '⚠️ 设备类型未知' },
  { value: 'missing_field', label: '⚠️ 字段缺失' },
  { value: 'parse_fail', label: '❌ JSON 解析失败' },
  { value: 'fail', label: '❌ 失败' },
  { value: 'internal_error', label: '💥 内部异常' },
  { value: 'precheck', label: '🛠️ 自检' },
];

function ParseStatusTag({ s }: { s: string }) {
  const map: Record<string, { color: string; text: string }> = {
    ok: { color: 'success', text: '✅ ok' },
    pending: { color: 'processing', text: '⏳ pending' },
    duplicate: { color: 'cyan', text: '🔁 duplicate' },
    unbound: { color: 'gold', text: '🚫 unbound' },
    unsupported_type: { color: 'orange', text: '⚠️ unsupported_type' },
    unknown_devtype: { color: 'orange', text: '⚠️ unknown_devtype' },
    missing_field: { color: 'orange', text: '⚠️ missing_field' },
    parse_fail: { color: 'error', text: '❌ parse_fail' },
    fail: { color: 'error', text: '❌ fail' },
    internal_error: { color: 'red', text: '💥 internal_error' },
    precheck: { color: 'purple', text: '🛠️ precheck' },
  };
  const it = map[s] || { color: 'default', text: s };
  return <Tag color={it.color}>{it.text}</Tag>;
}

function CallbackLogTab() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);

  const [filters, setFilters] = useState<{
    parse_status: string;
    device_sn: string;
    source_ip: string;
    keyword: string;
    start_at?: string;
    end_at?: string;
  }>({
    parse_status: 'all',
    device_sn: '',
    source_ip: '',
    keyword: '',
  });

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [detail, setDetail] = useState<any>(null);

  const load = useCallback(
    async (p: number = page, s: number = size, f = filters) => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        params.set('page', String(p));
        params.set('size', String(s));
        if (f.parse_status && f.parse_status !== 'all') params.set('parse_status', f.parse_status);
        if (f.device_sn) params.set('device_sn', f.device_sn);
        if (f.source_ip) params.set('source_ip', f.source_ip);
        if (f.keyword) params.set('keyword', f.keyword);
        if (f.start_at) params.set('start_at', f.start_at);
        if (f.end_at) params.set('end_at', f.end_at);
        const data: any = await get(`/api/admin/home_safety/callback_log?${params.toString()}`);
        setItems(data.items || []);
        setTotal(data.total || 0);
      } catch (e: any) {
        message.error('加载失败：' + (e?.response?.data?.detail || ''));
      } finally {
        setLoading(false);
      }
    },
    [page, size, filters]
  );

  useEffect(() => {
    load(1, size, filters);
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSearch = () => {
    setPage(1);
    load(1, size, filters);
  };

  const openDetail = async (id: number) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    setDetail(null);
    try {
      const d: any = await get(`/api/admin/home_safety/callback_log/${id}`);
      setDetail(d);
    } catch (e: any) {
      message.error('加载详情失败');
    } finally {
      setDrawerLoading(false);
    }
  };

  return (
    <Card
      title={
        <span>
          <AuditOutlined /> 回调原始记录
        </span>
      }
      extra={
        <Button icon={<ReloadOutlined />} onClick={() => load(page, size, filters)} loading={loading}>
          刷新
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="本页展示厂商云端推送给我方的所有原始回调流水，包括解析成功、重复、未绑定、字段缺失、不支持类型等全部场景，便于审计是否有回调以及回调内容是否正确。"
      />

      {/* 筛选区 */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          style={{ width: 180 }}
          value={filters.parse_status}
          options={PARSE_STATUS_OPTIONS}
          onChange={(v) => setFilters({ ...filters, parse_status: v })}
        />
        <Input
          placeholder="设备 SN（模糊）"
          allowClear
          style={{ width: 180 }}
          value={filters.device_sn}
          onChange={(e) => setFilters({ ...filters, device_sn: e.target.value })}
        />
        <Input
          placeholder="来源 IP（精确）"
          allowClear
          style={{ width: 160 }}
          value={filters.source_ip}
          onChange={(e) => setFilters({ ...filters, source_ip: e.target.value })}
        />
        <Input
          placeholder="关键字（在请求体中搜索）"
          allowClear
          style={{ width: 240 }}
          value={filters.keyword}
          onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
        />
        <Button type="primary" onClick={onSearch}>
          查询
        </Button>
        <Button
          onClick={() => {
            const f = { parse_status: 'all', device_sn: '', source_ip: '', keyword: '' };
            setFilters(f);
            setPage(1);
            load(1, size, f);
          }}
        >
          重置
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        scroll={{ x: 1200 }}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: true,
          onChange: (p, s) => {
            setPage(p);
            setSize(s);
            load(p, s, filters);
          },
        }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 80 },
          {
            title: '接收时间',
            dataIndex: 'received_at',
            width: 180,
            render: (v: string) => formatDateTime(v),
          },
          { title: '来源 IP', dataIndex: 'source_ip', width: 140 },
          {
            title: '解析状态',
            dataIndex: 'parse_status',
            width: 160,
            render: (v: string) => <ParseStatusTag s={v} />,
          },
          { title: '设备 SN', dataIndex: 'device_sn', width: 120, render: (v) => v || '-' },
          {
            title: '厂商消息 ID',
            dataIndex: 'vendor_msg_id',
            width: 200,
            ellipsis: true,
            render: (v) => v || '-',
          },
          {
            title: '失败原因',
            dataIndex: 'parse_fail_reason',
            ellipsis: true,
            render: (v) => v || '-',
          },
          {
            title: '响应',
            dataIndex: 'response_status',
            width: 90,
            render: (v) => v ?? '-',
          },
          {
            title: '操作',
            width: 90,
            fixed: 'right' as const,
            render: (_: any, r: any) => (
              <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openDetail(r.id)}>
                查看
              </Button>
            ),
          },
        ]}
      />

      <Drawer
        title={
          <span>
            <AuditOutlined /> 回调记录详情 #{detail?.id || ''}
          </span>
        }
        width={720}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {drawerLoading ? (
          <Spin />
        ) : detail ? (
          <div>
            <Descriptions bordered column={1} size="small" title="基本信息">
              <Descriptions.Item label="接收时间">{formatDateTime(detail.received_at)}</Descriptions.Item>
              <Descriptions.Item label="处理完成">{formatDateTime(detail.processed_at)}</Descriptions.Item>
              <Descriptions.Item label="来源 IP">{detail.source_ip || '-'}</Descriptions.Item>
              <Descriptions.Item label="请求方法">{detail.request_method || '-'}</Descriptions.Item>
              <Descriptions.Item label="请求 URL">
                <span style={{ wordBreak: 'break-all' }}>{detail.request_url || '-'}</span>
              </Descriptions.Item>
              <Descriptions.Item label="解析状态">
                <ParseStatusTag s={detail.parse_status || ''} />
              </Descriptions.Item>
              <Descriptions.Item label="失败原因">{detail.parse_fail_reason || '-'}</Descriptions.Item>
              <Descriptions.Item label="设备 SN">{detail.device_sn || '-'}</Descriptions.Item>
              <Descriptions.Item label="厂商消息 ID">{detail.vendor_msg_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="关联告警 ID">
                {detail.linked_alarm_id ? (
                  <Tag color="blue">#{detail.linked_alarm_id}</Tag>
                ) : (
                  '-'
                )}
              </Descriptions.Item>
              <Descriptions.Item label="我方响应">
                HTTP {detail.response_status ?? '-'}
              </Descriptions.Item>
            </Descriptions>

            <Typography.Title level={5} style={{ marginTop: 16 }}>请求 Headers</Typography.Title>
            <pre
              style={{
                maxHeight: 200,
                overflow: 'auto',
                background: '#fafafa',
                padding: 8,
                fontSize: 12,
              }}
            >
              {JSON.stringify(detail.request_headers || {}, null, 2)}
            </pre>

            <Typography.Title level={5} style={{ marginTop: 16 }}>请求 Body（原始）</Typography.Title>
            <pre
              style={{
                maxHeight: 240,
                overflow: 'auto',
                background: '#fafafa',
                padding: 8,
                fontSize: 12,
              }}
            >
              {detail.request_body || '(空)'}
            </pre>

            <Typography.Title level={5} style={{ marginTop: 16 }}>字段映射对照</Typography.Title>
            <Table
              size="small"
              rowKey={(r: any) => r.vendor}
              dataSource={detail.field_mapping || []}
              pagination={false}
              columns={[
                { title: '厂商字段', dataIndex: 'vendor', width: 180 },
                { title: '我方字段', dataIndex: 'ours', width: 160 },
                {
                  title: '落库值',
                  dataIndex: 'value',
                  render: (v: any) => (v === null || v === undefined || v === '' ? '-' : String(v)),
                },
              ]}
            />

            <Typography.Title level={5} style={{ marginTop: 16 }}>我方响应 Body</Typography.Title>
            <pre
              style={{
                maxHeight: 160,
                overflow: 'auto',
                background: '#fafafa',
                padding: 8,
                fontSize: 12,
              }}
            >
              {detail.response_body || '(空)'}
            </pre>
          </div>
        ) : null}
      </Drawer>
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
          { key: 'log', label: '回调原始记录', children: <CallbackLogTab /> },
        ]}
      />
    </div>
  );
}
