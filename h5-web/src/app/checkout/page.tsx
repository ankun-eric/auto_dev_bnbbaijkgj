'use client';

import { useState, useEffect, Suspense } from 'react';
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
  DatePicker,
} from 'antd-mobile';
import { RightOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface ProductInfo {
  id: number;
  name: string;
  sale_price: number;
  original_price: number;
  images: string[] | null;
  fulfillment_type: string;
  points_deductible: boolean;
  appointment_mode: string;
  redeem_count: number;
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
  const [notes, setNotes] = useState('');
  const [appointmentTime, setAppointmentTime] = useState<Date | null>(null);
  const [showDatePicker, setShowDatePicker] = useState(false);

  useEffect(() => {
    if (!productId) return;
    Promise.allSettled([
      api.get(`/api/products/${productId}`),
      api.get('/api/addresses'),
      api.get('/api/coupons/mine?tab=unused'),
      api.get('/api/points/summary'),
    ]).then(([pRes, aRes, cRes, ptRes]) => {
      if (pRes.status === 'fulfilled') {
        const data = (pRes.value as any).data || pRes.value;
        setProduct(data);
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
        setCoupons(data.items || data || []);
      }
      if (ptRes.status === 'fulfilled') {
        const data = (ptRes.value as any).data || ptRes.value;
        setUserPoints(data.total_points || 0);
      }
    }).finally(() => setLoading(false));
  }, [productId]);

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

  const selectedSku = skuId && Array.isArray((product as any).skus)
    ? (product as any).skus.find((s: any) => s.id === skuId)
    : null;
  const unitPrice = selectedSku ? Number(selectedSku.sale_price) : product.sale_price;
  const skuName = selectedSku ? String(selectedSku.spec_name || '') : '';
  const subtotal = unitPrice * quantity;
  const couponDiscount = selectedCoupon?.coupon
    ? selectedCoupon.coupon.type === 'discount'
      ? subtotal * (1 - selectedCoupon.coupon.discount_rate)
      : selectedCoupon.coupon.discount_value
    : 0;
  const pointsValue = usePoints ? pointsDeduction / 100 : 0;
  const totalAmount = Math.max(0, subtotal - couponDiscount - pointsValue);

  const handleSubmit = async () => {
    if (product.fulfillment_type === 'delivery' && !selectedAddress) {
      Toast.show({ content: '请选择收货地址' });
      return;
    }
    setSubmitting(true);
    try {
      const orderData: any = {
        items: [{
          product_id: product.id,
          quantity,
          ...(skuId ? { sku_id: skuId } : {}),
          ...(appointmentTime ? { appointment_time: appointmentTime.toISOString() } : {}),
        }],
        payment_method: paymentMethod,
        points_deduction: usePoints ? pointsDeduction : 0,
        notes: notes || undefined,
      };
      if (selectedCoupon) orderData.coupon_id = selectedCoupon.coupon_id;
      if (selectedAddress) orderData.shipping_address_id = selectedAddress.id;

      const res: any = await api.post('/api/orders/unified', orderData);
      const order = res.data || res;
      Toast.show({ content: '下单成功' });
      router.push(`/unified-order/${order.id}`);
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '下单失败' });
    } finally {
      setSubmitting(false);
    }
  };

  const isDelivery = product.fulfillment_type === 'delivery';
  const isInStore = product.fulfillment_type === 'in_store';

  return (
    <div className="min-h-screen bg-gray-50 pb-28">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        确认订单
      </NavBar>

      <div className="px-4 pt-3">
        {isDelivery && (
          <Card
            style={{ borderRadius: 12, marginBottom: 12 }}
            onClick={() => setShowAddressPicker(true)}
          >
            {selectedAddress ? (
              <div className="flex items-center">
                <div className="flex-1">
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
                <span className="text-sm text-gray-400">请选择收货地址</span>
                <RightOutline fontSize={14} color="#999" />
              </div>
            )}
          </Card>
        )}

        {isInStore && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center">
              <span className="text-primary mr-2">📍</span>
              <span className="text-sm text-gray-600">到店核销（购买后凭核销码到店使用）</span>
            </div>
          </Card>
        )}

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex">
            <div className="w-20 h-20 rounded-lg flex-shrink-0 overflow-hidden">
              {product.images && product.images.length > 0 ? (
                <Image src={product.images[0]} width={80} height={80} fit="cover" style={{ borderRadius: 8 }} />
              ) : (
                <div
                  className="w-full h-full flex items-center justify-center text-2xl"
                  style={{ background: '#f6ffed' }}
                >
                  🛍️
                </div>
              )}
            </div>
            <div className="flex-1 ml-3">
              <div className="font-medium text-sm">{product.name}</div>
              {skuName && <div className="text-xs text-gray-500 mt-0.5">规格：{skuName}</div>}
              <div className="text-sm text-red-500 font-bold mt-1">¥{unitPrice}</div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-400">数量</span>
                <Stepper
                  value={quantity}
                  onChange={setQuantity}
                  min={1}
                  max={10}
                  style={{ '--height': '28px', '--input-width': '36px' }}
                />
              </div>
            </div>
          </div>
        </Card>

        {product.appointment_mode !== 'none' && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">预约时间</span>
              <div className="flex items-center" onClick={() => setShowDatePicker(true)}>
                <span className="text-sm text-gray-500">
                  {appointmentTime ? appointmentTime.toLocaleDateString('zh-CN') : '请选择'}
                </span>
                <RightOutline fontSize={12} color="#999" className="ml-1" />
              </div>
            </div>
          </Card>
        )}

        <Card
          style={{ borderRadius: 12, marginBottom: 12 }}
          onClick={() => setShowCouponPicker(true)}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">优惠券</span>
            <div className="flex items-center">
              {selectedCoupon ? (
                <span className="text-sm text-red-500">-¥{couponDiscount.toFixed(2)}</span>
              ) : (
                <span className="text-sm text-gray-400">
                  {coupons.length > 0 ? `${coupons.length}张可用` : '暂无可用'}
                </span>
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
                <span className="text-xs text-gray-500">使用{pointsDeduction}积分抵扣¥{pointsValue.toFixed(2)}</span>
              </div>
            )}
          </Card>
        )}

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="section-title" style={{ marginBottom: 8 }}>支付方式</div>
          <Radio.Group value={paymentMethod} onChange={(val) => setPaymentMethod(val as string)}>
            <Space direction="vertical" block>
              <Radio value="wechat">微信支付</Radio>
              <Radio value="alipay">支付宝</Radio>
            </Space>
          </Radio.Group>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <TextArea
            placeholder="订单备注（选填）"
            value={notes}
            onChange={setNotes}
            maxLength={200}
            showCount
            rows={2}
          />
        </Card>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-500">
            小计 ¥{subtotal.toFixed(2)}
            {couponDiscount > 0 && <span className="text-red-500 ml-2">-¥{couponDiscount.toFixed(2)}</span>}
            {pointsValue > 0 && <span className="text-red-500 ml-2">-¥{pointsValue.toFixed(2)}</span>}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <span className="text-sm text-gray-500">合计：</span>
            <span className="text-xl font-bold text-red-500">¥{totalAmount.toFixed(2)}</span>
          </div>
          <Button
            loading={submitting}
            onClick={handleSubmit}
            style={{
              borderRadius: 24,
              height: 44,
              width: 140,
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
            }}
          >
            提交订单
          </Button>
        </div>
      </div>

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
            <div className="text-center text-gray-400 py-8">
              暂无收货地址，请先添加
            </div>
          ) : (
            <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
              {addresses.map((addr) => (
                <List.Item
                  key={addr.id}
                  onClick={() => { setSelectedAddress(addr); setShowAddressPicker(false); }}
                  prefix={
                    <Radio checked={selectedAddress?.id === addr.id} style={{ '--icon-size': '18px' }} />
                  }
                  description={`${addr.province}${addr.city}${addr.district}${addr.street}`}
                >
                  <span className="text-sm">{addr.name} {addr.phone}</span>
                  {addr.is_default && (
                    <Tag style={{ '--background-color': '#52c41a15', '--text-color': '#52c41a', '--border-color': 'transparent', fontSize: 10, marginLeft: 6 }}>
                      默认
                    </Tag>
                  )}
                </List.Item>
              ))}
            </List>
          )}
        </div>
      </Popup>

      <Popup
        visible={showCouponPicker}
        onMaskClick={() => setShowCouponPicker(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '60vh' }}
      >
        <div className="p-4">
          <div className="font-medium mb-3">选择优惠券</div>
          <List.Item
            onClick={() => { setSelectedCoupon(null); setShowCouponPicker(false); }}
            prefix={<Radio checked={!selectedCoupon} style={{ '--icon-size': '18px' }} />}
          >
            不使用优惠券
          </List.Item>
          {coupons.map((uc) => (
            <List.Item
              key={uc.id}
              onClick={() => {
                if (uc.coupon && subtotal >= uc.coupon.condition_amount) {
                  setSelectedCoupon(uc);
                  setShowCouponPicker(false);
                } else {
                  Toast.show({ content: '不满足使用条件' });
                }
              }}
              prefix={
                <Radio
                  checked={selectedCoupon?.id === uc.id}
                  disabled={!uc.coupon || subtotal < uc.coupon.condition_amount}
                  style={{ '--icon-size': '18px' }}
                />
              }
              description={
                uc.coupon
                  ? `满${uc.coupon.condition_amount}可用 ${uc.coupon.valid_end ? `| 有效期至${new Date(uc.coupon.valid_end).toLocaleDateString('zh-CN')}` : ''}`
                  : ''
              }
            >
              <span className="text-sm">{uc.coupon?.name || '优惠券'}</span>
            </List.Item>
          ))}
        </div>
      </Popup>

      <DatePicker
        visible={showDatePicker}
        onClose={() => setShowDatePicker(false)}
        onConfirm={(val) => setAppointmentTime(val)}
        min={new Date()}
      />
    </div>
  );
}
