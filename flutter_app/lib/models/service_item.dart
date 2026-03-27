class ServiceItem {
  final String id;
  final String name;
  final String? description;
  final String? coverImage;
  final List<String> images;
  final double price;
  final double? originalPrice;
  final String? categoryId;
  final String? categoryName;
  final int salesCount;
  final double rating;
  final String? duration;
  final String? location;
  final bool isAvailable;
  final List<String> tags;
  final String? detail;

  ServiceItem({
    required this.id,
    required this.name,
    this.description,
    this.coverImage,
    this.images = const [],
    required this.price,
    this.originalPrice,
    this.categoryId,
    this.categoryName,
    this.salesCount = 0,
    this.rating = 5.0,
    this.duration,
    this.location,
    this.isAvailable = true,
    this.tags = const [],
    this.detail,
  });

  factory ServiceItem.fromJson(Map<String, dynamic> json) {
    return ServiceItem(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      description: json['description'],
      coverImage: json['cover_image'],
      images: List<String>.from(json['images'] ?? []),
      price: (json['price'] ?? 0).toDouble(),
      originalPrice: json['original_price']?.toDouble(),
      categoryId: json['category_id']?.toString(),
      categoryName: json['category_name'],
      salesCount: json['sales_count'] ?? 0,
      rating: (json['rating'] ?? 5.0).toDouble(),
      duration: json['duration'],
      location: json['location'],
      isAvailable: json['is_available'] ?? true,
      tags: List<String>.from(json['tags'] ?? []),
      detail: json['detail'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'cover_image': coverImage,
      'images': images,
      'price': price,
      'original_price': originalPrice,
      'category_id': categoryId,
      'category_name': categoryName,
      'sales_count': salesCount,
      'rating': rating,
      'duration': duration,
      'location': location,
      'is_available': isAvailable,
      'tags': tags,
      'detail': detail,
    };
  }
}
