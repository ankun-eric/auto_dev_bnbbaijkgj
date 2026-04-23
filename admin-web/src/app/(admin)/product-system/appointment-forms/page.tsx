'use client';

/**
 * 预约表单库（BUG-PRODUCT-APPT-001）
 * 管理可复用的预约表单：CRUD + 启用/停用 + 字段管理。
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  FormOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { del, get, post, put } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface AppointmentForm {
  id: number;
  name: string;
  description: string;
  status: string;
  field_count: number;
  product_count: number;
  created_at: string;
}

interface FormField {
  id: number;
  form_id: number;
  field_type: string;
  label: string;
  placeholder: string;
  required: boolean;
  options: any;
  sort_order: number;
}

const fieldTypeOptions = [
  { label: '文本输入', value: 'text' },
  { label: '数字输入', value: 'number' },
  { label: '日期选择', value: 'date' },
  { label: '时间选择', value: 'time' },
  { label: '下拉选择', value: 'select' },
  { label: '单选', value: 'radio' },
  { label: '多选', value: 'checkbox' },
  { label: '多行文本', value: 'textarea' },
  { label: '手机号', value: 'phone' },
];

export default function AppointmentFormLibraryPage() {
  const [forms, setForms] = useState<AppointmentForm[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');

  const [editVisible, setEditVisible] = useState(false);
  const [editing, setEditing] = useState<AppointmentForm | null>(null);
  const [form] = Form.useForm();

  const [fieldsVisible, setFieldsVisible] = useState(false);
  const [activeForm, setActiveForm] = useState<AppointmentForm | null>(null);
  const [fields, setFields] = useState<FormField[]>([]);
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const [fieldEditVisible, setFieldEditVisible] = useState(false);
  const [editingField, setEditingField] = useState<FormField | null>(null);
  const [fieldForm] = Form.useForm();

  const fetchForms = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/appointment-forms', {
        page: 1,
        page_size: 100,
        keyword: keyword || undefined,
      });
      setForms(res?.items || []);
    } catch (err: any) {
      setForms([]);
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    fetchForms();
  }, [fetchForms]);

  const openEdit = (f?: AppointmentForm) => {
    setEditing(f || null);
    form.resetFields();
    if (f) {
      form.setFieldsValue({
        name: f.name,
        description: f.description,
        status: f.status === 'active',
      });
    } else {
      form.setFieldsValue({ status: true });
    }
    setEditVisible(true);
  };

  const submitForm = async () => {
    try {
      const vals = await form.validateFields();
      const payload = {
        name: vals.name,
        description: vals.description || '',
        status: vals.status ? 'active' : 'inactive',
      };
      if (editing) {
        await put(`/api/admin/appointment-forms/${editing.id}`, payload);
        message.success('已更新');
      } else {
        await post('/api/admin/appointment-forms', payload);
        message.success('已创建');
      }
      setEditVisible(false);
      fetchForms();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    }
  };

  const deleteForm = async (f: AppointmentForm) => {
    try {
      await del(`/api/admin/appointment-forms/${f.id}`);
      message.success('已删除');
      fetchForms();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  // ── 字段管理 ──
  const openFields = async (f: AppointmentForm) => {
    setActiveForm(f);
    setFieldsVisible(true);
    await fetchFields(f.id);
  };

  const fetchFields = async (formId: number) => {
    setFieldsLoading(true);
    try {
      const res = await get(`/api/admin/appointment-forms/${formId}/fields`);
      setFields(res?.items || []);
    } finally {
      setFieldsLoading(false);
    }
  };

  const openFieldEdit = (field?: FormField) => {
    setEditingField(field || null);
    fieldForm.resetFields();
    if (field) {
      fieldForm.setFieldsValue({
        field_type: field.field_type,
        label: field.label,
        placeholder: field.placeholder,
        required: field.required,
        sort_order: field.sort_order,
      });
    } else {
      fieldForm.setFieldsValue({ required: false, sort_order: fields.length });
    }
    setFieldEditVisible(true);
  };

  const submitField = async () => {
    if (!activeForm) return;
    try {
      const vals = await fieldForm.validateFields();
      if (editingField) {
        await put(
          `/api/admin/appointment-forms/${activeForm.id}/fields/${editingField.id}`,
          vals,
        );
        message.success('已更新字段');
      } else {
        await post(`/api/admin/appointment-forms/${activeForm.id}/fields`, vals);
        message.success('已新增字段');
      }
      setFieldEditVisible(false);
      fetchFields(activeForm.id);
      fetchForms();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    }
  };

  const deleteField = async (field: FormField) => {
    if (!activeForm) return;
    try {
      await del(`/api/admin/appointment-forms/${activeForm.id}/fields/${field.id}`);
      message.success('已删除');
      fetchFields(activeForm.id);
      fetchForms();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    { title: '表单名称', dataIndex: 'name' },
    { title: '描述', dataIndex: 'description', ellipsis: true },
    {
      title: '字段数',
      dataIndex: 'field_count',
      width: 90,
      render: (n: number) => <Tag color="blue">{n}</Tag>,
    },
    {
      title: '引用商品数',
      dataIndex: 'product_count',
      width: 110,
      render: (n: number) => <Tag color={n > 0 ? 'green' : 'default'}>{n}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (s: string) =>
        s === 'inactive' ? <Tag color="red">已停用</Tag> : <Tag color="green">启用中</Tag>,
    },
    {
      title: '操作',
      width: 260,
      render: (_: any, record: AppointmentForm) => (
        <Space size="small">
          <Button size="small" icon={<FormOutlined />} onClick={() => openFields(record)}>
            字段
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确定删除这张表单？"
            description={
              record.product_count > 0
                ? `已被 ${record.product_count} 个商品引用，无法删除，需先解绑`
                : '删除后不可恢复'
            }
            disabled={record.product_count > 0}
            onConfirm={() => deleteForm(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} disabled={record.product_count > 0}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>预约表单库</Title>
        <Space>
          <Input
            placeholder="搜索表单名称"
            prefix={<SearchOutlined />}
            allowClear
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onPressEnter={fetchForms}
            style={{ width: 240 }}
          />
          <Button onClick={fetchForms}>查询</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit()}>
            新建表单
          </Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={forms}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      {/* 表单基础信息编辑 */}
      <Modal
        title={editing ? '编辑表单' : '新建表单'}
        open={editVisible}
        onCancel={() => setEditVisible(false)}
        onOk={submitForm}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="表单名称"
            name="name"
            rules={[{ required: true, message: '请输入表单名称' }, { max: 100 }]}
          >
            <Input placeholder="例如：中医理疗预约表" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <TextArea rows={3} maxLength={500} placeholder="该表单适用场景 / 字段说明" />
          </Form.Item>
          <Form.Item label="启用" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 字段管理 */}
      <Modal
        title={`字段管理 - ${activeForm?.name || ''}`}
        open={fieldsVisible}
        onCancel={() => setFieldsVisible(false)}
        footer={null}
        width={800}
        destroyOnClose
      >
        <div style={{ marginBottom: 12, textAlign: 'right' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openFieldEdit()}>
            新增字段
          </Button>
        </div>
        <Table
          dataSource={fields}
          rowKey="id"
          loading={fieldsLoading}
          pagination={false}
          columns={[
            { title: '排序', dataIndex: 'sort_order', width: 60 },
            { title: '标签', dataIndex: 'label' },
            {
              title: '类型',
              dataIndex: 'field_type',
              render: (v: string) => fieldTypeOptions.find(o => o.value === v)?.label || v,
            },
            {
              title: '必填',
              dataIndex: 'required',
              width: 80,
              render: (v: boolean) => (v ? <Tag color="red">是</Tag> : <Tag>否</Tag>),
            },
            {
              title: '操作',
              width: 160,
              render: (_: any, field: FormField) => (
                <Space size="small">
                  <Button size="small" onClick={() => openFieldEdit(field)}>
                    编辑
                  </Button>
                  <Popconfirm title="删除该字段？" onConfirm={() => deleteField(field)}>
                    <Button size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Modal>

      {/* 字段编辑 */}
      <Modal
        title={editingField ? '编辑字段' : '新增字段'}
        open={fieldEditVisible}
        onCancel={() => setFieldEditVisible(false)}
        onOk={submitField}
        destroyOnClose
      >
        <Form form={fieldForm} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="字段类型" name="field_type" rules={[{ required: true }]}>
                <Select options={fieldTypeOptions} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="排序" name="sort_order">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="字段标签" name="label" rules={[{ required: true }]}>
            <Input placeholder="例如：姓名" />
          </Form.Item>
          <Form.Item label="占位符" name="placeholder">
            <Input placeholder="例如：请输入姓名" />
          </Form.Item>
          <Form.Item label="必填" name="required" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
