'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import cardsV2 from '@/services/cardsV2';

export default function RenewCardPage() {
  const params = useParams();
  const router = useRouter();
  const userCardId = Number(params?.id);
  const [loading, setLoading] = useState(false);

  const handleRenew = async () => {
    if (!userCardId) return;
    setLoading(true);
    try {
      const res: any = await cardsV2.renewCard(userCardId);
      Toast.show({ icon: 'success', content: '续卡订单已创建，请支付' });
      // 跳到支付页（沿用现有支付页路由，按订单 ID）
      router.replace(`/cards/pay/${res.order_id}`);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '续卡失败' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar title="续卡确认" onBack={() => router.back()} />
      <div className="p-6">
        <div className="bg-white rounded-2xl p-6 shadow">
          <h2 className="text-lg font-semibold">续卡确认</h2>
          <p className="text-sm text-gray-500 mt-3 leading-relaxed">
            将基于您当前的卡发起续卡：
            <br />· 叠加（STACK）：剩余次数累加，有效期顺延
            <br />· 重置（RESET）：发新卡，老卡作废
            <br />· 不允许续卡（DISABLED）：将提示无法续卡
          </p>
          <Button
            block
            color="primary"
            loading={loading}
            className="mt-6"
            onClick={handleRenew}
          >
            生成续卡订单
          </Button>
        </div>
      </div>
    </div>
  );
}
