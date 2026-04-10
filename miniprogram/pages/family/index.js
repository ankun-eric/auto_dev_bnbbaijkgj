const { generateId } = require('../../utils/util');
const { get, post, put } = require('../../utils/request');

const RELATION_COLORS = {
  '本人': '#52c41a',
  '爸爸': '#1890ff', '妈妈': '#1890ff',
  '儿子': '#eb2f96', '女儿': '#eb2f96',
  '爷爷': '#fa8c16', '奶奶': '#fa8c16',
  '外公': '#fa8c16', '外婆': '#fa8c16'
};
function getRelationColor(name) {
  return RELATION_COLORS[name] || '#8c8c8c';
}

Page({
  data: {
    members: [],
    showAddModal: false,
    editIndex: -1,
    formData: { name: '', relation: '', relation_type_id: null, age: '', phone: '' },
    relations: [],
    relationTypes: [],
    selectedRelationIndex: -1
  },

  onLoad() {
    this.loadRelationTypes();
    this.loadMembers();
  },

  async loadRelationTypes() {
    try {
      const res = await get('/api/relation-types', {}, { showLoading: false, suppressErrorToast: true });
      const items = res && res.items ? res.items : [];
      const filtered = items.filter(t => t.name !== '本人');
      this.setData({
        relationTypes: filtered,
        relations: filtered.map(t => t.name)
      });
    } catch (e) {
      console.log('loadRelationTypes error', e);
    }
  },

  async loadMembers() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const items = res && res.items ? res.items : [];
      const members = items.filter(m => !m.is_self).map(m => ({
        id: String(m.id),
        name: m.nickname || '',
        relation: m.relation_type_name || m.relationship_type || '',
        age: m.birthday ? new Date().getFullYear() - new Date(m.birthday).getFullYear() : '',
        phone: '',
        color: getRelationColor(m.relation_type_name || ''),
        conditions: m.medical_histories || []
      }));
      this.setData({ members });
    } catch (e) {
      console.log('loadMembers error', e);
    }
  },

  addMember() {
    this.setData({
      showAddModal: true,
      editIndex: -1,
      formData: { name: '', relation: '', relation_type_id: null, age: '', phone: '' },
      selectedRelationIndex: -1
    });
  },

  editMember(e) {
    const index = e.currentTarget.dataset.index;
    const member = this.data.members[index];
    const relIdx = this.data.relations.indexOf(member.relation);
    this.setData({
      showAddModal: true,
      editIndex: index,
      formData: { name: member.name, relation: member.relation, relation_type_id: null, age: String(member.age), phone: member.phone },
      selectedRelationIndex: relIdx >= 0 ? relIdx : -1
    });
  },

  closeModal() {
    this.setData({ showAddModal: false });
  },

  onFormInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`formData.${field}`]: e.detail.value });
  },

  onRelationSelect(e) {
    const index = parseInt(e.currentTarget.dataset.index, 10);
    const rt = this.data.relationTypes[index];
    this.setData({
      selectedRelationIndex: index,
      'formData.relation': rt.name,
      'formData.relation_type_id': rt.id
    });
  },

  async saveMember() {
    const { formData, editIndex, members } = this.data;
    if (!formData.name) {
      wx.showToast({ title: '请输入姓名', icon: 'none' });
      return;
    }
    if (!formData.relation) {
      wx.showToast({ title: '请选择关系', icon: 'none' });
      return;
    }

    try {
      const payload = {
        name: formData.name,
        nickname: formData.name,
        relationship_type: formData.relation,
        relation_type_id: formData.relation_type_id || undefined
      };
      if (editIndex >= 0) {
        const memberId = members[editIndex].id;
        await put(`/api/family/members/${memberId}`, payload, { suppressErrorToast: true }).catch(() => null);
      } else {
        await post('/api/family/members', payload);
      }
      this.setData({ showAddModal: false });
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.loadMembers();
    } catch (e) {
      const color = getRelationColor(formData.relation);
      if (editIndex >= 0) {
        const updated = { ...members[editIndex], name: formData.name, relation: formData.relation, age: Number(formData.age), color };
        const newMembers = [...members];
        newMembers[editIndex] = updated;
        this.setData({ members: newMembers, showAddModal: false });
      } else {
        const newMember = {
          id: generateId(),
          name: formData.name,
          relation: formData.relation,
          age: Number(formData.age),
          phone: formData.phone,
          color,
          conditions: []
        };
        this.setData({ members: [...members, newMember], showAddModal: false });
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
    }
  },

  deleteMember(e) {
    const index = e.currentTarget.dataset.index;
    wx.showModal({
      title: '确认删除',
      content: `确定删除${this.data.members[index].name}吗？`,
      success: (res) => {
        if (res.confirm) {
          const members = this.data.members.filter((_, i) => i !== index);
          this.setData({ members });
        }
      }
    });
  },

  consultFor(e) {
    const member = e.currentTarget.dataset.member;
    wx.navigateTo({
      url: `/pages/chat/index?type=general&question=${encodeURIComponent('我想代家人' + member.name + '（' + member.relation + '，' + member.age + '岁）咨询健康问题')}`
    });
  },

  triggerSOS() {
    wx.showModal({
      title: '紧急呼叫',
      content: '确定要发起紧急呼叫吗？将通知所有家庭成员',
      confirmColor: '#ff4d4f',
      success: (res) => {
        if (res.confirm) {
          wx.makePhoneCall({ phoneNumber: '120', fail() {} });
        }
      }
    });
  }
});
