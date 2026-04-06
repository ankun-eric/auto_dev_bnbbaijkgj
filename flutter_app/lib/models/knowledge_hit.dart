class KnowledgeHit {
  final int entryId;
  final String kbName;
  final String matchType;
  final double matchScore;
  final String? title;
  final String? question;
  final dynamic contentJson;
  final String displayMode;
  final List<ProductCard>? products;
  final int? hitLogId;

  KnowledgeHit({
    required this.entryId,
    required this.kbName,
    required this.matchType,
    required this.matchScore,
    this.title,
    this.question,
    this.contentJson,
    this.displayMode = 'direct',
    this.products,
    this.hitLogId,
  });

  factory KnowledgeHit.fromJson(Map<String, dynamic> json) {
    List<ProductCard>? products;
    final rawProducts = json['products'];
    if (rawProducts is List) {
      products = rawProducts
          .map((e) => ProductCard.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    }

    final scoreRaw = json['match_score'] ?? json['score'];
    double matchScore = 0;
    if (scoreRaw is num) {
      matchScore = scoreRaw.toDouble();
    }

    final hitLogRaw = json['hit_log_id'];
    int? hitLogId;
    if (hitLogRaw is num) {
      hitLogId = hitLogRaw.toInt();
    }

    return KnowledgeHit(
      entryId: (json['entry_id'] as num?)?.toInt() ?? 0,
      kbName: json['kb_name']?.toString() ?? '',
      matchType: json['match_type']?.toString() ?? '',
      matchScore: matchScore,
      title: json['title']?.toString(),
      question: json['question']?.toString(),
      contentJson: json['content_json'],
      displayMode: json['display_mode']?.toString() ?? 'direct',
      products: products,
      hitLogId: hitLogId,
    );
  }
}

class ProductCard {
  final int id;
  final String name;
  final double price;
  final String? image;
  final String type;

  ProductCard({
    required this.id,
    required this.name,
    required this.price,
    this.image,
    this.type = '',
  });

  factory ProductCard.fromJson(Map<String, dynamic> json) {
    final priceRaw = json['price'];
    double price = 0;
    if (priceRaw is num) {
      price = priceRaw.toDouble();
    } else if (priceRaw != null) {
      price = double.tryParse(priceRaw.toString()) ?? 0;
    }

    final idRaw = json['id'] ?? json['product_id'];
    int id = 0;
    if (idRaw is num) {
      id = idRaw.toInt();
    }

    return ProductCard(
      id: id,
      name: json['name']?.toString() ?? '',
      price: price,
      image: json['image']?.toString() ?? json['image_url']?.toString(),
      type: json['type']?.toString() ?? json['product_type']?.toString() ?? '',
    );
  }
}
