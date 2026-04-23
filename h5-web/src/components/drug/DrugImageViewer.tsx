'use client';

import { useEffect, useRef, useState } from 'react';

interface DrugImageViewerProps {
  visible: boolean;
  images: string[];
  defaultIndex?: number;
  onClose: () => void;
}

export default function DrugImageViewer({
  visible,
  images,
  defaultIndex = 0,
  onClose,
}: DrugImageViewerProps) {
  const [index, setIndex] = useState(defaultIndex);
  const touchStartX = useRef<number | null>(null);
  const touchDeltaX = useRef(0);
  const [dragDelta, setDragDelta] = useState(0);

  useEffect(() => {
    if (visible) setIndex(defaultIndex);
  }, [visible, defaultIndex]);

  useEffect(() => {
    if (!visible) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [visible, onClose]);

  if (!visible || images.length === 0) return null;

  const total = images.length;
  const canSwipe = total > 1;

  const onTouchStart = (e: React.TouchEvent) => {
    if (!canSwipe) return;
    touchStartX.current = e.touches[0].clientX;
    touchDeltaX.current = 0;
  };
  const onTouchMove = (e: React.TouchEvent) => {
    if (!canSwipe || touchStartX.current == null) return;
    touchDeltaX.current = e.touches[0].clientX - touchStartX.current;
    setDragDelta(touchDeltaX.current);
  };
  const onTouchEnd = () => {
    if (!canSwipe || touchStartX.current == null) return;
    const dx = touchDeltaX.current;
    const threshold = 50;
    if (dx > threshold && index > 0) {
      setIndex(index - 1);
    } else if (dx < -threshold && index < total - 1) {
      setIndex(index + 1);
    }
    touchStartX.current = null;
    touchDeltaX.current = 0;
    setDragDelta(0);
  };

  return (
    <div
      className="fixed inset-0 z-[9999] bg-black flex items-center justify-center select-none"
      style={{ touchAction: 'none' }}
      onClick={onClose}
    >
      <button
        aria-label="关闭"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="absolute top-4 right-4 w-11 h-11 rounded-full bg-white/20 text-white text-2xl leading-none flex items-center justify-center z-10"
        style={{ backdropFilter: 'blur(4px)' }}
      >
        ×
      </button>

      <div
        className="w-full h-full relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <div
          className="absolute inset-0 flex transition-transform"
          style={{
            transform: `translateX(calc(${-index * 100}% + ${dragDelta}px))`,
            transitionDuration: dragDelta === 0 ? '260ms' : '0ms',
          }}
        >
          {images.map((url, i) => (
            <div
              key={i}
              className="w-full h-full flex-shrink-0 flex items-center justify-center px-4"
            >
              <img
                src={url}
                alt={`药品图片 ${i + 1}`}
                className="max-w-full max-h-full object-contain"
                draggable={false}
              />
            </div>
          ))}
        </div>
      </div>

      {total > 1 && (
        <div className="absolute bottom-6 left-0 right-0 flex justify-center pointer-events-none">
          <div
            className="px-3 py-1 rounded-full bg-white/20 text-white text-sm"
            style={{ backdropFilter: 'blur(4px)' }}
          >
            图 {index + 1}/{total}
          </div>
        </div>
      )}
    </div>
  );
}
