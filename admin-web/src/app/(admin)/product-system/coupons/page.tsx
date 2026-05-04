'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Tag, message,
  Typography, Popconfirm, Row, Col, Drawer, DatePicker, Divider, Tooltip,
  Statistic, Card, Alert, Radio, Image,
} from 'antd';
import {
  PlusOutlined, EditOutlined, SendOutlined, SearchOutlined,
  HistoryOutlined, RollbackOutlined, DownloadOutlined,
  StopOutlined, ReloadOutlined, EyeOutlined, EyeInvisibleOutlined,
  CopyOutlined, FileTextOutlined, QuestionCircleOutlined, AppstoreOutlined,
} from '@ant-design/icons';
import { get, post, put } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
import dayjs from 'dayjs';
import CouponTypeHelpModal from '@/components/coupon/CouponTypeHelpModal';
import CategoryTreePicker from '@/components/coupon/CategoryTreePicker';
import ProductPickerModal, { PickerProduct } from '@/components/coupon/ProductPickerModal';
import ScopeSummaryBar from '@/components/coupon/ScopeSummaryBar';

const { Title, Text } = Typography;

const VALIDITY_OPTIONS = [3, 7, 15, 30, 60, 90, 180, 365];

interface Coupon {
  id: number;
  name: string;
  type: string;
  condition_amount: number;
  discount_value: number;
  discount_rate: number;
  scope: string;
  scope_ids: any;
  exclude_ids?: number[] | null;
  total_count: number;
  claimed_count: number;
  used_count: number;
  validity_days: number;
  status: string;
  created_at: string;
  is_offline?: boolean;
  offline_reason?: string | null;
  offline_at?: string | null;
  offline_by?: number | null;
  points_exchange_limit?: number | null;
}

interface GrantItem {
  id: number;
  coupon_id: number;
  user_id: number | null;
  user_phone: string | null;
  method: string;
  status: string;
  granted_at: string | null;
  used_at: string | null;
  order_no: string | null;
  operator_name: string | null;
  redeem_code: string | null;
  recall_reason: string | null;
}

interface CodeBatchItem {
  id: number;
  batch_no: string;
  coupon_id: number;
  coupon_name: string;
  code_type: string;
  total_count: number;
  used_codes_count: number;
  available_count: number;
  voided_count: number;
  claim_limit: number | null;
  expire_at: string | null;
  voided_at: string | null;
  void_reason: string | null;
  created_at: string;
  creator_name: string | null;
}

const couponTypeOptions = [
  { label: '满减券', value: 'full_reduction' },
  { label: '折扣券', value: 'discount' },
  { label: '代金券', value: 'voucher' },
  { label: '免费体验', value: 'free_trial' },
];

const couponTypeMap: Record<string, string> = {
  full_reduction: '满减券', discount: '折扣券', voucher: '代金券', free_trial: '免费体验',
};

const couponTypeColorMap: Record<string, string> = {
  full_reduction: 'volcano', discount: 'blue', voucher: 'green', free_trial: 'purple',
};

const scopeOptions = [
  { label: '全部商品', value: 'all' },
  { label: '指定分类', value: 'category' },
  { label: '指定商品', value: 'product' },
];

const statusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
];

const offlineFilterOptions = [
  { label: '全部', value: '' },
  { label: '上架中', value: 'false' },
  { label: '已下架', value: 'true' },
];

const grantMethodMap: Record<string, string> = {
  self: '自助领取', direct: '定向发放', new_user: '新人券', redeem_code: '兑换码',
};

const grantStatusMap: Record<string, { label: string; color: string }> = {
  granted: { label: '已发放', color: 'blue' },
  used: { label: '已使用', color: 'green' },
  recalled: { label: '已回收', color: 'red' },
  expired: { label: '已过期', color: 'default' },
};

const OFFLINE_REASON_PRESETS = ['活动结束', '配置错误', '库存调整', '业务调整', '其他'];

/**
 * BUG ③ 修复：CSV 下载工具
 * - 旧实现用 `window.open(url)` 跳转，没带 Authorization 头，被 gateway-nginx 兜底返回 "Gateway OK"
 * - 新实现用 fetch + Blob：携带 token、真实错误透传到 message.error、最后通过临时 <a> 触发下载
 * - 加入 NEXT_PUBLIC_API_URL / NEXT_PUBLIC_BASE_PATH 前缀拼接，确保经过 gateway 反向代理
 */
async function downloadAsCsv(apiPath: string, filename: string): Promise<void> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
  const apiBase = apiUrl ? apiUrl.replace(/\/api\/?$/, '') : '';
  const url = `${apiBase}${apiPath}`;
  let token: string | null = null;
  if (typeof window !== 'undefined') {
    token = localStorage.getItem('admin_token');
  }
  try {
    const resp = await fetch(url, {
      method: 'GET',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
    });
    if (!resp.ok) {
      let errMsg = `导出失败：HTTP ${resp.status}`;
      try {
        const text = await resp.text();
        if (text) {
          try {
            const j = JSON.parse(text);
            errMsg = j?.detail || j?.message || text.slice(0, 200);
          } catch {
            errMsg = text.slice(0, 200);
          }
        }
      } catch {}
      message.error(errMsg);
      return;
    }
    const blob = await resp.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(objectUrl);
  } catch (e: unknown) {
    message.error(`导出失败：${(e as Error)?.message || '网络异常'}`);
  }
}

export default function CouponsPage() {
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Coupon | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [filterOffline, setFilterOffline] = useState<string>('');
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();
  const [couponType, setCouponType] = useState<string>('full_reduction');
  const [scope, setScope] = useState<string>('all');
  const [isSuperuser, setIsSuperuser] = useState(false);

  // V2.2 适用范围 & 类型说明优化
  const [typeHelpVisible, setTypeHelpVisible] = useState(false);
  const [scopeCategoryIds, setScopeCategoryIds] = useState<number[]>([]);
  const [scopeProductIds, setScopeProductIds] = useState<number[]>([]);
  const [excludeProductIds, setExcludeProductIds] = useState<number[]>([]);
  const [productPickerOpen, setProductPickerOpen] = useState(false);
  const [excludePickerOpen, setExcludePickerOpen] = useState(false);
  // 已选商品/排除商品的回显详情（图+名）
  const [productDetailsCache, setProductDetailsCache] = useState<Record<number, PickerProduct & { missing?: boolean; off_shelf?: boolean }>>({});
  // 上限配置
  const [scopeMax, setScopeMax] = useState(100);
  const [excludeMax, setExcludeMax] = useState(50);

  // 发放记录抽屉
  const [grantsVisible, setGrantsVisible] = useState(false);
  const [grantsCoupon, setGrantsCoupon] = useState<Coupon | null>(null);
  const [grants, setGrants] = useState<GrantItem[]>([]);
  const [grantsLoading, setGrantsLoading] = useState(false);
  const [grantFilters, setGrantFilters] = useState<{ phone?: string; status?: string; method?: string; range?: any[] }>({});
  const [selectedGrantIds, setSelectedGrantIds] = useState<number[]>([]);

  // 4 种发放方式
  const [grantTypeModalVisible, setGrantTypeModalVisible] = useState(false);
  const [grantTypeCoupon, setGrantTypeCoupon] = useState<Coupon | null>(null);
  const [grantTypeForm] = Form.useForm();
  const [grantTypeMethod, setGrantTypeMethod] = useState<string>('direct');

  // 兑换码批次创建
  const [codeBatchModalVisible, setCodeBatchModalVisible] = useState(false);
  const [codeBatchCoupon, setCodeBatchCoupon] = useState<Coupon | null>(null);
  const [codeBatchForm] = Form.useForm();
  const [partners, setPartners] = useState<Array<{ id: number; name: string }>>([]);

  // V2.1：批次列表抽屉（按 coupon 维度）
  const [batchListVisible, setBatchListVisible] = useState(false);
  const [batchListCoupon, setBatchListCoupon] = useState<Coupon | null>(null);
  const [batches, setBatches] = useState<CodeBatchItem[]>([]);
  const [batchesLoading, setBatchesLoading] = useState(false);

  // V2.1：批次明细抽屉
  const [batchDetailVisible, setBatchDetailVisible] = useState(false);
  const [batchDetailLoading, setBatchDetailLoading] = useState(false);
  const [batchDetail, setBatchDetail] = useState<any>(null);
  const [revealCodes, setRevealCodes] = useState(false);

  // V2.1：下架弹窗
  const [offlineModalVisible, setOfflineModalVisible] = useState(false);
  const [offlineCoupon, setOfflineCoupon] = useState<Coupon | null>(null);
  const [offlineForm] = Form.useForm();

  // V2.1：整批作废弹窗
  const [voidBatchVisible, setVoidBatchVisible] = useState(false);
  const [voidBatchTarget, setVoidBatchTarget] = useState<CodeBatchItem | null>(null);
  const [voidBatchForm] = Form.useForm();

  useEffect(() => {
    try {
      const stored = localStorage.getItem('admin_user');
      if (stored) {
        const u = JSON.parse(stored);
        setIsSuperuser(!!u.is_superuser);
      }
    } catch {}
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterStatus) params.status = filterStatus;
      if (filterOffline !== '') params.is_offline = filterOffline;
      if (searchText) params.keyword = searchText;
      const res = await get('/api/admin/coupons', params);
      if (res) {
        const items = res.items || res.list || [];
        setCoupons(Array.isArray(items) ? items : []);
        setPagination(prev => ({ ...prev, current: page, pageSize, total: res.total ?? items.length }));
      }
    } catch (err: any) {
      setCoupons([]);
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterOffline, searchText]);

  useEffect(() => { fetchData(); }, []);
  useEffect(() => { get('/api/admin/partners').then((r: any) => setPartners(r?.items || [])).catch(() => {}); }, []);
  // V2.2：拉适用范围 / 排除商品上限
  useEffect(() => {
    get('/api/admin/coupons/scope-limits')
      .then((r: any) => {
        if (typeof r?.scope_max_products === 'number') setScopeMax(r.scope_max_products);
        if (typeof r?.exclude_max_products === 'number') setExcludeMax(r.exclude_max_products);
      })
      .catch(() => {});
  }, []);

  // V2.2：根据 scopeProductIds + excludeProductIds 拉取详情，用于卡片回显
  const fetchProductDetails = useCallback(async (ids: number[]) => {
    if (!ids || ids.length === 0) return;
    const missing = ids.filter(id => !productDetailsCache[id]);
    if (missing.length === 0) return;
    try {
      const res: any = await get(`/api/admin/coupons/product-picker?selected_ids=${missing.join(',')}&page=1&page_size=1`);
      const next = { ...productDetailsCache };
      (res?.selected_items || []).forEach((it: any) => {
        next[it.id] = it;
      });
      setProductDetailsCache(next);
    } catch {}
  }, [productDetailsCache]);

  useEffect(() => { fetchProductDetails([...scopeProductIds, ...excludeProductIds]); }, [scopeProductIds, excludeProductIds, fetchProductDetails]);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({
      type: 'full_reduction', scope: 'all', status: 'active',
      total_count: 100, condition_amount: 0, discount_value: 0,
      discount_rate: 0.8, validity_days: 30,
      points_exchange_limit: null,
    });
    setCouponType('full_reduction');
    setScope('all');
    setScopeCategoryIds([]);
    setScopeProductIds([]);
    setExcludeProductIds([]);
    setModalVisible(true);
  };

  const handleEdit = (record: Coupon) => {
    setEditingRecord(record);
    setCouponType(record.type);
    setScope(record.scope);
    // 历史 scope_ids 兼容（字符串/数组）
    let scopeIdsArr: number[] = [];
    const raw = record.scope_ids;
    if (Array.isArray(raw)) {
      scopeIdsArr = raw.map((x: any) => Number(x)).filter((n: number) => !isNaN(n));
    } else if (typeof raw === 'string' && raw) {
      scopeIdsArr = raw.split(',').map((s: string) => Number(s.trim())).filter((n: number) => !isNaN(n));
    } else if (typeof raw === 'number') {
      scopeIdsArr = [raw];
    }
    if (record.scope === 'category') {
      setScopeCategoryIds(scopeIdsArr);
      setScopeProductIds([]);
    } else if (record.scope === 'product') {
      setScopeProductIds(scopeIdsArr);
      setScopeCategoryIds([]);
    } else {
      setScopeCategoryIds([]);
      setScopeProductIds([]);
    }
    setExcludeProductIds(Array.isArray(record.exclude_ids) ? record.exclude_ids : []);
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      condition_amount: record.condition_amount,
      discount_value: record.discount_value,
      discount_rate: record.discount_rate,
      scope: record.scope,
      total_count: record.total_count,
      validity_days: record.validity_days || 30,
      status: record.status,
      points_exchange_limit: record.points_exchange_limit ?? null,
    });
    setModalVisible(true);
  };

  // V2.1：下架
  const openOffline = (record: Coupon) => {
    setOfflineCoupon(record);
    offlineForm.resetFields();
    offlineForm.setFieldsValue({ reason_type: '活动结束' });
    setOfflineModalVisible(true);
  };

  const submitOffline = async () => {
    if (!offlineCoupon) return;
    try {
      const values = await offlineForm.validateFields();
      const payload: any = { reason_type: values.reason_type };
      if (values.reason_type === '其他') {
        payload.reason_detail = values.reason_detail;
      }
      await post(`/api/admin/coupons/${offlineCoupon.id}/offline`, payload);
      message.success('已下架');
      setOfflineModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '下架失败');
    }
  };

  const handleOnline = async (record: Coupon) => {
    Modal.confirm({
      title: '确认重新上架？',
      content: '上架后该券将立即在领券中心可见。',
      onOk: async () => {
        try {
          await post(`/api/admin/coupons/${record.id}/online`, {});
          message.success('上架成功');
          fetchData(pagination.current, pagination.pageSize);
        } catch (err: any) {
          message.error(err?.response?.data?.detail || '上架失败');
        }
      },
    });
  };

  const submitCoupon = async (values: any, allowFreeTrialAll = false) => {
    let scopeIds: number[] | null = null;
    if (values.scope === 'category') {
      if (!scopeCategoryIds.length) {
        message.error('请至少选择 1 个分类');
        return;
      }
      scopeIds = scopeCategoryIds;
    } else if (values.scope === 'product') {
      if (!scopeProductIds.length) {
        message.error('请至少选择 1 个商品');
        return;
      }
      scopeIds = scopeProductIds;
    }
    let excludeIds: number[] | null = null;
    if (values.scope !== 'product' && excludeProductIds.length > 0) {
      excludeIds = excludeProductIds;
    }
    // 类型 free_trial + scope=all 黄色二次确认
    if (values.type === 'free_trial' && values.scope === 'all' && !allowFreeTrialAll) {
      Modal.confirm({
        title: '免费体验券设为全店生效风险较高，是否继续？',
        okText: '继续保存',
        okType: 'warning' as any,
        onOk: () => submitCoupon(values, true),
      });
      return;
    }
    // [优惠券下单页 Bug 修复 v2 · B2] free_trial 强制清零，避免 UI 隐藏后历史值仍被提交
    const isFreeTrial = values.type === 'free_trial';
    const payload: any = {
      name: values.name,
      type: values.type,
      condition_amount: isFreeTrial ? 0 : (values.condition_amount ?? 0),
      discount_value: isFreeTrial ? 0 : (values.discount_value ?? 0),
      discount_rate: isFreeTrial ? 1.0 : (values.discount_rate ?? 1.0),
      scope: values.scope,
      scope_ids: scopeIds,
      exclude_ids: excludeIds,
      total_count: values.total_count ?? 0,
      validity_days: values.validity_days ?? 30,
      status: values.status,
    };
    if (values.points_exchange_limit !== undefined && values.points_exchange_limit !== null) {
      payload.points_exchange_limit = values.points_exchange_limit;
    }
    try {
      if (editingRecord) {
        await put(`/api/admin/coupons/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/coupons', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      await submitCoupon(values);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  // 渲染已选商品/排除商品的小卡片
  const renderProductChips = (ids: number[], onRemove: (id: number) => void) => (
    <Space size={[6, 6]} wrap style={{ marginTop: 8 }}>
      {ids.map(id => {
        const d = productDetailsCache[id];
        const isMissing = d?.missing;
        const isOff = d?.off_shelf;
        const color = isMissing ? 'red' : (isOff ? 'orange' : 'default');
        const tip = isMissing
          ? `❌ 商品已不存在(ID:${id})`
          : (isOff ? `⚠️ 商品已下架(${d?.name || id})` : (d?.name || `商品#${id}`));
        return (
          <Tag
            key={id}
            color={color}
            closable
            onClose={(e) => { e.preventDefault(); onRemove(id); }}
            style={{ padding: '4px 8px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
          >
            {d?.image && !isMissing && (
              <Image src={resolveAssetUrl(d.image)} width={20} height={20} preview={false} fallback="/no-image.png" />
            )}
            <span>{tip}</span>
          </Tag>
        );
      })}
    </Space>
  );

  // ─── 发放记录 ───
  const openGrants = async (record: Coupon) => {
    setGrantsCoupon(record);
    setGrantFilters({});
    setSelectedGrantIds([]);
    setGrantsVisible(true);
    await loadGrants(record.id, {});
  };

  const loadGrants = async (couponId: number, filters: any) => {
    setGrantsLoading(true);
    try {
      const params: any = { page: 1, page_size: 100 };
      if (filters.phone) params.phone = filters.phone;
      if (filters.status) params.status = filters.status;
      if (filters.method) params.method = filters.method;
      if (filters.range?.[0]) params.start = filters.range[0].toISOString();
      if (filters.range?.[1]) params.end = filters.range[1].toISOString();
      const res: any = await get(`/api/admin/coupons/${couponId}/grants`, params);
      setGrants(res?.items || []);
    } catch (err: any) {
      setGrants([]);
      message.error(err?.response?.data?.detail || '加载发放记录失败');
    } finally {
      setGrantsLoading(false);
    }
  };

  const exportGrants = async () => {
    if (!grantsCoupon) return;
    // BUG ③修复：用 fetch+Blob 下载（带 token），避免 window.open 跳转命中 gateway 兜底
    await downloadAsCsv(
      `/api/admin/coupons/${grantsCoupon.id}/grants/export`,
      `coupon_grants_${grantsCoupon.id}.csv`,
    );
  };

  const recallGrants = async () => {
    if (selectedGrantIds.length === 0) {
      message.warning('请先选择要回收的记录');
      return;
    }
    let reason = '';
    Modal.confirm({
      title: `回收 ${selectedGrantIds.length} 条发放记录`,
      content: (
        <Input.TextArea rows={3} placeholder="请填写回收原因（必填）"
          onChange={(e) => { reason = e.target.value; }} />
      ),
      okText: '确认回收',
      onOk: async () => {
        if (!reason.trim()) {
          message.error('回收原因必填');
          return Promise.reject();
        }
        try {
          await post('/api/admin/coupons/grants/recall', { grant_ids: selectedGrantIds, reason });
          message.success('回收成功');
          setSelectedGrantIds([]);
          if (grantsCoupon) await loadGrants(grantsCoupon.id, grantFilters);
        } catch (err: any) {
          message.error(err?.response?.data?.detail || '回收失败');
        }
      },
    });
  };

  // ─── 4 种发放 ───
  const openGrantType = (record: Coupon) => {
    setGrantTypeCoupon(record);
    setGrantTypeMethod('direct');
    grantTypeForm.resetFields();
    grantTypeForm.setFieldsValue({ method: 'direct' });
    setGrantTypeModalVisible(true);
  };

  const submitGrantType = async () => {
    if (!grantTypeCoupon) return;
    try {
      const values = await grantTypeForm.validateFields();
      if (grantTypeMethod === 'direct') {
        const payload: any = {
          coupon_id: grantTypeCoupon.id,
          user_ids: values.user_ids
            ? String(values.user_ids).split(',').map((s: string) => Number(s.trim())).filter((n: number) => !isNaN(n) && n > 0)
            : null,
          phones: values.phones
            ? String(values.phones).split(/[,\s]+/).map((s: string) => s.trim()).filter(Boolean)
            : null,
          filter_tags: {},
        };
        if (values.member_level !== undefined && values.member_level !== null && values.member_level !== '')
          payload.filter_tags.member_level = values.member_level;
        if (values.registered_within_days)
          payload.filter_tags.registered_within_days = values.registered_within_days;
        const res: any = await post(`/api/admin/coupons/${grantTypeCoupon.id}/grant/direct`, payload);
        message.success(res?.message || '发放成功');
        setGrantTypeModalVisible(false);
        fetchData(pagination.current, pagination.pageSize);
      } else if (grantTypeMethod === 'new_user') {
        const cur: any = await get('/api/admin/new-user-coupons');
        const ids = Array.from(new Set([...(cur?.coupon_ids || []), grantTypeCoupon.id]));
        await put('/api/admin/new-user-coupons', { coupon_ids: ids });
        message.success('已加入新人券（注册后自动发放）');
        setGrantTypeModalVisible(false);
      } else if (grantTypeMethod === 'self') {
        message.success('该券为启用状态时，用户即可在「领券中心」自助领取');
        setGrantTypeModalVisible(false);
      } else if (grantTypeMethod === 'redeem_code') {
        setGrantTypeModalVisible(false);
        setCodeBatchCoupon(grantTypeCoupon);
        codeBatchForm.resetFields();
        codeBatchForm.setFieldsValue({ code_type: 'unique', total_count: 100, per_user_limit: 1, claim_limit: 100 });
        setCodeBatchModalVisible(true);
      }
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const submitCodeBatch = async () => {
    if (!codeBatchCoupon) return;
    try {
      const values = await codeBatchForm.validateFields();
      const payload: any = {
        coupon_id: codeBatchCoupon.id,
        code_type: values.code_type,
        name: values.name,
        total_count: values.total_count,
        universal_code: values.universal_code,
        per_user_limit: values.per_user_limit ?? 1,
        partner_id: values.partner_id || null,
      };
      if (values.code_type === 'universal') {
        payload.claim_limit = values.claim_limit;
      }
      if (values.expire_at) {
        payload.expire_at = values.expire_at.toISOString();
      }
      const res: any = await post('/api/admin/coupons/redeem-code-batches', payload);
      message.success(values.code_type === 'universal'
        ? `通用兑换码已生成（批次号：${res.batch_no}）`
        : `已生成 ${res.total_count} 个一次性唯一码（批次号：${res.batch_no}）`);
      setCodeBatchModalVisible(false);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  // ─── V2.1：批次列表 ───
  const openBatchList = async (record: Coupon) => {
    setBatchListCoupon(record);
    setBatchListVisible(true);
    await loadBatches(record.id);
  };

  const loadBatches = async (couponId: number) => {
    setBatchesLoading(true);
    try {
      const res: any = await get('/api/admin/coupons/redeem-code-batches', {
        coupon_id: couponId, page: 1, page_size: 100,
      });
      setBatches(res?.items || []);
    } catch (err: any) {
      setBatches([]);
      message.error(err?.response?.data?.detail || '加载批次失败');
    } finally {
      setBatchesLoading(false);
    }
  };

  const [currentBatchId, setCurrentBatchId] = React.useState<number | null>(null);
  const [currentBatchNo, setCurrentBatchNo] = React.useState<string>('');

  const openBatchDetail = async (batch: CodeBatchItem) => {
    setBatchDetailVisible(true);
    setRevealCodes(false);
    setCurrentBatchId(batch.id);
    setCurrentBatchNo(batch.batch_no);
    await loadBatchDetail(batch.id, false);
  };

  const loadBatchDetail = async (batchId: number, reveal: boolean) => {
    setBatchDetailLoading(true);
    try {
      const res: any = await get(`/api/admin/coupons/redeem-code-batches/${batchId}/codes`, {
        reveal: reveal ? 'true' : 'false',
      });
      setBatchDetail(res);
    } catch (err: any) {
      setBatchDetail(null);
      message.error(err?.response?.data?.detail || '加载明细失败');
    } finally {
      setBatchDetailLoading(false);
    }
  };

  const toggleReveal = async () => {
    if (!currentBatchId) return;
    const next = !revealCodes;
    setRevealCodes(next);
    await loadBatchDetail(currentBatchId, next);
  };

  const copyCode = (code: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code).then(() => message.success(`已复制：${code}`));
    } else {
      const ta = document.createElement('textarea');
      ta.value = code; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); message.success(`已复制：${code}`); }
      finally { document.body.removeChild(ta); }
    }
  };

  const exportBatchCsv = async (batch: CodeBatchItem) => {
    // BUG ③修复：后端实际路径为 `/codes/export`；改用 fetch+Blob 下载（带 token + 真实错误提示）
    await downloadAsCsv(
      `/api/admin/coupons/redeem-code-batches/${batch.id}/codes/export`,
      `${batch.batch_no || `batch_${batch.id}`}_codes.csv`,
    );
  };

  const openVoidBatch = (batch: CodeBatchItem) => {
    setVoidBatchTarget(batch);
    voidBatchForm.resetFields();
    setVoidBatchVisible(true);
  };

  const submitVoidBatch = async () => {
    if (!voidBatchTarget) return;
    try {
      const values = await voidBatchForm.validateFields();
      if (values.batch_no_confirm !== voidBatchTarget.batch_no) {
        message.error('批次编号输入不一致，请仔细核对');
        return;
      }
      await post(`/api/admin/coupons/redeem-code-batches/${voidBatchTarget.id}/void`, {
        batch_no_confirm: values.batch_no_confirm,
        reason: values.reason,
      });
      message.success('整批作废成功');
      setVoidBatchVisible(false);
      if (batchListCoupon) await loadBatches(batchListCoupon.id);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '作废失败');
    }
  };

  const voidSingleCode = async (codeId: number) => {
    let reason = '';
    Modal.confirm({
      title: '确认作废该兑换码？',
      content: (
        <Input.TextArea rows={3} placeholder="请填写作废原因（必填）"
          onChange={(e) => { reason = e.target.value; }} />
      ),
      okText: '确认作废',
      okButtonProps: { danger: true },
      onOk: async () => {
        if (!reason.trim()) {
          message.error('作废原因必填');
          return Promise.reject();
        }
        try {
          await post(`/api/admin/coupons/codes/${codeId}/void`, { reason });
          message.success('已作废');
          if (currentBatchId) await loadBatchDetail(currentBatchId, revealCodes);
        } catch (err: any) {
          message.error(err?.response?.data?.detail || '作废失败');
        }
      },
    });
  };

  const descriptionText = (record: Coupon) => {
    switch (record.type) {
      case 'full_reduction': return `满${record.condition_amount}减${record.discount_value}`;
      case 'discount': return `${(record.discount_rate * 10).toFixed(1)}折${record.condition_amount > 0 ? ` (满${record.condition_amount})` : ''}`;
      case 'voucher': return `代金券 ¥${record.discount_value}`;
      case 'free_trial': return `免费体验`;
      default: return '-';
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '优惠券名称', dataIndex: 'name', key: 'name', width: 200,
      render: (v: string, r: Coupon) => (
        <Space size={4}>
          <span>{v}</span>
          {r.is_offline && <Tag color="red">已下架</Tag>}
        </Space>
      ),
    },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 90,
      render: (v: string) => <Tag color={couponTypeColorMap[v] || 'default'}>{couponTypeMap[v] || v}</Tag>,
    },
    { title: '优惠规则', key: 'rule', width: 180, render: (_: unknown, r: Coupon) => descriptionText(r) },
    {
      title: '适用范围', dataIndex: 'scope', key: 'scope', width: 100,
      render: (v: string) => ({ all: '全部商品', category: '指定分类', product: '指定商品' } as Record<string, string>)[v] || v,
    },
    {
      title: '库存/已领/已用', key: 'counts', width: 140,
      render: (_: unknown, r: Coupon) => `${r.total_count} / ${r.claimed_count} / ${r.used_count}`,
    },
    {
      title: '有效期', key: 'valid', width: 140,
      render: (_: unknown, r: Coupon) => <Tag color="cyan">领取后 {r.validity_days || 30} 天</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 380, fixed: 'right' as const,
      render: (_: unknown, record: Coupon) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<SendOutlined />} onClick={() => openGrantType(record)} disabled={!!record.is_offline}>发放</Button>
          <Button type="link" size="small" icon={<HistoryOutlined />} onClick={() => openGrants(record)}>发放记录</Button>
          <Button type="link" size="small" icon={<FileTextOutlined />} onClick={() => openBatchList(record)}>兑换码批次</Button>
          {record.is_offline ? (
            <Tooltip title={isSuperuser ? '重新上架' : '仅超级管理员可操作'}>
              <Button type="link" size="small" icon={<ReloadOutlined />} disabled={!isSuperuser}
                onClick={() => handleOnline(record)}>重新上架</Button>
            </Tooltip>
          ) : (
            <Tooltip title={isSuperuser ? '下架（不可物理删除）' : '仅超级管理员可下架'}>
              <Button type="link" size="small" danger icon={<StopOutlined />} disabled={!isSuperuser}
                onClick={() => openOffline(record)}>下架</Button>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>优惠券管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增优惠券</Button>
      </div>

      {!isSuperuser && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message="提示：当前账号非超级管理员，无法执行下架/上架操作（V2.1：优惠券一律不可物理删除，统一改为下架）" />
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select placeholder="按状态筛选" allowClear style={{ width: 120 }}
            options={statusOptions} value={filterStatus} onChange={v => setFilterStatus(v)} />
        </Col>
        <Col>
          <Select placeholder="上下架筛选" style={{ width: 130 }}
            options={offlineFilterOptions} value={filterOffline}
            onChange={v => setFilterOffline(v ?? '')} />
        </Col>
        <Col>
          <Input placeholder="搜索优惠券名称" prefix={<SearchOutlined />}
            value={searchText} onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch} style={{ width: 220 }} allowClear />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table columns={columns} dataSource={coupons} rowKey="id" loading={loading}
        pagination={{
          ...pagination, showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1600 }} />

      {/* 新增/编辑弹窗 */}
      <Modal title={editingRecord ? '编辑优惠券' : '新增优惠券'} open={modalVisible}
        onOk={handleSubmit} onCancel={() => setModalVisible(false)} width={680} destroyOnClose>
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="优惠券名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="请输入优惠券名称" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label={
                  <span>
                    优惠券类型
                    <Tooltip title="点击查看 4 种类型的完整说明">
                      <QuestionCircleOutlined
                        style={{ marginLeft: 6, color: '#999', cursor: 'pointer' }}
                        onClick={() => setTypeHelpVisible(true)}
                        onMouseEnter={(e) => (e.currentTarget.style.color = '#52c41a')}
                        onMouseLeave={(e) => (e.currentTarget.style.color = '#999')}
                      />
                    </Tooltip>
                  </span>
                }
                name="type"
                rules={[{ required: true, message: '请选择类型' }]}
              >
                <Select options={couponTypeOptions} onChange={v => setCouponType(v)} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="状态" name="status">
                <Select options={statusOptions} />
              </Form.Item>
            </Col>
          </Row>

          {/* [优惠券下单页 Bug 修复 v2 · B2] 免费体验券：本质是"整单 0 元"，不存在门槛金额 / 优惠金额，全部隐藏。 */}
          {couponType !== 'free_trial' && (
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="使用门槛金额" name="condition_amount">
                  <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0 表示无门槛" />
                </Form.Item>
              </Col>
              {(couponType === 'full_reduction' || couponType === 'voucher') && (
                <Col span={12}>
                  <Form.Item label="优惠金额" name="discount_value">
                    <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
                  </Form.Item>
                </Col>
              )}
              {couponType === 'discount' && (
                <Col span={12}>
                  <Form.Item label="折扣率" name="discount_rate" extra="如 0.8 表示八折">
                    <InputNumber min={0.01} max={1} step={0.01} style={{ width: '100%' }} placeholder="0.80" />
                  </Form.Item>
                </Col>
              )}
            </Row>
          )}
          {couponType === 'free_trial' && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message='免费体验券：凭券免费体验指定商品，整单按 0 元结算，无需设置门槛金额和优惠金额。建议搭配"指定商品"使用并设置发行总量、单人限领，避免被刷。'
            />
          )}

          <Divider plain>适用范围</Divider>
          <Form.Item name="scope" label="适用范围" rules={[{ required: true }]}>
            <Radio.Group onChange={(e) => setScope(e.target.value)}>
              <Space direction="vertical">
                <Radio value="all">
                  全部商品
                  <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>适合全场满减、节日券</span>
                </Radio>
                <Radio value="category">
                  指定分类
                  <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>适合品类清仓、分类专享</span>
                </Radio>
                <Radio value="product">
                  指定商品
                  <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>适合爆款促销、新品试用</span>
                </Radio>
              </Space>
            </Radio.Group>
          </Form.Item>

          {scope === 'all' && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="该券对全店所有在售商品生效（实物 + 到店服务，虚拟商品本期不纳入）"
            />
          )}

          {scope === 'category' && (
            <Form.Item label="选择分类">
              <CategoryTreePicker
                value={scopeCategoryIds}
                onChange={setScopeCategoryIds}
              />
            </Form.Item>
          )}

          {scope === 'product' && (
            <Form.Item label={`选择商品（最多 ${scopeMax} 个）`}>
              <Button icon={<AppstoreOutlined />} onClick={() => setProductPickerOpen(true)}>
                {scopeProductIds.length > 0 ? `已选 ${scopeProductIds.length} 个，点击修改` : '点击选择商品'}
              </Button>
              {scopeProductIds.length > 0 && renderProductChips(
                scopeProductIds,
                (id) => setScopeProductIds(prev => prev.filter(x => x !== id)),
              )}
            </Form.Item>
          )}

          {(scope === 'all' || scope === 'category') && (
            <Form.Item
              label={
                <span>
                  排除商品（可选，最多 {excludeMax} 个）
                  <Tooltip title="设置后，本券对所选范围生效，但被排除的商品不参与">
                    <QuestionCircleOutlined style={{ marginLeft: 6, color: '#999' }} />
                  </Tooltip>
                </span>
              }
            >
              <Button onClick={() => setExcludePickerOpen(true)}>
                {excludeProductIds.length > 0 ? `已排除 ${excludeProductIds.length} 个，点击修改` : '+ 选择排除商品'}
              </Button>
              {excludeProductIds.length > 0 && renderProductChips(
                excludeProductIds,
                (id) => setExcludeProductIds(prev => prev.filter(x => x !== id)),
              )}
            </Form.Item>
          )}

          <ScopeSummaryBar
            scope={scope}
            scopeIds={scope === 'category' ? scopeCategoryIds : (scope === 'product' ? scopeProductIds : [])}
            excludeIds={excludeProductIds}
          />
          <Divider plain>其他</Divider>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="发行总量" name="total_count">
                <InputNumber min={0} style={{ width: '100%' }} placeholder="0 表示不限量" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="有效期" name="validity_days" extra="从用户领取时刻起算 N 天后失效"
                rules={[{ required: true, message: '请选择有效期' }]}>
                <Select
                  options={VALIDITY_OPTIONS.map(d => ({ label: `${d} 天`, value: d }))}
                  placeholder="请选择" />
              </Form.Item>
            </Col>
          </Row>

          <Divider plain>积分兑换（预留，本期不启用）</Divider>
          <Form.Item label="积分兑换次数上限"
            name="points_exchange_limit"
            extra="留空 = 无限次；与「免费领取限领 1 次」独立计数。待积分兑换功能上线后启用">
            <InputNumber min={1} style={{ width: '100%' }} placeholder="留空 = 无限次" />
          </Form.Item>
        </Form>
      </Modal>

      {/* V2.2 类型说明弹窗 */}
      <CouponTypeHelpModal open={typeHelpVisible} onClose={() => setTypeHelpVisible(false)} />

      {/* V2.2 商品弹窗（适用商品） */}
      <ProductPickerModal
        open={productPickerOpen}
        title="选择商品"
        maxCount={scopeMax}
        showSwitchToCategory
        initialSelectedIds={scopeProductIds}
        onCancel={() => setProductPickerOpen(false)}
        onConfirm={(ids) => { setScopeProductIds(ids); setProductPickerOpen(false); }}
        onSwitchToCategory={() => {
          setScope('category');
          form.setFieldValue('scope', 'category');
          setScopeProductIds([]);
        }}
      />

      {/* V2.2 商品弹窗（排除商品） */}
      <ProductPickerModal
        open={excludePickerOpen}
        title="选择要排除的商品"
        maxCount={excludeMax}
        showSwitchToCategory={false}
        initialSelectedIds={excludeProductIds}
        onCancel={() => setExcludePickerOpen(false)}
        onConfirm={(ids) => { setExcludeProductIds(ids); setExcludePickerOpen(false); }}
      />

      {/* 4 种发放方式 */}
      <Modal title={`发放优惠券：${grantTypeCoupon?.name || ''}`}
        open={grantTypeModalVisible} onOk={submitGrantType}
        onCancel={() => setGrantTypeModalVisible(false)} width={680} destroyOnClose>
        <Form form={grantTypeForm} layout="vertical">
          <Form.Item label="发放方式" name="method" initialValue="direct">
            <Select onChange={v => setGrantTypeMethod(v)}
              options={[
                { label: 'A 自助领取（用户在领券中心自助领取）', value: 'self' },
                { label: 'B 定向发放（指定用户/手机号/标签）', value: 'direct' },
                { label: 'D 新人券（注册自动发放）', value: 'new_user' },
                { label: 'F 兑换码（一码通用 / 一次性唯一码）', value: 'redeem_code' },
              ]} />
          </Form.Item>
          {grantTypeMethod === 'direct' && (
            <>
              <Form.Item label="用户ID（多个用逗号分隔）" name="user_ids">
                <Input placeholder="如: 1,2,3" />
              </Form.Item>
              <Form.Item label="手机号（多个用逗号或空格分隔）" name="phones">
                <Input.TextArea rows={2} placeholder="13800000000,13800000001" />
              </Form.Item>
              <Divider plain>标签筛选（可选）</Divider>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="用户等级" name="member_level" extra="0=普通会员，1+=付费/高级">
                    <InputNumber min={0} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="注册时长 ≤ N 天" name="registered_within_days">
                    <InputNumber min={0} style={{ width: '100%' }} placeholder="如 30 表示新注册 30 天内" />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}
          {grantTypeMethod === 'new_user' && (
            <div style={{ padding: 16, background: '#f6ffed', borderRadius: 8 }}>
              <p>确定后，新注册用户将自动获得本券（每人 1 张）</p>
              <p style={{ color: '#999', marginBottom: 0 }}>已加入新人券池后，可在「新人券池」中管理。</p>
            </div>
          )}
          {grantTypeMethod === 'self' && (
            <div style={{ padding: 16, background: '#e6f7ff', borderRadius: 8 }}>
              <p>启用状态的优惠券将自动出现在用户「领券中心」。</p>
              <p style={{ color: '#999', marginBottom: 0 }}>每人每券限领 1 张。已领取后按钮置灰显示「已领取」。</p>
            </div>
          )}
          {grantTypeMethod === 'redeem_code' && (
            <div style={{ padding: 16, background: '#fff7e6', borderRadius: 8 }}>
              <p>确定后将打开兑换码批次创建窗口</p>
            </div>
          )}
        </Form>
      </Modal>

      {/* 兑换码批次创建 */}
      <Modal title={`生成兑换码批次：${codeBatchCoupon?.name || ''}`}
        open={codeBatchModalVisible} onOk={submitCodeBatch}
        onCancel={() => setCodeBatchModalVisible(false)} width={620} destroyOnClose>
        <Form form={codeBatchForm} layout="vertical">
          <Form.Item label="批次名称" name="name">
            <Input placeholder="如：2026Q2 双11 通用券" />
          </Form.Item>
          <Form.Item label="码类型" name="code_type" rules={[{ required: true }]}>
            <Select options={[
              { label: 'A 一码通用（所有用户使用同一个码，需指定领取人数上限）', value: 'universal' },
              { label: 'C+ 一次性唯一码（每码每人 1 次）', value: 'unique' },
            ]} />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {() => codeBatchForm.getFieldValue('code_type') === 'universal' ? (
              <>
                <Form.Item label="自定义通用码（留空自动生成）" name="universal_code">
                  <Input placeholder="如 NEW2026" />
                </Form.Item>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="领取人数上限" name="claim_limit"
                      rules={[{ required: true, message: '一码通用必须指定领取人数上限' }]}
                      extra="V2.1：一码通用必填，超出后兑换码失效">
                      <InputNumber min={1} style={{ width: '100%' }} placeholder="如 100" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="每用户限兑次数" name="per_user_limit" initialValue={1}>
                      <InputNumber min={1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
              </>
            ) : (
              <Form.Item label="生成数量" name="total_count" rules={[{ required: true }]}
                extra="单批最多 100000 个，16 位随机字符。领取人数上限 = 生成数量">
                <InputNumber min={1} max={100000} style={{ width: '100%' }} />
              </Form.Item>
            )}
          </Form.Item>
          <Form.Item label="兑换码有效期" name="expire_at" extra="留空表示与优惠券同步">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="第三方合作方（可选，C+ 模式必填）" name="partner_id">
            <Select allowClear placeholder="选择合作方"
              options={partners.map(p => ({ label: p.name, value: p.id }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* V2.1：批次列表抽屉 */}
      <Drawer title={`兑换码批次：${batchListCoupon?.name || ''}`} width={1200}
        open={batchListVisible} onClose={() => setBatchListVisible(false)}>
        <Table size="small" rowKey="id" loading={batchesLoading} dataSource={batches}
          columns={[
            { title: '批次编号', dataIndex: 'batch_no', width: 200,
              render: (v: string) => <Text code copyable>{v}</Text> },
            { title: '关联券', dataIndex: 'coupon_name', width: 160 },
            { title: '码类型', dataIndex: 'code_type', width: 100,
              render: (v: string) => v === 'universal' ? <Tag color="orange">一码通用</Tag> : <Tag color="blue">一次性唯一</Tag> },
            { title: '生成时间', dataIndex: 'created_at', width: 160,
              render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            { title: '生成人', dataIndex: 'creator_name', width: 110, render: (v: string) => v || '-' },
            { title: '总数', dataIndex: 'total_count', width: 70 },
            { title: '已用', dataIndex: 'used_codes_count', width: 70 },
            { title: '未用', dataIndex: 'available_count', width: 70 },
            { title: '已作废', dataIndex: 'voided_count', width: 80 },
            { title: '上限', dataIndex: 'claim_limit', width: 70, render: (v: number) => v ?? '-' },
            { title: '有效期', dataIndex: 'expire_at', width: 140,
              render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '永久' },
            { title: '状态', key: 'state', width: 100,
              render: (_: any, r: CodeBatchItem) => r.voided_at
                ? <Tag color="red">已作废</Tag>
                : <Tag color="green">有效</Tag> },
            { title: '操作', key: 'action', fixed: 'right' as const, width: 240,
              render: (_: any, r: CodeBatchItem) => (
                <Space size={0} wrap>
                  <Button type="link" size="small" onClick={() => openBatchDetail(r)}>查看明细</Button>
                  <Button type="link" size="small" icon={<DownloadOutlined />}
                    onClick={() => exportBatchCsv(r)}>导出CSV</Button>
                  {!r.voided_at && (
                    <Button type="link" size="small" danger icon={<StopOutlined />}
                      onClick={() => openVoidBatch(r)}>作废整批</Button>
                  )}
                </Space>
              ) },
          ]}
          scroll={{ x: 1500 }} />
      </Drawer>

      {/* V2.1：批次明细抽屉 */}
      <Drawer title={`批次明细：${currentBatchNo || ''}`} width={1100}
        open={batchDetailVisible} onClose={() => setBatchDetailVisible(false)}
        extra={
          batchDetail && (
            <Space>
              <Button icon={revealCodes ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                onClick={toggleReveal}>{revealCodes ? '隐藏码' : '显示完整码'}</Button>
            </Space>
          )
        }>
        {batchDetailLoading || !batchDetail ? (
          <div style={{ padding: 40, textAlign: 'center' }}>加载中...</div>
        ) : batchDetail.code_type === 'universal' ? (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="兑换码" value={batchDetail.code}
                    valueStyle={{ fontSize: 16, fontFamily: 'monospace' }}
                    suffix={<Button size="small" icon={<CopyOutlined />}
                      onClick={() => copyCode(batchDetail.code)} disabled={!revealCodes} />} />
                </Card>
              </Col>
              <Col span={6}><Card size="small"><Statistic title="领取上限" value={batchDetail.claim_limit ?? '∞'} /></Card></Col>
              <Col span={6}><Card size="small"><Statistic title="已被兑换" value={batchDetail.used || 0} /></Card></Col>
              <Col span={6}><Card size="small"><Statistic title="剩余"
                value={batchDetail.claim_limit ? Math.max(0, (batchDetail.claim_limit || 0) - (batchDetail.used || 0)) : '∞'} /></Card></Col>
            </Row>
            {batchDetail.voided_at && (
              <Alert type="error" showIcon style={{ marginBottom: 12 }}
                message={`本批次已作废 · 原因：${batchDetail.void_reason || '-'} · 时间：${dayjs(batchDetail.voided_at).format('YYYY-MM-DD HH:mm')}`} />
            )}
            <Title level={5}>兑换记录</Title>
            <Table size="small" rowKey={(r: any) => `${r.user_id}-${r.redeemed_at}`} dataSource={batchDetail.records || []}
              columns={[
                { title: '用户ID', dataIndex: 'user_id', width: 80 },
                { title: '手机号', dataIndex: 'user_phone', width: 130 },
                { title: '兑换时间', dataIndex: 'redeemed_at', width: 160,
                  render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                { title: '状态', dataIndex: 'status', width: 90,
                  render: (v: string) => {
                    const s = grantStatusMap[v] || { label: v, color: 'default' };
                    return <Tag color={s.color}>{s.label}</Tag>;
                  } },
              ]} />
          </>
        ) : (
          <>
            {batchDetail.voided_at && (
              <Alert type="error" showIcon style={{ marginBottom: 12 }}
                message={`本批次已整批作废 · 原因：${batchDetail.void_reason || '-'}`} />
            )}
            <Table size="small" rowKey="id" dataSource={batchDetail.items || []}
              columns={[
                { title: '兑换码', dataIndex: 'code', width: 200,
                  render: (v: string, r: any) => (
                    <Space>
                      <Text code style={{ fontFamily: 'monospace' }}>{v}</Text>
                      <Button size="small" type="text" icon={<CopyOutlined />}
                        disabled={!revealCodes} onClick={() => copyCode(r.code_full || v)} />
                    </Space>
                  ) },
                { title: '状态', dataIndex: 'status', width: 100,
                  render: (v: string, r: any) => {
                    if (r.voided_at) return <Tag color="red">已作废</Tag>;
                    if (v === 'used') return <Tag color="green">已使用</Tag>;
                    if (v === 'sold') return <Tag color="orange">已售出</Tag>;
                    return <Tag color="blue">未用</Tag>;
                  } },
                { title: '兑换用户', dataIndex: 'used_by_user_phone', width: 130, render: (v: string) => v || '-' },
                { title: '兑换时间', dataIndex: 'used_at', width: 160,
                  render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                { title: '作废原因', dataIndex: 'void_reason', width: 150, render: (v: string) => v || '-' },
                { title: '操作', key: 'action', width: 150,
                  render: (_: any, r: any) => (
                    <Space size={0}>
                      <Button size="small" type="link" icon={<CopyOutlined />}
                        disabled={!revealCodes} onClick={() => copyCode(r.code_full || r.code)}>复制</Button>
                      {!r.voided_at && r.status !== 'used' && (
                        <Button size="small" type="link" danger icon={<StopOutlined />}
                          onClick={() => voidSingleCode(r.id)}>作废</Button>
                      )}
                    </Space>
                  ) },
              ]} />
          </>
        )}
      </Drawer>

      {/* V2.1：下架弹窗（强校验 + 必填原因） */}
      <Modal title={`下架优惠券：${offlineCoupon?.name || ''}`}
        open={offlineModalVisible} onOk={submitOffline}
        onCancel={() => setOfflineModalVisible(false)} okText="确认下架"
        okButtonProps={{ danger: true }} destroyOnClose width={520}>
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message="下架后该券将不再展示在领券中心，但已领取的用户仍可正常使用至过期" />
        <Form form={offlineForm} layout="vertical">
          <Form.Item label="下架原因" name="reason_type"
            rules={[{ required: true, message: '请选择下架原因' }]}>
            <Select options={OFFLINE_REASON_PRESETS.map(o => ({ label: o, value: o }))} />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {() => offlineForm.getFieldValue('reason_type') === '其他' && (
              <Form.Item label="详细原因（最少 5 字）" name="reason_detail"
                rules={[
                  { required: true, message: '请填写详细原因' },
                  { min: 5, message: '至少 5 个字' },
                ]}>
                <Input.TextArea rows={3} placeholder="请填写下架的详细原因" />
              </Form.Item>
            )}
          </Form.Item>
        </Form>
      </Modal>

      {/* V2.1：整批作废弹窗（强二次确认） */}
      <Modal title="作废整批兑换码（不可恢复）"
        open={voidBatchVisible} onOk={submitVoidBatch}
        onCancel={() => setVoidBatchVisible(false)} okText="确认作废"
        okButtonProps={{ danger: true }} destroyOnClose width={520}>
        <Alert type="error" showIcon style={{ marginBottom: 12 }}
          message="作废后该批次内所有未使用兑换码将立即失效，已领取的优惠券不受影响" />
        <Form form={voidBatchForm} layout="vertical">
          <Form.Item label={`请输入完整批次编号 ${voidBatchTarget?.batch_no} 以确认`}
            name="batch_no_confirm"
            rules={[{ required: true, message: '请输入批次编号' }]}>
            <Input placeholder="复制批次编号粘贴" />
          </Form.Item>
          <Form.Item label="作废原因" name="reason"
            rules={[{ required: true, message: '请填写作废原因' }, { min: 2, message: '至少 2 个字' }]}>
            <Input.TextArea rows={3} placeholder="请填写作废原因" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 发放记录抽屉 */}
      <Drawer title={`发放记录：${grantsCoupon?.name || ''}`} width={1100}
        open={grantsVisible} onClose={() => setGrantsVisible(false)}
        extra={
          <Space>
            <Button icon={<DownloadOutlined />} onClick={exportGrants}>导出 Excel</Button>
            <Button danger icon={<RollbackOutlined />} onClick={recallGrants}
              disabled={selectedGrantIds.length === 0}>批量回收</Button>
          </Space>
        }>
        <Row gutter={8} style={{ marginBottom: 12 }}>
          <Col><Input placeholder="手机号" allowClear style={{ width: 160 }}
            value={grantFilters.phone} onChange={e => setGrantFilters(f => ({ ...f, phone: e.target.value }))} /></Col>
          <Col><Select placeholder="状态" allowClear style={{ width: 120 }}
            options={Object.entries(grantStatusMap).map(([k, v]) => ({ label: v.label, value: k }))}
            value={grantFilters.status} onChange={v => setGrantFilters(f => ({ ...f, status: v }))} /></Col>
          <Col><Select placeholder="发放方式" allowClear style={{ width: 140 }}
            options={Object.entries(grantMethodMap).map(([k, v]) => ({ label: v, value: k }))}
            value={grantFilters.method} onChange={v => setGrantFilters(f => ({ ...f, method: v }))} /></Col>
          <Col><DatePicker.RangePicker showTime
            value={grantFilters.range as any}
            onChange={v => setGrantFilters(f => ({ ...f, range: v as any }))} /></Col>
          <Col><Button type="primary" onClick={() => grantsCoupon && loadGrants(grantsCoupon.id, grantFilters)}>筛选</Button></Col>
        </Row>
        <Table size="small" rowKey="id" loading={grantsLoading} dataSource={grants}
          rowSelection={{
            selectedRowKeys: selectedGrantIds,
            onChange: (keys) => setSelectedGrantIds(keys as number[]),
          }}
          columns={[
            { title: '用户/手机号', key: 'who', width: 160,
              render: (_: any, r: GrantItem) => `${r.user_id ?? ''} ${r.user_phone ?? ''}`.trim() || '-' },
            { title: '发放时间', dataIndex: 'granted_at', width: 160,
              render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            { title: '方式', dataIndex: 'method', width: 100,
              render: (v: string) => grantMethodMap[v] || v },
            { title: '状态', dataIndex: 'status', width: 90,
              render: (v: string) => {
                const s = grantStatusMap[v] || { label: v, color: 'default' };
                return <Tag color={s.color}>{s.label}</Tag>;
              } },
            { title: '使用时间', dataIndex: 'used_at', width: 160,
              render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            { title: '订单号', dataIndex: 'order_no', width: 160,
              render: (v: string) => v ? <a>{v}</a> : '-' },
            { title: '操作人', dataIndex: 'operator_name', width: 120,
              render: (v: string) => v || '-' },
            { title: '兑换码', dataIndex: 'redeem_code', width: 160,
              render: (v: string) => v || '-' },
            { title: '回收原因', dataIndex: 'recall_reason', width: 160,
              render: (v: string) => v || '-' },
          ]} />
      </Drawer>
    </div>
  );
}
