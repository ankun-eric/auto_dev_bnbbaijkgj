/// [2026-05-05 用户地址改造 PRD v1.0] v2 地址模型。
class UserAddress {
  final int id;
  final int userId;
  // 新字段（v2）
  final String consigneeName;
  final String consigneePhone;
  final String province;
  final String? provinceCode;
  final String city;
  final String? cityCode;
  final String district;
  final String? districtCode;
  final String detail;
  final double? longitude;
  final double? latitude;
  final String? tag;
  final bool isDefault;
  final bool needsRegionCompletion;
  final String? createdAt;
  final String? updatedAt;

  UserAddress({
    required this.id,
    required this.userId,
    required this.consigneeName,
    required this.consigneePhone,
    required this.province,
    this.provinceCode,
    required this.city,
    this.cityCode,
    required this.district,
    this.districtCode,
    required this.detail,
    this.longitude,
    this.latitude,
    this.tag,
    this.isDefault = false,
    this.needsRegionCompletion = false,
    this.createdAt,
    this.updatedAt,
  });

  // v1 兼容字段
  String get name => consigneeName;
  String get phone => consigneePhone;
  String get street => detail;

  String get fullAddress => '$province$city$district$detail';

  factory UserAddress.fromJson(Map<String, dynamic> json) {
    final consigneeName = (json['consignee_name'] ?? json['name'] ?? '').toString();
    final consigneePhone = (json['consignee_phone'] ?? json['phone'] ?? '').toString();
    final detail = (json['detail'] ?? json['street'] ?? '').toString();
    final lng = json['longitude'];
    final lat = json['latitude'];
    return UserAddress(
      id: json['id'] ?? 0,
      userId: json['user_id'] ?? 0,
      consigneeName: consigneeName,
      consigneePhone: consigneePhone,
      province: json['province']?.toString() ?? '',
      provinceCode: json['province_code']?.toString(),
      city: json['city']?.toString() ?? '',
      cityCode: json['city_code']?.toString(),
      district: json['district']?.toString() ?? '',
      districtCode: json['district_code']?.toString(),
      detail: detail,
      longitude: lng == null ? null : double.tryParse(lng.toString()),
      latitude: lat == null ? null : double.tryParse(lat.toString()),
      tag: json['tag']?.toString(),
      isDefault: json['is_default'] ?? false,
      needsRegionCompletion: json['needs_region_completion'] ?? false,
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'consignee_name': consigneeName,
      'consignee_phone': consigneePhone,
      'province': province,
      if (provinceCode != null) 'province_code': provinceCode,
      'city': city,
      if (cityCode != null) 'city_code': cityCode,
      'district': district,
      if (districtCode != null) 'district_code': districtCode,
      'detail': detail,
      if (longitude != null) 'longitude': longitude,
      if (latitude != null) 'latitude': latitude,
      if (tag != null) 'tag': tag,
      'is_default': isDefault,
    };
  }
}
