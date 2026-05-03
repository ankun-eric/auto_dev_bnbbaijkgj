'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Empty, List, SpinLoading } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import cardsV2, { CardUsageLog } from '@/services/cardsV2';

export default function CardUsageLogsPage() {
  const params = useParams();
  const router = useRouter();
  const userCardId = Number(params?.id);
  const [items, setItems] = useState<CardUsageLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userCardId) return;
    cardsV2
      .myUsageLogs(userCardId)
      .then((res) => {
        setItems(res.items || []);
        setTotal(res.total || 0);
      })
      .finally(() => setLoading(false));
  }, [userCardId]);

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar title="核销记录" onBack={() => router.back()} />
      <div className="px-4 pt-4 pb-10">
        <div className="text-sm text-gray-500 mb-3">共 {total} 条</div>
        {loading && (
          <div className="text-center py-20">
            <SpinLoading color="primary" />
          </div>
        )}
        {!loading && items.length === 0 && <Empty description="暂无核销记录" />}
        {!loading && items.length > 0 && (
          <List>
            {items.map((it) => (
              <List.Item
                key={it.id}
                description={
                  <>
                    {it.store_name || `门店#${it.store_id || '-'}`} · {new Date(it.used_at).toLocaleString()}
                  </>
                }
              >
                {it.product_name || `商品#${it.product_id}`}
              </List.Item>
            ))}
          </List>
        )}
      </div>
    </div>
  );
}
