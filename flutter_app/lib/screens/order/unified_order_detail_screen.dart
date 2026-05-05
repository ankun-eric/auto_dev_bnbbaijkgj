import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/unified_order.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';
import '../../utils/fulfillment_label.dart';
// [2026-05-05 订单页地址导航按钮 PRD v1.0]
import '../../widgets/address_nav_button.dart';
import 'contact_store_sheet.dart';

class UnifiedOrderDetailScreen extends StatefulWidget {
  const UnifiedOrderDetailScreen({super.key});

  @override
  State<UnifiedOrderDetailScreen> createState() => _UnifiedOrderDetailScreenState();
}

class _UnifiedOrderDetailScreenState extends State<UnifiedOrderDetailScreen> {
  final ApiService _api = ApiService();
  UnifiedOrder? _order;
  bool _loading = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_order == null) {
      final orderId = ModalRoute.of(context)!.settings.arguments as int;
      _loadOrder(orderId);
    }
  }

  Future<void> _loadOrder(int id) async {
    try {
      final res = await _api.getUnifiedOrderDetail(id);
      if (res.data is Map) {
        setState(() {
          _order = UnifiedOrder.fromJson(res.data as Map<String, dynamic>);
          _loading = false;
        });
      }
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('订单详情'), backgroundColor: const Color(0xFF52C41A)),
        body: const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))),
      );
    }
    if (_order == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('订单详情'), backgroundColor: const Color(0xFF52C41A)),
        body: const Center(child: Text('订单不存在')),
      );
    }

    final o = _order!;
    return Scaffold(
      appBar: AppBar(title: const Text('订单详情'), backgroundColor: const Color(0xFF52C41A)),
      body: SingleChildScrollView(
        child: Column(
          children: [
            _buildStatusHeader(o),
            // [先下单后预约 Bug 修复 v1.0] 待预约横幅
            if (o.status == 'pending_appointment' && o.refundStatus == 'none') ...[
              _buildBookAfterPayBanner(o),
            ],
            if (o.refundStatus != 'none') ...[
              _buildRefundStatusBanner(o),
            ],
            const SizedBox(height: 8),
            _buildItemsSection(o),
            const SizedBox(height: 8),
            _buildPriceSection(o),
            const SizedBox(height: 8),
            // [2026-05-05 订单页地址导航按钮 PRD v1.0 · F-04/F-05/F-06]
            // 订单地址独立卡片：门店地址 / 收货地址 / 上门地址 + 导航按钮
            if (_hasAnyAddress(o)) ...[
              _buildAddressSection(o),
              const SizedBox(height: 8),
            ],
            _buildInfoSection(o),
            if (o.items.any((i) => i.appointmentTime != null)) ...[
              const SizedBox(height: 8),
              _buildAppointmentSection(o),
            ],
            if (o.items.any((i) => i.verificationCode != null && i.verificationCode!.isNotEmpty)) ...[
              const SizedBox(height: 8),
              _buildVerificationSection(o),
            ],
            if (o.trackingNumber != null && o.trackingNumber!.isNotEmpty) ...[
              const SizedBox(height: 8),
              _buildTrackingSection(o),
            ],
            const SizedBox(height: 80),
          ],
        ),
      ),
      bottomNavigationBar: _buildBottomActions(o),
    );
  }

  Widget _buildStatusHeader(UnifiedOrder o) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_statusColor(o.status), _statusColor(o.status).withOpacity(0.7)],
        ),
      ),
      child: Column(
        children: [
          Icon(_statusIcon(o.status), color: Colors.white, size: 40),
          const SizedBox(height: 8),
          Text(o.displayStatusLabel, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          if (o.refundStatus != 'none') ...[
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text('退款状态: ${_refundLabel(o.refundStatus)}',
                  style: const TextStyle(color: Colors.white, fontSize: 12)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildItemsSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('商品信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          ...o.items.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: SizedBox(
                    width: 70,
                    height: 70,
                    child: item.productImage != null
                        ? Image.network(item.productImage!, fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => _placeholder())
                        : _placeholder(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(item.productName, style: const TextStyle(fontWeight: FontWeight.w500)),
                      const SizedBox(height: 4),
                      Text(_fulfillmentLabel(item.fulfillmentType),
                          style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                      const SizedBox(height: 4),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('¥${formatPrice(item.productPrice)}',
                              style: const TextStyle(color: Color(0xFFFF4D4F))),
                          Text('x${item.quantity}', style: TextStyle(color: Colors.grey[500])),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildPriceSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _infoRow('商品总额', '¥${formatPrice(o.totalAmount)}'),
          if (o.couponDiscount > 0) _infoRow('优惠券', '-¥${formatPrice(o.couponDiscount)}'),
          if (o.pointsDeduction > 0) _infoRow('积分抵扣', '-¥${formatPrice(o.pointsDeduction / 100)}'),
          const Divider(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('实付金额', style: TextStyle(fontWeight: FontWeight.bold)),
              Text('¥${formatPrice(o.paidAmount)}',
                  style: const TextStyle(color: Color(0xFFFF4D4F), fontSize: 18, fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('订单信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _infoRow('订单编号', o.orderNo, copyable: true),
          _infoRow('下单时间', _formatTime(o.createdAt)),
          // [支付配置 PRD v1.0] 优先显示具体通道文案
          // [2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0 · D5]
          // 当 paymentMethodText 为空时，按映射表显示中文，避免直接展示英文枚举（如 coupon_deduction）。
          // 映射与后端 PAYMENT_METHOD_TEXT_MAP / admin payMethodMap 全端一致。
          if ((o.paymentMethodText ?? '').isNotEmpty)
            _infoRow('支付方式', o.paymentMethodText!)
          else if (o.paymentMethod != null)
            _infoRow('支付方式', _localizePaymentMethod(o.paymentMethod!)),
          if (o.paidAt != null) _infoRow('支付时间', _formatTime(o.paidAt)),
          if (o.notes != null && o.notes!.isNotEmpty) _infoRow('备注', o.notes!),
        ],
      ),
    );
  }

  // [订单详情页订单地址展示统一 Bug 修复 v1.0]
  // 计算订单地址类型：
  //   优先使用后端下发的 orderAddressType（store / delivery / onsite_service）；
  //   缺失时按 OrderItem.fulfillmentType 兜底。
  String? _resolveOrderAddressType(UnifiedOrder o) {
    final fromBackend = o.orderAddressType;
    if (fromBackend != null && fromBackend.isNotEmpty) {
      return fromBackend;
    }
    if (o.items.any((i) => i.fulfillmentType == 'on_site')) return 'onsite_service';
    if (o.items.any((i) => i.fulfillmentType == 'delivery')) return 'delivery';
    if (o.items.any((i) => i.fulfillmentType == 'in_store')) return 'store';
    return null;
  }

  // [订单详情页订单地址展示统一 Bug 修复 v1.0]
  // 是否需要渲染【订单地址】区块：
  //   到店核销（store）→ 隐藏，避免与【预约信息·预约门店】重复
  //   配送 / 上门服务   → 仅当存在地址文本/姓名/电话任一项时渲染
  bool _hasAnyAddress(UnifiedOrder o) {
    final t = _resolveOrderAddressType(o);
    if (t == 'store' || t == null) return false;
    final addr = o.orderAddress ?? const {};
    final text = (addr['address_text']?.toString() ?? o.shippingAddressText ?? '');
    final name = (addr['contact_name']?.toString() ?? o.shippingAddressName ?? '');
    final phone = (addr['contact_phone']?.toString() ?? o.shippingAddressPhone ?? '');
    return text.isNotEmpty || name.isNotEmpty || phone.isNotEmpty;
  }

  // [订单详情页订单地址展示统一 Bug 修复 v1.0]
  // 配送 / 上门服务订单：渲染统一【订单地址】区块（联系人 + 电话 + 完整地址 + 导航）。
  // 到店核销订单走 _hasAnyAddress 短路，本方法不会被调用。
  Widget _buildAddressSection(UnifiedOrder o) {
    final t = _resolveOrderAddressType(o);
    final isOnSite = t == 'onsite_service';
    final addr = o.orderAddress ?? const {};
    final text = (addr['address_text']?.toString() ?? o.shippingAddressText ?? '');
    final name = (addr['contact_name']?.toString() ?? o.shippingAddressName ?? '');
    final phone = (addr['contact_phone']?.toString() ?? o.shippingAddressPhone ?? '');

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('订单地址',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.location_on_outlined,
                  size: 18, color: Color(0xFF52C41A)),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isOnSite ? '上门服务地址' : '收货地址',
                      style: const TextStyle(
                          fontSize: 12, color: Color(0xFF999999)),
                    ),
                    if (name.isNotEmpty || phone.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          if (name.isNotEmpty)
                            Text(name,
                                style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500)),
                          if (phone.isNotEmpty) ...[
                            const SizedBox(width: 12),
                            Text(phone,
                                style: const TextStyle(
                                    fontSize: 12,
                                    color: Color(0xFF999999))),
                          ],
                        ],
                      ),
                    ],
                    if (text.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(text,
                          style: const TextStyle(
                              fontSize: 12, color: Color(0xFF666666))),
                    ],
                  ],
                ),
              ),
              AddressNavButton(
                name: name.isNotEmpty
                    ? name
                    : (isOnSite ? '上门地址' : '收货地址'),
                address: text,
                semanticLabel:
                    isOnSite ? '导航到上门地址' : '导航到收货地址',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAppointmentSection(UnifiedOrder o) {
    final appointmentItems = o.items.where((i) => i.appointmentTime != null).toList();
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('预约信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          ...appointmentItems.map((item) {
            final apptData = item.appointmentData is Map
                ? item.appointmentData as Map
                : null;
            final timeSlot = apptData?['time_slot']?.toString();
            final note = apptData?['note']?.toString();
            // [预约日期模式 Bug 修复 v1.0] 仅 time_slot 模式才展示「预约时段」行；
            // date 模式无论历史脏数据如何，一律不渲染时段
            final isTimeSlotMode = (item.appointmentMode ?? 'time_slot') == 'time_slot';

            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (appointmentItems.length > 1)
                    Text(item.productName, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13)),
                  _infoRow('预约日期', _formatTime(item.appointmentTime).split(' ').first),
                  if (isTimeSlotMode && timeSlot != null && timeSlot.isNotEmpty)
                    _infoRow('预约时段', timeSlot),
                  if (note != null && note.isNotEmpty)
                    _infoRow('预约备注', note),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  bool get _isRefundBlocking =>
      const {'applied', 'reviewing', 'approved', 'returning'}
          .contains(_order?.refundStatus);

  bool get _isRefundSuccess =>
      _order?.refundStatus == 'refund_success' || _order?.refundStatus == 'refunded';

  Widget _buildVerificationSection(UnifiedOrder o) {
    final bool blocking = _isRefundBlocking;
    final bool refunded = _isRefundSuccess;
    final double codeOpacity = (blocking || refunded) ? 0.3 : 1.0;

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('核销码', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              if (refunded) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(color: Colors.grey[400], borderRadius: BorderRadius.circular(4)),
                  child: const Text('已退款', style: TextStyle(color: Colors.white, fontSize: 11)),
                ),
              ],
            ],
          ),
          if (blocking)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: Colors.orange[700]),
                  const SizedBox(width: 4),
                  Text('退款处理中，核销码暂时不可用',
                      style: TextStyle(fontSize: 13, color: Colors.orange[700])),
                ],
              ),
            ),
          if (refunded)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text('该订单已退款，核销码已失效',
                      style: TextStyle(fontSize: 13, color: Colors.grey[600])),
                ],
              ),
            ),
          const SizedBox(height: 12),
          Opacity(
            opacity: codeOpacity,
            child: Column(
              children: o.items.where((i) => i.verificationCode != null).map((item) => Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF0F9EB),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.qr_code, color: Color(0xFF52C41A), size: 32),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.productName, style: const TextStyle(fontSize: 13)),
                        Text(item.verificationCode!, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: 2)),
                        Text('已使用${item.usedRedeemCount}/${item.totalRedeemCount}次', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                      ],
                    ),
                  ],
                ),
              )).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrackingSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('物流信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _infoRow('物流公司', o.trackingCompany ?? ''),
          _infoRow('运单号', o.trackingNumber!, copyable: true),
        ],
      ),
    );
  }

  Widget? _buildBottomActions(UnifiedOrder o) {
    final actions = <Widget>[];
    final bool canApplyRefund = o.refundStatus == 'none' || o.refundStatus == 'rejected';
    final bool isRefundApplied = o.refundStatus == 'applied';

    switch (o.status) {
      case 'pending_payment':
        actions.add(_actionBtn('取消订单', Colors.grey, () => _cancelOrder(o)));
        actions.add(const SizedBox(width: 12));
        actions.add(_actionBtn('去支付', const Color(0xFF52C41A), () => _payOrder(o), filled: true));
        break;
      case 'pending_receipt':
        if (isRefundApplied) {
          actions.add(_actionBtn('撤回退款', Colors.orange, () => _withdrawRefund(o)));
        } else if (canApplyRefund) {
          actions.add(_actionBtn('申请退款', Colors.grey, () {
            Navigator.pushNamed(context, '/refund', arguments: o.id);
          }));
        }
        if (canApplyRefund) {
          actions.add(const SizedBox(width: 12));
          actions.add(_actionBtn('确认收货', const Color(0xFF52C41A), () => _confirmReceipt(o), filled: true));
        }
        break;
      case 'pending_review':
        if (isRefundApplied) {
          actions.add(_actionBtn('撤回退款', Colors.orange, () => _withdrawRefund(o)));
        } else if (canApplyRefund) {
          actions.add(_actionBtn('申请退款', Colors.grey, () {
            Navigator.pushNamed(context, '/refund', arguments: o.id);
          }));
          actions.add(const SizedBox(width: 12));
          actions.add(_actionBtn('去评价', const Color(0xFFFAAD14), () {
            Navigator.pushNamed(context, '/review', arguments: o.id);
          }, filled: true));
        }
        break;
      case 'pending_use':
      case 'appointed':
      case 'partial_used':
        // [核销订单过期+改期规则优化 v1.0] 改约：达上限置灰
        if (o.refundStatus == 'none' || o.refundStatus.isEmpty) {
          final reachedLimit = o.rescheduleCount >= o.rescheduleLimit;
          if (reachedLimit) {
            actions.add(_actionBtn('改约', Colors.grey, () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('本订单已达改期上限')),
              );
            }));
          } else {
            actions.add(_actionBtn('改约', const Color(0xFF722ED1), () async {
              try {
                await _openAppointmentDialog(o);
              } catch (e, st) {
                debugPrint('[appt] open dialog failed: $e\n$st');
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('打开预约失败：$e')),
                  );
                }
              }
            }));
          }
          actions.add(const SizedBox(width: 12));
        }
        if (isRefundApplied) {
          actions.add(_actionBtn('撤回退款', const Color(0xFFFA8C16),
              () => _withdrawRefund(o)));
        } else if (canApplyRefund) {
          actions.add(_actionBtn('申请退款', const Color(0xFFFA541C), () {
            Navigator.pushNamed(context, '/refund', arguments: o.id);
          }));
        }
        break;
      case 'pending_shipment':
        if (isRefundApplied) {
          actions.add(_actionBtn('撤回退款', const Color(0xFFFA8C16),
              () => _withdrawRefund(o)));
        } else if (canApplyRefund) {
          actions.add(_actionBtn('申请退款', const Color(0xFFFA541C), () {
            Navigator.pushNamed(context, '/refund', arguments: o.id);
          }));
        }
        break;
      case 'pending_appointment':
        // [先下单后预约 Bug 修复 v1.0] 立即预约入口
        // [修改预约 Bug 修复 v1.0] 加 try-catch，防止 _openAppointmentDialog 异步异常被静默吞噬
        if (canApplyRefund) {
          actions.add(_actionBtn('立即预约', const Color(0xFF52C41A), () async {
            try {
              await _openAppointmentDialog(o);
            } catch (e, st) {
              debugPrint('[appt] open dialog failed: $e\n$st');
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('打开预约失败：$e')),
                );
              }
            }
          }, filled: true));
        }
        break;
    }

    // [核销订单过期+改期规则优化 v1.0] 联系商家：所有状态均展示
    if (actions.isNotEmpty) {
      actions.add(const SizedBox(width: 12));
    }
    actions.add(_actionBtn('联系商家', const Color(0xFF52C41A), () {
      ContactStoreSheet.show(
        context,
        storeId: o.storeId,
        fallbackStoreName: o.storeName,
      );
    }));

    if (actions.isEmpty) return null;

    return Container(
      padding: EdgeInsets.fromLTRB(16, 8, 16, MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 8, offset: const Offset(0, -2))],
      ),
      child: Row(mainAxisAlignment: MainAxisAlignment.end, children: actions),
    );
  }

  Widget _actionBtn(String text, Color color, VoidCallback onTap, {bool filled = false}) {
    return filled
        ? ElevatedButton(
            onPressed: onTap,
            style: ElevatedButton.styleFrom(
              backgroundColor: color,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            ),
            child: Text(text),
          )
        : OutlinedButton(
            onPressed: onTap,
            style: OutlinedButton.styleFrom(
              foregroundColor: color,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              side: BorderSide(color: color),
            ),
            child: Text(text),
          );
  }

  Widget _placeholder() {
    return Container(
      color: const Color(0xFFF0F9EB),
      child: const Icon(Icons.shopping_bag_outlined, color: Color(0xFF52C41A), size: 24),
    );
  }

  Widget _infoRow(String label, String value, {bool copyable = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 80, child: Text(label, style: TextStyle(color: Colors.grey[500], fontSize: 14))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 14))),
          if (copyable)
            GestureDetector(
              onTap: () {
                Clipboard.setData(ClipboardData(text: value));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
                );
              },
              child: Icon(Icons.copy, size: 16, color: Colors.grey[400]),
            ),
        ],
      ),
    );
  }

  String _formatTime(String? time) {
    if (time == null) return '';
    return time.replaceFirst('T', ' ').split('.').first;
  }

  // [2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0 · D5]
  // 把后端返回的 payment_method 英文枚举值翻译为中文，
  // 与后端 PAYMENT_METHOD_TEXT_MAP / admin payMethodMap 全端口径一致。
  String _localizePaymentMethod(String method) {
    switch (method) {
      case 'wechat':
        return '微信支付';
      case 'alipay':
        return '支付宝';
      case 'coupon_deduction':
        return '优惠券全额抵扣';
      case 'balance':
        return '余额支付';
      case 'points':
        return '积分兑换';
      default:
        return '其他';
    }
  }

  // [先下单后预约 Bug 修复 v1.0] 待预约横幅
  Widget _buildBookAfterPayBanner(UnifiedOrder o) {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFFFFBE6), Color(0xFFFFF7E6)],
        ),
        border: Border.all(color: const Color(0xFFFFD591)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          const Expanded(
            child: Text(
              '🗓️ 您还未预约服务时间，请尽快选择您方便的时间',
              style: TextStyle(fontSize: 13, color: Color(0xFFD48806)),
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton(
            // [修改预约 Bug 修复 v1.0] 顶层 try-catch，防止异步异常被全局 handler 静默吞噬
            onPressed: () async {
              try {
                await _openAppointmentDialog(o);
              } catch (e, st) {
                debugPrint('[appt] open dialog failed: $e\n$st');
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('打开预约失败：$e')),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF52C41A),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              minimumSize: const Size(0, 32),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            child: const Text('立即预约', style: TextStyle(color: Colors.white, fontSize: 12)),
          ),
        ],
      ),
    );
  }

  // [先下单后预约 Bug 修复 v1.0] 立即预约弹窗
  static const List<String> _kAppointmentSlots = [
    '09:00-10:00', '10:00-11:00', '11:00-12:00',
    '13:00-14:00', '14:00-15:00', '15:00-16:00',
    '16:00-17:00', '17:00-18:00',
  ];

  Future<void> _openAppointmentDialog(UnifiedOrder o) async {
    // [修改预约 Bug 修复 v1.0]
    // - 移除 firstWhere(orElse: throw)，改用安全查找避免异常静默吞噬
    // - 优先选择 appointment_mode != none 的 in_store 商品
    // - custom_form 模式跳转到自定义表单页（暂以 SnackBar 提示降级）
    OrderItem? apptItem;
    for (final i in o.items) {
      if (i.fulfillmentType == 'in_store' &&
          (i.appointmentMode != null && i.appointmentMode != 'none')) {
        apptItem = i;
        break;
      }
    }
    apptItem ??= o.items.firstWhere(
      (i) => i.fulfillmentType == 'in_store',
      orElse: () => o.items.isNotEmpty ? o.items.first : _emptyItemSentinel,
    );
    if (apptItem.id == 0) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('该订单暂无可预约商品')),
        );
      }
      return;
    }

    final mode = apptItem.appointmentMode ?? 'time_slot';

    // custom_form 模式：跳转到自定义预约表单页面
    if (mode == 'custom_form') {
      try {
        await Navigator.of(context).pushNamed(
          '/custom-appointment',
          arguments: {
            'orderId': o.id,
            'itemId': apptItem.id,
            'mode': 'edit',
          },
        );
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('请前往商品详情页填写预约表单')),
          );
        }
      }
      return;
    }

    // 默认日期：已存在则回填，否则明天
    DateTime initialDate = DateTime.now().add(const Duration(days: 1));
    if (apptItem.appointmentTime != null && apptItem.appointmentTime!.isNotEmpty) {
      try {
        initialDate = DateTime.parse(apptItem.appointmentTime!);
      } catch (_) { /* 保持默认 */ }
    }
    DateTime selectedDate = DateTime(initialDate.year, initialDate.month, initialDate.day);
    // 已存在时段则回填
    String? selectedSlot;
    if (apptItem.appointmentData is Map &&
        (apptItem.appointmentData as Map)['time_slot'] != null) {
      selectedSlot = (apptItem.appointmentData as Map)['time_slot']?.toString();
    }

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx2, setS) {
          final dateStr =
              '${selectedDate.year}-${selectedDate.month.toString().padLeft(2, '0')}-${selectedDate.day.toString().padLeft(2, '0')}';
          return AlertDialog(
            title: const Text('选择预约时间', textAlign: TextAlign.center),
            content: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('预约日期', style: TextStyle(color: Colors.grey, fontSize: 13)),
                  const SizedBox(height: 6),
                  OutlinedButton(
                    onPressed: () async {
                      final picked = await showDatePicker(
                        context: ctx2,
                        initialDate: selectedDate,
                        firstDate: DateTime.now(),
                        lastDate: DateTime.now().add(const Duration(days: 90)),
                      );
                      if (picked != null) setS(() => selectedDate = picked);
                    },
                    child: Text(dateStr),
                  ),
                  // [修改预约 Bug 修复 v1.0] date 模式整块时段隐藏；time_slot 模式用 GridView 3 列
                  if (mode != 'date') ...[
                    const SizedBox(height: 14),
                    const Text('预约时段', style: TextStyle(color: Colors.grey, fontSize: 13)),
                    const SizedBox(height: 6),
                    GridView.count(
                      crossAxisCount: 3,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      mainAxisSpacing: 8,
                      crossAxisSpacing: 8,
                      childAspectRatio: 2.6,
                      children: _kAppointmentSlots.map((slot) {
                        final active = slot == selectedSlot;
                        return GestureDetector(
                          onTap: () => setS(() => selectedSlot = slot),
                          child: Container(
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              color: active ? const Color(0xFF52C41A) : Colors.white,
                              border: Border.all(
                                color: active ? const Color(0xFF52C41A) : Colors.grey.shade300,
                              ),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              slot,
                              style: TextStyle(
                                color: active ? Colors.white : Colors.black87,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx2, false), child: const Text('取消')),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF52C41A)),
                onPressed: () async {
                  // [修改预约 Bug 修复 v1.0] date 模式不校验时段，只用日期；提交体不携带 time_slot
                  if (mode != 'date' && selectedSlot == null) {
                    ScaffoldMessenger.of(ctx2).showSnackBar(
                      const SnackBar(content: Text('请选择预约时段')),
                    );
                    return;
                  }
                  final start = (mode != 'date' && selectedSlot != null)
                      ? selectedSlot!.split('-')[0]
                      : '09:00';
                  final Map<String, dynamic> appointmentData = {'date': dateStr};
                  if (mode != 'date' && selectedSlot != null) {
                    appointmentData['time_slot'] = selectedSlot;
                  }
                  try {
                    await _api.post(
                      '/api/orders/unified/${o.id}/appointment',
                      data: {
                        'item_id': apptItem!.id,
                        'appointment_time': '${dateStr}T$start:00',
                        'appointment_data': appointmentData,
                      },
                    );
                    if (ctx2.mounted) Navigator.pop(ctx2, true);
                  } catch (e) {
                    if (ctx2.mounted) {
                      ScaffoldMessenger.of(ctx2).showSnackBar(
                        SnackBar(content: Text('预约失败：$e')),
                      );
                    }
                  }
                },
                child: const Text('确认预约', style: TextStyle(color: Colors.white)),
              ),
            ],
          );
        });
      },
    );

    if (result == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('预约成功')));
      _loadOrder(o.id);
    }
  }

  // 用于 firstWhere 的兜底空 item，避免抛出异常
  static final OrderItem _emptyItemSentinel = OrderItem(
    id: 0,
    orderId: 0,
    productId: 0,
    productName: '',
    productPrice: 0,
    quantity: 0,
    subtotal: 0,
    fulfillmentType: 'in_store',
  );

  Color _statusColor(String status) {
    switch (status) {
      case 'pending_payment':
        return const Color(0xFFFF4D4F);
      case 'pending_appointment':
      case 'appointed':
        return const Color(0xFF722ED1);
      case 'pending_shipment':
      case 'pending_receipt':
      case 'pending_use':
        return const Color(0xFF1890FF);
      case 'partial_used':
        return const Color(0xFF13C2C2);
      case 'pending_review':
        return const Color(0xFFFAAD14);
      case 'completed':
        return const Color(0xFF52C41A);
      default:
        return Colors.grey;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'pending_payment':
        return Icons.payment;
      case 'pending_appointment':
        return Icons.event_note;
      case 'appointed':
        return Icons.event_available;
      case 'pending_shipment':
        return Icons.local_shipping;
      case 'pending_receipt':
        return Icons.inventory;
      case 'pending_use':
        return Icons.qr_code;
      case 'pending_review':
        return Icons.rate_review;
      case 'completed':
        return Icons.check_circle;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.receipt_long;
    }
  }

  String _refundLabel(String status) {
    switch (status) {
      case 'applied':
        return '申请中';
      case 'reviewing':
        return '审核中';
      case 'approved':
        return '已同意';
      case 'rejected':
        return '已拒绝';
      case 'returning':
        return '退款中';
      case 'refunded':
      case 'refund_success':
        return '已退款';
      default:
        return status;
    }
  }

  String _fulfillmentLabel(String type) => fulfillmentLabel(type);

  Widget _buildRefundStatusBanner(UnifiedOrder o) {
    Color bgColor;
    Color textColor;
    IconData icon;
    String message;
    bool showReapplyButton = false;

    switch (o.refundStatus) {
      case 'applied':
        bgColor = const Color(0xFFFFF7E6);
        textColor = const Color(0xFFFA8C16);
        icon = Icons.hourglass_top;
        message = '退款申请已提交，正在处理中...';
        break;
      case 'reviewing':
        bgColor = const Color(0xFFE6F7FF);
        textColor = const Color(0xFF1890FF);
        icon = Icons.policy;
        message = '退款审核中...';
        break;
      case 'approved':
      case 'returning':
        bgColor = const Color(0xFFF6FFED);
        textColor = const Color(0xFF52C41A);
        icon = Icons.check_circle_outline;
        message = '退款已批准，退款处理中...';
        break;
      case 'rejected':
        bgColor = const Color(0xFFFFF1F0);
        textColor = const Color(0xFFFF4D4F);
        icon = Icons.cancel_outlined;
        message = '退款申请已被拒绝';
        showReapplyButton = true;
        break;
      case 'refund_success':
      case 'refunded':
        bgColor = const Color(0xFFF5F5F5);
        textColor = Colors.grey[600]!;
        icon = Icons.monetization_on_outlined;
        message = '退款成功';
        break;
      default:
        return const SizedBox.shrink();
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: bgColor,
      child: Row(
        children: [
          Icon(icon, color: textColor, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(message, style: TextStyle(color: textColor, fontSize: 14))),
          if (showReapplyButton)
            GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/refund', arguments: o.id),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  border: Border.all(color: textColor),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text('重新申请', style: TextStyle(color: textColor, fontSize: 12)),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _withdrawRefund(UnifiedOrder o) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('撤回退款'),
        content: const Text('确定要撤回退款申请吗？撤回后可重新申请。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定撤回')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.withdrawRefund(o.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('退款申请已撤回')));
        _loadOrder(o.id);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('撤回失败，请稍后重试')));
      }
    }
  }

  Future<void> _cancelOrder(UnifiedOrder o) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('取消订单'),
        content: const Text('确定要取消该订单吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('再想想')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定取消')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.cancelUnifiedOrder(o.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('订单已取消')));
        _loadOrder(o.id);
      }
    } catch (_) {}
  }

  Future<void> _payOrder(UnifiedOrder o) async {
    try {
      // [H5 支付链路修复 v1.0] 拉取可用支付方式
      String? channelCode;
      try {
        final methodsRes = await _api.getAvailablePayMethods(platform: 'app');
        final raw = methodsRes.data;
        List list = raw is List
            ? raw
            : (raw is Map && raw['data'] is List ? raw['data'] as List : []);
        if (list.isNotEmpty) {
          channelCode = (list.first as Map)['channel_code'] as String?;
        }
      } catch (_) {
        // 忽略，channelCode 保持 null
      }

      final paidAmount = o.paidAmount;
      if (paidAmount == 0) {
        await _api.confirmFreeUnifiedOrder(o.id, channelCode: channelCode);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('支付成功')),
          );
          _loadOrder(o.id);
        }
        return;
      }

      if (channelCode == null || channelCode.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('暂未开通支付方式')),
          );
        }
        return;
      }

      final payRes = await _api.payUnifiedOrder(o.id, channelCode: channelCode);
      final payData = payRes.data is Map ? payRes.data as Map : null;
      final payUrl = payData?['pay_url'] as String?;
      if (mounted) {
        if (payUrl != null && payUrl.isNotEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('请在浏览器完成支付：$payUrl')),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('支付成功')),
          );
        }
        _loadOrder(o.id);
      }
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付失败')));
    }
  }

  Future<void> _confirmReceipt(UnifiedOrder o) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认收货'),
        content: const Text('确定已收到货物吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确认')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.confirmReceipt(o.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('确认收货成功')));
        _loadOrder(o.id);
      }
    } catch (_) {}
  }
}
