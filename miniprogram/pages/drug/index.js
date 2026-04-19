const { get, put } = require('../../utils/request');
const { uploadFile } = require('../../utils/request');
const { checkLogin, formatRelativeTime } = require('../../utils/util');
const { checkFileSize, uploadWithProgress } = require('../../utils/upload-utils');

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

const MAX_DRUG_NAME_LEN = 80;

function joinDrugNamesFromAI(aiResult) {
  if (!aiResult || typeof aiResult !== 'object') return '';
  const names = [];
  const top = aiResult.drug_name || aiResult.drugName || aiResult['药品名称'] || aiResult.name
    || aiResult['药品通用名'] || aiResult['通用名'] || aiResult['商品名'];
  if (top && typeof top === 'string') names.push(top);
  if (Array.isArray(aiResult.drugs)) {
    aiResult.drugs.forEach(d => {
      if (d && typeof d === 'object') {
        const n = d.drug_name || d.name || d['药品名称'];
        if (n && typeof n === 'string' && names.indexOf(n) < 0) names.push(n);
      }
    });
  }
  if (aiResult.result && typeof aiResult.result === 'object') {
    const n = aiResult.result.drug_name || aiResult.result.name || aiResult.result['药品名称'];
    if (n && typeof n === 'string' && names.indexOf(n) < 0) names.push(n);
  }
  const joined = names.filter(Boolean).join(',');
  return joined.length <= MAX_DRUG_NAME_LEN ? joined : joined.slice(0, MAX_DRUG_NAME_LEN) + '…';
}

function truncateDrugName(s) {
  if (!s) return '';
  return s.length <= MAX_DRUG_NAME_LEN ? s : s.slice(0, MAX_DRUG_NAME_LEN) + '…';
}

function getCustomItems(items) {
  return (items || []).filter(i => typeof i === 'object' && i.type === 'custom');
}

Page({
  data: {
    historyList: [],
    loading: false,
    uploading: false,
    selectedImages: [],
    maxImages: 5,
    uploadProgressText: '',
    uploadPercent: -1,

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

  onShow() {
    if (!checkLogin()) return;
    if (!this.data.today) {
      const now = new Date();
      const y = now.getFullYear();
      const m = String(now.getMonth() + 1).padStart(2, '0');
      const d = String(now.getDate()).padStart(2, '0');
      this.setData({ today: `${y}-${m}-${d}` });
      this.loadPresets();
    }
    this.loadHistory();
    this.loadFamilyMembers();
  },

  onPullDownRefresh() {
    this.loadHistory().finally(() => wx.stopPullDownRefresh());
  },

  async loadHistory() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/drug-identify/history', {}, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res.items || res.data || []);
      const historyList = list.map(item => ({
        id: item.id,
        sessionId: item.session_id || item.id,
        drugName: item.drug_name || item.title || '未识别药品',
        thumbnail: item.image_url || item.thumbnail || '',
        time: this._formatTime(item.created_at || item.updated_at),
        status: item.status || 'completed',
        statusText: this._getStatusText(item.status),
        family_member: item.family_member || null
      }));
      this.setData({ historyList });
    } catch (e) {
      console.log('loadHistory error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  _formatTime(dateStr) {
    if (!dateStr) return '';
    const ts = new Date(dateStr).getTime();
    if (isNaN(ts)) return '';
    return formatRelativeTime(ts);
  },

  _getStatusText(status) {
    const map = {
      pending: '识别中',
      completed: '已完成',
      failed: '识别失败'
    };
    return map[status] || '已完成';
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

  chooseAlbum() {
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
      const sizeCheck = await checkFileSize(images[i].path, 'drug_identify');
      if (!sizeCheck.ok) {
        wx.showToast({ title: `第${i + 1}张图片超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
        return;
      }
    }

    this.setData({ uploadStep: 2 });
  },

  confirmFamilyMember() {
    if (!this.data.selectedFamilyMemberId) {
      wx.showToast({ title: '请选择咨询对象', icon: 'none' });
      return;
    }
    this.setData({ uploadStep: 3 });
    this.doUpload();
  },

  async doUpload() {
    const images = this.data.selectedImages;
    const total = images.length;
    const familyMemberId = this.data.selectedFamilyMemberId;

    this.setData({ uploading: true, uploadProgressText: `正在上传 1/${total} 张...`, uploadPercent: 0 });

    let firstSessionId = null;
    const collectedDrugNames = [];
    try {
      for (let i = 0; i < images.length; i++) {
        this.setData({ uploadProgressText: `正在上传 ${i + 1}/${total} 张...` });
        const formData = { scene_name: '拍照识药' };
        if (familyMemberId) {
          formData.family_member_id = String(familyMemberId);
        }
        const res = await uploadWithProgress('/api/ocr/recognize', images[i].path, {
          formData,
          onProgress: (percent) => {
            const overallPercent = Math.round(((i + percent / 100) / total) * 100);
            this.setData({ uploadPercent: overallPercent });
          }
        });
        const sessionId = res && (res.session_id || res.id || res.sessionId);
        if (sessionId && !firstSessionId) {
          firstSessionId = sessionId;
        }
        const aiResult = res && (res.ai_result || res.aiResult);
        const partial = joinDrugNamesFromAI(aiResult);
        if (partial) {
          partial.split(',').forEach(n => {
            if (n && collectedDrugNames.indexOf(n) < 0) collectedDrugNames.push(n);
          });
        }
      }

      this.setData({ uploading: false, uploadProgressText: '', uploadPercent: -1, selectedImages: [], uploadStep: 1 });

      if (!firstSessionId) {
        wx.showToast({ title: '识别失败，请重试', icon: 'none' });
        return;
      }
      const memberId = this.data.selectedFamilyMemberId || '';
      const memberName = this.data.selectedFamilyMemberName || '本人';
      const drugNames = truncateDrugName(collectedDrugNames.join(','));
      wx.navigateTo({
        url: `/pages/chat/index?type=drug_identify&chatId=${firstSessionId}`
          + `&family_member_id=${memberId}`
          + `&summary=${encodeURIComponent('用药识别 · ' + memberName)}`
          + `&member=${encodeURIComponent(memberName)}`
          + `&drug_name=${encodeURIComponent(drugNames)}`
      });
    } catch (e) {
      this.setData({ uploading: false, uploadProgressText: '', uploadPercent: -1, uploadStep: 1 });
      wx.showToast({ title: e.detail || '识别失败，请重试', icon: 'none' });
    }
  },

  goChat(e) {
    const sessionId = e.currentTarget.dataset.sessionid;
    if (!sessionId) return;
    const item = e.currentTarget.dataset.item || {};
    const fm = item.family_member || null;
    let memberName = '本人';
    if (fm) {
      memberName = fm.is_self
        ? '本人'
        : (fm.nickname || fm.relation_type_name || fm.relationship_type || '本人');
    }
    const drugName = truncateDrugName(item.drugName || item.drug_name || '');
    wx.navigateTo({
      url: `/pages/chat/index?type=drug_identify&chatId=${sessionId}`
        + `&member=${encodeURIComponent(memberName)}`
        + `&drug_name=${encodeURIComponent(drugName)}`
    });
  }
});
