import 'knowledge_hit.dart';

class ChatMessage {
  final String id;
  final String sessionId;
  final String role;
  final String content;
  final String type;
  final String? imageUrl;
  final bool isLoading;
  final String? createdAt;
  final List<KnowledgeHit>? knowledgeHits;

  ChatMessage({
    required this.id,
    required this.sessionId,
    required this.role,
    required this.content,
    this.type = 'text',
    this.imageUrl,
    this.isLoading = false,
    this.createdAt,
    this.knowledgeHits,
  });

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    List<KnowledgeHit>? hits;
    final rawHits = json['knowledge_hits'];
    if (rawHits is List) {
      hits = rawHits
          .map((e) => KnowledgeHit.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    }

    return ChatMessage(
      id: json['id']?.toString() ?? '',
      sessionId: json['session_id']?.toString() ?? '',
      role: json['role'] ?? 'user',
      content: json['content'] ?? '',
      type: json['message_type']?.toString() ?? json['type']?.toString() ?? 'text',
      imageUrl: json['image_url'] as String?,
      createdAt: json['created_at']?.toString(),
      knowledgeHits: hits,
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

