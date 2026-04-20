import 'dart:convert';
import 'package:flutter/material.dart';
import 'disease_tag_selector.dart';

const _kPrimaryGreen = Color(0xFF52C41A);
const _kCompleteColor = Color(0xFF52c41a);
const _kIncompleteColor = Color(0xFFfa8c16);

enum HealthProfileMode { existing, newMember }

/// 健康档案数据快照（用于对比判断是否脏）
class HealthProfileSnapshot {
  final String nickname;
  final String birthday;
  final String gender;
  final String height;
  final String weight;
  final List<dynamic> chronicDiseases;
  final List<dynamic> allergies;
  final List<dynamic> geneticDiseases;

  const HealthProfileSnapshot({
    this.nickname = '',
    this.birthday = '',
    this.gender = '',
    this.height = '',
    this.weight = '',
    this.chronicDiseases = const [],
    this.allergies = const [],
    this.geneticDiseases = const [],
  });

  Map<String, dynamic> toMap() => {
        'nickname': nickname,
        'birthday': birthday,
        'gender': gender,
        'height': height,
        'weight': weight,
        'chronic_diseases': chronicDiseases,
        'allergies': allergies,
        'genetic_diseases': geneticDiseases,
      };

  static String _normalizeList(List<dynamic>? items) {
    if (items == null) return '[]';
    final normalized = items.map((it) {
      if (it is String) return {'type': 'preset', 'value': it.trim()};
      if (it is Map) {
        return {
          'type': (it['type'] ?? 'preset').toString(),
          'value': (it['value'] ?? '').toString().trim(),
        };
      }
      return {'type': 'preset', 'value': it.toString().trim()};
    }).where((it) => (it['value'] as String).isNotEmpty).toList();
    normalized.sort((a, b) {
      final ta = a['type']!; final tb = b['type']!;
      if (ta != tb) return ta.compareTo(tb);
      return (a['value']!).compareTo(b['value']!);
    });
    return jsonEncode(normalized);
  }

  bool equalsTo(HealthProfileSnapshot? other) {
    if (other == null) return false;
    if (nickname.trim() != other.nickname.trim()) return false;
    if (gender != other.gender) return false;
    if (birthday != other.birthday) return false;
    if (height.trim() != other.height.trim()) return false;
    if (weight.trim() != other.weight.trim()) return false;
    if (_normalizeList(chronicDiseases) != _normalizeList(other.chronicDiseases)) return false;
    if (_normalizeList(allergies) != _normalizeList(other.allergies)) return false;
    if (_normalizeList(geneticDiseases) != _normalizeList(other.geneticDiseases)) return false;
    return true;
  }
}

/// 显示三选项未保存修改对话框
/// 返回 'save' / 'discard' / 'cancel'
Future<String> showUnsavedChangesDialog(
  BuildContext context, {
  required String scene, // 'analyze' | 'switch'
}) async {
  final primary = scene == 'analyze' ? '保存并分析' : '保存并切换';
  final discard = scene == 'analyze' ? '放弃修改并分析' : '放弃修改并切换';
  final result = await showDialog<String>(
    context: context,
    barrierDismissible: true,
    builder: (ctx) => AlertDialog(
      title: const Text('档案有未保存的修改', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
      content: const Text('您对档案做了修改但尚未保存，请选择：'),
      actionsPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      actions: [
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: _kPrimaryGreen,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 11),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => Navigator.of(ctx).pop('save'),
            child: Text(primary),
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFFFF4D4F),
              side: const BorderSide(color: Color(0xFFFF4D4F)),
              padding: const EdgeInsets.symmetric(vertical: 11),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => Navigator.of(ctx).pop('discard'),
            child: Text(discard),
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.grey[700],
              side: BorderSide(color: Colors.grey[300]!),
              padding: const EdgeInsets.symmetric(vertical: 11),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => Navigator.of(ctx).pop('cancel'),
            child: const Text('取消'),
          ),
        ),
      ],
    ),
  );
  return result ?? 'cancel';
}

class HealthProfileEditor extends StatefulWidget {
  final String? nickname;
  final String? birthday;
  final String? gender;
  final String? height;
  final String? weight;
  final List<dynamic>? chronicDiseases;
  final List<dynamic>? allergies;
  final List<dynamic>? geneticDiseases;
  final List<dynamic> chronicPresets;
  final List<dynamic> allergyPresets;
  final List<dynamic> geneticPresets;
  final String memberName;
  final ValueChanged<Map<String, dynamic>> onChanged;
  final Map<String, String?> errors;

  /// existing: 已有成员，默认收起 + 独立保存按钮；newMember: 新建，默认展开，无独立保存按钮
  final HealthProfileMode mode;

  /// 初始档案快照（仅 existing 模式使用）
  final HealthProfileSnapshot? initialProfile;

  /// 独立保存回调（仅 existing 模式），返回 true 表示保存成功
  final Future<bool> Function(HealthProfileSnapshot profile)? onSaveProfile;

  /// 收起时卡片显示的 emoji
  final String? memberEmoji;

  /// 放弃修改时回调（由父组件重置 profile 数据）
  final VoidCallback? onDiscardChanges;

  const HealthProfileEditor({
    super.key,
    this.nickname,
    this.birthday,
    this.gender,
    this.height,
    this.weight,
    this.chronicDiseases,
    this.allergies,
    this.geneticDiseases,
    this.chronicPresets = const [],
    this.allergyPresets = const [],
    this.geneticPresets = const [],
    this.memberName = '本人',
    required this.onChanged,
    this.errors = const {},
    this.mode = HealthProfileMode.existing,
    this.initialProfile,
    this.onSaveProfile,
    this.memberEmoji,
    this.onDiscardChanges,
  });

  @override
  State<HealthProfileEditor> createState() => HealthProfileEditorState();
}

class HealthProfileEditorState extends State<HealthProfileEditor> {
  late bool _expanded;
  bool _saving = false;
  late TextEditingController _nicknameController;
  late TextEditingController _heightController;
  late TextEditingController _weightController;

  @override
  void initState() {
    super.initState();
    _expanded = widget.mode == HealthProfileMode.newMember;
    _nicknameController = TextEditingController(text: widget.nickname ?? '');
    _heightController = TextEditingController(text: widget.height ?? '');
    _weightController = TextEditingController(text: widget.weight ?? '');
  }

  @override
  void didUpdateWidget(covariant HealthProfileEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.nickname != oldWidget.nickname) {
      _nicknameController.text = widget.nickname ?? '';
    }
    if (widget.height != oldWidget.height) {
      _heightController.text = widget.height ?? '';
    }
    if (widget.weight != oldWidget.weight) {
      _weightController.text = widget.weight ?? '';
    }
  }

  HealthProfileSnapshot _currentSnapshot() => HealthProfileSnapshot(
        nickname: widget.nickname ?? '',
        birthday: widget.birthday ?? '',
        gender: widget.gender ?? '',
        height: widget.height ?? '',
        weight: widget.weight ?? '',
        chronicDiseases: widget.chronicDiseases ?? [],
        allergies: widget.allergies ?? [],
        geneticDiseases: widget.geneticDiseases ?? [],
      );

  bool hasUnsavedChanges() {
    if (widget.mode == HealthProfileMode.newMember) return false;
    final init = widget.initialProfile;
    if (init == null) return false;
    return !init.equalsTo(_currentSnapshot());
  }

  /// 触发独立保存，返回 true 表示已保存
  Future<bool> saveProfile() async {
    final onSave = widget.onSaveProfile;
    if (onSave == null) return true;
    if (!validate()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填写必填项'), duration: Duration(seconds: 2)),
      );
      return false;
    }
    setState(() => _saving = true);
    try {
      final ok = await onSave(_currentSnapshot());
      return ok;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// 放弃修改：调用父组件的 onDiscardChanges
  void discardChanges() {
    widget.onDiscardChanges?.call();
  }

  bool validate() {
    final errors = <String, String?>{};
    if ((widget.nickname ?? '').trim().isEmpty) errors['nickname'] = '请输入姓名';
    if ((widget.gender ?? '').isEmpty) errors['gender'] = '请选择性别';
    if ((widget.birthday ?? '').isEmpty) errors['birthday'] = '请选择出生日期';
    widget.onChanged({'__errors': errors});
    return errors.isEmpty;
  }

  void resetExpanded() {
    if (mounted) setState(() => _expanded = widget.mode == HealthProfileMode.newMember);
  }

  void expand() {
    if (mounted) setState(() => _expanded = true);
  }

  void collapse() {
    if (mounted) setState(() => _expanded = false);
  }

  String _calcAge(String birthday) {
    if (birthday.isEmpty) return '';
    final parts = birthday.split('-');
    if (parts.length < 3) return '';
    final y = int.tryParse(parts[0]) ?? 0;
    final m = int.tryParse(parts[1]) ?? 0;
    final d = int.tryParse(parts[2]) ?? 0;
    if (y == 0 || m == 0 || d == 0) return '';
    final now = DateTime.now();
    var age = now.year - y;
    if (now.month < m || (now.month == m && now.day < d)) age -= 1;
    if (age < 0) return '';
    return '$age岁';
  }

  bool get isProfileComplete {
    final hasNickname = (widget.nickname ?? '').trim().isNotEmpty;
    final hasGender = (widget.gender ?? '').isNotEmpty;
    final hasBirthday = (widget.birthday ?? '').isNotEmpty;
    final hasHeight = (widget.height ?? '').trim().isNotEmpty;
    final hasWeight = (widget.weight ?? '').trim().isNotEmpty;
    return hasNickname && hasGender && hasBirthday && hasHeight && hasWeight;
  }

  void _notify(String key, dynamic value) {
    widget.onChanged({key: value});
  }

  Future<void> _pickBirthday() async {
    final currentBirthday = widget.birthday ?? '';
    final initial = currentBirthday.isNotEmpty
        ? (DateTime.tryParse(currentBirthday) ?? DateTime(2000))
        : DateTime(2000);
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(1900),
      lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(primary: _kPrimaryGreen),
          ),
          child: child!,
        );
      },
    );
    if (date != null) {
      final formatted =
          '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
      _notify('birthday', formatted);
    }
  }

  @override
  void dispose() {
    _nicknameController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // existing 模式且未展开：只显示精简卡片
    if (widget.mode == HealthProfileMode.existing && !_expanded) {
      return _buildCollapsedCard();
    }

    final isDirty = hasUnsavedChanges();
    return Column(
      children: [
        if (widget.mode == HealthProfileMode.existing)
          _buildExpandedHeader(),
        _buildBasicInfoCard(),
        const SizedBox(height: 12),
        _buildExpandedSection(),
        if (widget.mode == HealthProfileMode.existing && isDirty) ...[
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: _saving ? const Color(0xFF91D5A4) : _kPrimaryGreen,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: _saving ? null : () async { await saveProfile(); },
              child: Text(_saving ? '保存中...' : '保存档案',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildCollapsedCard() {
    final name = (widget.nickname ?? '').trim().isNotEmpty
        ? widget.nickname!
        : (widget.memberName.isNotEmpty ? widget.memberName : '未填写姓名');
    final age = _calcAge(widget.birthday ?? '');
    final genderText = widget.gender == 'male' ? '男' : widget.gender == 'female' ? '女' : '';
    return GestureDetector(
      onTap: expand,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xFFE8F5E9), width: 2),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 4, offset: const Offset(0, 2))],
        ),
        child: Row(
          children: [
            Container(
              width: 44, height: 44,
              decoration: const BoxDecoration(color: Color(0xFFF0F9F0), shape: BoxShape.circle),
              alignment: Alignment.center,
              child: Text(widget.memberEmoji ?? '👤', style: const TextStyle(fontSize: 22)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333)), maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      if (genderText.isNotEmpty)
                        Text(genderText, style: const TextStyle(fontSize: 12, color: Color(0xFF666666)))
                      else
                        const Text('性别待完善', style: TextStyle(fontSize: 12, color: Color(0xFFFAAD14))),
                      const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Text('·', style: TextStyle(color: Color(0xFFCCCCCC)))),
                      if (age.isNotEmpty)
                        Text(age, style: const TextStyle(fontSize: 12, color: Color(0xFF666666)))
                      else
                        const Text('年龄待完善', style: TextStyle(fontSize: 12, color: Color(0xFFFAAD14))),
                    ],
                  ),
                ],
              ),
            ),
            const Text('编辑 ▼', style: TextStyle(fontSize: 12, color: _kPrimaryGreen)),
          ],
        ),
      ),
    );
  }

  Widget _buildExpandedHeader() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text('${widget.memberName}档案', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
          GestureDetector(
            onTap: collapse,
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Text('收起 ▲', style: TextStyle(fontSize: 12, color: _kPrimaryGreen)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBasicInfoCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.person, color: _kPrimaryGreen, size: 20),
              SizedBox(width: 8),
              Text('基本信息',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          _buildFormLabel('姓名', true),
          const SizedBox(height: 8),
          TextField(
            controller: _nicknameController,
            onChanged: (v) => _notify('nickname', v),
            decoration: _inputDecoration(
              hint: '请输入姓名',
              hasError: widget.errors.containsKey('nickname'),
            ),
          ),
          if (widget.errors.containsKey('nickname') && widget.errors['nickname'] != null)
            _buildErrorText(widget.errors['nickname']!),
          const SizedBox(height: 16),
          _buildFormLabel('出生日期', true),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: _pickBirthday,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: widget.errors.containsKey('birthday')
                      ? const Color(0xFFFF4D4F)
                      : Colors.transparent,
                ),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      (widget.birthday ?? '').isNotEmpty
                          ? widget.birthday!
                          : '请选择出生日期',
                      style: TextStyle(
                        fontSize: 14,
                        color: (widget.birthday ?? '').isNotEmpty
                            ? Colors.black87
                            : Colors.grey[400],
                      ),
                    ),
                  ),
                  Icon(Icons.calendar_today, size: 18, color: Colors.grey[400]),
                ],
              ),
            ),
          ),
          if (widget.errors.containsKey('birthday') && widget.errors['birthday'] != null)
            _buildErrorText(widget.errors['birthday']!),
          const SizedBox(height: 16),
          _buildFormLabel('性别', true),
          const SizedBox(height: 8),
          Row(
            children: ['male', 'female'].map((g) {
              final isSelected = widget.gender == g;
              return Expanded(
                child: GestureDetector(
                  onTap: () => _notify('gender', g),
                  child: Container(
                    margin: EdgeInsets.only(
                      right: g == 'male' ? 6 : 0,
                      left: g == 'female' ? 6 : 0,
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? const Color(0xFFF0F9EB)
                          : const Color(0xFFF5F5F5),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected
                            ? _kPrimaryGreen
                            : widget.errors.containsKey('gender')
                                ? const Color(0xFFFF4D4F)
                                : Colors.transparent,
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                    alignment: Alignment.center,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          g == 'male' ? Icons.male : Icons.female,
                          size: 18,
                          color: isSelected
                              ? _kPrimaryGreen
                              : Colors.grey[600],
                        ),
                        const SizedBox(width: 4),
                        Text(
                          g == 'male' ? '男' : '女',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: isSelected
                                ? FontWeight.w600
                                : FontWeight.normal,
                            color: isSelected
                                ? _kPrimaryGreen
                                : Colors.grey[800],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          if (widget.errors.containsKey('gender') && widget.errors['gender'] != null)
            _buildErrorText(widget.errors['gender']!),
        ],
      ),
    );
  }

  // 旧的折叠区已整合进 _buildExpandedHeader + 主 build 逻辑
  @Deprecated('replaced by collapsed card in existing mode')
  Widget _buildExpandToggle() {
    final complete = isProfileComplete;
    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(children: [
          Expanded(child: Divider(color: Colors.grey[300], height: 1)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(_expanded ? '收起信息' : '更多信息', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
              Text(complete ? '（已完善）' : '（待完善）', style: TextStyle(fontSize: 12, color: complete ? _kCompleteColor : _kIncompleteColor)),
              Icon(_expanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down, size: 16, color: Colors.grey[600]),
            ]),
          ),
          Expanded(child: Divider(color: Colors.grey[300], height: 1)),
        ]),
      ),
    );
  }

  Widget _buildExpandedSection() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildFormLabel('身高 (cm)', false),
              const SizedBox(height: 8),
              TextField(
                controller: _heightController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                onChanged: (v) => _notify('height', v),
                decoration: _inputDecoration(hint: '请输入身高'),
              ),
              const SizedBox(height: 16),
              _buildFormLabel('体重 (kg)', false),
              const SizedBox(height: 8),
              TextField(
                controller: _weightController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                onChanged: (v) => _notify('weight', v),
                decoration: _inputDecoration(hint: '请输入体重'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        DiseaseTagSelector(
          title: '既往病史',
          presets: widget.chronicPresets.cast<String>(),
          selectedItems: widget.chronicDiseases ?? [],
          onChanged: (items) => _notify('chronic_diseases', items),
          color: const Color(0xFFFA8C16),
        ),
        DiseaseTagSelector(
          title: '过敏史',
          presets: widget.allergyPresets.cast<String>(),
          selectedItems: widget.allergies ?? [],
          onChanged: (items) => _notify('allergies', items),
          color: const Color(0xFFEB2F96),
        ),
        DiseaseTagSelector(
          title: '家族遗传病史',
          presets: widget.geneticPresets.cast<String>(),
          selectedItems: widget.geneticDiseases ?? [],
          onChanged: (items) => _notify('genetic_diseases', items),
          color: const Color(0xFF1890FF),
        ),
      ],
    );
  }

  InputDecoration _inputDecoration({
    required String hint,
    bool hasError = false,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: Colors.grey[400], fontSize: 14),
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      filled: true,
      fillColor: const Color(0xFFF5F5F5),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: hasError
            ? const BorderSide(color: Color(0xFFFF4D4F))
            : BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _kPrimaryGreen),
      ),
    );
  }

  Widget _buildFormLabel(String text, bool required) {
    return RichText(
      text: TextSpan(
        text: text,
        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
        children: required
            ? const [
                TextSpan(
                    text: ' *',
                    style: TextStyle(color: Color(0xFFFF4D4F)))
              ]
            : null,
      ),
    );
  }

  Widget _buildErrorText(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child:
          Text(text, style: const TextStyle(fontSize: 12, color: Color(0xFFFF4D4F))),
    );
  }
}
