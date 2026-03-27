class Article {
  final String id;
  final String title;
  final String? summary;
  final String? content;
  final String? coverImage;
  final String? author;
  final String? category;
  final int viewCount;
  final int likeCount;
  final int commentCount;
  final bool isCollected;
  final List<String> tags;
  final String? createdAt;

  Article({
    required this.id,
    required this.title,
    this.summary,
    this.content,
    this.coverImage,
    this.author,
    this.category,
    this.viewCount = 0,
    this.likeCount = 0,
    this.commentCount = 0,
    this.isCollected = false,
    this.tags = const [],
    this.createdAt,
  });

  factory Article.fromJson(Map<String, dynamic> json) {
    return Article(
      id: json['id']?.toString() ?? '',
      title: json['title'] ?? '',
      summary: json['summary'],
      content: json['content'],
      coverImage: json['cover_image'],
      author: json['author'],
      category: json['category'],
      viewCount: json['view_count'] ?? 0,
      likeCount: json['like_count'] ?? 0,
      commentCount: json['comment_count'] ?? 0,
      isCollected: json['is_collected'] ?? false,
      tags: List<String>.from(json['tags'] ?? []),
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'summary': summary,
      'content': content,
      'cover_image': coverImage,
      'author': author,
      'category': category,
      'view_count': viewCount,
      'like_count': likeCount,
      'comment_count': commentCount,
      'is_collected': isCollected,
      'tags': tags,
      'created_at': createdAt,
    };
  }
}
