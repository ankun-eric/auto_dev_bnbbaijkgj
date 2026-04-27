class ProductCategory {
  final int id;
  final String name;
  final int? parentId;
  final String? icon;
  final String? description;
  final int sortOrder;
  final String status;
  final int level;
  final String? createdAt;
  final List<ProductCategory> children;

  ProductCategory({
    required this.id,
    required this.name,
    this.parentId,
    this.icon,
    this.description,
    this.sortOrder = 0,
    this.status = 'active',
    this.level = 1,
    this.createdAt,
    this.children = const [],
  });

  factory ProductCategory.fromJson(Map<String, dynamic> json) {
    return ProductCategory(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      parentId: json['parent_id'],
      icon: json['icon'],
      description: json['description'],
      sortOrder: json['sort_order'] ?? 0,
      status: json['status'] ?? 'active',
      level: json['level'] ?? 1,
      createdAt: json['created_at']?.toString(),
      children: (json['children'] as List<dynamic>?)
              ?.map((e) => ProductCategory.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class Product {
  final int id;
  final String name;
  final int categoryId;
  final String fulfillmentType;
  final double? originalPrice;
  final double salePrice;
  final List<String> images;
  final String? videoUrl;
  final String? description;
  final List<String> symptomTags;
  final int stock;
  final String? validStartDate;
  final String? validEndDate;
  final bool pointsExchangeable;
  final int pointsPrice;
  final bool pointsDeductible;
  final int redeemCount;
  final String appointmentMode;
  final String? purchaseAppointmentMode;
  final int? customFormId;
  final dynamic faq;
  final int recommendWeight;
  final int salesCount;
  final String status;
  final int sortOrder;
  final int paymentTimeoutMinutes;
  final String? createdAt;
  final String? updatedAt;

  // Detail-only fields
  final List<ProductStore> stores;
  final int reviewCount;
  final double? avgRating;
  final String? categoryName;

  Product({
    required this.id,
    required this.name,
    required this.categoryId,
    required this.fulfillmentType,
    this.originalPrice,
    required this.salePrice,
    this.images = const [],
    this.videoUrl,
    this.description,
    this.symptomTags = const [],
    this.stock = 0,
    this.validStartDate,
    this.validEndDate,
    this.pointsExchangeable = false,
    this.pointsPrice = 0,
    this.pointsDeductible = false,
    this.redeemCount = 1,
    this.appointmentMode = 'none',
    this.purchaseAppointmentMode,
    this.customFormId,
    this.faq,
    this.recommendWeight = 0,
    this.salesCount = 0,
    this.status = 'active',
    this.sortOrder = 0,
    this.paymentTimeoutMinutes = 15,
    this.createdAt,
    this.updatedAt,
    this.stores = const [],
    this.reviewCount = 0,
    this.avgRating,
    this.categoryName,
  });

  String get firstImage {
    if (images.isNotEmpty) return images.first;
    return '';
  }

  String get fulfillmentLabel {
    switch (fulfillmentType) {
      case 'delivery':
        return '快递配送';
      case 'in_store':
        return '到店消费';
      case 'virtual':
        return '虚拟商品';
      default:
        return fulfillmentType;
    }
  }

  factory Product.fromJson(Map<String, dynamic> json) {
    List<String> parseImages(dynamic val) {
      if (val == null) return [];
      if (val is List) return val.map((e) => e.toString()).toList();
      if (val is String) return [val];
      return [];
    }

    List<String> parseTags(dynamic val) {
      if (val == null) return [];
      if (val is List) return val.map((e) => e.toString()).toList();
      return [];
    }

    return Product(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      categoryId: json['category_id'] ?? 0,
      fulfillmentType: json['fulfillment_type'] ?? 'in_store',
      originalPrice: json['original_price'] != null ? (json['original_price'] as num).toDouble() : null,
      salePrice: (json['sale_price'] ?? 0).toDouble(),
      images: parseImages(json['images']),
      videoUrl: json['video_url'],
      description: json['description'],
      symptomTags: parseTags(json['symptom_tags']),
      stock: json['stock'] ?? 0,
      validStartDate: json['valid_start_date']?.toString(),
      validEndDate: json['valid_end_date']?.toString(),
      pointsExchangeable: json['points_exchangeable'] ?? false,
      pointsPrice: json['points_price'] ?? 0,
      pointsDeductible: json['points_deductible'] ?? false,
      redeemCount: json['redeem_count'] ?? 1,
      appointmentMode: json['appointment_mode'] ?? 'none',
      purchaseAppointmentMode: json['purchase_appointment_mode'],
      customFormId: json['custom_form_id'],
      faq: json['faq'],
      recommendWeight: json['recommend_weight'] ?? 0,
      salesCount: json['sales_count'] ?? 0,
      status: json['status'] ?? 'active',
      sortOrder: json['sort_order'] ?? 0,
      paymentTimeoutMinutes: json['payment_timeout_minutes'] ?? 15,
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
      stores: (json['stores'] as List<dynamic>?)
              ?.map((e) => ProductStore.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      reviewCount: json['review_count'] ?? 0,
      avgRating: json['avg_rating'] != null ? (json['avg_rating'] as num).toDouble() : null,
      categoryName: json['category_name'],
    );
  }
}

class ProductStore {
  final int id;
  final int storeId;
  final String? storeName;

  ProductStore({required this.id, required this.storeId, this.storeName});

  factory ProductStore.fromJson(Map<String, dynamic> json) {
    return ProductStore(
      id: json['id'] ?? 0,
      storeId: json['store_id'] ?? 0,
      storeName: json['store_name'],
    );
  }
}
