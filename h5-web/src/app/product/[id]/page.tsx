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
} from 'antd-mobile';
import { HeartOutline, HeartFill } from 'antd-mobile-icons';
import api from '@/lib/api';

interface Store {
  id: number;
  store_id: number;
  store_name: string | null;
}

interface ProductDetail {
  id: number;
  name: string;
  category_id: number;
  category_name: string | null;
  fulfillment_type: string;
  original_price: number;
  sale_price: number;
  images: string[] | null;
  video_url: string | null;
  description: string | null;
  faq: Array<{ question: string; answer: string }> | null;
  sales_count: number;
  points_exchangeable: boolean;
  points_price: number;
  points_deductible: boolean;
  redeem_count: number;
  appointment_mode: string;
  stores: Store[];
  review_count: number;
  avg_rating: number | null;
  stock: number;
}

export default function ProductDetailPage() {
  const router = useRouter();
  const params = useParams();
  const productId = params.id as string;
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [favorited, setFavorited] = useState(false);

  useEffect(() => {
    api.get(`/api/products/${productId}`).then((res: any) => {
      setProduct(res.data || res);
    }).catch(() => {
      Toast.show({ content: '加载失败' });
    }).finally(() => setLoading(false));
  }, [productId]);

  const handleToggleFavorite = async () => {
    try {
      const res: any = await api.post(`/api/favorites?content_type=product&content_id=${productId}`);
      const data = res.data || res;
      setFavorited(data.is_favorited);
      Toast.show({ content: data.message });
    } catch {
      Toast.show({ content: '操作失败' });
    }
  };

  const handleBuy = () => {
    router.push(`/checkout?product_id=${productId}&quantity=1`);
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

  const mediaItems: Array<{ type: 'image' | 'video'; src: string }> = [];
  if (product.video_url) {
    mediaItems.push({ type: 'video', src: product.video_url });
  }
  if (product.images) {
    product.images.forEach((img) => mediaItems.push({ type: 'image', src: img }));
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        商品详情
      </NavBar>

      {mediaItems.length > 0 ? (
        <Swiper autoplay loop style={{ '--height': '280px' }}>
          {mediaItems.map((item, i) => (
            <Swiper.Item key={i}>
              {item.type === 'video' ? (
                <video src={item.src} controls className="w-full h-[280px] object-cover bg-black" />
              ) : (
                <Image src={item.src} width="100%" height={280} fit="cover" />
              )}
            </Swiper.Item>
          ))}
        </Swiper>
      ) : (
        <div
          className="h-[280px] flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #52c41a30, #13c2c230)' }}
        >
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
            <span className="text-2xl font-bold text-red-500">¥{product.sale_price}</span>
            {product.original_price > product.sale_price && (
              <span className="text-sm text-gray-300 line-through ml-2">¥{product.original_price}</span>
            )}
          </div>
          <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-gray-400">已售{product.sales_count}</span>
            <span className="text-xs text-gray-400">库存{product.stock}</span>
          </div>
        </div>

        {product.description && (
          <div className="card">
            <div className="section-title">商品详情</div>
            <div
              className="text-sm text-gray-600 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: product.description }}
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

        {product.fulfillment_type === 'in_store' && product.stores.length > 0 && (
          <div className="card">
            <div className="section-title">适用门店</div>
            <div className="space-y-2">
              {product.stores.map((store) => (
                <div key={store.id} className="flex items-center text-sm">
                  <span className="text-primary mr-2">📍</span>
                  <span className="text-gray-600">{store.store_name || `门店${store.store_id}`}</span>
                </div>
              ))}
            </div>
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
          disabled={product.stock <= 0}
          style={{
            flex: 1,
            borderRadius: 24,
            height: 44,
            background: product.stock > 0 ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
            color: product.stock > 0 ? '#fff' : '#999',
            border: 'none',
          }}
        >
          {product.stock > 0 ? '立即购买' : '已售罄'}
        </Button>
      </div>
    </div>
  );
}
