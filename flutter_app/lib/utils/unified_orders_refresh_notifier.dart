// [BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v1.0]
//
// 全局订单列表刷新信号器：当顾客在「订单详情页」改约/预约成功后，
// 通过 [UnifiedOrdersRefreshNotifier.instance.markNeedsRefresh] 触发；
// 「订单列表页」监听该 ValueNotifier，在收到 true 时自动刷新一次列表数据
// 并将信号置回 false。
//
// 这种实现避开了对 RouteObserver 的耦合，且与 Flutter 现有 `pushNamed` +
// `await` 后 `_loadOrders()` 的就地刷新机制并存（即便用户从其它入口
// 直接进入详情页改约后退回列表页，也能确保列表显示最新预约时间）。
import 'package:flutter/foundation.dart';

class UnifiedOrdersRefreshNotifier extends ValueNotifier<bool> {
  UnifiedOrdersRefreshNotifier._() : super(false);

  static final UnifiedOrdersRefreshNotifier instance =
      UnifiedOrdersRefreshNotifier._();

  /// 由订单详情页改约/预约成功后调用，触发订单列表页刷新。
  void markNeedsRefresh() {
    value = true;
  }

  /// 由订单列表页消费完信号后调用，避免重复刷新。
  void consume() {
    if (value) value = false;
  }
}
