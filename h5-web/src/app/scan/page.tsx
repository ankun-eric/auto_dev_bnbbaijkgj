'use client';

import { useEffect, useRef, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Toast } from 'antd-mobile';
import { Html5Qrcode } from 'html5-qrcode';

export default function ScanPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-black flex items-center justify-center text-gray-400">加载中...</div>}>
      <ScanContent />
    </Suspense>
  );
}

function ScanContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const type = searchParams.get('type');
  const codeParam = searchParams.get('code');

  const scannerRef = useRef<Html5Qrcode | null>(null);
  const [scanning, setScanning] = useState(false);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (type === 'family_invite' && codeParam) {
      router.replace(`/family-auth?code=${codeParam}`);
      return;
    }

    stoppedRef.current = false;
    startScanner();
    return () => {
      stoppedRef.current = true;
      stopScanner();
    };
  }, [type, codeParam]);

  const stopScanner = async () => {
    try {
      if (scannerRef.current?.isScanning) {
        await scannerRef.current.stop();
      }
      scannerRef.current?.clear();
    } catch { /* ignore */ }
    scannerRef.current = null;
  };

  const startScanner = async () => {
    try {
      const scanner = new Html5Qrcode('qr-reader');
      scannerRef.current = scanner;
      setScanning(true);
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (text) => handleScanResult(text),
        () => {},
      );
    } catch (err: any) {
      setScanning(false);
      if (!stoppedRef.current) {
        Toast.show({ content: '无法访问摄像头，请检查权限设置', icon: 'fail', duration: 3000 });
      }
    }
  };

  const handleScanResult = (text: string) => {
    stopScanner();
    setScanning(false);

    try {
      const url = new URL(text);
      const params = url.searchParams;
      const type = params.get('type');
      const code = params.get('code');

      if (type === 'family_invite' && code) {
        router.replace(`/family-auth?code=${code}`);
        return;
      }
    } catch { /* not a URL, fall through */ }

    if (text.includes('type=family_invite') && text.includes('code=')) {
      const match = text.match(/code=([^&]+)/);
      if (match) {
        router.replace(`/family-auth?code=${match[1]}`);
        return;
      }
    }

    Toast.show({ content: '无法识别该二维码', icon: 'fail', duration: 2000 });
    setTimeout(() => {
      if (!stoppedRef.current) startScanner();
    }, 2500);
  };

  if (type === 'family_invite' && codeParam) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center text-gray-400">
        正在跳转...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black">
      <NavBar
        onBack={() => router.back()}
        style={{ background: 'transparent', color: '#fff' }}
      >
        <span className="text-white">扫一扫</span>
      </NavBar>

      <div className="flex flex-col items-center justify-center" style={{ minHeight: 'calc(100vh - 45px)' }}>
        <div
          id="qr-reader"
          style={{ width: '100%', maxWidth: 400 }}
        />
        {!scanning && (
          <div className="text-gray-400 text-sm mt-4">正在启动摄像头...</div>
        )}
        <div className="text-gray-500 text-xs mt-4">将二维码放入框内即可自动扫描</div>
      </div>
    </div>
  );
}
