'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  NavBar,
  Swiper,
  Image,
  Tag,
  Collapse,
  Card,
  Rate,
  Button,
  Toast,
  SpinLoading,
  Divider,
  Popup,
  List,
} from 'antd-mobile';
import { HeartOutline, HeartFill } from 'antd-mobile-icons';
import api from '@/lib/api';
import MarketingBadge from '@/components/MarketingBadge';

interface Store {
  id: number;
  store_id: number;
  store_name: string | null;
}

interface SlotAvailability {
  start_time: string;
  end_time: string;
  capacity: number;
  booked: number;
  available: number;
}

interface AvailableStore {
  store_id: number;
  store_code?: string;
  name: string;
  address?: string;
  lat?: number | null;
  lng?: number | null;
  distance_km?: number | null;
  is_nearest?: boolean;
}

interface ProductSku {
  id: number;
  spec_name: string;
  sale_price: number;
  origin_price: number | null;
  stock: number;
  is_default: boolean;
  status: number;
  sort_order: number;
}

interface ProductDetail {
  id: number;
  name: string;
  category_id: number;
  category_name: string | null;
  fulfillment_type: string;
  original_price: number | null;
  sale_price: number;
  images: string[] | null;
  video_url: string | null;
  description: string | null;
  description_rich?: string | null;
  selling_point?: string | null;
  main_video_url?: string | null;
  spec_mode?: number;
  skus?: ProductSku[] | null;
  faq: Array<{ question: string; answer: string }> | null;
  sales_count: number;
  points_exchangeable: boolean;
  points_price: number;
  points_deductible: boolean;
  redeem_count: number;
  appointment_mode: string;
  time_slots?: { start: string; end: string; capacity: number }[];
  stores: Store[];
  review_count: number;
  avg_rating: number | null;
  stock: number;
  marketing_badges?: string[] | null;
}

export default function ProductDetailPage() {
  const router = useRouter();
  const params = useParams();
  const productId = params.id as string;
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [favorited, setFavorited] = useState(false);
  const [mediaTab, setMediaTab] = useState<'image' | 'video'>('image');
  const [selectedSkuId, setSelectedSkuId] = useState<number | null>(null);
  const [slotAvailability, setSlotAvailability] = useState<SlotAvailability[]>([]);
  const [availableStores, setAvailableStores] = useState<AvailableStore[]>([]);
  const [selectedStoreIdx, setSelectedStoreIdx] = useState<number>(0);
  const [storeDrawerVisible, setStoreDrawerVisible] = useState<boolean>(false);

  useEffect(() => {
    api.get(`/api/products/${productId}`).then((res: any) => {
      const p = res.data || res;
      setProduct(p);
      // 默认选中默认规格
      if (p && p.spec_mode === 2 && Array.isArray(p.skus) && p.skus.length > 0) {
        const enabled = p.skus.filter((s: ProductSku) => s.status === 1);
        const def = enabled.find((s: ProductSku) => s.is_default) || enabled[0];
        if (def) setSelectedSkuId(def.id);
      }
    }).catch(() => {
      Toast.show({ content: '加载失败' });
    }).finally(() => setLoading(false));

    // 收藏状态回显
    api.get(`/api/favorites/status?content_type=product&content_id=${productId}`).then((res: any) => {
      const data = res.data || res;
      setFavorited(Boolean(data?.is_favorited));
    }).catch(() => { /* 未登录或失败时静默 */ });
  }, [productId]);

  // 加载今日时段可用性（用于预览页置灰"已约满"）
  useEffect(() => {
    if (!product || !productId) return;
    if (product.appointment_mode === 'none') return;
    if (!product.time_slots || product.time_slots.length === 0) return;
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    api.get(`/api/products/${productId}/time-slots/availability?date=${todayStr}`)
      .then((res: any) => {
        const data = res.data || res;
        setSlotAvailability(data?.data?.slots || []);
      })
      .catch(() => setSlotAvailability([]));
  }, [product, productId]);

  // 加载可用门店（按距离排序，定位失败/拒绝则后端按字母兜底）
  useEffect(() => {
    if (!product || !productId) return;
    if (product.fulfillment_type !== 'in_store') return;

    const fetchStores = (lat?: number, lng?: number) => {
      const params = (lat !== undefined && lng !== undefined) ? `?lat=${lat}&lng=${lng}` : '';
      api.get(`/api/products/${productId}/available-stores${params}`)
        .then((res: any) => {
          const data = res.data || res;
          const list: AvailableStore[] = data?.data?.stores || [];
          setAvailableStores(list);
          setSelectedStoreIdx(0);
        })
        .catch(() => setAvailableStores([]));
    };

    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => fetchStores(pos.coords.latitude, pos.coords.longitude),
        () => fetchStores(),
        { enableHighAccuracy: false, timeout: 8000, maximumAge: 30 * 60 * 1000 },
      );
    } else {
      fetchStores();
    }
  }, [product, productId]);

  const handleToggleFavorite = async () => {
    try {
      const res: any = await api.post(`/api/favorites?content_type=product&content_id=${productId}`);
      const data = res.data || res;
      setFavorited(data.is_favorited);
      // 收藏成功统一文案；取消收藏沿用后端默认文案
      const msg = data.is_favorited
        ? '收藏成功，可在「我的-收藏」中查看'
        : (data.message || '已取消收藏');
      Toast.show({ content: msg });
    } catch {
      Toast.show({ content: '操作失败' });
    }
  };

  const handleBuy = () => {
    if (product?.spec_mode === 2) {
      if (!selectedSkuId) {
        Toast.show({ content: '请选择规格' });
        return;
      }
      router.push(`/checkout?product_id=${productId}&quantity=1&sku_id=${selectedSkuId}`);
    } else {
      router.push(`/checkout?product_id=${productId}&quantity=1`);
    }
  };

  const fulfillmentLabel = (type: string) => {
    const map: Record<string, string> = { in_store: '到店服务', delivery: '快递配送', virtual: '虚拟商品' };
    return map[type] || type;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>商品详情</NavBar>
        <div className="flex items-center justify-center py-40"><SpinLoading color="primary" /></div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>商品详情</NavBar>
        <div className="text-center text-gray-400 py-40">商品不存在</div>
      </div>
    );
  }

  const videoSrc = product.main_video_url || product.video_url || '';
  const hasVideo = !!videoSrc;
  const imageList: string[] = Array.isArray(product.images) ? product.images : [];

  // 规格相关
  const isMulti = product.spec_mode === 2 && Array.isArray(product.skus) && product.skus.length > 0;
  const visibleSkus: ProductSku[] = isMulti ? (product.skus as ProductSku[]).filter(s => s.status === 1) : [];
  const selectedSku = visibleSkus.find(s => s.id === selectedSkuId) || null;
  const currentSalePrice = selectedSku ? selectedSku.sale_price : product.sale_price;
  const currentOriginPrice = selectedSku ? selectedSku.origin_price : product.original_price;
  const currentStock = selectedSku ? selectedSku.stock : product.stock;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        商品详情
      </NavBar>

      {/* 媒体 Tab：图片 | 视频 */}
      {(imageList.length > 0 || hasVideo) && (
        <div style={{ background: '#fff' }}>
          {hasVideo && (
            <div style={{ display: 'flex', borderBottom: '1px solid #f0f0f0' }}>
              <div
                onClick={() => setMediaTab('image')}
                style={{
                  flex: 1, textAlign: 'center', padding: '8px 0',
                  borderBottom: mediaTab === 'image' ? '2px solid #52c41a' : '2px solid transparent',
                  color: mediaTab === 'image' ? '#52c41a' : '#666', fontWeight: 500,
                }}
              >图片</div>
              <div
                onClick={() => setMediaTab('video')}
                style={{
                  flex: 1, textAlign: 'center', padding: '8px 0',
                  borderBottom: mediaTab === 'video' ? '2px solid #52c41a' : '2px solid transparent',
                  color: mediaTab === 'video' ? '#52c41a' : '#666', fontWeight: 500,
                }}
              >视频</div>
            </div>
          )}
          {mediaTab === 'video' && hasVideo ? (
            <video src={videoSrc} controls className="w-full" style={{ height: 280, objectFit: 'cover', background: '#000', display: 'block' }} />
          ) : imageList.length > 0 ? (
            <div style={{ position: 'relative' }}>
              <Swiper autoplay loop style={{ '--height': '280px' }}>
                {imageList.map((img, i) => (
                  <Swiper.Item key={i}>
                    <Image src={img} width="100%" height={280} fit="cover" />
                  </Swiper.Item>
                ))}
              </Swiper>
              {/* 商品功能优化 v1.0：详情页头图左上角角标 */}
              <MarketingBadge badges={product?.marketing_badges} />
            </div>
          ) : (
            <div className="h-[280px] flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #52c41a30, #13c2c230)' }}>
              <div className="text-center">
                <div className="text-5xl mb-2">🛍️</div>
                <p className="text-sm text-gray-500">商品图片</p>
              </div>
            </div>
          )}
        </div>
      )}
      {imageList.length === 0 && !hasVideo && (
        <div className="h-[280px] flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #52c41a30, #13c2c230)' }}>
          <div className="text-center">
            <div className="text-5xl mb-2">🛍️</div>
            <p className="text-sm text-gray-500">商品图片</p>
          </div>
        </div>
      )}

      <div className="px-4 pt-4">
        <div className="card">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h1 className="text-lg font-bold">{product.name}</h1>
              <div className="flex items-center mt-1 flex-wrap gap-1">
                <Tag
                  style={{
                    '--background-color': '#52c41a15',
                    '--text-color': '#52c41a',
                    '--border-color': 'transparent',
                    fontSize: 10,
                  }}
                >
                  {fulfillmentLabel(product.fulfillment_type)}
                </Tag>
                {product.points_exchangeable && (
                  <Tag
                    style={{
                      '--background-color': '#fa8c1615',
                      '--text-color': '#fa8c16',
                      '--border-color': 'transparent',
                      fontSize: 10,
                    }}
                  >
                    {product.points_price}积分可兑
                  </Tag>
                )}
                {product.category_name && (
                  <Tag
                    style={{
                      '--background-color': '#1890ff15',
                      '--text-color': '#1890ff',
                      '--border-color': 'transparent',
                      fontSize: 10,
                    }}
                  >
                    {product.category_name}
                  </Tag>
                )}
              </div>
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-red-500">¥{currentSalePrice}</span>
            {currentOriginPrice && currentOriginPrice > currentSalePrice && (
              <span className="text-sm text-gray-300 line-through ml-2">¥{currentOriginPrice}</span>
            )}
          </div>
          <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-gray-400">已售{product.sales_count}</span>
            <span className="text-xs text-gray-400">库存{currentStock}</span>
          </div>
          {product.selling_point && (
            <div className="mt-2 text-xs" style={{ color: '#fa541c', background: '#fff7e6', padding: '6px 8px', borderRadius: 4 }}>
              {product.selling_point}
            </div>
          )}
        </div>

        {isMulti && (
          <div className="card">
            <div className="section-title">选择规格</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {visibleSkus.map(s => {
                const soldOut = s.stock <= 0;
                const selected = s.id === selectedSkuId;
                return (
                  <div
                    key={s.id}
                    onClick={() => { if (!soldOut) setSelectedSkuId(s.id); }}
                    style={{
                      position: 'relative',
                      padding: '6px 14px',
                      borderRadius: 20,
                      border: selected ? '1px solid #52c41a' : '1px solid #e5e5e5',
                      background: selected ? '#f6ffed' : (soldOut ? '#f5f5f5' : '#fff'),
                      color: soldOut ? '#bbb' : (selected ? '#52c41a' : '#333'),
                      cursor: soldOut ? 'not-allowed' : 'pointer',
                      fontSize: 13,
                    }}
                  >
                    {s.spec_name}
                    {soldOut && (
                      <span style={{
                        position: 'absolute', top: -6, right: -6, fontSize: 10,
                        background: '#bbb', color: '#fff', borderRadius: 8, padding: '0 4px',
                      }}>已售罄</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {(product.description_rich || product.description) && (
          <div className="card">
            <div className="section-title">商品详情</div>
            <div
              className="text-sm text-gray-600 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: (product.description_rich || product.description || '') as string }}
            />
          </div>
        )}

        {product.faq && product.faq.length > 0 && (
          <div className="card">
            <div className="section-title">常见问题</div>
            <Collapse>
              {product.faq.map((item, i) => (
                <Collapse.Panel key={String(i)} title={item.question}>
                  <div className="text-sm text-gray-600">{item.answer}</div>
                </Collapse.Panel>
              ))}
            </Collapse>
          </div>
        )}

        {product.appointment_mode !== 'none' && product.time_slots && product.time_slots.length > 0 && (
          <div className="card">
            <div className="section-title">可预约时段（今日）</div>
            <div className="flex flex-wrap gap-2">
              {product.time_slots.map((slot) => {
                const label = `${slot.start}-${slot.end}`;
                const now = new Date();
                const nowHM = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
                const expired = slot.end <= nowHM;
                const avail = slotAvailability.find(s => `${s.start_time}-${s.end_time}` === label);
                const fullyBooked = avail ? avail.available <= 0 : false;
                const disabled = expired || fullyBooked;
                const suffix = expired ? ' 已结束' : (fullyBooked ? ' 已约满' : '');
                return (
                  <div
                    key={label}
                    className="px-3 py-1.5 rounded-full text-xs border"
                    style={{
                      background: disabled ? '#f5f5f5' : '#fff',
                      color: disabled ? '#999' : '#333',
                      borderColor: '#e5e5e5',
                      cursor: disabled ? 'not-allowed' : 'default',
                    }}
                  >
                    {label}{suffix}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {product.fulfillment_type === 'in_store' && availableStores.length > 0 && (
          <div className="card">
            <div className="section-title">可用门店</div>
            {(() => {
              const cur = availableStores[selectedStoreIdx] || availableStores[0];
              return (
                <div
                  onClick={() => setStoreDrawerVisible(true)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px',
                    border: '1px solid #f0f0f0',
                    borderRadius: 8,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>{cur.name}</div>
                    {cur.address && <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>{cur.address}</div>}
                    {cur.distance_km !== null && cur.distance_km !== undefined && (
                      <div style={{ color: '#52c41a', fontSize: 12, marginTop: 4 }}>距您 {cur.distance_km} km</div>
                    )}
                  </div>
                  <div style={{ color: '#999', fontSize: 12 }}>
                    {availableStores.length > 1 ? '切换 ▼' : ''}
                  </div>
                </div>
              );
            })()}
            {availableStores.every(s => s.distance_km === null || s.distance_km === undefined) && (
              <div style={{ fontSize: 12, color: '#bbb', marginTop: 8 }}>
                暂未获取位置，已按门店名排序
              </div>
            )}
          </div>
        )}

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div className="section-title" style={{ marginBottom: 0 }}>用户评价</div>
            <span className="text-xs text-gray-400">{product.review_count}条评价</span>
          </div>
          {product.avg_rating ? (
            <div className="flex items-center gap-2">
              <Rate readOnly value={product.avg_rating} style={{ '--star-size': '16px' }} />
              <span className="text-sm text-gray-500">{product.avg_rating.toFixed(1)}分</span>
            </div>
          ) : (
            <div className="text-sm text-gray-400">暂无评价</div>
          )}
        </div>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3 flex items-center gap-3"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        <div
          className="flex flex-col items-center justify-center px-3 cursor-pointer"
          onClick={handleToggleFavorite}
        >
          {favorited ? (
            <HeartFill fontSize={22} color="#f5222d" />
          ) : (
            <HeartOutline fontSize={22} color="#999" />
          )}
          <span className="text-xs text-gray-400 mt-0.5">收藏</span>
        </div>
        <Button
          block
          onClick={handleBuy}
          disabled={currentStock <= 0}
          style={{
            flex: 1,
            borderRadius: 24,
            height: 44,
            background: currentStock > 0 ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
            color: currentStock > 0 ? '#fff' : '#999',
            border: 'none',
          }}
        >
          {currentStock > 0 ? '立即购买' : '已售罄'}
        </Button>
      </div>

      <Popup
        visible={storeDrawerVisible}
        position="bottom"
        onMaskClick={() => setStoreDrawerVisible(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, maxHeight: '70vh', overflow: 'auto' }}
      >
        <div style={{ padding: '16px 0' }}>
          <div style={{ textAlign: 'center', fontWeight: 500, padding: '0 16px 12px', borderBottom: '1px solid #f5f5f5' }}>选择门店</div>
          <List>
            {availableStores.map((s, idx) => (
              <List.Item
                key={s.store_id}
                onClick={() => { setSelectedStoreIdx(idx); setStoreDrawerVisible(false); }}
                extra={idx === selectedStoreIdx ? '✓' : ''}
                description={
                  <>
                    {s.address && <div style={{ color: '#999' }}>{s.address}</div>}
                    {s.distance_km !== null && s.distance_km !== undefined && (
                      <div style={{ color: '#52c41a', marginTop: 2 }}>距您 {s.distance_km} km</div>
                    )}
                  </>
                }
              >
                {s.name}
              </List.Item>
            ))}
          </List>
        </div>
      </Popup>
    </div>
  );
}
