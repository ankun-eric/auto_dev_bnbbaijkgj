class PointsRecord {
  final String id;
  final String type;
  final int points;
  final String description;
  final String? createdAt;

  PointsRecord({
    required this.id,
    required this.type,
    required this.points,
    required this.description,
    this.createdAt,
  });

  bool get isIncome => points > 0;

  factory PointsRecord.fromJson(Map<String, dynamic> json) {
    return PointsRecord(
      id: json['id']?.toString() ?? '',
      type: json['type'] ?? '',
      points: json['points'] ?? 0,
      description: json['description'] ?? '',
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'points': points,
      'description': description,
      'created_at': createdAt,
    };
  }
}

class PointsMallItem {
  final String id;
  final String name;
  final String? image;
  final int pointsCost;
  final int stock;
  final String? description;

  PointsMallItem({
    required this.id,
    required this.name,
    this.image,
    required this.pointsCost,
    this.stock = 0,
    this.description,
  });

  factory PointsMallItem.fromJson(Map<String, dynamic> json) {
    return PointsMallItem(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      image: json['image'],
      pointsCost: json['points_cost'] ?? 0,
      stock: json['stock'] ?? 0,
      description: json['description'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'image': image,
      'points_cost': pointsCost,
      'stock': stock,
      'description': description,
    };
  }
}
