import 'package:flutter/material.dart';
import '../../models/address.dart';
import '../../services/api_service.dart';

class AddressEditScreen extends StatefulWidget {
  const AddressEditScreen({super.key});

  @override
  State<AddressEditScreen> createState() => _AddressEditScreenState();
}

class _AddressEditScreenState extends State<AddressEditScreen> {
  final ApiService _api = ApiService();
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _provinceController = TextEditingController();
  final _cityController = TextEditingController();
  final _districtController = TextEditingController();
  final _streetController = TextEditingController();
  bool _isDefault = false;
  bool _submitting = false;
  UserAddress? _existing;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is UserAddress && _existing == null) {
      _existing = args;
      _nameController.text = args.name;
      _phoneController.text = args.phone;
      _provinceController.text = args.province;
      _cityController.text = args.city;
      _districtController.text = args.district;
      _streetController.text = args.street;
      _isDefault = args.isDefault;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _provinceController.dispose();
    _cityController.dispose();
    _districtController.dispose();
    _streetController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    final data = {
      'name': _nameController.text.trim(),
      'phone': _phoneController.text.trim(),
      'province': _provinceController.text.trim(),
      'city': _cityController.text.trim(),
      'district': _districtController.text.trim(),
      'street': _streetController.text.trim(),
      'is_default': _isDefault,
    };

    try {
      if (_existing != null) {
        await _api.updateAddress(_existing!.id, data);
      } else {
        await _api.createAddress(data);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_existing != null ? '地址已更新' : '地址已添加')),
        );
        Navigator.pop(context, true);
      }
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('保存失败')));
    }
    setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_existing != null ? '编辑地址' : '新增地址'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                _buildField('收货人', _nameController, '请输入收货人姓名'),
                _buildField('手机号码', _phoneController, '请输入手机号码', keyboardType: TextInputType.phone),
                _buildField('省份', _provinceController, '请输入省份'),
                _buildField('城市', _cityController, '请输入城市'),
                _buildField('区/县', _districtController, '请输入区/县'),
                _buildField('详细地址', _streetController, '请输入详细地址', maxLines: 2),
                const SizedBox(height: 8),
                SwitchListTile(
                  title: const Text('设为默认地址'),
                  value: _isDefault,
                  onChanged: (v) => setState(() => _isDefault = v),
                  activeColor: const Color(0xFF52C41A),
                  contentPadding: EdgeInsets.zero,
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submitting ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF52C41A),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    child: _submitting
                        ? const SizedBox(width: 20, height: 20,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                        : Text(_existing != null ? '保存修改' : '添加地址', style: const TextStyle(fontSize: 16)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildField(String label, TextEditingController controller, String hint,
      {TextInputType? keyboardType, int maxLines = 1}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        keyboardType: keyboardType,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        ),
        validator: (v) => v == null || v.trim().isEmpty ? hint : null,
      ),
    );
  }
}
