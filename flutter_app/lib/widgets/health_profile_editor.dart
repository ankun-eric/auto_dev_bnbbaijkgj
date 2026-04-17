import 'package:flutter/material.dart';
import 'disease_tag_selector.dart';

const _kPrimaryGreen = Color(0xFF52C41A);
const _kCompleteColor = Color(0xFF52c41a);
const _kIncompleteColor = Color(0xFFfa8c16);

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
  });

  @override
  State<HealthProfileEditor> createState() => HealthProfileEditorState();
}

class HealthProfileEditorState extends State<HealthProfileEditor> {
  bool _expanded = false;
  late TextEditingController _nicknameController;
  late TextEditingController _heightController;
  late TextEditingController _weightController;

  @override
  void initState() {
    super.initState();
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

  void resetExpanded() {
    if (mounted) setState(() => _expanded = false);
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
    return Column(
      children: [
        _buildBasicInfoCard(),
        _buildExpandToggle(),
        AnimatedSize(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeInOut,
          alignment: Alignment.topCenter,
          child: _expanded ? _buildExpandedSection() : const SizedBox.shrink(),
        ),
      ],
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

  Widget _buildExpandToggle() {
    final complete = isProfileComplete;
    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(
          children: [
            Expanded(
                child: Divider(color: Colors.grey[300], height: 1)),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _expanded ? '收起信息' : '更多信息',
                    style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                  ),
                  Text(
                    complete ? '（已完善）' : '（待完善）',
                    style: TextStyle(
                      fontSize: 12,
                      color: complete ? _kCompleteColor : _kIncompleteColor,
                    ),
                  ),
                  Icon(
                    _expanded
                        ? Icons.keyboard_arrow_up
                        : Icons.keyboard_arrow_down,
                    size: 16,
                    color: Colors.grey[600],
                  ),
                ],
              ),
            ),
            Expanded(
                child: Divider(color: Colors.grey[300], height: 1)),
          ],
        ),
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
