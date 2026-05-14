'use client';
/**
 * [PRD-HEALTH-OPT-V1 2026-05-14] 全局 Dialog 统一规范 R4。
 *
 * 规则：
 *  - 居中（水平+垂直）
 *  - Dialog 320px / 16px 圆角；二次确认 300px
 *  - 半透明黑遮罩 rgba(0,0,0,0.45)
 *  - z-index 1000；fade + scale(0.95→1.0)；时长 200ms
 *  - 按钮区高度 44px；主按钮蓝色填充；次按钮灰色描边
 *  - 二次确认：取消左、确认右；危险操作确认为红色
 *
 * 使用：
 *  import { showUnifiedDialog, showUnifiedConfirm } from '@/lib/dialog-unified';
 *  await showUnifiedConfirm({ title:'解绑设备', content:'确认解绑该设备？', danger:true });
 */
import React from 'react';
import { createRoot, type Root } from 'react-dom/client';

const BLUE = '#4A9EE0';
const GREY_BORDER = '#D1D5DB';
const RED = '#F26B6B';

interface BaseProps {
  title?: string;
  content?: string;
  icon?: React.ReactNode;
}

interface ConfirmProps extends BaseProps {
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  onConfirm?: () => void | Promise<void>;
  onCancel?: () => void;
}

interface DialogProps extends BaseProps {
  buttons?: { text: string; onClick?: () => void; primary?: boolean; danger?: boolean }[];
}

let mountedRoot: Root | null = null;
let mountedEl: HTMLDivElement | null = null;

function ensureMount(): HTMLDivElement {
  if (mountedEl && document.body.contains(mountedEl)) return mountedEl;
  const el = document.createElement('div');
  el.setAttribute('data-bh-dialog-root', 'true');
  document.body.appendChild(el);
  mountedEl = el;
  mountedRoot = createRoot(el);
  return el;
}

function close() {
  if (mountedRoot) {
    mountedRoot.render(null);
  }
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.45)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  animation: 'bh-fade 200ms',
};

const cardBase: React.CSSProperties = {
  background: '#fff',
  borderRadius: 16,
  padding: '20px 20px 16px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
  animation: 'bh-scale 200ms',
};

function injectKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.querySelector('#bh-dialog-keyframes')) return;
  const styleEl = document.createElement('style');
  styleEl.id = 'bh-dialog-keyframes';
  styleEl.innerHTML = `
    @keyframes bh-fade { from { opacity: 0; } to { opacity: 1; } }
    @keyframes bh-scale { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
  `;
  document.head.appendChild(styleEl);
}

const btnStyle = (primary: boolean, danger: boolean): React.CSSProperties => ({
  flex: 1,
  height: 44,
  borderRadius: 12,
  border: primary ? 'none' : `1px solid ${GREY_BORDER}`,
  background: primary ? (danger ? RED : BLUE) : '#fff',
  color: primary ? '#fff' : '#374151',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
});

export function showUnifiedDialog(p: DialogProps): Promise<void> {
  return new Promise((resolve) => {
    ensureMount();
    injectKeyframes();
    const buttons = p.buttons && p.buttons.length > 0 ? p.buttons : [{ text: '知道了', primary: true }];
    mountedRoot?.render(
      <div style={overlayStyle} onClick={() => { close(); resolve(); }} data-testid="bh-dialog-mask">
        <div
          style={{ ...cardBase, width: 320, maxWidth: '85vw' }}
          onClick={(e) => e.stopPropagation()}
          data-testid="bh-dialog-card"
        >
          {p.icon ? <div style={{ textAlign: 'center', fontSize: 32, marginBottom: 8 }}>{p.icon}</div> : null}
          {p.title ? (
            <div style={{ fontSize: 17, fontWeight: 700, color: '#1F2A37', textAlign: 'center', marginBottom: 10 }}>{p.title}</div>
          ) : null}
          {p.content ? (
            <div
              style={{ fontSize: 14, color: '#4B5563', textAlign: 'center', lineHeight: 1.6, marginBottom: 18, padding: '0 4px' }}
            >
              {p.content}
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: 10 }}>
            {buttons.map((b, idx) => (
              <button
                key={idx}
                style={btnStyle(!!b.primary, !!b.danger)}
                onClick={() => {
                  try { b.onClick?.(); } catch {}
                  close();
                  resolve();
                }}
              >
                {b.text}
              </button>
            ))}
          </div>
        </div>
      </div>,
    );
  });
}

export function showUnifiedConfirm(p: ConfirmProps): Promise<boolean> {
  return new Promise((resolve) => {
    ensureMount();
    injectKeyframes();
    mountedRoot?.render(
      <div style={overlayStyle} data-testid="bh-confirm-mask">
        <div style={{ ...cardBase, width: 300, maxWidth: '85vw' }} data-testid="bh-confirm-card">
          {p.danger ? (
            <div style={{ textAlign: 'center', fontSize: 28, marginBottom: 8 }}>⚠️</div>
          ) : (p.icon ? <div style={{ textAlign: 'center', fontSize: 28, marginBottom: 8 }}>{p.icon}</div> : null)}
          {p.title ? (
            <div style={{ fontSize: 17, fontWeight: 700, color: '#1F2A37', textAlign: 'center', marginBottom: 10 }}>{p.title}</div>
          ) : null}
          {p.content ? (
            <div style={{ fontSize: 14, color: '#4B5563', textAlign: 'center', lineHeight: 1.6, marginBottom: 18 }}>
              {p.content}
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              style={btnStyle(false, false)}
              onClick={() => { try { p.onCancel?.(); } catch {} close(); resolve(false); }}
              data-testid="bh-confirm-cancel"
            >
              {p.cancelText || '取消'}
            </button>
            <button
              style={btnStyle(true, !!p.danger)}
              onClick={async () => {
                try { await p.onConfirm?.(); } catch {}
                close();
                resolve(true);
              }}
              data-testid="bh-confirm-ok"
            >
              {p.confirmText || '确认'}
            </button>
          </div>
        </div>
      </div>,
    );
  });
}

export const UnifiedDialog = { show: showUnifiedDialog, confirm: showUnifiedConfirm };
export default UnifiedDialog;
