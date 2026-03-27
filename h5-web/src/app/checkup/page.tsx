'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Button, Card, List, Tag, ImageUploader, Toast, Empty } from 'antd-mobile';
import type { ImageUploadItem } from 'antd-mobile/es/components/image-uploader';
import api from '@/lib/api';

const mockReports = [
  { id: 1, title: '2024年度体检报告', date: '2024-03-15', status: '已分析', riskLevel: '低风险' },
  { id: 2, title: '2023年度体检报告', date: '2023-09-20', status: '已分析', riskLevel: '中风险' },
  { id: 3, title: '血常规检查', date: '2024-01-10', status: '已分析', riskLevel: '正常' },
];

export default function CheckupPage() {
  const router = useRouter();
  const [fileList, setFileList] = useState<ImageUploadItem[]>([]);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res: any = await api.post('/api/health/checkup-reports', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return { url: res.url || URL.createObjectURL(file) };
    } catch {
      return { url: URL.createObjectURL(file) };
    }
  };

  const analyzeReport = async () => {
    if (fileList.length === 0) {
      Toast.show({ content: '请先上传体检报告' });
      return;
    }
    setUploading(true);
    Toast.show({ icon: 'loading', content: 'AI分析中...', duration: 0 });
    setTimeout(() => {
      Toast.clear();
      Toast.show({ content: '分析完成' });
      setUploading(false);
    }, 2000);
  };

  const riskColor = (level: string) => {
    if (level === '低风险' || level === '正常') return '#52c41a';
    if (level === '中风险') return '#fa8c16';
    return '#f5222d';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        体检报告
      </NavBar>

      <div className="px-4 pt-4">
        <div className="card">
          <div className="section-title">上传体检报告</div>
          <p className="text-xs text-gray-400 mb-3">支持拍照上传或PDF文件，AI将为您智能分析</p>
          <ImageUploader
            value={fileList}
            onChange={setFileList}
            upload={handleUpload}
            maxCount={5}
            style={{ '--cell-size': '80px' }}
          />
          <Button
            block
            loading={uploading}
            onClick={analyzeReport}
            style={{
              marginTop: 16,
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              height: 44,
            }}
          >
            AI智能分析
          </Button>
        </div>

        <div className="section-title mt-4">历史报告</div>
        {mockReports.length === 0 ? (
          <Empty description="暂无体检报告" style={{ padding: '40px 0' }} />
        ) : (
          mockReports.map((report) => (
            <Card key={report.id} style={{ marginBottom: 12, borderRadius: 12 }}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm">{report.title}</div>
                  <div className="text-xs text-gray-400 mt-1">{report.date}</div>
                </div>
                <div className="text-right">
                  <Tag
                    style={{
                      '--background-color': `${riskColor(report.riskLevel)}15`,
                      '--text-color': riskColor(report.riskLevel),
                      '--border-color': 'transparent',
                    }}
                  >
                    {report.riskLevel}
                  </Tag>
                  <div className="text-xs text-primary mt-1">{report.status}</div>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
