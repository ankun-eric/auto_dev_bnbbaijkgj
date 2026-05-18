'use client';

/**
 * [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.1.2 2026-05-18] 重新拍照选择抽屉
 *
 * 用户在「识药结果卡片」点击「重新拍照」按钮 → 弹出本抽屉
 * 抽屉内含两个入口：
 *   📷 拍照（调起系统相机）
 *   🖼 从相册选择（调起系统相册）
 *
 * 抽屉支持点击遮罩关闭。
 */
import React, { useRef } from 'react';

export interface RetakePhotoDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 用户选定一张图后回调；外层负责调用识别接口 */
  onPicked: (file: File, source: 'camera' | 'gallery') => void;
}

export default function RetakePhotoDrawer({ open, onClose, onPicked }: RetakePhotoDrawerProps) {
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const galleryInputRef = useRef<HTMLInputElement | null>(null);

  if (!open) return null;

  const handleCamera = () => cameraInputRef.current?.click();
  const handleGallery = () => galleryInputRef.current?.click();

  const handleFile = (source: 'camera' | 'gallery') => (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = ''; // 清空，便于同一文件再次触发
    if (f) {
      onPicked(f, source);
      onClose();
    }
  };

  return (
    <div
      data-testid="retake-photo-drawer"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          width: '100%',
          maxWidth: 600,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: '16px 16px 12px',
        }}
      >
        <div
          style={{
            textAlign: 'center',
            fontSize: 15,
            fontWeight: 600,
            color: '#111827',
            paddingBottom: 12,
            borderBottom: '1px solid #E5E7EB',
            marginBottom: 12,
          }}
        >
          重新拍照
        </div>
        <button
          type="button"
          data-testid="retake-camera-btn"
          onClick={handleCamera}
          style={btnStyle}
        >
          📷 拍照
        </button>
        <button
          type="button"
          data-testid="retake-gallery-btn"
          onClick={handleGallery}
          style={{ ...btnStyle, marginTop: 8 }}
        >
          🖼 从相册选择
        </button>
        <button
          type="button"
          onClick={onClose}
          data-testid="retake-cancel-btn"
          style={{ ...btnStyle, marginTop: 16, color: '#6B7280', background: '#F3F4F6' }}
        >
          取消
        </button>

        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ display: 'none' }}
          onChange={handleFile('camera')}
        />
        <input
          ref={galleryInputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={handleFile('gallery')}
        />
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '14px 0',
  background: '#0EA5E9',
  color: '#fff',
  border: 'none',
  borderRadius: 12,
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
};
