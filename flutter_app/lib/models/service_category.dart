class ServiceCategory {
  final String id;
  final String name;
  final String? icon;
  final int sortOrder;
  final int serviceCount;

  ServiceCategory({
    required this.id,
    required this.name,
    this.icon,
    this.sortOrder = 0,
    this.serviceCount = 0,
  });

  factory ServiceCategory.fromJson(Map<String, dynamic> json) {
    return ServiceCategory(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      icon: json['icon'],
      sortOrder: json['sort_order'] ?? 0,
      serviceCount: json['service_count'] ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'icon': icon,
      'sort_order': sortOrder,
      'service_count': serviceCount,
    };
  }
}
