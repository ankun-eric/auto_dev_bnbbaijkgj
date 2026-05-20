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
  // [PRD-433 F-14] 可选的参考资料列表（每项任意结构 Map），仅当非空时由 UI 渲染。
  final List<Map<String, dynamic>>? references;
  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查卡片 payload（type=='health_self_check_card' 时使用）
  final Map<String, dynamic>? healthSelfCheckPayload;
  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 问卷结果卡片 payload（type=='questionnaire_result_card' 时使用）
  final Map<String, dynamic>? questionnaireResultPayload;
  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 追问 chips 列表 + 是否已置灰 + 关联 answer_id
  final List<Map<String, dynamic>>? followupChips;
  final bool followupChipsDisabled;
  final int? questionnaireAnswerId;
  final String? questionnaireCode;

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
    this.references,
    this.healthSelfCheckPayload,
    this.questionnaireResultPayload,
    this.followupChips,
    this.followupChipsDisabled = false,
    this.questionnaireAnswerId,
    this.questionnaireCode,
  });

  /// [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 复制并替换 followupChipsDisabled
  ChatMessage copyWith({
    bool? followupChipsDisabled,
  }) {
    return ChatMessage(
      id: id,
      sessionId: sessionId,
      role: role,
      content: content,
      type: type,
      imageUrl: imageUrl,
      isLoading: isLoading,
      createdAt: createdAt,
      knowledgeHits: knowledgeHits,
      references: references,
      healthSelfCheckPayload: healthSelfCheckPayload,
      questionnaireResultPayload: questionnaireResultPayload,
      followupChips: followupChips,
      followupChipsDisabled: followupChipsDisabled ?? this.followupChipsDisabled,
      questionnaireAnswerId: questionnaireAnswerId,
      questionnaireCode: questionnaireCode,
    );
  }

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

    List<Map<String, dynamic>>? refs;
    final rawRefs = json['references'];
    if (rawRefs is List && rawRefs.isNotEmpty) {
      refs = rawRefs
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
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
      references: refs,
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

