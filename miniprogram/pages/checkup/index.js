const { get, put, uploadFile } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');
const { checkFileSize, uploadWithProgress } = require('../../utils/upload-utils');
const { compressImage } = require('../../utils/image-compress');

const RELATION_EMOJI = {
  '本人': '👤', '爸爸': '👨', '妈妈': '👩', '父亲': '👨', '母亲': '👩',
  '老公': '💑', '老婆': '💑', '配偶': '💑',
  '儿子': '👦', '女儿': '👧', '子女': '👶',
  '哥哥': '👱‍♂️', '弟弟': '🧑', '姐姐': '👱‍♀️', '妹妹': '👧',
  '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵',
  '其他': '🧑'
};

function getMemberEmoji(name) {
  return RELATION_EMOJI[name] || '🧑';
}

function getCustomItems(items) {
  return (items || []).filter(i => typeof i === 'object' && i.type === 'custom');
}

Page({
  data: {
    historyReports: [],
    alerts: [],
    hasUnreadAlerts: false,
    loading: false,
    page: 1,
    pageSize: 10,
    hasMore: true,
    uploading: false,
    selectedImages: [],
    maxImages: 5,
    uploadProgressText: '',
    uploadPercent: -1,
    compareMode: false,
    selectedIds: [],

    uploadStep: 1,
    familyMembers: [],
    familyMembersLoaded: false,
    selectedFamilyMemberId: null,
    selectedFamilyMemberName: '',

    showHealthEdit: false,
    selfNickname: '',
    selfGender: '',
    selfBirthday: '',
    selfHeight: '',
    selfWeight: '',
    selfErrors: {},
    today: '',
    chronicPresets: [],
    allergyPresets: [],
    geneticPresets: [],
    chronic_diseases: [],
    allergies: [],
    genetic_diseases: [],
    chronicCustomItems: [],
    allergyCustomItems: [],
    geneticCustomItems: [],
    showChronicOther: false,
    showAllergyOther: false,
    showGeneticOther: false,
    chronicOtherInput: '',
    allergyOtherInput: '',
    geneticOtherInput: ''
  },

  onLoad() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    this.setData({ today: `${y}-${m}-${d}` });
    this.loadHistory();
    this.loadAlerts();
    this.loadPresets();
  },

  onShow() {
    this.setData({ page: 1, historyReports: [], hasMore: true });
    this.loadHistory();
    this.loadAlerts();
    this.loadFamilyMembers();
  },

  onPullDownRefresh() {
    this.setData({ page: 1, historyReports: [], hasMore: true });
    Promise.all([this.loadHistory(), this.loadAlerts()]).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadHistory();
    }
  },

  async loadHistory() {
    if (this.data.loading) return;
    this.setData({ loading: true });
    try {
      const res = await get('/api/report/list', {
        page: this.data.page,
        page_size: this.data.pageSize
      }, { showLoading: false, suppressErrorToast: true });
      const items = res.items || res.data || [];
      const list = items.map(item => ({
        ...item,
        dateFormatted: (item.created_at || item.date || '').substring(0, 10),
        abnormalCount: item.abnormal_count || 0,
        thumbnail: item.thumbnail || item.image_url || '',
        healthScore: item.health_score || 0,
        scoreColor: this.getScoreColor(item.health_score || 0),
        family_member: item.family_member || null
      }));
      this.setData({
        historyReports: [...this.data.historyReports, ...list],
        page: this.data.page + 1,
        hasMore: list.length >= this.data.pageSize,
        loading: false
      });
    } catch (e) {
      console.log('loadHistory error', e);
      this.setData({ loading: false });
    }
  },

  getScoreColor(score) {
    if (score >= 90) return '#1B8C3D';
    if (score >= 75) return '#4CAF50';
    if (score >= 60) return '#FFC107';
    if (score >= 40) return '#FF9800';
    if (score > 0) return '#F44336';
    return '#ccc';
  },

  async loadAlerts() {
    try {
      const res = await get('/api/report/alerts', {}, { showLoading: false, suppressErrorToast: true });
      const alerts = res.items || res.data || res || [];
      const unread = Array.isArray(alerts) ? alerts.filter(a => !a.is_read) : [];
      this.setData({
        alerts: Array.isArray(alerts) ? alerts : [],
        hasUnreadAlerts: unread.length > 0
      });
    } catch (e) {
      console.log('loadAlerts error', e);
    }
  },

  async loadFamilyMembers() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const list = (res && (res.items || res)) || [];
      const members = list.map(m => ({
        id: m.id,
        nickname: m.nickname,
        relationship_type: m.relationship_type || '本人',
        is_self: m.is_self,
        emoji: getMemberEmoji(m.relationship_type || '本人')
      }));
      members.sort((a, b) => (b.is_self ? 1 : 0) - (a.is_self ? 1 : 0));
      const selfMember = members.find(m => m.is_self) || members[0];
      this.setData({
        familyMembers: members,
        familyMembersLoaded: true,
        selectedFamilyMemberId: selfMember ? selfMember.id : null,
        selectedFamilyMemberName: selfMember ? (selfMember.nickname || selfMember.relationship_type) : ''
      });
      if (selfMember) {
        this.loadMemberHealth(selfMember);
      }
    } catch (e) {
      this.setData({ familyMembersLoaded: true });
    }
  },

  selectFamilyMember(e) {
    const member = e.currentTarget.dataset.member;
    this.setData({
      selectedFamilyMemberId: member.id,
      selectedFamilyMemberName: member.nickname || member.relationship_type,
      showHealthEdit: false,
      selfErrors: {}
    });
    this.loadMemberHealth(member);
  },

  goAddFamilyMember() {
    wx.navigateTo({ url: '/pages/family/add' });
  },

  async loadPresets() {
    try {
      const [chronicRes, allergyRes, geneticRes] = await Promise.all([
        get('/api/disease-presets', { category: 'chronic' }, { showLoading: false, suppressErrorToast: true }),
        get('/api/disease-presets', { category: 'allergy' }, { showLoading: false, suppressErrorToast: true }),
        get('/api/disease-presets', { category: 'genetic' }, { showLoading: false, suppressErrorToast: true })
      ]);
      this.setData({
        chronicPresets: (chronicRes && chronicRes.items) || [],
        allergyPresets: (allergyRes && allergyRes.items) || [],
        geneticPresets: (geneticRes && geneticRes.items) || []
      });
    } catch (e) {
      console.log('loadPresets error', e);
    }
  },

  async loadMemberHealth(member) {
    try {
      let profile;
      if (member.is_self) {
        profile = await get('/api/health/profile', {}, { showLoading: false, suppressErrorToast: true });
      } else {
        profile = await get(`/api/health/profile/member/${member.id}`, {}, { showLoading: false, suppressErrorToast: true });
      }
      if (profile) {
        const cd = profile.chronic_diseases || [];
        const al = profile.allergies || [];
        const gd = profile.genetic_diseases || [];
        this.setData({
          chronic_diseases: cd,
          allergies: al,
          genetic_diseases: gd,
          chronicCustomItems: getCustomItems(cd),
          allergyCustomItems: getCustomItems(al),
          geneticCustomItems: getCustomItems(gd),
          selfNickname: profile.nickname || member.nickname || '',
          selfGender: profile.gender || '',
          selfBirthday: profile.birthday || '',
          selfHeight: profile.height || '',
          selfWeight: profile.weight || '',
          selfErrors: {}
        });
      }
    } catch (e) {
      this.setData({
        chronic_diseases: [], allergies: [], genetic_diseases: [],
        chronicCustomItems: [], allergyCustomItems: [], geneticCustomItems: []
      });
    }
  },

  toggleHealthEdit() {
    this.setData({ showHealthEdit: !this.data.showHealthEdit });
  },

  onSelfNicknameInput(e) { this.setData({ selfNickname: e.detail.value }); },
  onSelfGenderSelect(e) { this.setData({ selfGender: e.currentTarget.dataset.gender }); },
  onSelfBirthdayChange(e) { this.setData({ selfBirthday: e.detail.value }); },
  onSelfHeightInput(e) { this.setData({ selfHeight: e.detail.value }); },
  onSelfWeightInput(e) { this.setData({ selfWeight: e.detail.value }); },

  toggleChronicPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.chronic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ chronic_diseases: items });
  },
  toggleChronicOther() { this.setData({ showChronicOther: !this.data.showChronicOther }); },
  onChronicOtherInput(e) { this.setData({ chronicOtherInput: e.detail.value }); },
  confirmChronicOther() {
    const val = (this.data.chronicOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.chronicPresets.some(p => p.name === val)) { wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return; }
    const items = [...this.data.chronic_diseases];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) { wx.showToast({ title: '已添加该项', icon: 'none' }); return; }
    items.push({ type: 'custom', value: val });
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items), chronicOtherInput: '' });
  },
  removeChronicCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.chronic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items) });
  },

  toggleAllergyPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.allergies];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ allergies: items });
  },
  toggleAllergyOther() { this.setData({ showAllergyOther: !this.data.showAllergyOther }); },
  onAllergyOtherInput(e) { this.setData({ allergyOtherInput: e.detail.value }); },
  confirmAllergyOther() {
    const val = (this.data.allergyOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.allergyPresets.some(p => p.name === val)) { wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return; }
    const items = [...this.data.allergies];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) { wx.showToast({ title: '已添加该项', icon: 'none' }); return; }
    items.push({ type: 'custom', value: val });
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items), allergyOtherInput: '' });
  },
  removeAllergyCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.allergies.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items) });
  },

  toggleGeneticPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.genetic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ genetic_diseases: items });
  },
  toggleGeneticOther() { this.setData({ showGeneticOther: !this.data.showGeneticOther }); },
  onGeneticOtherInput(e) { this.setData({ geneticOtherInput: e.detail.value }); },
  confirmGeneticOther() {
    const val = (this.data.geneticOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.geneticPresets.some(p => p.name === val)) { wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return; }
    const items = [...this.data.genetic_diseases];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) { wx.showToast({ title: '已添加该项', icon: 'none' }); return; }
    items.push({ type: 'custom', value: val });
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items), geneticOtherInput: '' });
  },
  removeGeneticCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.genetic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items) });
  },

  async saveHealthInfo() {
    const member = this.data.familyMembers.find(m => m.id === this.data.selectedFamilyMemberId);
    if (!member) return;
    const payload = {
      chronic_diseases: this.data.chronic_diseases,
      allergies: this.data.allergies,
      genetic_diseases: this.data.genetic_diseases,
      nickname: this.data.selfNickname,
      gender: this.data.selfGender,
      birthday: this.data.selfBirthday,
      height: this.data.selfHeight,
      weight: this.data.selfWeight
    };
    try {
      if (member.is_self) {
        await put('/api/health/profile', payload);
      } else {
        await put(`/api/health/profile/member/${member.id}`, payload);
      }
      wx.showToast({ title: '健康档案信息已同步更新', icon: 'success' });
      this.setData({ showHealthEdit: false });
    } catch (e) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    }
  },

  onStepTap(e) {
    const step = parseInt(e.currentTarget.dataset.step, 10);
    if (step < this.data.uploadStep) {
      this.setData({ uploadStep: step });
    }
  },

  confirmFamilyMember() {
    if (!this.data.selectedFamilyMemberId) {
      wx.showToast({ title: '请选择咨询对象', icon: 'none' });
      return;
    }
    this.setData({ uploadStep: 3 });
    this.doUpload();
  },

  dismissAlert() {
    const unread = this.data.alerts.filter(a => !a.is_read);
    unread.forEach(a => {
      const { put } = require('../../utils/request');
      put(`/api/report/alerts/${a.id}/read`, {}, { showLoading: false, suppressErrorToast: true }).catch(() => {});
    });
    this.setData({ hasUnreadAlerts: false });
  },

  chooseFromAlbum() {
    if (!checkLogin()) return;
    const remaining = this.data.maxImages - this.data.selectedImages.length;
    if (remaining <= 0) {
      wx.showToast({ title: `最多选择${this.data.maxImages}张图片`, icon: 'none' });
      return;
    }
    wx.chooseMedia({
      count: remaining,
      mediaType: ['image'],
      sourceType: ['album'],
      success: (res) => {
        const newImages = res.tempFiles.map(f => ({ path: f.tempFilePath }));
        this.setData({
          selectedImages: [...this.data.selectedImages, ...newImages]
        });
      }
    });
  },

  takePhoto() {
    if (!checkLogin()) return;
    if (this.data.selectedImages.length >= this.data.maxImages) {
      wx.showToast({ title: `最多选择${this.data.maxImages}张图片`, icon: 'none' });
      return;
    }
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: (res) => {
        const newImages = res.tempFiles.map(f => ({ path: f.tempFilePath }));
        this.setData({
          selectedImages: [...this.data.selectedImages, ...newImages]
        });
      }
    });
  },

  choosePDF() {
    if (!checkLogin()) return;
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['pdf'],
      success: (res) => {
        this.handleUploadFiles(res.tempFiles.map(f => f.path));
      }
    });
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.index;
    const images = [...this.data.selectedImages];
    images.splice(idx, 1);
    this.setData({ selectedImages: images });
  },

  async startRecognize() {
    if (this.data.selectedImages.length === 0) {
      wx.showToast({ title: '请先选择图片', icon: 'none' });
      return;
    }
    if (this.data.uploading) return;

    const images = this.data.selectedImages;
    for (let i = 0; i < images.length; i++) {
      const sizeCheck = await checkFileSize(images[i].path, 'checkup_report');
      if (!sizeCheck.ok) {
        wx.showToast({ title: `第${i + 1}张图片超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
        return;
      }
    }

    this.setData({ uploadStep: 2 });
  },

  async doUpload() {
    const images = this.data.selectedImages;
    const total = images.length;
    const familyMemberId = this.data.selectedFamilyMemberId;

    this.setData({ uploading: true, uploadProgressText: `正在上传 1/${total} 张...`, uploadPercent: 0 });

    try {
      let lastRecordId = null;
      let successCount = 0;

      for (let i = 0; i < images.length; i++) {
        this.setData({ uploadProgressText: `正在准备 ${i + 1}/${total} 张...` });
        try {
          // [2026-04-25 PRD F1] 上传前自动压缩：长边≤1600px、目标≤600KB；压缩后更大则回退原图
          let pathToUpload = images[i].path;
          try {
            pathToUpload = await compressImage(images[i].path);
          } catch (_) { pathToUpload = images[i].path; }

          this.setData({ uploadProgressText: `正在上传 ${i + 1}/${total} 张...` });
          const formData = { scene_name: '体检报告识别' };
          if (familyMemberId) {
            formData.family_member_id = String(familyMemberId);
          }
          const res = await uploadWithProgress('/api/ocr/recognize', pathToUpload, {
            formData,
            onProgress: (percent) => {
              const overallPercent = Math.round(((i + percent / 100) / total) * 100);
              this.setData({ uploadPercent: overallPercent });
            }
          });
          const reportId = res && (res.report_id || res.record_id || res.id);
          if (reportId) {
            lastRecordId = reportId;
            successCount++;
          }
        } catch (uploadErr) {
          console.log('单张上传失败', uploadErr);
        }
      }

      this.setData({ uploading: false, uploadProgressText: '', uploadPercent: -1, selectedImages: [], uploadStep: 1 });

      if (!lastRecordId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }

      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${lastRecordId}` });
    } catch (e) {
      this.setData({ uploading: false, uploadProgressText: '', uploadPercent: -1, uploadStep: 1 });
      if (e && e.statusCode === 503) {
        wx.showToast({ title: '解读功能暂时维护中，请稍后再试', icon: 'none', duration: 3000 });
      } else {
        wx.showToast({ title: (e && e.detail) || '上传失败，请重试', icon: 'none' });
      }
    }
  },

  async handleUploadFiles(filePaths) {
    if (!filePaths || !filePaths.length) return;

    for (const path of filePaths) {
      const sizeCheck = await checkFileSize(path, 'checkup_report');
      if (!sizeCheck.ok) {
        wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
        return;
      }
    }

    const familyMemberId = this.data.selectedFamilyMemberId;
    this.setData({ uploading: true, uploadPercent: 0 });

    try {
      let lastRecordId = null;
      const total = filePaths.length;
      for (let i = 0; i < filePaths.length; i++) {
        try {
          // [2026-04-25 PRD F1] 上传前压缩（仅图片，PDF 自动跳过）
          let pathToUpload = filePaths[i];
          try {
            pathToUpload = await compressImage(filePaths[i]);
          } catch (_) { pathToUpload = filePaths[i]; }

          const formData = { scene_name: '体检报告识别' };
          if (familyMemberId) {
            formData.family_member_id = String(familyMemberId);
          }
          const res = await uploadWithProgress('/api/ocr/recognize', pathToUpload, {
            formData,
            onProgress: (percent) => {
              const overallPercent = Math.round(((i + percent / 100) / total) * 100);
              this.setData({ uploadPercent: overallPercent });
            }
          });
          const reportId = res && (res.report_id || res.record_id || res.id);
          if (reportId) lastRecordId = reportId;
        } catch (e) {
          console.log('文件上传失败', e);
        }
      }

      this.setData({ uploading: false, uploadPercent: -1 });

      if (!lastRecordId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }

      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${lastRecordId}` });
    } catch (e) {
      this.setData({ uploading: false, uploadPercent: -1 });
      if (e && e.statusCode === 503) {
        wx.showToast({ title: '解读功能暂时维护中，请稍后再试', icon: 'none', duration: 3000 });
      } else {
        wx.showToast({ title: (e && e.detail) || '上传失败，请重试', icon: 'none' });
      }
    }
  },

  onItemTap(e) {
    const id = e.currentTarget.dataset.id;
    if (this.data.compareMode) {
      this.toggleSelectReport(e);
    } else {
      wx.navigateTo({ url: `/pages/checkup-detail/index?id=${id}` });
    }
  },

  viewReport(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/checkup-detail/index?id=${id}` });
  },

  toggleCompareMode() {
    this.setData({
      compareMode: !this.data.compareMode,
      selectedIds: []
    });
  },

  toggleSelectReport(e) {
    const id = String(e.currentTarget.dataset.id);
    let selected = [...this.data.selectedIds];
    const idx = selected.indexOf(id);
    if (idx >= 0) {
      selected.splice(idx, 1);
    } else {
      if (selected.length >= 2) {
        wx.showToast({ title: '最多选择2份报告', icon: 'none' });
        return;
      }
      selected.push(id);
    }
    this.setData({ selectedIds: selected });
  },

  goCompare() {
    const { selectedIds } = this.data;
    if (selectedIds.length !== 2) {
      wx.showToast({ title: '请选择2份报告进行对比', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: `/pages/checkup-compare/index?id1=${selectedIds[0]}&id2=${selectedIds[1]}`
    });
  }
});
