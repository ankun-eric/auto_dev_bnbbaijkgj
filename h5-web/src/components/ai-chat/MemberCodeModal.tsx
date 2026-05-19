'use client';

/**
 * [PRD-AI-HOME-V1 2026-05-19] 会员码二维码弹窗
 *
 * 触发位置：AI 抽屉（Sidebar.tsx）顶栏「🎫 会员码」按钮。
 * 数据源：复用 /api/member/qrcode（与 /member-card 页同源），无新增后端接口。
 *
 * 行为：
 *   - 打开时拉取一次二维码 token，60s 内自动刷新一次
 *   - 失败时显示「加载失败」+ 重试按钮
 *   - 未登录交由调用方拦截（本组件假设 user 已存在）
 *   - 关闭后清理定时器，再次打开重新拉取
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Image, SpinLoading, Button } from 'antd-mobile';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';

interface QRCodeData {
  token: string;
  expires_at?: string;
  user_id?: number;
}

interface MemberCodeModalProps {
  visible: boolean;
  onClose: () => void;
}

const REFRESH_INTERVAL_SEC = 60;

export default function MemberCodeModal({ visible, onClose }: MemberCodeModalProps) {
  const { user } = useAuth();
  const [qrData, setQrData] = useState<QRCodeData | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL_SEC);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchQRCode = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const res: any = await api.get('/api/member/qrcode');
      const data = res?.data ?? res;
      if (data && data.token) {
        setQrData({
          token: String(data.token),
          expires_at: data.expires_at,
          user_id: data.user_id,
        });
        setCountdown(REFRESH_INTERVAL_SEC);
      } else {
        setFailed(true);
      }
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!visible) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }
    fetchQRCode();
  }, [visible, fetchQRCode]);

  useEffect(() => {
    if (!visible || failed || !qrData) return;
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          fetchQRCode();
          return REFRESH_INTERVAL_SEC;
        }
        return prev - 1;
      });
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [visible, failed, qrData, fetchQRCode]);

  if (!visible) return null;

  const userNo = (user as any)?.user_no || (user as any)?.id || '';

  return (
    <div
      data-testid="bh-member-code-modal-root"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9000,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        data-testid="bh-member-code-modal"
        style={{
          width: '100%',
          maxWidth: 320,
          background: '#FFFFFF',
          borderRadius: 16,
          padding: '20px 20px 16px',
          boxShadow: '0 12px 40px rgba(0,0,0,0.25)',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: '#1F2937',
            marginBottom: 4,
          }}
        >
          我的会员码
        </div>
        <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 14 }}>
          向工作人员出示此码完成签到或核销
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 220,
          }}
        >
          {loading && !qrData ? (
            <SpinLoading color="primary" />
          ) : failed ? (
            <div data-testid="bh-member-code-failed">
              <div style={{ color: '#EF4444', fontSize: 13, marginBottom: 10 }}>
                加载失败，请重试
              </div>
              <Button
                size="small"
                onClick={fetchQRCode}
                style={{
                  borderRadius: 16,
                  color: '#0EA5E9',
                  borderColor: '#0EA5E9',
                }}
                data-testid="bh-member-code-retry"
              >
                重试
              </Button>
            </div>
          ) : qrData ? (
            <Image
              src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(
                qrData.token
              )}`}
              width={220}
              height={220}
              fit="contain"
              style={{ borderRadius: 8 }}
            />
          ) : null}
        </div>

        {userNo && (
          <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 10 }}>
            会员号：{String(userNo)}
          </div>
        )}
        {qrData && !failed && (
          <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>
            <span style={{ color: '#0EA5E9', fontWeight: 500 }}>{countdown}s</span> 后自动刷新
          </div>
        )}

        <Button
          block
          onClick={onClose}
          style={{
            marginTop: 16,
            borderRadius: 22,
            background: '#0EA5E9',
            color: '#fff',
            border: 'none',
            height: 40,
            fontSize: 14,
          }}
          data-testid="bh-member-code-close"
        >
          关闭
        </Button>
      </div>
    </div>
  );
}
