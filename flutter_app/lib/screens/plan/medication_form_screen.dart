import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class MedicationFormScreen extends StatefulWidget {
  const MedicationFormScreen({super.key});

  @override
  State<MedicationFormScreen> createState() => _MedicationFormScreenState();
}

class _MedicationFormScreenState extends State<MedicationFormScreen> {
  final ApiService _apiService = ApiService();
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _dosageController = TextEditingController();
  final _notesController = TextEditingController();

  String _timePeriod = 'morning';
  TimeOfDay _remindTime = const TimeOfDay(hour: 8, minute: 0);
  bool _submitting = false;

  Map<String, dynamic>? _editData;
  bool get _isEdit => _editData != null;

  static const _timePeriodOptions = [
    {'value': 'morning', 'label': '早上'},
    {'value': 'noon', 'label': '中午'},
    {'value': 'afternoon', 'label': '下午'},
    {'value': 'evening', 'label': '晚上'},
    {'value': 'night', 'label': '睡前'},
  ];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_editData == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map<String, dynamic>) {
        _editData = args;
        _nameController.text = args['medicine_name']?.toString() ?? '';
        _dosageController.text = args['dosage']?.toString() ?? '';
        _notesController.text = args['notes']?.toString() ?? '';
        _timePeriod = args['time_period']?.toString() ?? 'morning';
        final remindStr = args['remind_time']?.toString() ?? '';
        if (remindStr.contains(':')) {
          final parts = remindStr.split(':');
          _remindTime = TimeOfDay(hour: int.tryParse(parts[0]) ?? 8, minute: int.tryParse(parts[1]) ?? 0);
        }
      }
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _dosageController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(context: context, initialTime: _remindTime);
    if (picked != null) setState(() => _remindTime = picked);
  }

  String _formatTime(TimeOfDay t) {
    return '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    final data = {
      'medicine_name': _nameController.text.trim(),
      'dosage': _dosageController.text.trim(),
      'time_period': _timePeriod,
      'remind_time': _formatTime(_remindTime),
      'notes': _notesController.text.trim(),
    };

    try {
      if (_isEdit) {
        await _apiService.updateMedication(_editData!['id'] as int, data);
      } else {
        await _apiService.createMedication(data);
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
        title: Text(_isEdit ? '编辑用药提醒' : '添加用药提醒'),
        backgroundColor: const Color(0xFFFA8C16),
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
              _buildLabel('药品名称'),
              TextFormField(
                controller: _nameController,
                decoration: _inputDecoration('请输入药品名称'),
                validator: (v) => (v == null || v.trim().isEmpty) ? '请输入药品名称' : null,
              ),
              const SizedBox(height: 20),
              _buildLabel('用药剂量（选填）'),
              TextFormField(
                controller: _dosageController,
                decoration: _inputDecoration('如：每次1片'),
              ),
              const SizedBox(height: 20),
              _buildLabel('服药时段'),
              Wrap(
                spacing: 10,
                children: _timePeriodOptions.map((opt) {
                  final selected = _timePeriod == opt['value'];
                  return ChoiceChip(
                    label: Text(opt['label']!),
                    selected: selected,
                    selectedColor: const Color(0xFFFA8C16).withOpacity(0.15),
                    labelStyle: TextStyle(
                      color: selected ? const Color(0xFFFA8C16) : Colors.grey[600],
                      fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                    ),
                    onSelected: (_) => setState(() => _timePeriod = opt['value']!),
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),
              _buildLabel('提醒时间'),
              GestureDetector(
                onTap: _pickTime,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey[300]!),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(_formatTime(_remindTime), style: const TextStyle(fontSize: 16)),
                      Icon(Icons.access_time, color: Colors.grey[400]),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              _buildLabel('备注（选填）'),
              TextFormField(
                controller: _notesController,
                decoration: _inputDecoration('添加备注信息'),
                maxLines: 3,
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton(
                  onPressed: _submitting ? null : _submit,
                  style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFFA8C16)),
                  child: _submitting
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(_isEdit ? '保存修改' : '添加提醒'),
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
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFFFA8C16))),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    );
  }
}
