// [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 追问 chips 行
Component({
  properties: {
    chips: { type: Array, value: [] },
    disabled: { type: Boolean, value: false },
  },
  methods: {
    onTap(e) {
      if (this.data.disabled) return;
      const idx = e.currentTarget.dataset.idx;
      const chip = this.data.chips[idx];
      if (!chip) return;
      this.triggerEvent('chiptap', { chip });
    },
  },
});
