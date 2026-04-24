'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthed } from './lib';

export default function MerchantRoot() {
  const router = useRouter();
  useEffect(() => {
    if (isAuthed()) {
      router.replace('/merchant/dashboard');
    } else {
      router.replace('/merchant/login');
    }
  }, [router]);
  return null;
}
