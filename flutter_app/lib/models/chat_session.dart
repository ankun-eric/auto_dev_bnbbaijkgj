class ChatSession {
  final String id;
  final String type;
  final String? title;
  final String? lastMessage;
  final String? lastMessageTime;
  final int messageCount;
  final String? createdAt;

  ChatSession({
    required this.id,
    required this.type,
    this.title,
    this.lastMessage,
    this.lastMessageTime,
    this.messageCount = 0,
    this.createdAt,
  });

  String get typeLabel {
    switch (type) {
      case 'general':
        return '综合问诊';
      case 'pediatric':
        return '儿科问诊';
      case 'gynecology':
        return '妇科问诊';
      case 'tcm':
        return '中医问诊';
      default:
        return 'AI问诊';
    }
  }

  factory ChatSession.fromJson(Map<String, dynamic> json) {
    return ChatSession(
      id: json['id']?.toString() ?? '',
      type: json['type'] ?? 'general',
      title: json['title'],
      lastMessage: json['last_message'],
      lastMessageTime: json['last_message_time'],
      messageCount: json['message_count'] ?? 0,
      createdAt: json['created_at'],
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
    };
  }
}
