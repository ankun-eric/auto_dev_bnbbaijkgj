const { generateId } = require('../../utils/util');

Page({
  data: {
    members: [
      { id: '1', name: '张大明', relation: '父亲', age: 65, phone: '138****1234', color: '#52c41a', conditions: ['高血压', '糖尿病'] },
      { id: '2', name: '李秀英', relation: '母亲', age: 62, phone: '139****5678', color: '#13c2c2', conditions: ['骨质疏松'] },
      { id: '3', name: '张小宝', relation: '孩子', age: 8, phone: '', color: '#faad14', conditions: [] }
    ],
    showAddModal: false,
    editIndex: -1,
    formData: { name: '', relation: '', age: '', phone: '' },
    relations: ['父亲', '母亲', '配偶', '孩子', '兄弟', '姐妹', '祖父', '祖母', '其他'],
    relationIndex: 0
  },

  addMember() {
    this.setData({
      showAddModal: true,
      editIndex: -1,
      formData: { name: '', relation: '', age: '', phone: '' }
    });
  },

  editMember(e) {
    const index = e.currentTarget.dataset.index;
    const member = this.data.members[index];
    const relIdx = this.data.relations.indexOf(member.relation);
    this.setData({
      showAddModal: true,
      editIndex: index,
      formData: { name: member.name, relation: member.relation, age: String(member.age), phone: member.phone },
      relationIndex: relIdx >= 0 ? relIdx : 0
    });
  },

  closeModal() {
    this.setData({ showAddModal: false });
  },

  onFormInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`formData.${field}`]: e.detail.value });
  },

  onRelationChange(e) {
    const index = e.detail.value;
    this.setData({ relationIndex: index, 'formData.relation': this.data.relations[index] });
  },

  saveMember() {
    const { formData, editIndex, members } = this.data;
    if (!formData.name) {
      wx.showToast({ title: '请输入姓名', icon: 'none' });
      return;
    }

    const colors = ['#52c41a', '#13c2c2', '#faad14', '#722ed1', '#1890ff', '#eb2f96'];

    if (editIndex >= 0) {
      const updated = { ...members[editIndex], ...formData, age: Number(formData.age) };
      const newMembers = [...members];
      newMembers[editIndex] = updated;
      this.setData({ members: newMembers, showAddModal: false });
    } else {
      const newMember = {
        id: generateId(),
        ...formData,
        age: Number(formData.age),
        color: colors[members.length % colors.length],
        conditions: []
      };
      this.setData({ members: [...members, newMember], showAddModal: false });
    }
    wx.showToast({ title: '保存成功', icon: 'success' });
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
