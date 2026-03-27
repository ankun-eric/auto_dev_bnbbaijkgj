const { post, get, uploadFile } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    analysisResult: null,
    historyReports: [
      { id: '1', date: '2026-03-15', name: '年度体检报告', status: '已分析', summary: '整体健康状况良好，血脂偏高需注意' },
      { id: '2', date: '2026-01-08', name: '血常规检查', status: '已分析', summary: '各项指标正常' }
    ]
  },

  onLoad() {
    this.loadHistory();
  },

  async loadHistory() {
    try {
      // const res = await get('/api/health/checkup-reports');
      // this.setData({ historyReports: res.data });
    } catch (e) {
      console.log('loadHistory error', e);
    }
  },

  uploadReport() {
    if (!checkLogin()) return;

    wx.chooseMedia({
      count: 9,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const filePaths = res.tempFiles.map(f => f.tempFilePath);
        wx.showLoading({ title: 'AI分析中...', mask: true });

        try {
          // for (const path of filePaths) {
          //   await uploadFile('/api/checkup/upload', path);
          // }
          await new Promise(resolve => setTimeout(resolve, 2000));

          this.setData({
            analysisResult: {
              items: [
                { name: '血红蛋白', value: '145 g/L', reference: '120-160 g/L', status: 'normal' },
                { name: '白细胞计数', value: '6.8×10⁹/L', reference: '4.0-10.0×10⁹/L', status: 'normal' },
                { name: '总胆固醇', value: '5.8 mmol/L', reference: '3.1-5.2 mmol/L', status: 'abnormal', advice: '建议减少高脂肪饮食，增加运动量' },
                { name: '空腹血糖', value: '5.1 mmol/L', reference: '3.9-6.1 mmol/L', status: 'normal' },
                { name: '甘油三酯', value: '2.1 mmol/L', reference: '0.56-1.70 mmol/L', status: 'abnormal', advice: '建议控制碳水化合物和酒精摄入' }
              ],
              summary: '整体健康状况良好。总胆固醇和甘油三酯偏高，建议调整饮食结构，减少高脂肪食物摄入，增加有氧运动。3个月后复查血脂。'
            }
          });
          wx.hideLoading();
          wx.showToast({ title: '分析完成', icon: 'success' });
        } catch (e) {
          wx.hideLoading();
          wx.showToast({ title: '分析失败', icon: 'none' });
        }
      }
    });
  },

  viewReport(e) {
    const id = e.currentTarget.dataset.id;
    wx.showToast({ title: '查看报告详情', icon: 'none' });
  }
});
