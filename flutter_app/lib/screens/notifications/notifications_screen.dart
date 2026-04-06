import 'package:flutter/material.dart';
import '../../models/notification_model.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/empty_widget.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final List<NotificationModel> _notifications = [
    NotificationModel(
      id: '1',
      title: '健康提醒',
      content: '距离您上次体检已过6个月，建议进行定期体检。',
      type: 'health',
      isRead: false,
      createdAt: '2024-03-27 08:00',
    ),
    NotificationModel(
      id: '2',
      title: '订单通知',
      content: '您的全面体检套餐订单已确认，请按时到店。',
      type: 'order',
      isRead: false,
      createdAt: '2024-03-26 15:30',
    ),
    NotificationModel(
      id: '3',
      title: '系统通知',
      content: '您的积分账户新增20积分，来自完成健康咨询奖励。',
      type: 'system',
      isRead: true,
      createdAt: '2024-03-25 10:00',
    ),
    NotificationModel(
      id: '4',
      title: '活动通知',
      content: '春季健康周活动开启，参与即可获得双倍积分！',
      type: 'activity',
      isRead: true,
      createdAt: '2024-03-24 09:00',
    ),
  ];

  IconData _getTypeIcon(String type) {
    switch (type) {
      case 'health':
        return Icons.favorite;
      case 'order':
        return Icons.receipt_long;
      case 'activity':
        return Icons.celebration;
      default:
        return Icons.notifications;
    }
  }

  Color _getTypeColor(String type) {
    switch (type) {
      case 'health':
        return const Color(0xFF52C41A);
      case 'order':
        return const Color(0xFF1890FF);
      case 'activity':
        return const Color(0xFFFA8C16);
      default:
        return const Color(0xFF999999);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: '消息通知',
        actions: [
          TextButton(
            onPressed: () {
              setState(() {
                for (var n in _notifications) {
                  // Mark all as read conceptually
                }
              });
            },
            child: const Text('全部已读', style: TextStyle(color: Colors.white, fontSize: 14)),
          ),
        ],
      ),
      body: _notifications.isEmpty
          ? const EmptyWidget(message: '暂无消息', icon: Icons.notifications_off_outlined)
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _notifications.length,
              itemBuilder: (context, index) {
                final notification = _notifications[index];
                return Container(
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: notification.isRead ? Colors.white : const Color(0xFFF0F9EB),
                    borderRadius: BorderRadius.circular(12),
                    border: notification.isRead
                        ? null
                        : Border.all(color: const Color(0xFF52C41A).withOpacity(0.2)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: _getTypeColor(notification.type).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Stack(
                          children: [
                            Center(
                              child: Icon(
                                _getTypeIcon(notification.type),
                                color: _getTypeColor(notification.type),
                                size: 20,
                              ),
                            ),
                            if (!notification.isRead)
                              Positioned(
                                top: 2,
                                right: 2,
                                child: Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(
                                    color: Colors.red,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  notification.title,
                                  style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: notification.isRead ? FontWeight.normal : FontWeight.w600,
                                  ),
                                ),
                                Text(
                                  notification.createdAt ?? '',
                                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(
                              notification.content,
                              style: TextStyle(fontSize: 14, color: Colors.grey[600], height: 1.4),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}
