/**
 * [AI对话模式优化 PRD v1.0 §7] 全局 Toast 规范封装。
 *
 * 规范要点：
 *  - 位置：屏幕水平居中 + 垂直上方 1/3（top）
 *  - 三种类型：✅ success（绿色 + 对勾）/ ❌ fail（红色 + 叉号）/ ⚠️ warning（橙色 + 感叹号）
 *  - 停留时长：success 2s / fail 3s / warning 2.5s
 *  - 全站统一：所有 Toast 调用方走本封装；保留 antd-mobile 原生 Toast 兜底兼容
 *
 * 用法：
 *   import { ToastUnified } from '@/lib/toast-unified';
 *   ToastUnified.success('已删除');
 *   ToastUnified.fail('删除失败,请稍后重试');
 *   ToastUnified.warning('请先选择内容');
 */
import { Toast } from 'antd-mobile';

export type UnifiedToastType = 'success' | 'fail' | 'warning';

const TYPE_DURATION: Record<UnifiedToastType, number> = {
  success: 2000,
  fail: 3000,
  warning: 2500,
};

const TYPE_ICON: Record<UnifiedToastType, 'success' | 'fail' | undefined> = {
  success: 'success',
  fail: 'fail',
  warning: undefined,
};

const TYPE_BG: Record<UnifiedToastType, string> = {
  success: 'rgba(34, 197, 94, 0.92)',
  fail: 'rgba(239, 68, 68, 0.92)',
  warning: 'rgba(249, 115, 22, 0.92)',
};

const TYPE_PREFIX: Record<UnifiedToastType, string> = {
  success: '',
  fail: '',
  warning: '⚠ ',
};

function show(type: UnifiedToastType, content: string) {
  try {
    Toast.show({
      content: `${TYPE_PREFIX[type]}${content}`,
      icon: TYPE_ICON[type],
      duration: TYPE_DURATION[type],
      // antd-mobile v5 Toast 默认在屏幕中部，PRD 要求上方 1/3 —— 通过 maskStyle/wrapStyle 微调
      // 兼容性：Toast.show 不直接支持 position，使用 maskStyle 把容器整体上移
      maskStyle: {
        // 让 Toast 容器内容上移，避开输入键盘 + 与现有视觉冲击区错开
        // 屏幕高度 33vh 即 "上方 1/3"
        alignItems: 'flex-start',
        paddingTop: '25vh',
      },
      // afterClose 不设置；duration 到点自动隐藏
    });
    // 渲染后调整文字背景（antd-mobile 默认是黑色），通过临时样式覆盖
    if (typeof document !== 'undefined') {
      requestAnimationFrame(() => {
        const nodes = document.querySelectorAll('.adm-toast-main');
        const last = nodes[nodes.length - 1] as HTMLElement | undefined;
        if (last) {
          last.style.background = TYPE_BG[type];
          last.style.color = '#fff';
          last.style.fontWeight = '500';
          last.style.borderRadius = '12px';
        }
      });
    }
  } catch {
    // 兜底：直接走 antd-mobile 原生
    Toast.show({ content });
  }
}

export const ToastUnified = {
  success(content: string) {
    show('success', content);
  },
  fail(content: string) {
    show('fail', content);
  },
  warning(content: string) {
    show('warning', content);
  },
  // 兼容用法：透传到原生 Toast
  show: Toast.show,
};

export default ToastUnified;
