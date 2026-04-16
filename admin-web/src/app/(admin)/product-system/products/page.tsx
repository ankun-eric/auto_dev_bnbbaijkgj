'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, message,
  Typography, Tag, Popconfirm, Row, Col, DatePicker, Tabs, Divider,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SearchOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload } from '@/lib/api';
import dayjs from 'dayjs';
import type { UploadFile, RcFile } from 'antd/es/upload/interface';

const { Title } = Typography;
const { TextArea } = Input;

interface Product {
  id: number;
  name: string;
  category_id: number;
  fulfillment_type: string;
  original_price: number;
  sale_price: number;
  images: string[];
  video_url: string;
  description: string;
  symptom_tags: string[];
  stock: number;
  valid_start_date: string | null;
  valid_end_date: string | null;
  points_exchangeable: boolean;
  points_price: number;
  points_deductible: boolean;
  redeem_count: number;
  appointment_mode: string;
  purchase_appointment_mode: string | null;
  custom_form_id: number | null;
  faq: any;
  recommend_weight: number;
  sales_count: number;
  status: string;
  sort_order: number;
  payment_timeout_minutes: number;
  created_at: string;
  updated_at: string;
}

interface CategoryOption {
  label: string;
  value: number;
  level: number;
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

interface SymptomTag {
  tag: string;
  count: number;
}

function mapProduct(raw: Record<string, unknown>): Product {
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    category_id: Number(raw.category_id ?? 0),
    fulfillment_type: String(raw.fulfillment_type ?? 'in_store'),
    original_price: Number(raw.original_price ?? 0),
    sale_price: Number(raw.sale_price ?? 0),
    images: Array.isArray(raw.images) ? raw.images.map(String) : [],
    video_url: String(raw.video_url ?? ''),
    description: String(raw.description ?? ''),
    symptom_tags: Array.isArray(raw.symptom_tags) ? raw.symptom_tags.map(String) : [],
    stock: Number(raw.stock ?? 0),
    valid_start_date: raw.valid_start_date ? String(raw.valid_start_date) : null,
    valid_end_date: raw.valid_end_date ? String(raw.valid_end_date) : null,
    points_exchangeable: Boolean(raw.points_exchangeable),
    points_price: Number(raw.points_price ?? 0),
    points_deductible: Boolean(raw.points_deductible),
    redeem_count: Number(raw.redeem_count ?? 1),
    appointment_mode: String(raw.appointment_mode ?? 'none'),
    purchase_appointment_mode: raw.purchase_appointment_mode ? String(raw.purchase_appointment_mode) : null,
    custom_form_id: raw.custom_form_id ? Number(raw.custom_form_id) : null,
    faq: raw.faq ?? null,
    recommend_weight: Number(raw.recommend_weight ?? 0),
    sales_count: Number(raw.sales_count ?? 0),
    status: String(raw.status ?? 'draft'),
    sort_order: Number(raw.sort_order ?? 0),
    payment_timeout_minutes: Number(raw.payment_timeout_minutes ?? 15),
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? ''),
  };
}

const fulfillmentTypes = [
  { label: '到店服务', value: 'in_store' },
  { label: '快递配送', value: 'delivery' },
  { label: '虚拟商品', value: 'virtual' },
];

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '上架', value: 'active' },
  { label: '下架', value: 'inactive' },
];

const appointmentModes = [
  { label: '无需预约', value: 'none' },
  { label: '预约日期', value: 'date' },
  { label: '预约时段', value: 'time_slot' },
  { label: '自定义表单', value: 'custom_form' },
];

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

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  active: { color: 'green', text: '上架' },
  inactive: { color: 'red', text: '下架' },
};

const fulfillmentMap: Record<string, string> = {
  in_store: '到店服务',
  delivery: '快递配送',
  virtual: '虚拟商品',
};

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Product | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [categoryOptions, setCategoryOptions] = useState<CategoryOption[]>([]);
  const [categoryMap, setCategoryMap] = useState<Map<number, string>>(new Map());
  const [filterCategory, setFilterCategory] = useState<number | undefined>(undefined);
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [symptomTags, setSymptomTags] = useState<SymptomTag[]>([]);
  const [form] = Form.useForm();

  const [formFieldsVisible, setFormFieldsVisible] = useState(false);
  const [formFieldsProductId, setFormFieldsProductId] = useState<number | null>(null);
  const [formFields, setFormFields] = useState<FormField[]>([]);
  const [formFieldsLoading, setFormFieldsLoading] = useState(false);
  const [fieldModalVisible, setFieldModalVisible] = useState(false);
  const [editingField, setEditingField] = useState<FormField | null>(null);
  const [fieldForm] = Form.useForm();

  const fetchCategories = useCallback(async () => {
    try {
      const res = await get('/api/admin/products/categories');
      if (res) {
        const rawList = res.items || res.list || res;
        if (Array.isArray(rawList)) {
          const opts: CategoryOption[] = rawList.map((c: Record<string, unknown>) => ({
            label: `${Number(c.level) === 2 ? '  └ ' : ''}${String(c.name ?? '')}`,
            value: Number(c.id),
            level: Number(c.level ?? 1),
          }));
          const map = new Map<number, string>();
          rawList.forEach((c: Record<string, unknown>) => { map.set(Number(c.id), String(c.name ?? '')); });
          setCategoryOptions(opts);
          setCategoryMap(map);
          return map;
        }
      }
    } catch {}
    return new Map<number, string>();
  }, []);

  const fetchSymptomTags = useCallback(async () => {
    try {
      const res = await get('/api/admin/symptom-tags');
      if (res?.items) {
        setSymptomTags(res.items);
      }
    } catch {}
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterCategory) params.category_id = filterCategory;
      if (filterStatus) params.status = filterStatus;
      if (searchText) params.keyword = searchText;
      const res = await get('/api/admin/products', params);
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setProducts(rawList.map((r: Record<string, unknown>) => mapProduct(r)));
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch {
      setProducts([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
    } finally {
      setLoading(false);
    }
  }, [filterCategory, filterStatus, searchText]);

  useEffect(() => {
    (async () => {
      await fetchCategories();
      await fetchSymptomTags();
      await fetchData(1, 10);
    })();
  }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({
      status: 'draft',
      stock: 100,
      fulfillment_type: 'in_store',
      sort_order: 0,
      redeem_count: 1,
      appointment_mode: 'none',
      payment_timeout_minutes: 15,
      points_exchangeable: false,
      points_deductible: false,
    });
    setFileList([]);
    setModalVisible(true);
  };

  const handleEdit = (record: Product) => {
    setEditingRecord(record);
    form.setFieldsValue({
      name: record.name,
      category_id: record.category_id,
      fulfillment_type: record.fulfillment_type,
      original_price: record.original_price,
      sale_price: record.sale_price,
      description: record.description,
      symptom_tags: record.symptom_tags,
      stock: record.stock,
      valid_start_date: record.valid_start_date ? dayjs(record.valid_start_date) : null,
      valid_end_date: record.valid_end_date ? dayjs(record.valid_end_date) : null,
      points_exchangeable: record.points_exchangeable,
      points_price: record.points_price,
      points_deductible: record.points_deductible,
      redeem_count: record.redeem_count,
      appointment_mode: record.appointment_mode,
      recommend_weight: record.recommend_weight,
      status: record.status,
      sort_order: record.sort_order,
      payment_timeout_minutes: record.payment_timeout_minutes,
      video_url: record.video_url,
    });
    setFileList(
      record.images?.map((url, i) => ({ uid: String(-i - 1), name: `img_${i}`, status: 'done' as const, url })) || []
    );
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/products/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const handleToggleStatus = async (record: Product, newStatus: string) => {
    try {
      await put(`/api/admin/products/${record.id}`, { status: newStatus });
      message.success(newStatus === 'active' ? '已上架' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('操作失败');
    }
  };

  const doUpload = async (file: RcFile): Promise<string> => {
    try {
      const res = await upload('/api/upload/image', file);
      return (res as any)?.url || (res as any)?.data?.url || '';
    } catch {
      message.error('图片上传失败');
      return '';
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      const imageUrls: string[] = [];
      for (const f of fileList) {
        if (f.originFileObj) {
          const url = await doUpload(f.originFileObj as RcFile);
          if (url) imageUrls.push(url);
        } else if (f.url) {
          imageUrls.push(f.url);
        }
      }

      const payload: Record<string, unknown> = {
        name: values.name,
        category_id: values.category_id,
        fulfillment_type: values.fulfillment_type,
        original_price: values.original_price,
        sale_price: values.sale_price,
        images: imageUrls,
        video_url: values.video_url || '',
        description: values.description || '',
        symptom_tags: values.symptom_tags || [],
        stock: values.stock ?? 0,
        valid_start_date: values.valid_start_date ? values.valid_start_date.format('YYYY-MM-DD') : null,
        valid_end_date: values.valid_end_date ? values.valid_end_date.format('YYYY-MM-DD') : null,
        points_exchangeable: values.points_exchangeable || false,
        points_price: values.points_price ?? 0,
        points_deductible: values.points_deductible || false,
        redeem_count: values.redeem_count ?? 1,
        appointment_mode: values.appointment_mode || 'none',
        recommend_weight: values.recommend_weight ?? 0,
        status: values.status || 'draft',
        sort_order: values.sort_order ?? 0,
        payment_timeout_minutes: values.payment_timeout_minutes ?? 15,
      };

      if (editingRecord) {
        await put(`/api/admin/products/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/products', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const fetchFormFields = async (productId: number) => {
    setFormFieldsLoading(true);
    try {
      const res = await get(`/api/admin/products/${productId}/form-fields`);
      if (res) {
        setFormFields(Array.isArray(res.items) ? res.items : []);
      }
    } catch {
      setFormFields([]);
    } finally {
      setFormFieldsLoading(false);
    }
  };

  const openFormFields = (record: Product) => {
    setFormFieldsProductId(record.id);
    setFormFieldsVisible(true);
    fetchFormFields(record.id);
  };

  const handleAddField = () => {
    setEditingField(null);
    fieldForm.resetFields();
    fieldForm.setFieldsValue({ required: false, sort_order: 0 });
    setFieldModalVisible(true);
  };

  const handleEditField = (field: FormField) => {
    setEditingField(field);
    fieldForm.setFieldsValue({
      field_type: field.field_type,
      label: field.label,
      placeholder: field.placeholder,
      required: field.required,
      options: field.options ? JSON.stringify(field.options) : '',
      sort_order: field.sort_order,
    });
    setFieldModalVisible(true);
  };

  const handleDeleteField = async (fieldId: number) => {
    if (!formFieldsProductId) return;
    try {
      await del(`/api/admin/products/${formFieldsProductId}/form-fields/${fieldId}`);
      message.success('删除成功');
      fetchFormFields(formFieldsProductId);
    } catch {
      message.error('删除失败');
    }
  };

  const handleFieldSubmit = async () => {
    if (!formFieldsProductId) return;
    try {
      const values = await fieldForm.validateFields();
      let options = null;
      if (values.options) {
        try { options = JSON.parse(values.options); } catch { options = values.options.split(',').map((s: string) => s.trim()); }
      }
      const payload = {
        field_type: values.field_type,
        label: values.label,
        placeholder: values.placeholder || '',
        required: values.required || false,
        options,
        sort_order: values.sort_order ?? 0,
      };

      if (editingField) {
        await put(`/api/admin/products/${formFieldsProductId}/form-fields/${editingField.id}`, payload);
        message.success('编辑成功');
      } else {
        await post(`/api/admin/products/${formFieldsProductId}/form-fields`, payload);
        message.success('新增成功');
      }
      setFieldModalVisible(false);
      fetchFormFields(formFieldsProductId);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('操作失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '封面', dataIndex: 'images', key: 'images', width: 70,
      render: (v: string[]) => v && v.length > 0 ? <img src={v[0]} alt="" style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4 }} /> : '-',
    },
    { title: '商品名称', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
    {
      title: '分类', dataIndex: 'category_id', key: 'category_id', width: 100,
      render: (v: number) => <Tag color="cyan">{categoryMap.get(v) ?? '未分类'}</Tag>,
    },
    {
      title: '类型', dataIndex: 'fulfillment_type', key: 'fulfillment_type', width: 90,
      render: (v: string) => <Tag>{fulfillmentMap[v] ?? v}</Tag>,
    },
    {
      title: '售价', dataIndex: 'sale_price', key: 'sale_price', width: 90,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v}</span>,
    },
    {
      title: '原价', dataIndex: 'original_price', key: 'original_price', width: 90,
      render: (v: number) => v ? <span style={{ textDecoration: 'line-through', color: '#999' }}>¥{v}</span> : '—',
    },
    { title: '库存', dataIndex: 'stock', key: 'stock', width: 70 },
    { title: '销量', dataIndex: 'sales_count', key: 'sales_count', width: 70 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => {
        const s = statusMap[v] || { color: 'default', text: v };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? v.slice(0, 19).replace('T', ' ') : '',
    },
    {
      title: '操作', key: 'action', width: 260, fixed: 'right' as const,
      render: (_: unknown, record: Product) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" onClick={() => openFormFields(record)}>表单</Button>
          {record.status !== 'active' ? (
            <Popconfirm title="确定上架？" onConfirm={() => handleToggleStatus(record, 'active')}>
              <Button type="link" size="small" icon={<ArrowUpOutlined />}>上架</Button>
            </Popconfirm>
          ) : (
            <Popconfirm title="确定下架？" onConfirm={() => handleToggleStatus(record, 'inactive')}>
              <Button type="link" size="small" icon={<ArrowDownOutlined />}>下架</Button>
            </Popconfirm>
          )}
          <Popconfirm title="确定删除该商品？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const fieldColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '字段类型', dataIndex: 'field_type', key: 'field_type', width: 100 },
    { title: '标签', dataIndex: 'label', key: 'label', width: 150 },
    { title: '占位提示', dataIndex: 'placeholder', key: 'placeholder', width: 150 },
    {
      title: '必填', dataIndex: 'required', key: 'required', width: 70,
      render: (v: boolean) => <Tag color={v ? 'red' : 'default'}>{v ? '是' : '否'}</Tag>,
    },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 70 },
    {
      title: '操作', key: 'action', width: 150,
      render: (_: unknown, record: FormField) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditField(record)}>编辑</Button>
          <Popconfirm title="确定删除该字段？" onConfirm={() => handleDeleteField(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>商品管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增商品</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select
            placeholder="按分类筛选"
            allowClear
            style={{ width: 160 }}
            options={categoryOptions}
            value={filterCategory}
            onChange={v => setFilterCategory(v)}
          />
        </Col>
        <Col>
          <Select
            placeholder="按状态筛选"
            allowClear
            style={{ width: 120 }}
            options={statusOptions}
            value={filterStatus}
            onChange={v => setFilterStatus(v)}
          />
        </Col>
        <Col>
          <Input
            placeholder="搜索商品名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 220 }}
            allowClear
          />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={products}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1500 }}
      />

      <Modal
        title={editingRecord ? '编辑商品' : '新增商品'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={720}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16, maxHeight: '65vh', overflowY: 'auto', paddingRight: 8 }}>
          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="请输入商品名称" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="商品分类" name="category_id" rules={[{ required: true, message: '请选择分类' }]}>
                <Select options={categoryOptions} placeholder="请选择分类" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="履约类型" name="fulfillment_type" rules={[{ required: true, message: '请选择类型' }]}>
                <Select options={fulfillmentTypes} placeholder="请选择类型" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="售价 (元)" name="sale_price" rules={[{ required: true, message: '请输入售价' }]}>
                <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="原价 (元)" name="original_price" rules={[{ required: true, message: '请输入原价' }]}>
                <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="库存" name="stock" rules={[{ required: true, message: '请输入库存' }]}>
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="商品图片" name="_images">
            <div>
              <Upload
                listType="picture-card"
                maxCount={5}
                fileList={fileList}
                beforeUpload={() => false}
                onChange={({ fileList: fl }) => setFileList(fl)}
              >
                {fileList.length < 5 && (
                  <div><UploadOutlined /><div style={{ marginTop: 8 }}>上传图片</div></div>
                )}
              </Upload>
            </div>
          </Form.Item>
          <Form.Item label="视频链接" name="video_url">
            <Input placeholder="请输入视频URL" />
          </Form.Item>
          <Form.Item label="商品描述" name="description">
            <TextArea rows={4} placeholder="请输入商品描述" />
          </Form.Item>
          <Form.Item label="症状标签" name="symptom_tags">
            <Select
              mode="tags"
              placeholder="输入或选择症状标签"
              options={symptomTags.map(t => ({ label: `${t.tag} (${t.count})`, value: t.tag }))}
            />
          </Form.Item>

          <Divider>积分设置</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="可积分兑换" name="points_exchangeable" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="积分价格" name="points_price">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="可积分抵扣" name="points_deductible" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Divider>预约与核销</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="核销次数" name="redeem_count">
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="预约模式" name="appointment_mode">
                <Select options={appointmentModes} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="支付超时(分)" name="payment_timeout_minutes">
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="有效开始日期" name="valid_start_date">
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="有效结束日期" name="valid_end_date">
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Divider>排序与状态</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="推荐权重" name="recommend_weight">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="排序值" name="sort_order">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="状态" name="status">
                <Select options={statusOptions} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 表单字段管理弹窗 */}
      <Modal
        title="预约表单字段配置"
        open={formFieldsVisible}
        onCancel={() => setFormFieldsVisible(false)}
        footer={null}
        width={800}
        destroyOnClose
      >
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddField}>新增字段</Button>
        </div>
        <Table
          columns={fieldColumns}
          dataSource={formFields}
          rowKey="id"
          loading={formFieldsLoading}
          pagination={false}
          size="small"
        />
      </Modal>

      {/* 字段编辑弹窗 */}
      <Modal
        title={editingField ? '编辑字段' : '新增字段'}
        open={fieldModalVisible}
        onOk={handleFieldSubmit}
        onCancel={() => setFieldModalVisible(false)}
        destroyOnClose
      >
        <Form form={fieldForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="字段类型" name="field_type" rules={[{ required: true, message: '请选择字段类型' }]}>
            <Select options={fieldTypeOptions} placeholder="请选择字段类型" />
          </Form.Item>
          <Form.Item label="标签名称" name="label" rules={[{ required: true, message: '请输入标签' }]}>
            <Input placeholder="请输入字段标签" />
          </Form.Item>
          <Form.Item label="占位提示" name="placeholder">
            <Input placeholder="请输入占位提示文本" />
          </Form.Item>
          <Form.Item label="选项 (逗号分隔或JSON)" name="options">
            <TextArea rows={2} placeholder='如: 选项1,选项2 或 ["选项1","选项2"]' />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="是否必填" name="required" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="排序值" name="sort_order">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  );
}
