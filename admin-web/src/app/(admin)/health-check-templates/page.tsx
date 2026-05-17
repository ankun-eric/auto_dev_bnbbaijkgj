'use client';

/**
 * [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 管理后台 · 健康自查问卷模板页面。
 *
 * - 列表：模板名称 / 引用按钮数 / 状态 / 最后更新时间 / 操作
 * - 编辑页：基本信息 + 部位选择(多选) + 持续时间档位(标签输入) + 默认 Prompt + 启用
 * - 右侧：占位符速查表
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input,
  Typography, message, Select, Tooltip, Card, Row, Col,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import { formatDateTime } from '@/lib/datetime';

const { Title, Text } = Typography;
const { TextArea } = Input;

const PLACEHOLDER_LIST = [
  { key: '{档案信息}', desc: '完整档案摘要（必含）' },
  { key: '{档案年龄}', desc: '档案年龄' },
  { key: '{档案性别}', desc: '档案性别' },
  { key: '{档案既往病史}', desc: '既往病史' },
  { key: '{档案过敏史}', desc: '过敏史' },
  { key: '{部位}', desc: '自查选定的部位（必含）' },
  { key: '{症状列表}', desc: '症状列表（必含）' },
  { key: '{持续时间}', desc: '持续时间档位（必含）' },
];

const REQUIRED_PLACEHOLDERS = ['{档案信息}', '{部位}', '{症状列表}', '{持续时间}'];

const DEFAULT_DURATIONS = ['<1天', '1-3天', '3-7天', '>1周', '>1月'];

interface BodyPart {
  id: number;
  name: string;
  icon: string;
  enabled: boolean;
}

interface Template {
  id: number;
  name: string;
  description?: string;
  body_parts: { id: number; sort: number }[];
  duration_options: string[];
  default_prompt: string;
  enabled: boolean;
  reference_button_count: number;
  created_at?: string;
  updated_at?: string;
}

export default function HealthCheckTemplatesPage() {
  const [items, setItems] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [bodyParts, setBodyParts] = useState<BodyPart[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/health-check-templates', { page, page_size: pageSize });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch {
      message.error('获取问卷模板失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  const fetchBodyParts = useCallback(async () => {
    try {
      const res = await get<any>('/api/admin/body-part-dict', { page: 1, page_size: 200, enabled: true });
      setBodyParts(res.items || []);
    } catch {
      setBodyParts([]);
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchBodyParts();
  }, [fetchData, fetchBodyParts]);

  const openModal = (record?: Template) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        name: record.name,
        description: record.description || '',
        body_parts: (record.body_parts || []).map((p) => p.id),
        duration_options: record.duration_options || [],
        default_prompt: record.default_prompt || '',
        enabled: record.enabled,
      });
    } else {
      form.setFieldsValue({
        name: '',
        description: '',
        body_parts: [],
        duration_options: DEFAULT_DURATIONS,
        default_prompt: '',
        enabled: true,
      });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (!values.body_parts || values.body_parts.length === 0) {
        message.warning('请至少勾选 1 个部位');
        return;
      }
      if (!values.duration_options || values.duration_options.length < 2) {
        message.warning('持续时间档位至少 2 档');
        return;
      }
      // Prompt 必含占位符校验
      const missing = REQUIRED_PLACEHOLDERS.filter((p) => !(values.default_prompt || '').includes(p));
      if (missing.length > 0) {
        const ok = await new Promise<boolean>((resolve) => {
          Modal.confirm({
            title: 'Prompt 缺少必含占位符',
            content: `检测到缺少：${missing.join('、')}，是否仍要保存？`,
            okText: '仍要保存',
            cancelText: '返回修改',
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
          });
        });
        if (!ok) return;
      }
      setSaving(true);
      const payload = {
        name: values.name,
        description: values.description || null,
        body_parts: (values.body_parts as number[]).map((id, idx) => ({ id, sort: idx + 1 })),
        duration_options: values.duration_options,
        default_prompt: values.default_prompt,
        enabled: !!values.enabled,
      };
      if (editing) {
        await put(`/api/admin/health-check-templates/${editing.id}`, payload);
        message.success('模板更新成功');
      } else {
        await post('/api/admin/health-check-templates', payload);
        message.success('模板创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (record: Template) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除模板「${record.name}」吗？被按钮引用时无法删除。`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await del(`/api/admin/health-check-templates/${record.id}`);
          message.success('删除成功');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const toggleEnabled = async (record: Template, checked: boolean) => {
    try {
      await put(`/api/admin/health-check-templates/${record.id}`, { enabled: checked });
      message.success(checked ? '已启用' : '已停用');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '状态更新失败');
    }
  };

  const columns = [
    { title: '模板 ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: '模板名称', dataIndex: 'name', key: 'name', width: 200 },
    {
      title: '部位数', key: 'parts_count', width: 80,
      render: (_: any, r: Template) => <Tag color="blue">{(r.body_parts || []).length}</Tag>,
    },
    {
      title: '档位数', key: 'durations', width: 80,
      render: (_: any, r: Template) => <Tag>{(r.duration_options || []).length}</Tag>,
    },
    {
      title: '引用按钮', dataIndex: 'reference_button_count', key: 'reference_button_count', width: 100,
      render: (n: number) => <Tag color={n > 0 ? 'green' : 'default'}>{n}</Tag>,
    },
    {
      title: '启用状态', dataIndex: 'enabled', key: 'enabled', width: 120,
      render: (v: boolean, r: Template) => (
        <Switch checked={v} checkedChildren="启用" unCheckedChildren="停用"
          onChange={(c) => toggleEnabled(r, c)} />
      ),
    },
    { title: '最后更新', dataIndex: 'updated_at', key: 'updated_at', width: 180,
      render: (v?: string) => v ? formatDateTime(v) : '-' },
    {
      title: '操作', key: 'action', width: 160,
      render: (_: any, r: Template) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openModal(r)}>编辑</Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>健康自查问卷模板</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>
          新增模板
        </Button>
        <Text type="secondary" style={{ marginLeft: 12 }}>
          模板可被多个功能按钮（type=health_self_check）引用
        </Text>
      </div>
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page, pageSize, total,
          showSizeChanger: true, showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
        scroll={{ x: 1100 }}
      />
      <Modal
        title={editing ? '编辑问卷模板' : '新增问卷模板'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={900}
      >
        <Row gutter={16}>
          <Col span={16}>
            <Form form={form} layout="vertical">
              <Form.Item
                label="模板名称"
                name="name"
                rules={[{ required: true, message: '请输入模板名称' }, { max: 30, message: '最多 30 字' }]}
              >
                <Input placeholder="例：通用健康自查、老人专版自查" maxLength={30} />
              </Form.Item>
              <Form.Item label="模板描述" name="description">
                <Input placeholder="内部备注（可选）" maxLength={200} />
              </Form.Item>
              <Form.Item
                label="部位选择"
                name="body_parts"
                rules={[{ required: true, message: '请至少勾选 1 个部位' }]}
                extra="勾选顺序即用户端展示顺序"
              >
                <Select
                  mode="multiple"
                  placeholder="请选择部位"
                  options={bodyParts
                    .filter((b) => b.enabled)
                    .map((b) => ({ value: b.id, label: `${b.icon} ${b.name}` }))}
                  showSearch
                  filterOption={(input, option) =>
                    String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                  }
                />
              </Form.Item>
              <Form.Item
                label="持续时间档位"
                name="duration_options"
                rules={[{ required: true, message: '请输入至少 2 档持续时间' }]}
                extra="回车追加；至少 2 档；推荐 4~5 档"
              >
                <Select
                  mode="tags"
                  placeholder="例：<1天 1-3天 3-7天 >1周 >1月"
                  tokenSeparators={[',', '，']}
                />
              </Form.Item>
              <Form.Item
                label="默认 Prompt 模板"
                name="default_prompt"
                rules={[{ required: true, message: '请输入 Prompt 模板' }]}
                extra="使用右侧速查表中的占位符；保存时校验必含 4 项"
              >
                <TextArea rows={10} placeholder="例：你是一名专业的全科医生助手……" />
              </Form.Item>
              <Form.Item label="启用状态" name="enabled" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
            </Form>
          </Col>
          <Col span={8}>
            <Card size="small" title="📌 占位符速查表" style={{ position: 'sticky', top: 0 }}>
              {PLACEHOLDER_LIST.map((p) => (
                <div key={p.key} style={{ marginBottom: 8 }}>
                  <Tooltip title={p.desc}>
                    <Tag
                      color={REQUIRED_PLACEHOLDERS.includes(p.key) ? 'red' : 'blue'}
                      style={{ cursor: 'pointer' }}
                      onClick={() => {
                        const cur = form.getFieldValue('default_prompt') || '';
                        form.setFieldsValue({ default_prompt: cur + p.key });
                      }}
                    >
                      {p.key} {REQUIRED_PLACEHOLDERS.includes(p.key) ? '★' : ''}
                    </Tag>
                  </Tooltip>
                  <Text type="secondary" style={{ fontSize: 12 }}>{p.desc}</Text>
                </div>
              ))}
              <Text type="warning" style={{ fontSize: 12 }}>
                ★ 为必含占位符（保存时校验）
              </Text>
            </Card>
          </Col>
        </Row>
      </Modal>
    </div>
  );
}
