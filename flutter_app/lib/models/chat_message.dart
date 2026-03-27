class ChatMessage {
  final String id;
  final String sessionId;
  final String role;
  final String content;
  final String type;
  final String? imageUrl;
  final bool isLoading;
  final String? createdAt;

  ChatMessage({
    required this.id,
    required this.sessionId,
    required this.role,
    required this.content,
    this.type = 'text',
    this.imageUrl,
    this.isLoading = false,
    this.createdAt,
  });

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id']?.toString() ?? '',
      sessionId: json['session_id']?.toString() ?? '',
      role: json['role'] ?? 'user',
      content: json['content'] ?? '',
      type: json['type'] ?? 'text',
      imageUrl: json['image_url'],
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'session_id': sessionId,
      'role': role,
      'content': content,
      'type': type,
      'image_url': imageUrl,
      'created_at': createdAt,
    };
  }

  factory ChatMessage.loading(String sessionId) {
    return ChatMessage(
      id: 'loading',
      sessionId: sessionId,
      role: 'assistant',
      content: '',
      isLoading: true,
    );
  }
}
