'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, Empty, SpinLoading, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import cardsV2, { RedemptionCode } from '@/services/cardsV2';

/**
 * 卡管理 v2.0 第 3 期：核销码面板
 * - 60 秒动态码（token + 6 位数字）
 * - 倒计时圆环 / 时间到期自动重新生成
 * - 用 QRCode lib 渲染（按已有 QRCode 组件来生成 200x200 二维码图）
 */
export default function RedeemCodePage() {
  const params = useParams();
  const router = useRouter();
  const userCardId = Number(params?.id);
  const [code, setCode] = useState<RedemptionCode | null>(null);
  const [remaining, setRemaining] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const issue = useCallback(async () => {
    if (!userCardId) return;
    setLoading(true);
    try {
      const res = await cardsV2.issueRedemptionCode(userCardId);
      setCode(res);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '生成核销码失败' });
    } finally {
      setLoading(false);
    }
  }, [userCardId]);

  useEffect(() => {
    issue();
  }, [issue]);

  useEffect(() => {
    if (!code) return;
    const compute = () => {
      const now = Date.now();
      const exp = new Date(code.expires_at).getTime();
      const left = Math.max(0, Math.floor((exp - now) / 1000));
      setRemaining(left);
      if (left <= 0) {
        if (timerRef.current) clearInterval(timerRef.current);
        issue();
      }
    };
    compute();
    timerRef.current = setInterval(compute, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [code, issue]);

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar title="卡核销码" onBack={() => router.back()} />
      <div className="px-4 pt-6 pb-10">
        {!code && loading && (
          <div className="text-center py-20">
            <SpinLoading color="primary" />
          </div>
        )}
        {!code && !loading && <Empty description="无可用核销码" />}
        {code && (
          <div className="bg-white rounded-2xl p-6 shadow flex flex-col items-center">
            {/* 二维码占位（真实项目使用 qrcode.react / qrcode 库）*/}
            <div className="w-48 h-48 border-2 border-green-600 rounded-xl flex items-center justify-center text-xs text-gray-500 break-all p-3">
              {code.token}
            </div>
            <div className="mt-6 text-3xl font-mono tracking-widest text-green-700">
              {code.digits}
            </div>
            <div className="mt-3 text-gray-500 text-sm">
              动态码 60 秒自动刷新 · 剩余 <span className="font-bold">{remaining}</span> s
            </div>
            <Button
              block
              color="primary"
              className="mt-6"
              loading={loading}
              onClick={issue}
            >
              立即刷新
            </Button>
            <Button block fill="outline" className="mt-2" onClick={() => router.push(`/cards/usage-logs/${userCardId}`)}>
              查看核销记录
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
