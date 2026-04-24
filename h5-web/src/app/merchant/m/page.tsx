'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthed } from './mobile-lib';

export default function MerchantMobileIndex() {
  const router = useRouter();
  useEffect(() => {
    if (isAuthed()) router.replace('/merchant/m/dashboard');
    else router.replace('/merchant/m/login');
  }, [router]);
  return null;
}
