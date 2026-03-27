class NotificationModel {
  final String id;
  final String title;
  final String content;
  final String type;
  final bool isRead;
  final String? linkType;
  final String? linkId;
  final String? createdAt;

  NotificationModel({
    required this.id,
    required this.title,
    required this.content,
    required this.type,
    this.isRead = false,
    this.linkType,
    this.linkId,
    this.createdAt,
  });

  String get typeLabel {
    switch (type) {
      case 'system':
        return '系统通知';
      case 'order':
        return '订单通知';
      case 'health':
        return '健康提醒';
      case 'activity':
        return '活动通知';
      default:
        return '通知';
    }
  }

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id']?.toString() ?? '',
      title: json['title'] ?? '',
      content: json['content'] ?? '',
      type: json['type'] ?? 'system',
      isRead: json['is_read'] ?? false,
      linkType: json['link_type'],
      linkId: json['link_id']?.toString(),
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'content': content,
      'type': type,
      'is_read': isRead,
      'link_type': linkType,
      'link_id': linkId,
      'created_at': createdAt,
    };
  }
}
