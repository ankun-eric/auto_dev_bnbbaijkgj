import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';

import '../../models/address.dart';
import '../../services/api_service.dart';
import '../../widgets/region_picker_sheet.dart';

/// [2026-05-05 用户地址改造 PRD v1.0] 收货地址编辑/新增页（v2）。
///
/// 功能：省市县三级滚轮、详细地址 ≤80、收货人/手机号校验、
///       标签家/公司/自定义、默认地址、使用当前位置（占位 - geolocator 未集成时退化）。
class AddressEditScreen extends StatefulWidget {
  const AddressEditScreen({super.key});

  @override
  State<AddressEditScreen> createState() => _AddressEditScreenState();
}

const _kPrimary = Color(0xFF52C41A);
const _kPresetTags = ['家', '公司'];
const _kDetailMax = 80;

class _AddressEditScreenState extends State<AddressEditScreen> {
  final ApiService _api = ApiService();
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _detailController = TextEditingController();
  final _customTagController = TextEditingController();

  String _provinceCode = '';
  String _cityCode = '';
  String _districtCode = '';
  String _provinceName = '';
  String _cityName = '';
  String _districtName = '';
  double? _longitude;
  double? _latitude;

  String _tag = '';
  bool _customTagMode = false;
  bool _isDefault = false;
  bool _submitting = false;
  bool _locating = false;
  UserAddress? _existing;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is UserAddress && _existing == null) {
      _existing = args;
      _nameController.text = args.consigneeName;
      _phoneController.text = args.consigneePhone;
      _detailController.text = args.detail;
      _provinceName = args.province;
      _cityName = args.city;
      _districtName = args.district;
      _provinceCode = args.provinceCode ?? '';
      _cityCode = args.cityCode ?? '';
      _districtCode = args.districtCode ?? '';
      _longitude = args.longitude;
      _latitude = args.latitude;
      _isDefault = args.isDefault;
      if (args.tag != null && args.tag!.isNotEmpty) {
        if (_kPresetTags.contains(args.tag)) {
          _tag = args.tag!;
        } else {
          _customTagMode = true;
          _customTagController.text = args.tag!;
        }
      }
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _detailController.dispose();
    _customTagController.dispose();
    super.dispose();
  }

  Future<void> _pickRegion() async {
    FocusScope.of(context).unfocus();
    final r = await showRegionPickerSheet(
      context,
      initialProvinceCode: _provinceCode.isEmpty ? null : _provinceCode,
      initialCityCode: _cityCode.isEmpty ? null : _cityCode,
      initialDistrictCode: _districtCode.isEmpty ? null : _districtCode,
    );
    if (r == null) return;
    setState(() {
      _provinceName = r.province.name;
      _cityName = r.city.name;
      _districtName = r.district?.name ?? '';
      _provinceCode = r.province.code;
      _cityCode = r.city.code;
      _districtCode = r.district?.code ?? '';
    });
  }

  Future<void> _useCurrentLocation() async {
    setState(() => _locating = true);
    try {
      // 1. 检查权限
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        _toast('定位失败，请检查网络或定位权限，或手动选择地址');
        return;
      }

      // 2. 获取定位
      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );
      _longitude = pos.longitude;
      _latitude = pos.latitude;

      // 3. 调后端 reverse-geocode
      try {
        final res = await _api.reverseGeocode(pos.longitude, pos.latitude);
        final data = res.data is Map ? res.data as Map : {};
        final province = (data['province'] ?? '').toString();
        final city = (data['city'] ?? '').toString();
        final district = (data['district'] ?? '').toString();
        final detail = (data['detail'] ?? '').toString();
        if (province.isNotEmpty) {
          setState(() {
            _provinceName = province;
            _cityName = city.isEmpty ? province : city;
            _districtName = district;
            if (detail.isNotEmpty && _detailController.text.isEmpty) {
              _detailController.text = detail;
            }
          });
          _toast('已根据当前位置回填地区，请确认');
        } else {
          _toast('已记录经纬度，请手动选择省市县');
        }
      } catch (_) {
        _toast('已记录经纬度，请手动选择省市县');
      }
    } catch (e) {
      _toast('定位失败，请检查网络或定位权限，或手动选择地址');
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  String _resolveTag() {
    if (_customTagMode) {
      final v = _customTagController.text.trim();
      return v;
    }
    return _tag;
  }

  bool _validatePhone(String p) => RegExp(r'^1[3-9]\d{9}$').hasMatch(p);

  Future<void> _submit() async {
    final name = _nameController.text.trim();
    final phone = _phoneController.text.trim();
    final detail = _detailController.text.trim();

    if (name.length < 2 || name.length > 20) {
      _toast('收货人姓名为 2-20 个字符'); return;
    }
    if (!_validatePhone(phone)) {
      _toast('请输入正确的 11 位手机号'); return;
    }
    if (_provinceName.isEmpty || _cityName.isEmpty || _districtName.isEmpty) {
      _toast('请选择所在地区'); return;
    }
    if (detail.isEmpty) { _toast('请输入详细地址'); return; }
    if (detail.length > _kDetailMax) { _toast('详细地址最多 $_kDetailMax 字'); return; }

    final tag = _resolveTag();
    if (tag.length > 6) { _toast('自定义标签最多 6 个汉字'); return; }

    setState(() => _submitting = true);
    final payload = <String, dynamic>{
      'consignee_name': name,
      'consignee_phone': phone,
      'province': _provinceName,
      if (_provinceCode.isNotEmpty) 'province_code': _provinceCode,
      'city': _cityName,
      if (_cityCode.isNotEmpty) 'city_code': _cityCode,
      'district': _districtName,
      if (_districtCode.isNotEmpty) 'district_code': _districtCode,
      'detail': detail,
      'tag': tag,
      'is_default': _isDefault,
      if (_longitude != null) 'longitude': _longitude,
      if (_latitude != null) 'latitude': _latitude,
    };
    try {
      if (_existing != null) {
        await _api.updateAddress(_existing!.id, payload);
      } else {
        await _api.createAddress(payload);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_existing != null ? '地址已更新' : '地址已添加')),
        );
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) _toast('保存失败：$e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_existing != null ? '编辑地址' : '新增地址'),
        backgroundColor: _kPrimary,
        foregroundColor: Colors.white,
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
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                OutlinedButton.icon(
                  onPressed: _locating ? null : _useCurrentLocation,
                  icon: const Icon(Icons.my_location, size: 16),
                  label: Text(_locating ? '正在定位…' : '使用当前位置'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _kPrimary,
                    side: const BorderSide(color: _kPrimary),
                  ),
                ),
                const SizedBox(height: 12),
                _label('收货人'),
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    hintText: '请输入收货人姓名（2-20 字符）',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  inputFormatters: [LengthLimitingTextInputFormatter(20)],
                ),
                const SizedBox(height: 12),
                _label('手机号'),
                TextFormField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    hintText: '请输入 11 位手机号',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  inputFormatters: [
                    FilteringTextInputFormatter.digitsOnly,
                    LengthLimitingTextInputFormatter(11),
                  ],
                ),
                const SizedBox(height: 12),
                _label('所在地区'),
                InkWell(
                  onTap: _pickRegion,
                  borderRadius: BorderRadius.circular(4),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                    decoration: BoxDecoration(
                      border: Border.all(color: const Color(0xFFD9D9D9)),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            _provinceName.isEmpty
                                ? '请选择 省 / 市 / 区县'
                                : '$_provinceName / $_cityName / $_districtName',
                            style: TextStyle(
                              fontSize: 14,
                              color: _provinceName.isEmpty ? const Color(0xFFBFBFBF) : const Color(0xFF333333),
                            ),
                          ),
                        ),
                        const Icon(Icons.chevron_right, size: 18, color: Color(0xFFBFBFBF)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                _label('详细地址'),
                TextFormField(
                  controller: _detailController,
                  maxLines: 3,
                  maxLength: _kDetailMax,
                  decoration: const InputDecoration(
                    hintText: '请输入街道、楼栋、门牌号等详细信息',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                ),
                _label('地址标签'),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final t in _kPresetTags)
                      _tagChip(t, _tag == t && !_customTagMode, () {
                        setState(() {
                          _tag = t;
                          _customTagMode = false;
                          _customTagController.clear();
                        });
                      }),
                    if (!_customTagMode)
                      InkWell(
                        onTap: () {
                          setState(() {
                            _customTagMode = true;
                            _tag = '';
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                          decoration: BoxDecoration(
                            border: Border.all(color: _kPrimary, style: BorderStyle.solid),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: const Text('+ 自定义', style: TextStyle(fontSize: 12, color: _kPrimary)),
                        ),
                      ),
                    if (_customTagMode)
                      SizedBox(
                        width: 120,
                        child: TextField(
                          controller: _customTagController,
                          maxLength: 6,
                          decoration: const InputDecoration(
                            hintText: '≤6 字',
                            isDense: true,
                            counterText: '',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                SwitchListTile(
                  title: const Text('设为默认地址'),
                  value: _isDefault,
                  onChanged: (v) => setState(() => _isDefault = v),
                  activeColor: _kPrimary,
                  contentPadding: EdgeInsets.zero,
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submitting ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kPrimary,
                      foregroundColor: Colors.white,
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

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 6, top: 4),
        child: Text(text, style: const TextStyle(fontSize: 13, color: Color(0xFF666666))),
      );

  Widget _tagChip(String text, bool selected, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? _kPrimary.withOpacity(0.12) : const Color(0xFFF5F5F5),
          border: Border.all(color: selected ? _kPrimary : Colors.transparent),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(text, style: TextStyle(
          fontSize: 12,
          color: selected ? _kPrimary : const Color(0xFF666666),
        )),
      ),
    );
  }
}
