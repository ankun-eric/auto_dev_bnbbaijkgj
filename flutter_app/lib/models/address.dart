class UserAddress {
  final int id;
  final int userId;
  final String name;
  final String phone;
  final String province;
  final String city;
  final String district;
  final String street;
  final bool isDefault;
  final String? createdAt;
  final String? updatedAt;

  UserAddress({
    required this.id,
    required this.userId,
    required this.name,
    required this.phone,
    required this.province,
    required this.city,
    required this.district,
    required this.street,
    this.isDefault = false,
    this.createdAt,
    this.updatedAt,
  });

  String get fullAddress => '$province$city$district$street';

  factory UserAddress.fromJson(Map<String, dynamic> json) {
    return UserAddress(
      id: json['id'] ?? 0,
      userId: json['user_id'] ?? 0,
      name: json['name'] ?? '',
      phone: json['phone'] ?? '',
      province: json['province'] ?? '',
      city: json['city'] ?? '',
      district: json['district'] ?? '',
      street: json['street'] ?? '',
      isDefault: json['is_default'] ?? false,
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'phone': phone,
      'province': province,
      'city': city,
      'district': district,
      'street': street,
      'is_default': isDefault,
    };
  }
}
