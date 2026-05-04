'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, List, Input, Button, Toast, ImageUploader, Dialog } from 'antd-mobile';
import type { ImageUploadItem } from 'antd-mobile/es/components/image-uploader';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

export default function ProfileEditPage() {
  const router = useRouter();
  const { user, updateUser } = useAuth();
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [avatar, setAvatar] = useState<ImageUploadItem[]>(
    user?.avatar ? [{ url: resolveAssetUrl(user.avatar) }] : []
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setNickname(user.nickname || '');
      setAvatar(user.avatar ? [{ url: resolveAssetUrl(user.avatar) }] : []);
    }
  }, [user]);

  const handleUpload = async (file: File): Promise<ImageUploadItem> => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res: any = await api.post('/api/upload/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const data = res.data || res;
      return { url: resolveAssetUrl(data.url || data.file_url || '') };
    } catch {
      Toast.show({ content: '上传失败' });
      throw new Error('upload failed');
    }
  };

  const handleSave = async () => {
    if (!nickname.trim()) {
      Toast.show({ content: '请输入昵称' });
      return;
    }
    setSaving(true);
    try {
      const avatarUrl = avatar.length > 0 ? avatar[0].url : '';
      const res: any = await api.put('/api/users/me', {
        nickname: nickname.trim(),
        avatar: avatarUrl,
      });
      const data = res.data || res;
      if (user) {
        updateUser({ ...user, nickname: nickname.trim(), avatar: avatarUrl || user.avatar });
      }
      Toast.show({ content: '保存成功', icon: 'success' });
      router.back();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        修改个人信息
      </NavBar>

      <div className="pt-2">
        <List style={{ '--border-top': 'none' }}>
          <List.Item
            extra={
              <ImageUploader
                value={avatar}
                onChange={setAvatar}
                upload={handleUpload}
                maxCount={1}
                style={{ '--cell-size': '56px' }}
              />
            }
          >
            头像
          </List.Item>
          <List.Item
            extra={
              <Input
                value={nickname}
                onChange={setNickname}
                placeholder="请输入昵称"
                style={{ '--text-align': 'right', '--font-size': '14px' }}
              />
            }
          >
            昵称
          </List.Item>
          <List.Item
            extra={
              <div className="flex items-center gap-2">
                <span className="text-sm">{user?.phone || '未绑定'}</span>
                <span className="text-xs text-gray-400">不可修改</span>
              </div>
            }
          >
            手机号
          </List.Item>
        </List>
      </div>

      <div className="px-4 mt-6">
        <Button
          block
          color="primary"
          loading={saving}
          onClick={handleSave}
          style={{
            borderRadius: 24,
            height: 44,
            background: '#52c41a',
            border: 'none',
          }}
        >
          保存
        </Button>
      </div>
    </div>
  );
}
