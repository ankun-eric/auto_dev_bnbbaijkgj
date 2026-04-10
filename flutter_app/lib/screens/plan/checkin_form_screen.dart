import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class CheckinFormScreen extends StatefulWidget {
  const CheckinFormScreen({super.key});

  @override
  State<CheckinFormScreen> createState() => _CheckinFormScreenState();
}

class _CheckinFormScreenState extends State<CheckinFormScreen> {
  final ApiService _apiService = ApiService();
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _targetValueController = TextEditingController();
  final _targetUnitController = TextEditingController();

  String _repeatFrequency = 'daily';
  bool _submitting = false;

  Map<String, dynamic>? _editData;
  bool get _isEdit => _editData != null;

  static const _frequencyOptions = [
    {'value': 'daily', 'label': '每天'},
    {'value': 'weekly', 'label': '每周'},
    {'value': 'custom', 'label': '自定义'},
  ];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_editData == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map<String, dynamic>) {
        _editData = args;
        _nameController.text = args['name']?.toString() ?? '';
        _targetValueController.text = args['target_value']?.toString() ?? '';
        _targetUnitController.text = args['target_unit']?.toString() ?? '';
        _repeatFrequency = args['repeat_frequency']?.toString() ?? 'daily';
      }
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _targetValueController.dispose();
    _targetUnitController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    final data = <String, dynamic>{
      'name': _nameController.text.trim(),
      'repeat_frequency': _repeatFrequency,
    };
    final tv = _targetValueController.text.trim();
    if (tv.isNotEmpty) {
      data['target_value'] = double.tryParse(tv) ?? tv;
      data['target_unit'] = _targetUnitController.text.trim();
    }

    try {
      if (_isEdit) {
        await _apiService.updateCheckinItem(_editData!['id'] as int, data);
      } else {
        await _apiService.createCheckinItem(data);
      }
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_isEdit ? '更新失败' : '创建失败'), backgroundColor: Colors.red),
        );
      }
    }
    if (mounted) setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_isEdit ? '编辑打卡项' : '添加打卡项'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildLabel('打卡名称'),
              TextFormField(
                controller: _nameController,
                decoration: _inputDecoration('如：喝水、运动、早睡'),
                validator: (v) => (v == null || v.trim().isEmpty) ? '请输入打卡名称' : null,
              ),
              const SizedBox(height: 20),
              _buildLabel('目标值（选填）'),
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextFormField(
                      controller: _targetValueController,
                      keyboardType: TextInputType.number,
                      decoration: _inputDecoration('如：8'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 1,
                    child: TextFormField(
                      controller: _targetUnitController,
                      decoration: _inputDecoration('单位'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _buildLabel('重复频率'),
              Wrap(
                spacing: 10,
                children: _frequencyOptions.map((opt) {
                  final selected = _repeatFrequency == opt['value'];
                  return ChoiceChip(
                    label: Text(opt['label']!),
                    selected: selected,
                    selectedColor: const Color(0xFF52C41A).withOpacity(0.15),
                    labelStyle: TextStyle(
                      color: selected ? const Color(0xFF52C41A) : Colors.grey[600],
                      fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                    ),
                    onSelected: (_) => setState(() => _repeatFrequency = opt['value']!),
                  );
                }).toList(),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton(
                  onPressed: _submitting ? null : _submit,
                  child: _submitting
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(_isEdit ? '保存修改' : '添加打卡'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLabel(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
    );
  }

  InputDecoration _inputDecoration(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: Colors.grey[400]),
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey[300]!)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey[300]!)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF52C41A))),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    );
  }
}
