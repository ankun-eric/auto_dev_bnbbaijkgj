/**
 * 全局 Toast 规范封装 — 微信风格紧凑带小图标（v2.0）
 *
 * 使用自定义 React 节点作为 content，绕过 antd-mobile 的大图标模式，
 * 统一渲染 24px 小图标 + 14px 文字的垂直布局。
 *
 * 用法：
 *   import { showToast } from '@/lib/toast-unified';
 *   showToast('操作成功');
 *   showToast('操作成功', 'success');
 *   showToast('操作失败', 'fail');
 *
 *   // loading（不自动消失，返回 close 函数）
 *   const close = showToast('提交中...', 'loading');
 *   // 异步完成后
 *   close();
 */
import { Toast } from 'antd-mobile';
import React from 'react';

export type UnifiedToastType = 'success' | 'fail' | 'warning' | 'loading';

const DURATION = 1500;
const LOADING_TIMEOUT = 30000;

const SuccessIcon = () =>
  React.createElement(
    'svg',
    {
      width: 24,
      height: 24,
      viewBox: '0 0 24 24',
      fill: 'none',
      xmlns: 'http://www.w3.org/2000/svg',
    },
    React.createElement('path', {
      d: 'M5 13l4 4L19 7',
      stroke: '#ffffff',
      strokeWidth: 2.5,
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    })
  );

const FailIcon = () =>
  React.createElement(
    'svg',
    {
      width: 24,
      height: 24,
      viewBox: '0 0 24 24',
      fill: 'none',
      xmlns: 'http://www.w3.org/2000/svg',
    },
    React.createElement('path', {
      d: 'M6 6l12 12M18 6L6 18',
      stroke: '#ffffff',
      strokeWidth: 2.5,
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    })
  );

const LoadingIcon = () =>
  React.createElement(
    'div',
    { className: 'bh-toast-loading-spinner' },
    null
  );

function buildContent(text: string, type: UnifiedToastType) {
  const icons: Record<UnifiedToastType, (() => React.ReactElement) | null> = {
    success: SuccessIcon,
    fail: FailIcon,
    loading: LoadingIcon,
    warning: null,
  };

  const IconComponent = icons[type];

  return React.createElement(
    'div',
    { className: 'bh-toast-custom-content' },
    IconComponent ? React.createElement(IconComponent) : null,
    React.createElement(
      'span',
      { className: 'bh-toast-custom-text' },
      type === 'warning' ? `⚠ ${text}` : text
    )
  );
}

export function showToast(content: string, type: UnifiedToastType = 'success'): () => void {
  try {
    if (type === 'loading') {
      Toast.show({
        content: buildContent(content, type),
        duration: 0,
        position: 'center',
        maskClickable: false,
        maskClassName: 'bh-toast-loading-mask',
      });

      const timer = setTimeout(() => {
        Toast.clear();
      }, LOADING_TIMEOUT);

      return () => {
        clearTimeout(timer);
        Toast.clear();
      };
    }

    Toast.show({
      content: buildContent(content, type),
      duration: DURATION,
      position: 'center',
      maskClickable: true,
    });
  } catch {
    Toast.show({ content, position: 'center' });
  }

  return () => {
    Toast.clear();
  };
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
  loading(content: string) {
    return showToast(content, 'loading');
  },
  show: Toast.show,
};

export default ToastUnified;
