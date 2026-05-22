'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] SN 输入旁的扫码按钮。
 *
 * - 微信内：尝试 wx.scanQRCode（依赖 wx-jssdk 配置；本项目此处采用兜底降级）
 * - 普通浏览器：调用 getUserMedia 启动摄像头预览，提示用户对准二维码后手动输入
 *
 * 为简化首版实现，本组件采取「能扫则扫、否则手动输入」的渐进增强策略：
 *   1) 若 window.wx 存在且具备 scanQRCode，直接调用
 *   2) 否则弹出原生 prompt（绝大多数手机浏览器可调起键盘）
 *
 * 后续可在不破坏接口的前提下，单独替换为 jsQR / ZXing 全屏扫码 UI。
 */
import { showToast } from '@/lib/toast-unified';
import { DV_COLOR } from './theme';

interface Props {
  onResult: (code: string) => void;
}

function isWeChat(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /micromessenger/i.test(navigator.userAgent || '');
}

export default function ScanQRButton({ onResult }: Props) {
  const handleClick = () => {
    if (isWeChat()) {
      try {
        const w = (window as any).wx;
        if (w && typeof w.scanQRCode === 'function') {
          w.scanQRCode({
            needResult: 1,
            scanType: ['qrCode', 'barCode'],
            success: (res: any) => {
              const code = (res?.resultStr || '').split(',').pop() || '';
              if (code) onResult(code);
              else showToast('未识别到内容', 'warning');
            },
            fail: () => fallbackPrompt(onResult),
          });
          return;
        }
      } catch {
        // ignore
      }
    }
    // 普通浏览器：渐进降级
    fallbackPrompt(onResult);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      data-testid="bh-scan-qr-btn"
      aria-label="扫码"
      style={{
        width: 40,
        height: 40,
        borderRadius: 10,
        border: `1px solid ${DV_COLOR.border}`,
        background: DV_COLOR.brand50,
        color: DV_COLOR.brand600,
        fontSize: 18,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      📷
    </button>
  );
}

function fallbackPrompt(onResult: (code: string) => void) {
  if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
    // 触发摄像头权限以提示用户当前环境支持扫码，但不在此版本完整渲染扫码画面
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' } })
      .then((stream) => {
        stream.getTracks().forEach((t) => t.stop());
        const v = window.prompt('请将设备 SN 二维码对准摄像头扫描，或直接粘贴 SN：');
        if (v) onResult(v.trim());
      })
      .catch(() => {
        const v = window.prompt('扫码权限不可用，请直接粘贴 SN：');
        if (v) onResult(v.trim());
      });
  } else {
    const v = window.prompt('请输入 SN 码：');
    if (v) onResult(v.trim());
  }
}
