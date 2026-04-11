class ChatSession {
  final String id;
  final String type;
  final String? title;
  final String? lastMessage;
  final String? lastMessageTime;
  final int messageCount;
  final String? createdAt;
  final String? updatedAt;
  final bool isPinned;
  final bool isDeleted;
  final String? shareToken;

  ChatSession({
    required this.id,
    required this.type,
    this.title,
    this.lastMessage,
    this.lastMessageTime,
    this.messageCount = 0,
    this.createdAt,
    this.updatedAt,
    this.isPinned = false,
    this.isDeleted = false,
    this.shareToken,
  });

  String get typeLabel {
    switch (type) {
      case 'health_qa':
      case 'general':
        return '健康问答';
      case 'symptom_check':
      case 'symptom':
      case 'pediatric':
        return '健康自查';
      case 'tcm':
      case 'gynecology':
        return '中医养生';
      case 'drug_query':
        return '用药参考';
      default:
        return 'AI健康咨询';
    }
  }

  ChatSession copyWith({
    String? id,
    String? type,
    String? title,
    String? lastMessage,
    String? lastMessageTime,
    int? messageCount,
    String? createdAt,
    String? updatedAt,
    bool? isPinned,
    bool? isDeleted,
    String? shareToken,
  }) {
    return ChatSession(
      id: id ?? this.id,
      type: type ?? this.type,
      title: title ?? this.title,
      lastMessage: lastMessage ?? this.lastMessage,
      lastMessageTime: lastMessageTime ?? this.lastMessageTime,
      messageCount: messageCount ?? this.messageCount,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isPinned: isPinned ?? this.isPinned,
      isDeleted: isDeleted ?? this.isDeleted,
      shareToken: shareToken ?? this.shareToken,
    );
  }

  factory ChatSession.fromJson(Map<String, dynamic> json) {
    return ChatSession(
      id: json['id']?.toString() ?? '',
      type: json['session_type'] ?? json['type'] ?? 'general',
      title: json['title'],
      lastMessage: json['last_message'],
      lastMessageTime: json['last_message_time'],
      messageCount: json['message_count'] ?? 0,
      createdAt: json['created_at'],
      updatedAt: json['updated_at'],
      isPinned: json['is_pinned'] == true,
      isDeleted: json['is_deleted'] == true,
      shareToken: json['share_token'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'title': title,
      'last_message': lastMessage,
      'last_message_time': lastMessageTime,
      'message_count': messageCount,
      'created_at': createdAt,
      'updated_at': updatedAt,
      'is_pinned': isPinned,
      'is_deleted': isDeleted,
      'share_token': shareToken,
    };
  }
}
