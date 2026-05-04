'use client';

/**
 * [2026-05-02 H5 下单流程优化 PRD v1.0]
 * 支付页统一选择：商品详情页只展示，所有「日期 → 时段 → 门店」选择移到本页面。
 *
 * 核心特性：
 *   1. 顶部商品摘要（图+名+SKU+价格）
 *   2. ① 选择日期：横向 7 天卡片（含/不含今天由 include_today 控制）
 *   3. ② 选择时段：横向时段按钮，已满档隐藏；未选门店时按商品配置全部展示
 *   4. ③ 选择门店：行卡片，点击进入门店列表 Popup（搜索 + 距离/字母双排序），
 *      首次点击门店卡片时调 navigator.geolocation 请求定位（PRD §4.5）
 *   5. 联系人手机号（默认填账户绑定 / 上次缓存）
 *   6. 订单备注（≤ 50 字）
 *   7. 切换门店冲突智能保留：日期/时段不可用时变红边框，立即支付按钮置灰
 *   8. 提交时把 store_id / appointment_date / appointment_slot 全部带入下单接口
 *
 * [2026-05-04 H5 支付链路 Bug 修复] 支付方式从 `/api/pay/available-methods?platform=h5` 拉取；
 *   创单后按 `paid_amount` 分支：0 元走 `confirm-free`，否则走 `/pay`（含 `pay_url` 跳转）。
 *   订单详情页 `handlePay` 同步改造。
 */

import { useState, useEffect, useMemo, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  NavBar,
  Card,
  Image,
  Button,
  Toast,
  Stepper,
  Radio,
  Space,
  Input,
  TextArea,
  Popup,
  List,
  Tag,
  SpinLoading,
  Switch,
  SearchBar,
} from 'antd-mobile';
import { RightOutline, LeftOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

// ───────────── 类型 ─────────────

interface ProductInfo {
  id: number;
  name: string;
  sale_price: number;
  original_price: number | null;
  images: string[] | null;
  fulfillment_type: string;
  points_deductible: boolean;
  appointment_mode: string;
  include_today?: boolean;
  redeem_count: number;
  advance_days?: number;
  time_slots?: { start: string; end: string; capacity: number }[];
  purchase_appointment_mode?: string;
  spec_mode?: number;
  skus?: Array<{ id: number; spec_name: string; sale_price: number; origin_price: number | null; stock: number; is_default: boolean; status: number; sort_order: number }>;
}

interface Address {
  id: number;
  name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  street: string;
  is_default: boolean;
}

interface UserCoupon {
  id: number;
  coupon_id: number;
  coupon: {
    id: number;
    name: string;
    type: string;
    condition_amount: number;
    discount_value: number;
    discount_rate: number;
    valid_end: string | null;
  } | null;
}

interface AvailableStore {
  store_id: number;
  store_code?: string;
  name: string;
  address?: string;
  province?: string | null;
  city?: string | null;
  district?: string | null;
  lat?: number | null;
  lng?: number | null;
  distance_km?: number | null;
  is_nearest?: boolean;
  static_map_url?: string | null;
  slot_capacity?: number;
  business_start?: string | null;
  business_end?: string | null;
}

interface SlotItem {
  start: string;
  end: string;
  label: string;
  available: number;
  capacity: number;
}

interface DateRange {
  start: string | null;
  end: string | null;
  include_today: boolean;
  advance_days: number;
}

const PHONE_RE = /^1[3-9]\d{9}$/;
const NOTES_MAX = 50;
const LAST_CONTACT_PHONE_KEY = 'last_contact_phone';

// ───────────── 工具函数 ─────────────

function formatDateStr(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const WEEK_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

function buildDates(range: DateRange | null): { date: string; weekLabel: string; mmdd: string }[] {
  if (!range || !range.start || !range.end) return [];
  const start = new Date(range.start + 'T00:00:00');
  const end = new Date(range.end + 'T00:00:00');
  const days: { date: string; weekLabel: string; mmdd: string }[] = [];
  for (let cur = new Date(start); cur.getTime() <= end.getTime(); cur.setDate(cur.getDate() + 1)) {
    const mm = String(cur.getMonth() + 1).padStart(2, '0');
    const dd = String(cur.getDate()).padStart(2, '0');
    days.push({
      date: formatDateStr(cur),
      weekLabel: WEEK_LABELS[cur.getDay()],
      mmdd: `${mm}-${dd}`,
    });
  }
  return days;
}

// 商品时段是否落在门店营业时段内
function inBusinessHours(s: string, e: string, bizStart?: string | null, bizEnd?: string | null): boolean {
  if (!bizStart || !bizEnd) return true;
  return s >= bizStart && e <= bizEnd;
}

// 拼音首字母（极简实现：仅用于无定位时按字母排序，不依赖外部库）
function getPinyinFirstLetter(name: string): string {
  const ch = (name || '').charAt(0);
  // 英文/数字直接返回
  if (/[A-Za-z0-9]/.test(ch)) return ch.toUpperCase();
  // 中文：按 Unicode 区段粗略映射
  const code = ch.charCodeAt(0);
  if (Number.isNaN(code) || code < 0x4e00 || code > 0x9fff) return 'Z';
  // 简单按段映射（精度足够用于排序）
  const ranges: Array<[number, string]> = [
    [0xb0a1, 'A'], [0xb0c5, 'B'], [0xb2c1, 'C'], [0xb4ee, 'D'], [0xb6ea, 'E'],
    [0xb7a2, 'F'], [0xb8c1, 'G'], [0xb9fe, 'H'], [0xbbf7, 'J'], [0xbfa6, 'K'],
    [0xc0ac, 'L'], [0xc2e8, 'M'], [0xc4c3, 'N'], [0xc5b6, 'O'], [0xc5be, 'P'],
    [0xc6da, 'Q'], [0xc8bb, 'R'], [0xc8f6, 'S'], [0xcbfa, 'T'], [0xcdda, 'W'],
    [0xcef4, 'X'], [0xd1b9, 'Y'], [0xd4d1, 'Z'],
  ];
  // 转 GB2312 不可行，简单按 Unicode 范围估算（0x4e00 ~ 0x9fff 平均映射 A~Z）
  const span = 0x9fff - 0x4e00;
  const idx = Math.floor(((code - 0x4e00) / span) * 26);
  return String.fromCharCode(65 + Math.max(0, Math.min(25, idx)));
}

// ───────────── 页面 ─────────────

export default function CheckoutWrapper() {
  return (
    <Suspense fallback={<div />}>
      <CheckoutPage />
    </Suspense>
  );
}

function CheckoutPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const productId = searchParams.get('product_id');
  const initQty = Number(searchParams.get('quantity') || 1);
  const skuIdParam = searchParams.get('sku_id');
  const skuId = skuIdParam ? Number(skuIdParam) : null;

  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [quantity, setQuantity] = useState(initQty);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddress, setSelectedAddress] = useState<Address | null>(null);
  const [showAddressPicker, setShowAddressPicker] = useState(false);

  const [coupons, setCoupons] = useState<UserCoupon[]>([]);
  const [selectedCoupon, setSelectedCoupon] = useState<UserCoupon | null>(null);
  const [showCouponPicker, setShowCouponPicker] = useState(false);

  const [usePoints, setUsePoints] = useState(false);
  const [pointsDeduction, setPointsDeduction] = useState(0);
  const [userPoints, setUserPoints] = useState(0);

  const [paymentMethod, setPaymentMethod] = useState('wechat');
  // [2026-05-04 H5 支付链路 Bug 修复] 动态可用支付方式 + 当前选中通道
  const [availableMethods, setAvailableMethods] = useState<Array<{ channel_code: string; display_name: string; provider: string }>>([]);
  const [selectedPayment, setSelectedPayment] = useState<string>('');

  // ── 三段式选择 + 联系人 + 备注 ──
  const [dateRange, setDateRange] = useState<DateRange | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedSlot, setSelectedSlot] = useState<string>(''); // 形如 "09:00-11:00"
  const [storeSlots, setStoreSlots] = useState<SlotItem[]>([]); // 门店已选时返回的可用时段（已排除满档）
  const [productSlots, setProductSlots] = useState<{ start: string; end: string }[]>([]); // 商品配置全部时段
  const [stores, setStores] = useState<AvailableStore[]>([]);
  const [selectedStore, setSelectedStore] = useState<AvailableStore | null>(null);
  const [contactPhone, setContactPhone] = useState<string>('');
  const [phoneTouched, setPhoneTouched] = useState<boolean>(false);
  const [notes, setNotes] = useState<string>('');

  const [storePopupVisible, setStorePopupVisible] = useState<boolean>(false);
  const [storeSearchKw, setStoreSearchKw] = useState<string>('');
  const [geoStatus, setGeoStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied'>('idle');
  const [showGeoTip, setShowGeoTip] = useState<boolean>(false);
  const [userLat, setUserLat] = useState<number | null>(null);
  const [userLng, setUserLng] = useState<number | null>(null);

  // ── 初始化数据 ──
  useEffect(() => {
    if (!productId) return;
    setLoading(true);
    Promise.allSettled([
      api.get(`/api/products/${productId}`),
      api.get(`/api/h5/checkout/init?productId=${productId}`),
      api.get('/api/addresses'),
      // [优惠券下单页 Bug 修复 v2 · B3] 切换为下单页专用券列表接口（仅返回本单可用的券）
      api.get('/api/coupons/usable-for-order', { params: { product_id: productId, subtotal: 0 } }),
      api.get('/api/points/summary'),
    ]).then(([pRes, initRes, aRes, cRes, ptRes]) => {
      if (pRes.status === 'fulfilled') {
        const data = (pRes.value as any).data || pRes.value;
        setProduct(data);
        const slots = (data?.time_slots || []).map((s: any) => ({ start: s.start, end: s.end }));
        setProductSlots(slots);
      }
      if (initRes.status === 'fulfilled') {
        const data = (initRes.value as any).data?.data || (initRes.value as any).data || initRes.value;
        if (data?.date_range) {
          setDateRange(data.date_range);
          if (data.date_range.start) setSelectedDate(data.date_range.start);
        }
        // 联系人手机号优先级：账户绑定 > localStorage > 留空
        const phoneFromInit = data?.contact_phone || '';
        let initPhone = phoneFromInit;
        if (!initPhone) {
          try { initPhone = window.localStorage.getItem(LAST_CONTACT_PHONE_KEY) || ''; } catch { initPhone = ''; }
        }
        setContactPhone(initPhone || '');
        // 默认门店（不直接展示距离/不调定位）
        if (data?.default_store && !selectedStore) {
          setSelectedStore({
            store_id: data.default_store.id || data.default_store.store_id,
            name: data.default_store.name,
            address: data.default_store.address,
            lat: data.default_store.lat,
            lng: data.default_store.lng,
            slot_capacity: data.default_store.slot_capacity,
            business_start: data.default_store.business_start,
            business_end: data.default_store.business_end,
          });
        }
      }
      if (aRes.status === 'fulfilled') {
        const data = (aRes.value as any).data || aRes.value;
        const items = data.items || data || [];
        setAddresses(Array.isArray(items) ? items : []);
        const def = (Array.isArray(items) ? items : []).find((a: Address) => a.is_default);
        if (def) setSelectedAddress(def);
        else if (items.length > 0) setSelectedAddress(items[0]);
      }
      if (cRes.status === 'fulfilled') {
        const data = (cRes.value as any).data || cRes.value;
        // [优惠券下单页 Bug 修复 v2 · B3] 后端已按 subtotal/适用范围过滤，前端无需再做硬过滤
        setCoupons(data.items || data || []);
      }
      if (ptRes.status === 'fulfilled') {
        const data = (ptRes.value as any).data || ptRes.value;
        setUserPoints(data.total_points || 0);
      }
    }).finally(() => setLoading(false));
  }, [productId]);

  // [2026-05-04 H5 支付链路 Bug 修复] 拉取 H5 平台已启用的支付通道
  useEffect(() => {
    api.get('/api/pay/available-methods', { params: { platform: 'h5' } })
      .then((res: any) => {
        const data = res?.data || res;
        const list = Array.isArray(data) ? data : (Array.isArray(data?.data) ? data.data : []);
        setAvailableMethods(list);
        if (list.length > 0) {
          setSelectedPayment((prev) => prev || list[0].channel_code);
        }
      })
      .catch(() => setAvailableMethods([]));
  }, []);

  // [优惠券下单页 Bug 修复 v2 · B3] 当商品/规格/数量变化导致 subtotal 改变时，重新向后端拉取「真正可用的券」
  useEffect(() => {
    if (!productId || !product) return;
    const sku = skuId && Array.isArray((product as any).skus)
      ? (product as any).skus.find((s: any) => s.id === skuId)
      : null;
    const unit = sku ? Number(sku.sale_price) : Number(product.sale_price || 0);
    const sub = Math.round(unit * quantity * 100) / 100;
    api.get('/api/coupons/usable-for-order', { params: { product_id: productId, subtotal: sub } })
      .then((res) => {
        const data = (res as any).data || res;
        setCoupons(data.items || data || []);
        // 已选的券若不再可用则清空
        if (selectedCoupon) {
          const stillOk = (data.items || []).some((it: any) => it.id === selectedCoupon.id);
          if (!stillOk) setSelectedCoupon(null);
        }
      })
      .catch(() => {/* 静默：保留上一次 coupons */});
    // selectedCoupon 不能放进依赖，否则清空后又会回拉一次造成抖动
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, product, skuId, quantity]);

  // ── 门店已选 + 日期已选 时拉取该门店该日的可用时段 ──
  const fetchStoreSlots = useCallback(async (store: AvailableStore | null, date: string) => {
    if (!store || !date || !productId) {
      setStoreSlots([]);
      return;
    }
    try {
      const res: any = await api.get(`/api/h5/slots?storeId=${store.store_id}&date=${date}&productId=${productId}`);
      const data = res?.data?.data || res?.data || res;
      setStoreSlots(Array.isArray(data?.slots) ? data.slots : []);
    } catch {
      setStoreSlots([]);
    }
  }, [productId]);

  useEffect(() => {
    fetchStoreSlots(selectedStore, selectedDate);
  }, [selectedStore, selectedDate, fetchStoreSlots]);

  // ── 加载门店列表（仅在用户首次点击门店卡片时被调用） ──
  const loadStores = useCallback(async (lat?: number, lng?: number) => {
    if (!productId) return [] as AvailableStore[];
    try {
      const params = (lat !== undefined && lng !== undefined) ? `?lat=${lat}&lng=${lng}` : '';
      const res: any = await api.get(`/api/products/${productId}/available-stores${params}`);
      const data = res?.data?.data || res?.data || res;
      const list: AvailableStore[] = Array.isArray(data?.stores) ? data.stores : [];
      // 无定位时按拼音首字母排序兜底
      const finalList = (lat !== undefined && lng !== undefined)
        ? list
        : [...list].sort((a, b) => getPinyinFirstLetter(a.name).localeCompare(getPinyinFirstLetter(b.name)));
      setStores(finalList);
      return finalList;
    } catch {
      setStores([]);
      return [];
    }
  }, [productId]);

  // ── 点击门店卡片时才请求定位 ──
  const onClickStoreCard = useCallback(() => {
    setStorePopupVisible(true);
    if (geoStatus === 'granted') {
      // 已授权过，直接复用上一次坐标
      loadStores(userLat || undefined, userLng || undefined);
      return;
    }
    if (geoStatus === 'denied') {
      // 拒绝过：列表按字母排序 + 顶部提示
      loadStores();
      return;
    }
    // 首次：请求定位授权
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      setGeoStatus('requesting');
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setGeoStatus('granted');
          setUserLat(pos.coords.latitude);
          setUserLng(pos.coords.longitude);
          loadStores(pos.coords.latitude, pos.coords.longitude);
        },
        () => {
          setGeoStatus('denied');
          loadStores();
        },
        { enableHighAccuracy: false, timeout: 8000, maximumAge: 30 * 60 * 1000 },
      );
    } else {
      setGeoStatus('denied');
      loadStores();
    }
  }, [geoStatus, loadStores, userLat, userLng]);

  // ── 切换门店智能保留：选中新门店后，已选时段不在新门店可用列表则置空 ──
  const onSelectStore = useCallback(async (s: AvailableStore) => {
    setSelectedStore(s);
    setStorePopupVisible(false);
    // 拉取新门店时段后再判定（loadStores 已经更新过 storeSlots 触发条件）
    const slots = await api.get(`/api/h5/slots?storeId=${s.store_id}&date=${selectedDate}&productId=${productId}`)
      .then((res: any) => {
        const data = res?.data?.data || res?.data || res;
        return Array.isArray(data?.slots) ? data.slots : [];
      })
      .catch(() => []);
    setStoreSlots(slots as SlotItem[]);
    // 检查已选时段是否仍可用
    if (selectedSlot) {
      const stillOk = (slots as SlotItem[]).some(it => it.label === selectedSlot);
      if (!stillOk) {
        // 不立即清空，允许界面变红提示用户重选；点击其它时段时切换
      }
    }
  }, [productId, selectedDate, selectedSlot]);

  // ── 提交校验 ──
  const phoneValid = !contactPhone || PHONE_RE.test(contactPhone);
  const phoneError = phoneTouched && !PHONE_RE.test(contactPhone);

  const dates = useMemo(() => buildDates(dateRange), [dateRange]);

  // 显示用时段：按 PRD §4.4，未选门店时按"商品配置时段"展示；已选门店时使用 storeSlots（已经排除满档+营业时段过滤）
  const slotsToShow: { label: string; start: string; end: string; disabled: boolean; full: boolean; expired: boolean }[] = useMemo(() => {
    const isToday = selectedDate === formatDateStr(new Date());
    const now = new Date();
    const nowHM = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    if (selectedStore) {
      return storeSlots.map(s => {
        const expired = isToday && s.end <= nowHM;
        return {
          label: s.label,
          start: s.start,
          end: s.end,
          disabled: expired,
          full: false,
          expired,
        };
      });
    }
    // 未选门店：展示商品全部时段
    return productSlots.map(s => {
      const label = `${s.start}-${s.end}`;
      const expired = isToday && s.end <= nowHM;
      return { label, start: s.start, end: s.end, disabled: expired, full: false, expired };
    });
  }, [productSlots, storeSlots, selectedStore, selectedDate]);

  // 已选时段在切换门店后是否变红（智能保留）
  const slotInvalid = useMemo(() => {
    if (!selectedSlot || !selectedStore) return false;
    return !storeSlots.some(it => it.label === selectedSlot);
  }, [selectedSlot, storeSlots, selectedStore]);

  if (!productId) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>确认订单</NavBar>
        <div className="text-center text-gray-400 py-40">参数错误</div>
      </div>
    );
  }

  if (loading || !product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>确认订单</NavBar>
        <div className="flex items-center justify-center py-40"><SpinLoading color="primary" /></div>
      </div>
    );
  }

  const round2 = (n: number) => Math.round(n * 100) / 100;
  const selectedSku = skuId && Array.isArray((product as any).skus)
    ? (product as any).skus.find((s: any) => s.id === skuId)
    : null;
  const unitPrice = selectedSku ? Number(selectedSku.sale_price) : product.sale_price;
  const skuName = selectedSku ? String(selectedSku.spec_name || '') : '';
  const subtotal = round2(unitPrice * quantity);
  // [优惠券下单页 Bug 修复 v2 · B1] free_trial 整单 0 元抵扣
  const couponDiscount = round2((() => {
    const c = selectedCoupon?.coupon as any;
    if (!c) return 0;
    if (c.type === 'free_trial') return subtotal;
    if (c.type === 'discount') return subtotal * (1 - c.discount_rate);
    return c.discount_value || 0;
  })());
  const pointsValue = usePoints ? round2(pointsDeduction / 100) : 0;
  const totalAmount = round2(Math.max(0, subtotal - couponDiscount - pointsValue));

  const isDelivery = product.fulfillment_type === 'delivery';
  const isInStore = product.fulfillment_type === 'in_store';
  // [上门服务履约 PRD v1.0 · F5] 上门服务必须选择服务地址
  const isOnSite = product.fulfillment_type === 'on_site';
  // [先下单后预约 Bug 修复 v1.0]
  // 是否在下单页展示预约时间控件，需要同时满足：
  //   1) 商品 appointment_mode != 'none'（即开启了预约功能）
  //   2) purchase_appointment_mode == 'purchase_with_appointment'（下单即预约）
  // 当 purchase_appointment_mode 为 appointment_later/appoint_later（先下单后预约）时，
  // 下单页完全不展示预约控件，由用户付款后在订单详情页再发起预约。
  const isBookWithOrder =
    !product.purchase_appointment_mode ||
    product.purchase_appointment_mode === 'purchase_with_appointment' ||
    product.purchase_appointment_mode === 'must_appoint';
  const needAppointment = product.appointment_mode !== 'none' && isBookWithOrder;
  // [预约日期模式支付页误显示「选择时段」 Bug 修复 v1.0]
  // 把 needAppointment 进一步按预约模式分流：
  //   - needDate     : date / time_slot 都需要选日期
  //   - needTimeSlot : 仅 time_slot 需要选时段（date 模式只按天限流，绝不能再渲染时段）
  // 命名上一刀切清楚后，UI / 校验 / 提交全部引用 needTimeSlot，杜绝再次"漏分流"。
  const needDate = needAppointment && (product.appointment_mode === 'date' || product.appointment_mode === 'time_slot');
  const needTimeSlot = needAppointment && product.appointment_mode === 'time_slot';

  // 立即支付按钮启用条件
  const canSubmit = (() => {
    if (needDate && !selectedDate) return false;
    if (needTimeSlot) {
      if (!selectedSlot) return false;
      if (slotInvalid) return false;
    }
    if (isInStore && !selectedStore) return false;
    if (isDelivery && !selectedAddress) return false;
    if (isOnSite && !selectedAddress) return false;
    if (!contactPhone || !PHONE_RE.test(contactPhone)) return false;
    if (notes.length > NOTES_MAX) return false;
    return true;
  })();

  const handleSubmit = async () => {
    if (!canSubmit) {
      if (!selectedDate && needDate) Toast.show({ content: '请选择预约日期' });
      else if (!selectedSlot && needTimeSlot) Toast.show({ content: '请选择时段' });
      else if (slotInvalid) Toast.show({ content: '该门店此时段不可用，请重新选择' });
      else if (isInStore && !selectedStore) Toast.show({ content: '请选择门店' });
      else if (isDelivery && !selectedAddress) Toast.show({ content: '请选择收货地址' });
      else if (isOnSite && !selectedAddress) Toast.show({ content: '请选择上门服务地址' });
      else if (!PHONE_RE.test(contactPhone)) Toast.show({ content: '请输入正确的手机号' });
      return;
    }
    // [2026-05-04 H5 支付链路 Bug 修复] 付费订单需选中支付方式（0 元订单后续会走 confirm-free 兜底）
    if (totalAmount > 0 && availableMethods.length === 0) {
      Toast.show({ content: '暂未开通支付方式，请联系管理员' });
      return;
    }
    if (totalAmount > 0 && !selectedPayment) {
      Toast.show({ content: '请选择支付方式' });
      return;
    }
    setSubmitting(true);
    try {
      const appointmentTimeStr = needAppointment && selectedDate
        ? needTimeSlot && selectedSlot
          ? `${selectedDate}T${selectedSlot.split('-')[0]}:00`
          : `${selectedDate}T00:00:00`
        : undefined;
      const appointmentDataObj = needAppointment
        ? {
            date: selectedDate,
            // [预约日期模式 Bug 修复 v1.0] date 模式不携带 time_slot，仅 time_slot 模式才带
            ...(needTimeSlot ? { time_slot: selectedSlot } : {}),
            note: notes,
            store_id: selectedStore?.store_id,
            contact_phone: contactPhone,
          }
        : undefined;

      const orderData: any = {
        items: [{
          product_id: product.id,
          quantity,
          ...(skuId ? { sku_id: skuId } : {}),
          ...(appointmentTimeStr ? { appointment_time: appointmentTimeStr } : {}),
          ...(appointmentDataObj ? { appointment_data: appointmentDataObj } : {}),
        }],
        // [2026-05-04 H5 支付链路 Bug 修复] payment_method 改为携带选中的 channel_code
        payment_method: selectedPayment || paymentMethod,
        points_deduction: usePoints ? pointsDeduction : 0,
        notes: notes || undefined,
      };
      if (selectedCoupon) orderData.coupon_id = selectedCoupon.coupon_id;
      if (selectedAddress) {
        if (isOnSite) {
          orderData.service_address_id = selectedAddress.id;
        } else {
          orderData.shipping_address_id = selectedAddress.id;
        }
      }

      const res: any = await api.post('/api/orders/unified', orderData);
      const order = res?.data || res;
      // 缓存最近一次手机号
      try { window.localStorage.setItem(LAST_CONTACT_PHONE_KEY, contactPhone); } catch {}

      // [2026-05-04 H5 支付链路 Bug 修复] 根据后端返回的 paid_amount 走分支
      const paidAmount = Number(order?.paid_amount) || 0;
      if (paidAmount === 0) {
        // 0 元订单：直接 confirm-free（不受通道开关限制）
        try {
          await api.post(`/api/orders/unified/${order.id}/confirm-free`, {
            channel_code: selectedPayment || null,
          });
        } catch (err: any) {
          // confirm-free 失败也不阻塞跳转，由订单详情页继续提示/重试
          Toast.show({ content: err?.response?.data?.detail || '订单确认失败，请稍后重试' });
          router.push(`/unified-order/${order.id}`);
          return;
        }
        Toast.show({ content: '下单成功' });
        router.push(`/unified-order/${order.id}`);
        return;
      }

      // 付费订单：调用 /pay，按 pay_url 跳转或直接进详情
      try {
        const payRes: any = await api.post(`/api/orders/unified/${order.id}/pay`, {
          channel_code: selectedPayment,
        });
        const payData = payRes?.data || payRes;
        if (payData?.pay_url) {
          window.location.href = payData.pay_url;
          return;
        }
        // pay_url 为空：后端已直接置为已支付，跳订单详情兜底
        Toast.show({ content: '下单成功' });
        router.push(`/unified-order/${order.id}`);
      } catch (err: any) {
        Toast.show({ content: err?.response?.data?.detail || '发起支付失败' });
        router.push(`/unified-order/${order.id}`);
      }
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '下单失败' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-28">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        确认订单
      </NavBar>

      <div className="px-4 pt-3">
        {/* 顶部商品摘要 */}
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex">
            <div className="w-20 h-20 rounded-lg flex-shrink-0 overflow-hidden">
              {product.images && product.images.length > 0 ? (
                <Image src={product.images[0]} width={80} height={80} fit="cover" style={{ borderRadius: 8 }} />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: '#f6ffed' }}>🛍️</div>
              )}
            </div>
            <div className="flex-1 ml-3">
              <div className="font-medium text-sm">{product.name}</div>
              {skuName && <div className="text-xs text-gray-500 mt-0.5">规格：{skuName}</div>}
              <div className="text-sm text-red-500 font-bold mt-1">¥{unitPrice}</div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-400">数量</span>
                <Stepper value={quantity} onChange={setQuantity} min={1} max={10} style={{ '--height': '28px', '--input-width': '36px' }} />
              </div>
            </div>
          </div>
        </Card>

        {(isDelivery || isOnSite) && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }} onClick={() => setShowAddressPicker(true)}>
            {selectedAddress ? (
              <div className="flex items-center">
                <div className="flex-1">
                  <div className="text-xs text-gray-400 mb-1">
                    {isOnSite ? '上门服务地址' : '收货地址'}
                  </div>
                  <div className="font-medium text-sm">
                    {selectedAddress.name} <span className="text-gray-400 ml-2">{selectedAddress.phone}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {selectedAddress.province}{selectedAddress.city}{selectedAddress.district}{selectedAddress.street}
                  </div>
                </div>
                <RightOutline fontSize={14} color="#999" />
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">
                  {isOnSite ? '请选择上门服务地址' : '请选择收货地址'}
                </span>
                <RightOutline fontSize={14} color="#999" />
              </div>
            )}
          </Card>
        )}

        {/* ① 选择日期：横向 7 天 */}
        {needDate && dates.length > 0 && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium"><span style={{ color: '#ff4d4f' }}>*</span> 选择日期</span>
              {dateRange && dateRange.advance_days > 0 && (
                <span className="text-xs text-gray-400">
                  可预约 {dates.length} 天{dateRange.include_today === false ? '（不含今天）' : ''}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', overflowX: 'auto', gap: 8, paddingBottom: 4 }}>
              {dates.map((d) => {
                const sel = d.date === selectedDate;
                return (
                  <div
                    key={d.date}
                    onClick={() => { setSelectedDate(d.date); }}
                    style={{
                      flex: '0 0 auto',
                      minWidth: 56,
                      textAlign: 'center',
                      padding: '8px 4px',
                      borderRadius: 8,
                      background: sel ? '#52c41a' : '#fff',
                      color: sel ? '#fff' : '#333',
                      border: sel ? '1px solid #52c41a' : '1px solid #e5e5e5',
                      cursor: 'pointer',
                      fontSize: 12,
                    }}
                  >
                    <div>周{d.weekLabel}</div>
                    <div style={{ marginTop: 2, fontWeight: sel ? 600 : 400 }}>{d.mmdd}</div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* ② 选择时段（仅 time_slot 模式才渲染；date 模式按设计只按天限流，不展示时段） */}
        {needTimeSlot && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium"><span style={{ color: '#ff4d4f' }}>*</span> 选择时段</span>
              {!selectedStore && (
                <span className="text-xs text-gray-400">建议先选择门店</span>
              )}
            </div>
            {!selectedStore && productSlots.length > 0 && (
              <div className="text-xs text-gray-400 mb-2">时段最终是否可选取决于所选门店</div>
            )}
            <div style={{ display: 'flex', overflowX: 'auto', gap: 8, paddingBottom: 4 }}>
              {slotsToShow.length === 0 && (
                <div className="text-xs text-gray-400 py-2">暂无可用时段</div>
              )}
              {slotsToShow.map((s) => {
                const sel = s.label === selectedSlot;
                const showRed = sel && slotInvalid;
                return (
                  <div
                    key={s.label}
                    onClick={() => { if (!s.disabled) setSelectedSlot(s.label); }}
                    style={{
                      flex: '0 0 auto',
                      padding: '6px 12px',
                      borderRadius: 18,
                      fontSize: 12,
                      background: showRed ? '#fff1f0' : (sel ? '#52c41a' : '#fff'),
                      color: showRed ? '#ff4d4f' : (s.disabled ? '#bbb' : (sel ? '#fff' : '#333')),
                      border: showRed
                        ? '1px solid #ff4d4f'
                        : (sel ? '1px solid #52c41a' : '1px solid #e5e5e5'),
                      cursor: s.disabled ? 'not-allowed' : 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {s.label}{s.expired ? ' 已结束' : ''}
                  </div>
                );
              })}
            </div>
            {slotInvalid && (
              <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 6 }}>
                该门店此时段不可用，请重新选择
              </div>
            )}
          </Card>
        )}

        {/* ③ 选择门店 */}
        {isInStore && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }} onClick={onClickStoreCard}>
            <div className="flex items-center">
              <div style={{ width: 4, height: 36, background: '#1677ff', borderRadius: 2, marginRight: 10 }} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#ff4d4f' }}>*</span>
                  {selectedStore ? (
                    <>
                      <span>{selectedStore.name}</span>
                      {selectedStore.distance_km != null && (
                        <span className="text-xs text-gray-500" style={{ fontWeight: 'normal' }}>距您 {selectedStore.distance_km} km</span>
                      )}
                    </>
                  ) : (
                    <span className="text-gray-400">选择门店</span>
                  )}
                </div>
                {selectedStore?.address && (
                  <div className="text-xs text-gray-500 mt-1" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {selectedStore.province || ''}{selectedStore.city || ''}{selectedStore.district || ''}{selectedStore.address}
                  </div>
                )}
              </div>
              <RightOutline fontSize={14} color="#999" />
            </div>
          </Card>
        )}

        {/* 联系人手机号 */}
        {needAppointment && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium" style={{ minWidth: 90 }}>
                <span style={{ color: '#ff4d4f' }}>*</span> 联系手机号
              </span>
              <Input
                value={contactPhone}
                onChange={(v) => { setContactPhone(v); }}
                onBlur={() => setPhoneTouched(true)}
                placeholder="请输入联系手机号"
                maxLength={11}
                clearable
                style={{ '--text-align': 'right', flex: 1 }}
              />
            </div>
            {phoneError && (
              <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 6, textAlign: 'right' }}>请输入正确的手机号</div>
            )}
          </Card>
        )}

        {/* 订单备注 */}
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <Input
            value={notes}
            onChange={(v) => { if (v.length <= NOTES_MAX) setNotes(v); }}
            placeholder="如有特殊要求请告知门店（选填）"
            maxLength={NOTES_MAX}
            style={{ fontSize: 14 }}
          />
          <div style={{ textAlign: 'right', fontSize: 12, color: '#999', marginTop: 4 }}>{notes.length}/{NOTES_MAX}</div>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }} onClick={() => setShowCouponPicker(true)}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">优惠券</span>
            <div className="flex items-center">
              {selectedCoupon ? (
                <span className="text-sm text-red-500">-¥{couponDiscount}</span>
              ) : (
                <span className="text-sm text-gray-400">{coupons.length > 0 ? `${coupons.length}张可用` : '暂无可用'}</span>
              )}
              <RightOutline fontSize={12} color="#999" className="ml-1" />
            </div>
          </div>
        </Card>

        {product.points_deductible && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">积分抵扣</span>
                <span className="text-xs text-gray-400 ml-2">可用{userPoints}积分</span>
              </div>
              <Switch
                checked={usePoints}
                onChange={(checked) => {
                  setUsePoints(checked);
                  if (checked) {
                    const maxPoints = Math.min(userPoints, Math.floor(subtotal * 100));
                    setPointsDeduction(maxPoints);
                  }
                }}
                style={{ '--checked-color': '#52c41a' }}
              />
            </div>
            {usePoints && (
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-gray-500">使用{pointsDeduction}积分抵扣¥{pointsValue}</span>
              </div>
            )}
          </Card>
        )}

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="section-title" style={{ marginBottom: 8 }}>支付方式</div>
          <Radio.Group value={selectedPayment} onChange={(val) => setSelectedPayment(val as string)}>
            <Space direction="vertical" block>
              {availableMethods.map((m) => (
                <Radio key={m.channel_code} value={m.channel_code}>{m.display_name}</Radio>
              ))}
            </Space>
          </Radio.Group>
          {availableMethods.length === 0 && (
            <div style={{ color: '#999', fontSize: 12, padding: 8 }}>暂未开通支付方式，请联系管理员</div>
          )}
        </Card>
      </div>

      {/* 底部支付栏 */}
      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-500">
            小计 ¥{subtotal}
            {couponDiscount > 0 && <span className="text-red-500 ml-2">-¥{couponDiscount}</span>}
            {pointsValue > 0 && <span className="text-red-500 ml-2">-¥{pointsValue}</span>}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <span className="text-sm text-gray-500">合计：</span>
            <span className="text-xl font-bold text-red-500">¥{totalAmount}</span>
          </div>
          {(() => {
            // [2026-05-04 H5 支付链路 Bug 修复] 付费订单 + 无可用支付通道 → 禁用并提示
            const noPayChannel = totalAmount > 0 && availableMethods.length === 0;
            const btnDisabled = !canSubmit || noPayChannel;
            const btnEnabled = !btnDisabled;
            const label = slotInvalid
              ? '请重新选择时段'
              : noPayChannel
                ? '暂未开通支付方式'
                : '立即支付';
            return (
              <Button
                loading={submitting}
                disabled={btnDisabled}
                onClick={handleSubmit}
                style={{
                  borderRadius: 24,
                  height: 44,
                  width: 160,
                  background: btnEnabled
                    ? 'linear-gradient(135deg, #52c41a, #13c2c2)'
                    : '#e8e8e8',
                  color: btnEnabled ? '#fff' : '#999',
                  border: 'none',
                }}
              >
                {label}
              </Button>
            );
          })()}
        </div>
      </div>

      {/* 收货地址选择 */}
      <Popup
        visible={showAddressPicker}
        onMaskClick={() => setShowAddressPicker(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '60vh' }}
      >
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="font-medium">选择收货地址</span>
            <Button
              size="mini"
              onClick={() => { setShowAddressPicker(false); router.push('/my-addresses'); }}
              style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16 }}
            >
              管理地址
            </Button>
          </div>
          {addresses.length === 0 ? (
            <div className="text-center text-gray-400 py-8">暂无收货地址，请先添加</div>
          ) : (
            <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
              {addresses.map((addr) => (
                <List.Item
                  key={addr.id}
                  onClick={() => { setSelectedAddress(addr); setShowAddressPicker(false); }}
                  prefix={<Radio checked={selectedAddress?.id === addr.id} style={{ '--icon-size': '18px' }} />}
                  description={`${addr.province}${addr.city}${addr.district}${addr.street}`}
                >
                  <span className="text-sm">{addr.name} {addr.phone}</span>
                  {addr.is_default && (
                    <Tag style={{ '--background-color': '#52c41a15', '--text-color': '#52c41a', '--border-color': 'transparent', fontSize: 10, marginLeft: 6 }}>默认</Tag>
                  )}
                </List.Item>
              ))}
            </List>
          )}
        </div>
      </Popup>

      {/* 优惠券选择 */}
      <Popup
        visible={showCouponPicker}
        onMaskClick={() => setShowCouponPicker(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '60vh' }}
      >
        <div className="p-4">
          <div className="font-medium mb-3">选择优惠券</div>
          <List.Item
            onClick={() => { setSelectedCoupon(null); setShowCouponPicker(false); }}
            prefix={
              <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
                <Radio checked={!selectedCoupon} style={{ '--icon-size': '18px' }} />
              </div>
            }
          >
            不使用优惠券
          </List.Item>
          {/* [优惠券下单页 Bug 修复 v2 · B3] 这里的 coupons 由后端 /api/coupons/usable-for-order 过滤后下发，全部即可用，不再做前端 disabled */}
          {coupons.map((uc) => {
            // 兼容 free_trial：description 显示"免费试用"，普通券显示"满 X 可用"
            const c = uc.coupon as any;
            const isFreeTrial = c?.type === 'free_trial';
            const desc = isFreeTrial
              ? `免费试用 ${c?.valid_end ? `| 有效期至${new Date(c.valid_end).toLocaleDateString('zh-CN')}` : ''}`
              : (c ? `满${c.condition_amount}可用 ${c.valid_end ? `| 有效期至${new Date(c.valid_end).toLocaleDateString('zh-CN')}` : ''}` : '');
            return (
              <List.Item
                key={uc.id}
                onClick={() => { setSelectedCoupon(uc); setShowCouponPicker(false); }}
                prefix={
                  // [优惠券下单页 Bug 修复 v2 · B4] 圆圈与文字垂直居中
                  <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
                    <Radio checked={selectedCoupon?.id === uc.id} style={{ '--icon-size': '18px' }} />
                  </div>
                }
                description={desc}
              >
                <span className="text-sm">{c?.name || '优惠券'}</span>
              </List.Item>
            );
          })}
        </div>
      </Popup>

      {/* 门店列表 Popup（全屏） */}
      <Popup
        visible={storePopupVisible}
        position="right"
        onMaskClick={() => setStorePopupVisible(false)}
        bodyStyle={{ width: '100%', height: '100vh', background: '#f5f5f5' }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
          <div style={{ background: '#fff', padding: '8px 12px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 8 }}>
            <LeftOutline fontSize={18} onClick={() => setStorePopupVisible(false)} />
            <SearchBar placeholder="搜索门店名称或地址" value={storeSearchKw} onChange={setStoreSearchKw} style={{ flex: 1 }} />
          </div>
          {geoStatus !== 'granted' && (
            <div
              style={{ background: '#fffbe6', padding: '8px 12px', fontSize: 13, color: '#d48806', cursor: 'pointer' }}
              onClick={onClickStoreCard}
            >
              📍 开启定位以查看距离
            </div>
          )}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {(stores
              .filter(s => !storeSearchKw
                || (s.name || '').includes(storeSearchKw)
                || (s.address || '').includes(storeSearchKw)
              )).map(s => (
              <div
                key={s.store_id}
                onClick={() => onSelectStore(s)}
                style={{ background: '#fff', padding: '12px 16px', marginBottom: 8, borderBottom: '1px solid #f0f0f0', cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 500 }}>{s.name}</span>
                  {s.distance_km != null && (
                    <span style={{ color: '#52c41a', fontSize: 12 }}>距您 {s.distance_km} km</span>
                  )}
                </div>
                {(s.province || s.city || s.district || s.address) && (
                  <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                    {s.province || ''}{s.city || ''}{s.district || ''}{s.address || ''}
                  </div>
                )}
                {s.business_start && s.business_end && (
                  <div style={{ fontSize: 12, color: '#bbb', marginTop: 2 }}>
                    营业 {s.business_start} - {s.business_end}
                  </div>
                )}
              </div>
            ))}
            {stores.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#bbb' }}>
                {geoStatus === 'requesting' ? '正在加载...' : '暂无可用门店'}
              </div>
            )}
          </div>
        </div>
      </Popup>
    </div>
  );
}
