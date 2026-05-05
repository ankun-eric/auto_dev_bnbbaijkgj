'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, message,
  Typography, Tag, Popconfirm, Row, Col, Tabs, Divider, Checkbox, Radio,
  Tooltip, Badge,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SearchOutlined, QuestionCircleOutlined,
  CloseOutlined, MenuOutlined, PlayCircleOutlined, ShopOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
import { useRouter } from 'next/navigation';
import type { UploadFile, RcFile } from 'antd/es/upload/interface';
import SimpleRichEditor from '@/components/SimpleRichEditor';
import { fulfillmentLabel, FULFILLMENT_LABEL_MAP, FULFILLMENT_OPTIONS } from '@/utils/fulfillmentLabel';

const { Title } = Typography;
const { TextArea } = Input;

interface ProductSku {
  id?: number;
  spec_name: string;
  sale_price: number;
  origin_price?: number | null;
  stock: number;
  is_default: boolean;
  status: number; // 1启用 2停用
  sort_order: number;
  has_orders?: boolean;
}

interface Product {
  id: number;
  name: string;
  category_id: number;
  fulfillment_type: string;
  original_price: number | null;
  sale_price: number;
  images: string[];
  video_url: string;
  description: string;
  symptom_tags: string[];
  stock: number;
  points_exchangeable: boolean;
  points_price: number;
  points_deductible: boolean;
  redeem_count: number;
  appointment_mode: string;
  purchase_appointment_mode: string | null;
  custom_form_id: number | null;
  advance_days: number | null;
  daily_quota: number | null;
  time_slots: Array<{ start: string; end: string; capacity: number }> | null;
  include_today: boolean;
  // [2026-05-05 营业管理入口收敛 PRD v1.0 · N-06] 商品级当日截止 N 分钟
  booking_cutoff_minutes?: number | null;
  faq: any;
  recommend_weight: number;
  sales_count: number;
  status: string;
  sort_order: number;
  product_code_list?: string[];
  spec_mode?: number;
  main_video_url?: string;
  selling_point?: string;
  description_rich?: string;
  marketing_badges?: string[];
  // [核销订单过期+改期规则优化 v1.0] 是否允许用户错过预约后改期（默认 true）
  allow_reschedule?: boolean;
  skus?: ProductSku[];
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

function mapProduct(raw: Record<string, any>): Product {
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    category_id: Number(raw.category_id ?? 0),
    fulfillment_type: String(raw.fulfillment_type ?? 'in_store'),
    original_price: raw.original_price != null && raw.original_price !== 0 ? Number(raw.original_price) : null,
    sale_price: Number(raw.sale_price ?? 0),
    images: Array.isArray(raw.images) ? raw.images.map(String) : [],
    video_url: String(raw.video_url ?? ''),
    description: String(raw.description ?? ''),
    symptom_tags: Array.isArray(raw.symptom_tags) ? raw.symptom_tags.map(String) : [],
    stock: Number(raw.stock ?? 0),
    points_exchangeable: Boolean(raw.points_exchangeable),
    points_price: Number(raw.points_price ?? 0),
    points_deductible: Boolean(raw.points_deductible),
    redeem_count: Number(raw.redeem_count ?? 1),
    appointment_mode: String(raw.appointment_mode ?? 'none'),
    purchase_appointment_mode: raw.purchase_appointment_mode ? String(raw.purchase_appointment_mode) : null,
    custom_form_id: raw.custom_form_id ? Number(raw.custom_form_id) : null,
    advance_days: raw.advance_days != null ? Number(raw.advance_days) : null,
    daily_quota: raw.daily_quota != null ? Number(raw.daily_quota) : null,
    time_slots: Array.isArray(raw.time_slots)
      ? raw.time_slots.map((s: any) => ({
          start: String(s.start ?? ''),
          end: String(s.end ?? ''),
          capacity: Number(s.capacity ?? 0),
        }))
      : null,
    include_today: raw.include_today === false ? false : true,
    booking_cutoff_minutes: raw.booking_cutoff_minutes ?? null,
    faq: raw.faq ?? null,
    recommend_weight: Number(raw.recommend_weight ?? 0),
    sales_count: Number(raw.sales_count ?? 0),
    status: String(raw.status ?? 'draft'),
    sort_order: Number(raw.sort_order ?? 0),
    product_code_list: Array.isArray(raw.product_code_list) ? raw.product_code_list.map(String) : [],
    spec_mode: Number(raw.spec_mode ?? 1),
    main_video_url: String(raw.main_video_url ?? raw.video_url ?? ''),
    selling_point: String(raw.selling_point ?? ''),
    description_rich: String(raw.description_rich ?? ''),
    marketing_badges: Array.isArray(raw.marketing_badges)
      ? raw.marketing_badges.map(String).filter((b: string) => ['limited', 'hot', 'new', 'recommend'].includes(b))
      : [],
    allow_reschedule: raw.allow_reschedule === false ? false : true,
    skus: Array.isArray(raw.skus) ? raw.skus.map((s: any) => ({
      id: s.id,
      spec_name: String(s.spec_name ?? ''),
      sale_price: Number(s.sale_price ?? 0),
      origin_price: s.origin_price != null ? Number(s.origin_price) : null,
      stock: Number(s.stock ?? 0),
      is_default: Boolean(s.is_default),
      status: Number(s.status ?? 1),
      sort_order: Number(s.sort_order ?? 0),
      has_orders: Boolean(s.has_orders),
    })) : [],
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? ''),
  };
}

// 履约类型下拉：与后端 FulfillmentType 枚举严格一致；
// 全端统一复用公共字典 FULFILLMENT_OPTIONS，禁止再手写本地数组（避免再次散落、再次乱）。
const fulfillmentTypes = FULFILLMENT_OPTIONS;

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

// 商品功能优化 v1.0：营销角标选项（运营后台可多选）
const marketingBadgeOptions = [
  { label: '限时', value: 'limited', color: '#FF4D4F' },
  { label: '热销', value: 'hot', color: '#FF8C1A' },
  { label: '新品', value: 'new', color: '#1890FF' },
  { label: '推荐', value: 'recommend', color: '#52C41A' },
];

const purchaseApptModes = [
  { label: '下单即预约', value: 'purchase_with_appointment' },
  { label: '先下单后预约', value: 'appointment_later' },
];


interface AppointmentFormLite {
  id: number;
  name: string;
  status: string;
  field_count: number;
  product_count: number;
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

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  active: { color: 'green', text: '上架' },
  inactive: { color: 'red', text: '下架' },
};

// 履约方式映射统一改用公共字典 `@/utils/fulfillmentLabel`
const fulfillmentMap: Record<string, string> = FULFILLMENT_LABEL_MAP;

const CONSTITUTION_TYPES = [
  '气虚质', '阳虚质', '阴虚质', '痰湿质', '湿热质',
  '血瘀质', '气郁质', '特禀质', '平和质',
];

type TabKey = 'base' | 'tags' | 'points' | 'appointment' | 'sort';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'base', label: '基础信息' },
  { key: 'tags', label: '标签设置' },
  { key: 'points', label: '积分设置' },
  { key: 'appointment', label: '预约与核销' },
  { key: 'sort', label: '排序与权重' },
];

// 图片缩略图拖拽网格
function ImageGrid({
  list, onChange, max = 15,
}: { list: UploadFile[]; onChange: (l: UploadFile[]) => void; max?: number }) {
  const dragIndex = useRef<number | null>(null);

  const onDragStart = (idx: number) => { dragIndex.current = idx; };
  const onDragOver = (e: React.DragEvent) => e.preventDefault();
  const onDrop = (idx: number) => {
    const from = dragIndex.current;
    if (from == null || from === idx) return;
    const newList = [...list];
    const [moved] = newList.splice(from, 1);
    newList.splice(idx, 0, moved);
    dragIndex.current = null;
    onChange(newList);
  };
  const onRemove = (idx: number) => {
    const newList = [...list];
    newList.splice(idx, 1);
    onChange(newList);
  };

  const beforeUpload = (file: RcFile) => {
    const okType = /\.(jpe?g|png|gif|bmp)$/i.test(file.name);
    if (!okType) { message.error('仅支持 jpg/png/gif/bmp 格式'); return Upload.LIST_IGNORE; }
    if (file.size > 5 * 1024 * 1024) { message.error('单张图片不能超过 5M'); return Upload.LIST_IGNORE; }
    return false;
  };

  const onUploadChange = (info: any) => {
    const files: UploadFile[] = info.fileList || [];
    const merged = [...list, ...files.filter((f: UploadFile) => !list.find(l => l.uid === f.uid))];
    if (merged.length > max) {
      message.warning(`最多上传 ${max} 张图片`);
      onChange(merged.slice(0, max));
    } else {
      onChange(merged);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        {list.map((f, idx) => {
          const url = f.url || (f.originFileObj ? URL.createObjectURL(f.originFileObj as Blob) : '');
          return (
            <div
              key={f.uid}
              draggable
              onDragStart={() => onDragStart(idx)}
              onDragOver={onDragOver}
              onDrop={() => onDrop(idx)}
              style={{
                position: 'relative', width: 96, height: 96, border: '1px solid #d9d9d9', borderRadius: 6,
                overflow: 'hidden', cursor: 'move', background: '#fafafa',
              }}
            >
              {url && <img src={resolveAssetUrl(url)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
              {idx === 0 && (
                <div style={{
                  position: 'absolute', left: 0, top: 0, background: '#1677ff', color: '#fff',
                  fontSize: 12, padding: '2px 6px', borderBottomRightRadius: 4,
                }}>封面图</div>
              )}
              <Button
                type="primary" danger shape="circle" size="small" icon={<CloseOutlined />}
                style={{ position: 'absolute', right: 2, top: 2, width: 20, height: 20, minWidth: 20 }}
                onClick={() => onRemove(idx)}
              />
              <MenuOutlined style={{ position: 'absolute', right: 4, bottom: 4, color: '#fff', textShadow: '0 0 2px #000' }} />
            </div>
          );
        })}
        {list.length < max && (
          <Upload
            multiple
            beforeUpload={beforeUpload}
            onChange={onUploadChange}
            showUploadList={false}
            accept=".jpg,.jpeg,.png,.gif,.bmp"
          >
            <div style={{
              width: 96, height: 96, border: '1px dashed #d9d9d9', borderRadius: 6,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', background: '#fafafa',
            }}>
              <UploadOutlined /><div style={{ fontSize: 12, marginTop: 4 }}>上传图片</div>
            </div>
          </Upload>
        )}
      </div>
      <div style={{ fontSize: 12, color: '#999' }}>可拖拽排序，第 1 张自动成为封面图</div>
    </div>
  );
}

// SKU 规格表
function SkuTable({
  skus, onChange,
}: { skus: ProductSku[]; onChange: (s: ProductSku[]) => void }) {
  const dragIndex = useRef<number | null>(null);

  const setRow = (idx: number, patch: Partial<ProductSku>) => {
    const next = skus.map((s, i) => i === idx ? { ...s, ...patch } : s);
    onChange(next);
  };

  const addRow = () => {
    onChange([
      ...skus,
      { spec_name: '', sale_price: 0, origin_price: null, stock: 0, is_default: skus.length === 0, status: 1, sort_order: skus.length, has_orders: false },
    ]);
  };

  const removeRow = (idx: number) => {
    if (skus.length <= 1) { message.warning('至少保留 1 条规格'); return; }
    const removed = skus[idx];
    if (removed.has_orders) { message.warning('该规格已有订单，不可删除，请改为停用'); return; }
    const next = skus.filter((_, i) => i !== idx);
    if (removed.is_default && next.length > 0) next[0].is_default = true;
    onChange(next);
  };

  const setDefault = (idx: number) => {
    const next = skus.map((s, i) => ({ ...s, is_default: i === idx }));
    onChange(next);
  };

  const onDragStart = (idx: number) => { dragIndex.current = idx; };
  const onDragOver = (e: React.DragEvent) => e.preventDefault();
  const onDrop = (idx: number) => {
    const from = dragIndex.current;
    if (from == null || from === idx) return;
    const next = [...skus];
    const [m] = next.splice(from, 1);
    next.splice(idx, 0, m);
    next.forEach((s, i) => { s.sort_order = i; });
    dragIndex.current = null;
    onChange(next);
  };

  const lockedTip = '该规格已有订单，为保护已下单用户权益，此字段不可修改。如需调整请新增规格后停用当前规格';

  return (
    <div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#fafafa' }}>
            <th style={{ width: 30, padding: 6, border: '1px solid #f0f0f0' }}></th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', textAlign: 'left' }}>规格名称 *</th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', width: 110 }}>售价(元) *</th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', width: 110 }}>原价(元)</th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', width: 100 }}>库存 *</th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', width: 70 }}>默认</th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', width: 90 }}>启用</th>
            <th style={{ padding: 6, border: '1px solid #f0f0f0', width: 60 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {skus.map((s, idx) => {
            const locked = !!s.has_orders;
            return (
              <tr
                key={idx}
                draggable
                onDragStart={() => onDragStart(idx)}
                onDragOver={onDragOver}
                onDrop={() => onDrop(idx)}
              >
                <td style={{ border: '1px solid #f0f0f0', textAlign: 'center', color: '#aaa', cursor: 'move' }}>
                  <MenuOutlined />
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4 }}>
                  <Tooltip title={locked ? lockedTip : ''}>
                    <Input
                      size="small"
                      value={s.spec_name}
                      disabled={locked}
                      maxLength={20}
                      placeholder="如：单次 / 5 次套餐"
                      onChange={e => setRow(idx, { spec_name: e.target.value })}
                    />
                  </Tooltip>
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4 }}>
                  <Tooltip title={locked ? lockedTip : ''}>
                    <InputNumber
                      size="small" min={0} step={0.01} style={{ width: '100%' }}
                      value={s.sale_price} disabled={locked}
                      onChange={v => setRow(idx, { sale_price: Number(v ?? 0) })}
                    />
                  </Tooltip>
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4 }}>
                  <InputNumber
                    size="small" min={0} step={0.01} style={{ width: '100%' }}
                    value={s.origin_price ?? undefined}
                    onChange={v => setRow(idx, { origin_price: v == null ? null : Number(v) })}
                  />
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4 }}>
                  <InputNumber
                    size="small" min={0} style={{ width: '100%' }}
                    value={s.stock}
                    onChange={v => setRow(idx, { stock: Number(v ?? 0) })}
                  />
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4, textAlign: 'center' }}>
                  <Tooltip title={locked ? lockedTip : ''}>
                    <Radio checked={s.is_default} disabled={locked} onChange={() => setDefault(idx)} />
                  </Tooltip>
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4, textAlign: 'center' }}>
                  <Switch
                    size="small"
                    checked={s.status === 1}
                    onChange={v => setRow(idx, { status: v ? 1 : 2 })}
                    checkedChildren="启用" unCheckedChildren="停用"
                  />
                </td>
                <td style={{ border: '1px solid #f0f0f0', padding: 4, textAlign: 'center' }}>
                  <Tooltip title={locked ? '该规格已有订单，不可删除，请改为停用' : ''}>
                    <Button
                      size="small" danger type="link" disabled={locked}
                      icon={<DeleteOutlined />} onClick={() => removeRow(idx)}
                    />
                  </Tooltip>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Button type="dashed" block icon={<PlusOutlined />} onClick={addRow} style={{ marginTop: 8 }}>
        新增规格
      </Button>
    </div>
  );
}

export default function ProductsPage() {
  const router = useRouter();
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

  // 新增状态
  const [activeTab, setActiveTab] = useState<TabKey>('base');
  const [productCodes, setProductCodes] = useState<string[]>([]);
  const [codeInput, setCodeInput] = useState('');
  const [specMode, setSpecMode] = useState<number>(1); // 1统一 2多规格
  const [skuList, setSkuList] = useState<ProductSku[]>([]);
  const [skuPanelOpen, setSkuPanelOpen] = useState<boolean>(true);
  const [descRich, setDescRich] = useState<string>('');
  const [mainVideoUrl, setMainVideoUrl] = useState<string>('');
  const [videoUploading, setVideoUploading] = useState<boolean>(false);
  const [exampleModal, setExampleModal] = useState<{ open: boolean; type: 'code' | 'selling' | null }>({ open: false, type: null });

  // Tab 校验状态
  const [tabErrors, setTabErrors] = useState<Record<TabKey, boolean>>({ base: false, tags: false, points: false, appointment: false, sort: false });
  // ── BUG-PRODUCT-APPT-001：预约联动 state ──
  const [apptMode, setApptMode] = useState<string>('none');
  const [timeSlots, setTimeSlots] = useState<Array<{ start: string; end: string; capacity: number }>>([]);
  const [apptForms, setApptForms] = useState<AppointmentFormLite[]>([]);

  const [boundStoreCount, setBoundStoreCount] = useState<number>(0);

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
      if (res?.items) setSymptomTags(res.items);
    } catch {}
  }, []);

  const fetchApptForms = useCallback(async () => {
    try {
      const res = await get('/api/admin/appointment-forms', { page: 1, page_size: 200 });
      const items = res?.items || [];
      setApptForms(Array.isArray(items) ? items : []);
    } catch {
      setApptForms([]);
    }
  }, []);

  const fetchBoundStoreCount = useCallback(async (productId: number) => {
    try {
      const res = await get(`/api/admin/store-bindding/products/${productId}/bound-count`);
      setBoundStoreCount(res?.bound_store_count ?? 0);
    } catch {
      setBoundStoreCount(0);
    }
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
      await fetchApptForms();
      await fetchData(1, 10);
    })();
  }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const resetDialogState = () => {
    setActiveTab('base');
    setProductCodes([]);
    setCodeInput('');
    setSpecMode(1);
    setSkuList([]);
    setSkuPanelOpen(true);
    setDescRich('');
    setMainVideoUrl('');
    setFileList([]);
    setTabErrors({ base: false, tags: false, points: false, appointment: false, sort: false });
    setApptMode('none');
    setTimeSlots([]);
    setBoundStoreCount(0);
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    resetDialogState();
    form.setFieldsValue({
      status: 'draft',
      stock: 100,
      fulfillment_type: 'in_store',
      sort_order: 0,
      redeem_count: 1,
      appointment_mode: 'none',
      points_exchangeable: false,
      points_deductible: false,
      spec_mode: 1,
      include_today: true,
      // [核销订单过期+改期规则优化 v1.0] 默认允许改期
      allow_reschedule: true,
    });
    setModalVisible(true);
  };

  const handleEdit = async (record: Product) => {
    setEditingRecord(record);
    resetDialogState();
    // 拉取详情获取 SKU 与新字段
    let detail: Product = record;
    try {
      const res = await get(`/api/admin/products/${record.id}/detail`);
      if (res) detail = mapProduct(res);
    } catch {}

    const existingConstitutions = (detail.symptom_tags || []).filter(t => CONSTITUTION_TYPES.includes(t));
    const otherTags = (detail.symptom_tags || []).filter(t => !CONSTITUTION_TYPES.includes(t));

    form.setFieldsValue({
      name: detail.name,
      category_id: detail.category_id,
      fulfillment_type: detail.fulfillment_type,
      original_price: detail.original_price ?? undefined,
      sale_price: detail.sale_price,
      selling_point: detail.selling_point || '',
      symptom_tags: otherTags,
      constitution_types: existingConstitutions,
      stock: detail.stock,
      points_exchangeable: detail.points_exchangeable,
      points_price: detail.points_price,
      points_deductible: detail.points_deductible,
      redeem_count: detail.redeem_count,
      appointment_mode: detail.appointment_mode,
      purchase_appointment_mode: detail.purchase_appointment_mode || undefined,
      advance_days: detail.advance_days ?? undefined,
      daily_quota: detail.daily_quota ?? undefined,
      include_today: detail.include_today === false ? false : true,
      // [2026-05-05 N-06] 商品级当日截止 N 分钟
      booking_cutoff_minutes: detail.booking_cutoff_minutes ?? undefined,
      custom_form_id: detail.custom_form_id ?? undefined,
      recommend_weight: detail.recommend_weight,
      status: detail.status,
      sort_order: detail.sort_order,
      spec_mode: detail.spec_mode ?? 1,
      marketing_badges: Array.isArray(detail.marketing_badges) ? detail.marketing_badges : [],
      allow_reschedule: detail.allow_reschedule === false ? false : true,
    });
    setProductCodes(detail.product_code_list || []);
    setSpecMode(detail.spec_mode ?? 1);
    setSkuList(detail.skus || []);
    // 老数据：富文本优先，否则把纯文本转 HTML
    const rich = detail.description_rich;
    const plain = detail.description;
    if (rich && rich.trim()) {
      setDescRich(rich);
    } else if (plain && plain.trim()) {
      setDescRich(plain.replace(/\n/g, '<br/>'));
    } else {
      setDescRich('');
    }
    setMainVideoUrl(detail.main_video_url || detail.video_url || '');
    setFileList(
      detail.images?.map((url, i) => ({ uid: String(-i - 1), name: `img_${i}`, status: 'done' as const, url })) || []
    );
    setApptMode(detail.appointment_mode || 'none');
    setTimeSlots(detail.time_slots || []);
    await fetchBoundStoreCount(detail.id);
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

  const doUpload = async (file: RcFile | Blob): Promise<string> => {
    try {
      const res = await upload('/api/upload/image', file as File);
      return (res as any)?.url || (res as any)?.data?.url || '';
    } catch {
      message.error('上传失败');
      return '';
    }
  };

  const addCode = () => {
    const v = codeInput.trim();
    if (!v) return;
    if (v.length > 30) { message.warning('单个条码最多 30 字符'); return; }
    if (productCodes.length >= 10) { message.warning('最多 10 个条码'); return; }
    if (productCodes.includes(v)) { message.warning('条码重复'); return; }
    setProductCodes([...productCodes, v]);
    setCodeInput('');
  };

  const removeCode = (v: string) => setProductCodes(productCodes.filter(c => c !== v));

  const onSpecModeChange = (val: number) => {
    if (val === 1 && specMode === 2 && skuList.length > 0) {
      Modal.confirm({
        title: '切换到统一规格',
        content: '切换后已录入的规格数据将被清空，是否继续？',
        onOk: () => {
          setSkuList([]);
          setSpecMode(1);
          form.setFieldValue('spec_mode', 1);
        },
      });
      return;
    }
    setSpecMode(val);
    form.setFieldValue('spec_mode', val);
    if (val === 2 && skuList.length === 0) {
      setSkuList([{ spec_name: '', sale_price: 0, origin_price: null, stock: 0, is_default: true, status: 1, sort_order: 0, has_orders: false }]);
    }
  };

  const totalSkuStock = skuList.reduce((s, x) => s + Number(x.stock || 0), 0);

  const validateSkus = (strict: boolean): string | null => {
    if (specMode !== 2) return null;
    if (skuList.length === 0) return '请至少添加 1 条规格';
    const names = new Set<string>();
    for (const s of skuList) {
      if (!s.spec_name || s.spec_name.trim() === '') return '规格名称不能为空';
      if (s.spec_name.length > 20) return '规格名称最多 20 字';
      if (names.has(s.spec_name)) return `规格名称重复：${s.spec_name}`;
      names.add(s.spec_name);
      if (s.sale_price == null || isNaN(Number(s.sale_price)) || Number(s.sale_price) < 0) return `规格「${s.spec_name}」售价无效`;
      if (s.origin_price != null && Number(s.origin_price) < Number(s.sale_price)) return `规格「${s.spec_name}」原价需 ≥ 售价`;
      if (s.stock == null || Number(s.stock) < 0) return `规格「${s.spec_name}」库存无效`;
    }
    const defaults = skuList.filter(s => s.is_default);
    if (defaults.length !== 1) return '默认规格必须有且仅有 1 条';
    if (strict) {
      const anyEnabledWithStock = skuList.some(s => s.status === 1 && Number(s.stock) > 0);
      if (!anyEnabledWithStock) return '上架时至少需有 1 条启用规格且库存 > 0';
    }
    return null;
  };

  const handleSubmit = async (publish = false) => {
    // 校验基础必填
    let hasErrBase = false, hasErrTags = false;
    try {
      await form.validateFields();
    } catch (err: any) {
      if (err?.errorFields) {
        const errSet = new Set<string>();
        (err.errorFields as any[]).forEach(f => { if (Array.isArray(f.name)) errSet.add(String(f.name[0])); });
        hasErrBase = ['name', 'category_id', 'fulfillment_type', 'sale_price', 'original_price', 'stock', 'selling_point'].some(f => errSet.has(f));
        hasErrTags = ['symptom_tags', 'constitution_types'].some(f => errSet.has(f));
        setTabErrors(prev => ({ ...prev, base: hasErrBase, tags: hasErrTags }));
        if (hasErrBase) setActiveTab('base');
        else if (hasErrTags) setActiveTab('tags');
        return;
      }
    }
    const values = form.getFieldsValue();

    // SKU 校验
    const skuErr = validateSkus(publish);
    if (skuErr) {
      message.error(skuErr);
      setActiveTab('base');
      setTabErrors(prev => ({ ...prev, base: true }));
      return;
    }

    // 原价 ≥ 售价
    if (specMode === 1 && values.original_price != null && values.sale_price != null && Number(values.original_price) < Number(values.sale_price)) {
      message.error('原价必须 ≥ 售价');
      setActiveTab('base');
      setTabErrors(prev => ({ ...prev, base: true }));
      return;
    }

    // 上架强校验
    if (publish) {
      if (!fileList || fileList.length === 0) {
        message.error('上架需至少上传 1 张商品图片');
        setActiveTab('base');
        setTabErrors(prev => ({ ...prev, base: true }));
        return;
      }
      if (specMode === 1) {
        if (!values.stock || Number(values.stock) <= 0) {
          message.error('上架时库存必须 > 0');
          setActiveTab('base');
          setTabErrors(prev => ({ ...prev, base: true }));
          return;
        }
      }
    }

    // 卖点长度
    if (values.selling_point && String(values.selling_point).length > 100) {
      message.error('卖点需在 100 字以内');
      setActiveTab('base');
      return;
    }

    // ── BUG-PRODUCT-APPT-001：预约联动前端校验（彻底告别"操作失败"）──
    const mode = values.appointment_mode || 'none';
    if (mode !== 'none') {
      if (!values.purchase_appointment_mode) {
        message.error('请选择下单预约方式（下单即预约 / 先下单后预约）');
        setActiveTab('appointment');
        setTabErrors(prev => ({ ...prev, appointment: true }));
        return;
      }
      if (mode === 'date' || mode === 'time_slot') {
        // BUG-PRODUCT-APPT-002：date / time_slot 共用「提前可预约天数」校验
        if (!values.advance_days || Number(values.advance_days) <= 0) {
          message.error('请填写"提前可预约天数"（需大于 0）');
          setActiveTab('appointment');
          setTabErrors(prev => ({ ...prev, appointment: true }));
          return;
        }
      }
      if (mode === 'date') {
        if (!values.daily_quota || Number(values.daily_quota) <= 0) {
          message.error('请填写"单日最大预约人数"（需大于 0）');
          setActiveTab('appointment');
          setTabErrors(prev => ({ ...prev, appointment: true }));
          return;
        }
      } else if (mode === 'time_slot') {
        if (!timeSlots || timeSlots.length === 0) {
          message.error('请至少配置 1 个预约时段');
          setActiveTab('appointment');
          setTabErrors(prev => ({ ...prev, appointment: true }));
          return;
        }
        for (let i = 0; i < timeSlots.length; i++) {
          const s = timeSlots[i];
          if (!s.start || !s.end) {
            message.error(`第 ${i + 1} 个时段的开始/结束时间必填`);
            setActiveTab('appointment');
            setTabErrors(prev => ({ ...prev, appointment: true }));
            return;
          }
          if (!s.capacity || Number(s.capacity) <= 0) {
            message.error(`第 ${i + 1} 个时段的容量必须大于 0`);
            setActiveTab('appointment');
            setTabErrors(prev => ({ ...prev, appointment: true }));
            return;
          }
        }
      } else if (mode === 'custom_form') {
        if (!values.custom_form_id) {
          message.error('请选择或新建一张预约表单');
          setActiveTab('appointment');
          setTabErrors(prev => ({ ...prev, appointment: true }));
          return;
        }
      }
    }

    // 上传图片
    const imageUrls: string[] = [];
    for (const f of fileList) {
      if (f.originFileObj) {
        const url = await doUpload(f.originFileObj as RcFile);
        if (url) imageUrls.push(url);
      } else if (f.url) {
        imageUrls.push(f.url);
      }
    }

    if (videoUploading) {
      message.warning('视频正在上传中，请稍候');
      return;
    }

    const payload: Record<string, unknown> = {
      name: values.name,
      category_id: values.category_id,
      fulfillment_type: values.fulfillment_type,
      original_price: specMode === 1 ? (values.original_price ?? editingRecord?.original_price ?? null) : null,
      sale_price: specMode === 1 ? (values.sale_price ?? editingRecord?.sale_price ?? 0) : 0,
      images: imageUrls,
      video_url: mainVideoUrl || '',
      main_video_url: mainVideoUrl || '',
      description: descRich ? descRich.replace(/<[^>]+>/g, '').slice(0, 5000) : '',
      description_rich: descRich || '',
      selling_point: values.selling_point ?? editingRecord?.selling_point ?? '',
      product_code_list: productCodes,
      spec_mode: specMode,
      skus: specMode === 2 ? skuList : [],
      symptom_tags: [...(values.symptom_tags || []), ...(values.constitution_types || [])],
      stock: specMode === 1 ? (values.stock ?? editingRecord?.stock ?? 0) : totalSkuStock,
      points_exchangeable: values.points_exchangeable || false,
      points_price: values.points_price ?? 0,
      points_deductible: values.points_deductible || false,
      redeem_count: values.redeem_count ?? 1,
      appointment_mode: mode,
      purchase_appointment_mode: mode !== 'none' ? values.purchase_appointment_mode : null,
      // BUG-PRODUCT-APPT-002：date 与 time_slot 共用 advance_days / include_today
      advance_days: (mode === 'date' || mode === 'time_slot') ? Number(values.advance_days) : null,
      daily_quota: mode === 'date' ? Number(values.daily_quota) : null,
      time_slots: mode === 'time_slot' ? timeSlots : null,
      include_today: (mode === 'date' || mode === 'time_slot')
        ? (values.include_today === false ? false : true)
        : true,
      // [2026-05-05 营业管理入口收敛 PRD v1.0 · N-06] 商品级当日截止 N 分钟（双层兜底，留空 = 继承门店级）
      booking_cutoff_minutes: (mode === 'date' || mode === 'time_slot')
        ? (values.booking_cutoff_minutes === undefined || values.booking_cutoff_minutes === null
            ? null
            : Number(values.booking_cutoff_minutes))
        : null,
      custom_form_id: mode === 'custom_form' ? values.custom_form_id : null,
      recommend_weight: values.recommend_weight ?? 0,
      status: publish ? 'active' : (values.status || 'draft'),
      sort_order: values.sort_order ?? 0,
      marketing_badges: Array.isArray(values.marketing_badges) ? values.marketing_badges : [],
      // [核销订单过期+改期规则优化 v1.0] 是否允许改期（默认 true）
      allow_reschedule: values.allow_reschedule === false ? false : true,
    };

    try {
      if (editingRecord) {
        await put(`/api/admin/products/${editingRecord.id}`, payload);
        message.success(publish ? '保存并已上架' : '编辑成功');
      } else {
        await post('/api/admin/products', payload);
        message.success(publish ? '新增并已上架' : '新增成功');
        setModalVisible(false);
        fetchData(pagination.current, pagination.pageSize);
        Modal.confirm({
          title: '商品创建成功！',
          content: '该商品尚未绑定任何门店，请前往「适用门店」完成门店绑定。',
          okText: '立即前往',
          cancelText: '稍后处理',
          onOk: () => router.push('/product-system/store-bindding'),
        });
        return;
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      const resp = err?.response?.data;
      if (Array.isArray(resp?.detail)) {
        const msgs = resp.detail
          .map((d: any) => {
            const loc = Array.isArray(d?.loc) ? d.loc.slice(1).join('.') : '';
            return loc ? `${loc}: ${d?.msg || ''}` : String(d?.msg || '');
          })
          .filter(Boolean)
          .join('；');
        message.error(msgs || '表单校验失败');
      } else {
        message.error(resp?.detail || '操作失败，请稍后重试');
      }
    }
  };

  const handleCancelModal = () => {
    Modal.confirm({
      title: '关闭确认',
      content: '未保存的修改将丢失，是否继续？',
      onOk: () => setModalVisible(false),
    });
  };

  const handleVideoUpload = async (file: File) => {
    if (!/\.(mp4|mov)$/i.test(file.name)) { message.error('仅支持 mp4/mov 格式'); return false; }
    if (file.size > 100 * 1024 * 1024) { message.error('视频不能超过 100M'); return false; }
    setVideoUploading(true);
    try {
      const url = await doUpload(file);
      if (url) setMainVideoUrl(url);
    } finally {
      setVideoUploading(false);
    }
    return false;
  };

  // 以下为表单字段配置相关（原逻辑保持）
  const fetchFormFields = async (productId: number) => {
    setFormFieldsLoading(true);
    try {
      const res = await get(`/api/admin/products/${productId}/form-fields`);
      if (res) setFormFields(Array.isArray(res.items) ? res.items : []);
    } catch {
      setFormFields([]);
    } finally {
      setFormFieldsLoading(false);
    }
  };

  const openFormFields = (record: Product) => {
    // BUG-PRODUCT-APPT-001：未绑定表单时，不再偷偷建表单，而是引导用户去表单库
    if (!record.custom_form_id) {
      Modal.info({
        title: '该商品尚未绑定预约表单',
        content: (
          <div>
            请先到「预约表单库」新建一张表单，再回到商品编辑页的「预约与核销」Tab 中选择即可。
            <br />
            表单可被多个商品复用，避免重复录入。
          </div>
        ),
        okText: '去预约表单库',
        onOk: () => {
          window.open('/product-system/appointment-forms', '_blank');
        },
      });
      return;
    }
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
    } catch { message.error('删除失败'); }
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
        field_type: values.field_type, label: values.label,
        placeholder: values.placeholder || '', required: values.required || false,
        options, sort_order: values.sort_order ?? 0,
      };
      if (editingField) await put(`/api/admin/products/${formFieldsProductId}/form-fields/${editingField.id}`, payload);
      else await post(`/api/admin/products/${formFieldsProductId}/form-fields`, payload);
      message.success('操作成功');
      setFieldModalVisible(false);
      fetchFormFields(formFieldsProductId);
    } catch (err: any) { if (!err?.errorFields) message.error('操作失败'); }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '封面', dataIndex: 'images', key: 'images', width: 70,
      render: (v: string[]) => v && v.length > 0 ? <img src={resolveAssetUrl(v[0])} alt="" style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4 }} /> : '-',
    },
    { title: '商品名称', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
    {
      title: '分类', dataIndex: 'category_id', key: 'category_id', width: 100,
      render: (v: number) => <Tag color="cyan">{categoryMap.get(v) ?? '未分类'}</Tag>,
    },
    {
      title: '类型', dataIndex: 'fulfillment_type', key: 'fulfillment_type', width: 90,
      render: (v: string) => <Tag>{fulfillmentLabel(v)}</Tag>,
    },
    {
      title: '规格', dataIndex: 'spec_mode', key: 'spec_mode', width: 80,
      render: (v: number, r: Product) => v === 2 ? <Tag color="purple">多规格({r.skus?.length || 0})</Tag> : <Tag>统一</Tag>,
    },
    {
      title: '售价', dataIndex: 'sale_price', key: 'sale_price', width: 90,
      render: (v: number, r: Product) => r.spec_mode === 2 && r.skus && r.skus.length > 0
        ? <span style={{ color: '#f5222d' }}>¥{Math.min(...r.skus.map(s => s.sale_price))}起</span>
        : <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v}</span>,
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

  const renderTabContent = () => {
    const tabStyle = (tab: TabKey): React.CSSProperties => ({
      display: activeTab === tab ? 'block' : 'none',
    });

    return (
      <>
        {/* ── 基础信息 Tab ── */}
        <div style={tabStyle('base')}>
          <Form.Item
            label={
              <Space>
                <span>产品条码</span>
                <Tooltip title="用于快速识别商品所标记的唯一编码"><QuestionCircleOutlined style={{ color: '#999' }} /></Tooltip>
                <Button size="small" type="link" onClick={() => setExampleModal({ open: true, type: 'code' })}>实例</Button>
              </Space>
            }
          >
            <div style={{ border: '1px solid #d9d9d9', borderRadius: 6, padding: 6, minHeight: 40 }}>
              {productCodes.map(c => (
                <Tag key={c} closable onClose={() => removeCode(c)} style={{ marginBottom: 4 }}>{c}</Tag>
              ))}
              {productCodes.length < 10 && (
                <Input
                  size="small" bordered={false} style={{ width: 180 }}
                  placeholder="输入后回车添加" maxLength={30}
                  value={codeInput}
                  onChange={e => setCodeInput(e.target.value)}
                  onPressEnter={addCode}
                  onBlur={addCode}
                />
              )}
              <span style={{ color: '#999', fontSize: 12, marginLeft: 8 }}>{productCodes.length}/10</span>
            </div>
          </Form.Item>

          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }, { max: 50, message: '最多 50 字' }]}>
            <Input placeholder="请输入商品名称" maxLength={50} showCount />
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

          <Form.Item
            label={
              <Space>
                <ShopOutlined />
                <span>适用门店</span>
              </Space>
            }
          >
            <Space>
              <span>已绑定 {boundStoreCount} 个门店</span>
              <Button type="link" onClick={() => router.push('/product-system/store-bindding')}>去管理 →</Button>
            </Space>
          </Form.Item>

          <Form.Item label="商品规格" required>
            <Space>
              <Radio.Group value={specMode} onChange={e => onSpecModeChange(e.target.value)}>
                <Radio value={1}>统一规格</Radio>
                <Radio value={2}>多规格</Radio>
              </Radio.Group>
              {specMode === 2 && (
                <Button size="small" onClick={() => setSkuPanelOpen(o => !o)}>
                  {skuPanelOpen ? '收起规格管理' : '规格管理'}
                </Button>
              )}
            </Space>
          </Form.Item>

          {specMode === 2 && skuPanelOpen && (
            <div style={{ marginBottom: 16, background: '#fafafa', padding: 12, borderRadius: 6 }}>
              <SkuTable skus={skuList} onChange={setSkuList} />
              <div style={{ marginTop: 8, color: '#666' }}>总库存：<b>{totalSkuStock}</b></div>
            </div>
          )}

          {specMode === 1 && (
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item label="售价 (元)" name="sale_price" rules={[{ required: true, message: '请输入售价' }]}>
                  <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="原价 (元)" name="original_price">
                  <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="库存" name="stock" rules={[{ required: true, message: '请输入库存' }]}>
                  <InputNumber min={0} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
          )}

          <Form.Item
            label={
              <Space>
                <span>商品图片</span>
                <Tooltip title="最多上传 15 张，格式：jpg/bmp/png/gif，建议尺寸 750px * 600px">
                  <QuestionCircleOutlined style={{ color: '#999' }} />
                </Tooltip>
                <span style={{ color: '#ff4d4f' }}>*</span>
              </Space>
            }
          >
            <ImageGrid list={fileList} onChange={setFileList} max={15} />
          </Form.Item>

          <Form.Item
            label={
              <Space>
                <span>主图视频</span>
                <Tooltip title="最多可上传 1 个视频；视频不超过 3 分钟，大小不超过 100M，建议视频宽高和产品图片一致">
                  <QuestionCircleOutlined style={{ color: '#999' }} />
                </Tooltip>
              </Space>
            }
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              {mainVideoUrl && (
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <video src={mainVideoUrl} controls style={{ width: 240, height: 135, background: '#000', borderRadius: 6 }} />
                  <Button
                    type="primary" danger size="small" icon={<CloseOutlined />}
                    style={{ position: 'absolute', right: 4, top: 4 }}
                    onClick={() => setMainVideoUrl('')}
                  />
                </div>
              )}
              <Space>
                <Upload beforeUpload={handleVideoUpload} showUploadList={false} accept=".mp4,.mov">
                  <Button icon={<UploadOutlined />} loading={videoUploading}>上传视频（mp4/mov）</Button>
                </Upload>
                <Input
                  style={{ width: 360 }} placeholder="或粘贴视频 URL" value={mainVideoUrl}
                  onChange={e => setMainVideoUrl(e.target.value)}
                  prefix={<PlayCircleOutlined />}
                />
              </Space>
            </Space>
          </Form.Item>

          <Form.Item
            label={
              <Space>
                <span>商品卖点</span>
                <Button size="small" type="link" onClick={() => setExampleModal({ open: true, type: 'selling' })}>实例</Button>
              </Space>
            }
            name="selling_point"
            rules={[{ max: 100, message: '最多 100 字' }]}
          >
            <TextArea rows={2} maxLength={100} showCount placeholder="如：3 场直播口碑爆款 / 医生 1v1 辨证施治 / 无效可退" />
          </Form.Item>

          <Form.Item
            label="营销角标"
            name="marketing_badges"
            tooltip="多选，图片左上角按「限时>热销>新品>推荐」优先级仅展示 1 个"
          >
            <Checkbox.Group
              options={marketingBadgeOptions.map(opt => ({
                label: (
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 8px',
                      background: opt.color,
                      color: '#fff',
                      borderRadius: 2,
                      fontSize: 12,
                      lineHeight: '16px',
                    }}
                  >
                    {opt.label}
                  </span>
                ),
                value: opt.value,
              }))}
            />
          </Form.Item>

          <Form.Item label="商品描述">
            <SimpleRichEditor value={descRich} onChange={setDescRich} />
          </Form.Item>
        </div>

        {/* ── 标签设置 Tab ── */}
        <div style={tabStyle('tags')}>
          <Form.Item label="症状标签" name="symptom_tags">
            <Select
              mode="tags"
              placeholder="输入或选择症状标签"
              options={symptomTags.map(t => ({ label: `${t.tag} (${t.count})`, value: t.tag }))}
            />
          </Form.Item>
          <Form.Item label="适用体质" name="constitution_types">
            <Checkbox.Group options={CONSTITUTION_TYPES.map(t => ({ label: t, value: t }))} />
          </Form.Item>
        </div>

        {/* ── 积分设置 Tab ── */}
        <div style={tabStyle('points')}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="可积分兑换" name="points_exchangeable" valuePropName="checked"><Switch /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="积分价格" name="points_price"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="可积分抵扣" name="points_deductible" valuePropName="checked"><Switch /></Form.Item>
            </Col>
          </Row>
        </div>

        {/* ── 预约与核销 Tab ── */}
        <div style={tabStyle('appointment')}>
          {/* [核销订单过期+改期规则优化 v1.0] 是否允许改期 */}
          <Form.Item
            shouldUpdate={(prev, cur) => prev.allow_reschedule !== cur.allow_reschedule}
            noStyle
          >
            {() => {
              const allow = form.getFieldValue('allow_reschedule');
              const allowed = allow === false ? false : true;
              const helper = allowed
                ? '用户错过预约时段后，可在 App 内自助改约（最多 3 次），不会立即过期'
                : '错过预约时段后订单立即过期，不可改约、不可退款（适用于电影票/演出票等定时商品）';
              return (
                <Form.Item label="允许用户改期" extra={helper}>
                  <Form.Item name="allow_reschedule" valuePropName="checked" noStyle>
                    <Switch />
                  </Form.Item>
                </Form.Item>
              );
            }}
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="核销次数" name="redeem_count"><InputNumber min={1} style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="预约模式" name="appointment_mode">
                <Select
                  options={appointmentModes}
                  onChange={(val) => {
                    setApptMode(val);
                    if (val === 'none') {
                      form.setFieldValue('purchase_appointment_mode', undefined);
                    } else if (!form.getFieldValue('purchase_appointment_mode')) {
                      form.setFieldValue('purchase_appointment_mode', 'purchase_with_appointment');
                    }
                  }}
                />
              </Form.Item>
            </Col>
            {/* [订单核销码状态与未支付超时治理 v1.0] 已移除"支付超时(分)"字段，
                改由后端全局环境变量 PAYMENT_TIMEOUT_MINUTES 统一控制（默认 15 分钟） */}
          </Row>

          {apptMode !== 'none' && (
            <>
              <Divider orientation="left" plain style={{ margin: '4px 0 12px' }}>
                预约设置
              </Divider>
              <Form.Item
                label={<span>下单预约方式 <span style={{ color: '#ff4d4f' }}>*</span></span>}
                name="purchase_appointment_mode"
                rules={[{ required: true, message: '请选择下单预约方式' }]}
              >
                <Radio.Group options={purchaseApptModes} />
              </Form.Item>
            </>
          )}

          {/* BUG-PRODUCT-APPT-002：date 与 time_slot 共用「提前可预约天数」与「预约起始日」 */}
          {(apptMode === 'date' || apptMode === 'time_slot') && (
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label={<span>提前可预约天数 <span style={{ color: '#ff4d4f' }}>*</span></span>}
                  name="advance_days"
                  rules={[{ required: true, message: '请填写提前可预约天数' }]}
                >
                  <InputNumber min={1} max={365} style={{ width: '100%' }} placeholder="例如 7（最多可提前 7 天预约）" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label={<span>预约起始日 <span style={{ color: '#ff4d4f' }}>*</span></span>}
                  name="include_today"
                  initialValue={true}
                  tooltip="选择「包含今天」，可预约日期 = [今天, 今天 + N - 1 天]；选择「从明天起算」，可预约日期 = [明天, 明天 + N - 1 天]"
                >
                  <Radio.Group
                    options={[
                      { label: '包含今天', value: true },
                      { label: '从明天起算', value: false },
                    ]}
                  />
                </Form.Item>
              </Col>
            </Row>
          )}

          {/* [2026-05-05 营业管理入口收敛 PRD v1.0 · N-06] 商品级当日截止 N 分钟（下拉枚举） */}
          {(apptMode === 'date' || apptMode === 'time_slot') && (
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="当日最晚提前 N 分钟截止"
                  name="booking_cutoff_minutes"
                  tooltip="留空 = 继承门店级；门店级也未设置时使用系统默认 30 分钟。选择「不限制」即无截止。"
                >
                  <Select
                    allowClear
                    placeholder="留空 = 继承门店级"
                    options={[
                      { label: '不限制', value: 0 },
                      { label: '15 分钟', value: 15 },
                      { label: '30 分钟', value: 30 },
                      { label: '1 小时', value: 60 },
                      { label: '2 小时', value: 120 },
                      { label: '半天（720）', value: 720 },
                      { label: '1 天（1440）', value: 1440 },
                    ]}
                  />
                </Form.Item>
              </Col>
            </Row>
          )}

          {apptMode === 'date' && (
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label={<span>单日最大预约人数 <span style={{ color: '#ff4d4f' }}>*</span></span>}
                  name="daily_quota"
                  rules={[{ required: true, message: '请填写单日最大预约人数' }]}
                >
                  <InputNumber min={1} style={{ width: '100%' }} placeholder="例如 50" />
                </Form.Item>
              </Col>
            </Row>
          )}

          {apptMode === 'time_slot' && (
            <Form.Item label={<span>时段列表 <span style={{ color: '#ff4d4f' }}>*</span></span>}>
              <div style={{ border: '1px dashed #d9d9d9', borderRadius: 6, padding: 12 }}>
                {timeSlots.length === 0 && (
                  <div style={{ color: '#999', marginBottom: 8 }}>暂未配置时段，请至少添加 1 条。</div>
                )}
                {timeSlots.map((slot, idx) => (
                  <Row gutter={8} key={idx} style={{ marginBottom: 8 }} align="middle">
                    <Col span={7}>
                      <Input
                        placeholder="开始 HH:MM"
                        value={slot.start}
                        onChange={e => {
                          const next = [...timeSlots];
                          next[idx] = { ...next[idx], start: e.target.value };
                          setTimeSlots(next);
                        }}
                      />
                    </Col>
                    <Col span={7}>
                      <Input
                        placeholder="结束 HH:MM"
                        value={slot.end}
                        onChange={e => {
                          const next = [...timeSlots];
                          next[idx] = { ...next[idx], end: e.target.value };
                          setTimeSlots(next);
                        }}
                      />
                    </Col>
                    <Col span={6}>
                      <InputNumber
                        min={1}
                        placeholder="容量"
                        style={{ width: '100%' }}
                        value={slot.capacity}
                        onChange={v => {
                          const next = [...timeSlots];
                          next[idx] = { ...next[idx], capacity: Number(v || 0) };
                          setTimeSlots(next);
                        }}
                      />
                    </Col>
                    <Col span={4}>
                      <Button
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={() => setTimeSlots(timeSlots.filter((_, i) => i !== idx))}
                      >
                        删除
                      </Button>
                    </Col>
                  </Row>
                ))}
                <Button
                  type="dashed"
                  icon={<PlusOutlined />}
                  onClick={() =>
                    setTimeSlots([...timeSlots, { start: '09:00', end: '10:00', capacity: 10 }])
                  }
                  block
                >
                  添加时段
                </Button>
              </div>
            </Form.Item>
          )}

          {apptMode === 'custom_form' && (
            <Row gutter={16} align="middle">
              <Col span={16}>
                <Form.Item
                  label={<span>绑定预约表单 <span style={{ color: '#ff4d4f' }}>*</span></span>}
                  name="custom_form_id"
                  rules={[{ required: true, message: '请选择或新建一张预约表单' }]}
                >
                  <Select
                    placeholder="请选择已有表单"
                    showSearch
                    optionFilterProp="label"
                    options={apptForms
                      .filter(f => f.status !== 'inactive')
                      .map(f => ({ label: `${f.name}（${f.field_count} 个字段）`, value: f.id }))}
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Button
                  type="link"
                  onClick={() => {
                    window.open('/product-system/appointment-forms', '_blank');
                  }}
                >
                  去预约表单库新建 →
                </Button>
                <Button type="link" onClick={fetchApptForms}>刷新</Button>
              </Col>
            </Row>
          )}
        </div>

        {/* ── 排序与权重 Tab ── */}
        <div style={tabStyle('sort')}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="推荐权重" name="recommend_weight"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="排序值" name="sort_order"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="状态" name="status"><Select options={statusOptions} /></Form.Item>
            </Col>
          </Row>
        </div>
      </>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>商品管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增商品</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select placeholder="按分类筛选" allowClear style={{ width: 160 }}
            options={categoryOptions} value={filterCategory} onChange={v => setFilterCategory(v)} />
        </Col>
        <Col>
          <Select placeholder="按状态筛选" allowClear style={{ width: 120 }}
            options={statusOptions} value={filterStatus} onChange={v => setFilterStatus(v)} />
        </Col>
        <Col>
          <Input placeholder="搜索商品名称" prefix={<SearchOutlined />} value={searchText}
            onChange={e => setSearchText(e.target.value)} onPressEnter={handleSearch}
            style={{ width: 220 }} allowClear />
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
        onCancel={handleCancelModal}
        width={960}
        destroyOnClose
        maskClosable={false}
        footer={
          <Space>
            <Button onClick={handleCancelModal}>取消</Button>
            <Button type="primary" onClick={() => handleSubmit(false)}>保存</Button>
            <Button type="primary" danger onClick={() => handleSubmit(true)}>保存并上架</Button>
          </Space>
        }
      >
        <div style={{ display: 'flex', gap: 16, marginTop: 8, minHeight: 500 }}>
          {/* 左侧 Tab */}
          <div style={{ width: 140, borderRight: '1px solid #f0f0f0', paddingRight: 8 }}>
            {TABS.map(t => (
              <div
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                style={{
                  padding: '10px 12px', borderRadius: 6, cursor: 'pointer', marginBottom: 4,
                  background: activeTab === t.key ? '#e6f4ff' : 'transparent',
                  color: activeTab === t.key ? '#1677ff' : '#333',
                  fontWeight: activeTab === t.key ? 600 : 400,
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}
              >
                <span>{t.label}</span>
                {tabErrors[t.key] && <Badge color="red" />}
              </div>
            ))}
          </div>
          {/* 右侧内容 */}
          <div style={{ flex: 1, maxHeight: '65vh', overflowY: 'auto', paddingRight: 8 }}>
            <Form form={form} layout="vertical">
              {renderTabContent()}
            </Form>
          </div>
        </div>
      </Modal>

      {/* 实例弹图 */}
      <Modal
        open={exampleModal.open}
        title={exampleModal.type === 'code' ? '产品条码示例' : '商品卖点示例'}
        footer={null}
        onCancel={() => setExampleModal({ open: false, type: null })}
      >
        <div style={{ background: '#fff', border: '1px solid #eee', padding: 24, textAlign: 'center', borderRadius: 8 }}>
          {exampleModal.type === 'code' ? (
            <>
              <div style={{ fontFamily: 'monospace', fontSize: 20, marginBottom: 12 }}>
                6901234567890&nbsp;&nbsp;6905211234567&nbsp;&nbsp;6938765432109
              </div>
              <div style={{ color: '#666' }}>每个条码是商品的唯一编码，最多可以输入 10 个条码，每个最多 30 字符。</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 16, lineHeight: 2, marginBottom: 12 }}>
                3 场直播口碑爆款 / 医生 1v1 辨证施治 / 无效可退
              </div>
              <div style={{ color: '#666' }}>卖点用简短斜杠分隔的短语，突出商品核心价值，100 字以内。</div>
            </>
          )}
        </div>
      </Modal>

      {/* 表单字段管理弹窗 */}
      <Modal
        title="预约表单字段配置"
        open={formFieldsVisible}
        onCancel={() => setFormFieldsVisible(false)}
        footer={null} width={800} destroyOnClose
      >
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddField}>新增字段</Button>
        </div>
        <Table columns={fieldColumns} dataSource={formFields} rowKey="id"
          loading={formFieldsLoading} pagination={false} size="small" />
      </Modal>

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
          <Form.Item label="占位提示" name="placeholder"><Input placeholder="请输入占位提示文本" /></Form.Item>
          <Form.Item label="选项 (逗号分隔或JSON)" name="options">
            <TextArea rows={2} placeholder='如: 选项1,选项2 或 ["选项1","选项2"]' />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="是否必填" name="required" valuePropName="checked"><Switch /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="排序值" name="sort_order"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

    </div>
  );
}
