/**
 * [PRD-MED-OPTIM-V2 2026-05-21] 全局 Toast 规范封装 — 微信风格居中轻量 Toast。
 *
 * 规范要点：
 *  - 位置：屏幕垂直 + 水平居中
 *  - 形状：圆角矩形（border-radius: 8px）
 *  - 背景色：半透明深色（rgba(0, 0, 0, 0.7)）
 *  - 文字颜色：白色 14px
 *  - 内边距：上下 8px，左右 16px
 *  - 自动消失时间：1.5 秒
 *  - 动画：淡入淡出（opacity 过渡 0.3s）
 *  - 无关闭按钮，无遮罩层
 *
 * 用法：
 *   import { showToast } from '@/lib/toast-unified';
 *   showToast('已打卡');
 *   showToast('打卡失败', 'fail');
 *   showToast('请先选择内容', 'warning');
 *
 *   // 兼容旧 API：
 *   import { ToastUnified } from '@/lib/toast-unified';
 *   ToastUnified.success('已删除');
 *   ToastUnified.fail('删除失败');
 */
import { Toast } from 'antd-mobile';

export type UnifiedToastType = 'success' | 'fail' | 'warning';

const DURATION = 1500;

const TYPE_ICON: Record<UnifiedToastType, 'success' | 'fail' | undefined> = {
  success: 'success',
  fail: 'fail',
  warning: undefined,
};

const TYPE_PREFIX: Record<UnifiedToastType, string> = {
  success: '',
  fail: '',
  warning: '⚠ ',
};

export function showToast(content: string, type: UnifiedToastType = 'success') {
  try {
    Toast.show({
      content: `${TYPE_PREFIX[type]}${content}`,
      icon: TYPE_ICON[type],
      duration: DURATION,
      position: 'center',
      maskClickable: true,
    });
    if (typeof document !== 'undefined') {
      requestAnimationFrame(() => {
        const nodes = document.querySelectorAll('.adm-toast-main');
        const last = nodes[nodes.length - 1] as HTMLElement | undefined;
        if (last) {
          last.style.background = 'rgba(0, 0, 0, 0.7)';
          last.style.color = '#fff';
          last.style.fontSize = '14px';
          last.style.fontWeight = '500';
          last.style.borderRadius = '8px';
          last.style.padding = '8px 16px';
        }
      });
    }
  } catch {
    Toast.show({ content, position: 'center' });
  }
}

export const ToastUnified = {
  success(content: string) {
    showToast(content, 'success');
  },
  fail(content: string) {
    showToast(content, 'fail');
  },
  warning(content: string) {
    showToast(content, 'warning');
  },
  show: Toast.show,
};

export default ToastUnified;
