class OrderItem {
  final int id;
  final int orderId;
  final int productId;
  final String productName;
  final String? productImage;
  final double productPrice;
  final int quantity;
  final double subtotal;
  final String fulfillmentType;
  final String? verificationCode;
  final String? verificationQrcodeToken;
  final int totalRedeemCount;
  final int usedRedeemCount;
  final dynamic appointmentData;
  final String? appointmentTime;
  final String? createdAt;
  // [修改预约 Bug 修复 v1.0] 后端透传的预约模式：none / date / time_slot / custom_form
  final String? appointmentMode;
  final int? customFormId;

  OrderItem({
    required this.id,
    required this.orderId,
    required this.productId,
    required this.productName,
    this.productImage,
    required this.productPrice,
    required this.quantity,
    required this.subtotal,
    required this.fulfillmentType,
    this.verificationCode,
    this.verificationQrcodeToken,
    this.totalRedeemCount = 0,
    this.usedRedeemCount = 0,
    this.appointmentData,
    this.appointmentTime,
    this.createdAt,
    this.appointmentMode,
    this.customFormId,
  });

  factory OrderItem.fromJson(Map<String, dynamic> json) {
    return OrderItem(
      id: json['id'] ?? 0,
      orderId: json['order_id'] ?? 0,
      productId: json['product_id'] ?? 0,
      productName: json['product_name'] ?? '',
      productImage: json['product_image'],
      productPrice: (json['product_price'] ?? 0).toDouble(),
      quantity: json['quantity'] ?? 1,
      subtotal: (json['subtotal'] ?? 0).toDouble(),
      fulfillmentType: json['fulfillment_type'] ?? 'in_store',
      verificationCode: json['verification_code'],
      verificationQrcodeToken: json['verification_qrcode_token'],
      totalRedeemCount: json['total_redeem_count'] ?? 0,
      usedRedeemCount: json['used_redeem_count'] ?? 0,
      appointmentData: json['appointment_data'],
      appointmentTime: json['appointment_time']?.toString(),
      createdAt: json['created_at']?.toString(),
      appointmentMode: json['appointment_mode']?.toString(),
      customFormId: json['custom_form_id'] is int
          ? json['custom_form_id'] as int
          : (json['custom_form_id'] is String
              ? int.tryParse(json['custom_form_id'] as String)
              : null),
    );
  }
}

class UnifiedOrder {
  final int id;
  final String orderNo;
  final int userId;
  final double totalAmount;
  final double paidAmount;
  final int pointsDeduction;
  final String? paymentMethod;
  final int? couponId;
  final double couponDiscount;
  final String status;
  final String refundStatus;
  final int? shippingAddressId;
  final dynamic shippingInfo;
  final int? serviceAddressId;
  final dynamic serviceAddressSnapshot;
  final String? trackingNumber;
  final String? trackingCompany;
  final String? notes;
  final int paymentTimeoutMinutes;
  final String? paidAt;
  final String? shippedAt;
  final String? receivedAt;
  final String? completedAt;
  final String? cancelledAt;
  final String? cancelReason;
  final int autoConfirmDays;
  final List<OrderItem> items;
  final String? createdAt;
  final String? updatedAt;
  final String? displayStatus;
  final String? displayStatusColor;
  final List<String> actionButtons;
  // [支付配置 PRD v1.0] 实际支付通道
  final String? paymentChannelCode;
  final String? paymentDisplayName;
  final String? paymentMethodText; // 形如 "微信支付（小程序）"
  // [核销订单过期+改期规则优化 v1.0]
  final int rescheduleCount;
  final int rescheduleLimit;
  final bool allowReschedule;
  final int? storeId;
  final String? storeName;
  // [2026-05-05 订单页地址导航按钮 PRD v1.0] 后端透传字段，用于订单详情页地址行的导航按钮
  final String? storeAddress;
  final double? storeLat;
  final double? storeLng;
  final String? shippingAddressText;
  final String? shippingAddressName;
  final String? shippingAddressPhone;

  UnifiedOrder({
    required this.id,
    required this.orderNo,
    required this.userId,
    required this.totalAmount,
    required this.paidAmount,
    this.pointsDeduction = 0,
    this.paymentMethod,
    this.couponId,
    this.couponDiscount = 0,
    required this.status,
    this.refundStatus = 'none',
    this.shippingAddressId,
    this.shippingInfo,
    this.serviceAddressId,
    this.serviceAddressSnapshot,
    this.trackingNumber,
    this.trackingCompany,
    this.notes,
    this.paymentTimeoutMinutes = 15,
    this.paidAt,
    this.shippedAt,
    this.receivedAt,
    this.completedAt,
    this.cancelledAt,
    this.cancelReason,
    this.autoConfirmDays = 7,
    this.items = const [],
    this.createdAt,
    this.updatedAt,
    this.displayStatus,
    this.displayStatusColor,
    this.actionButtons = const [],
    this.paymentChannelCode,
    this.paymentDisplayName,
    this.paymentMethodText,
    this.rescheduleCount = 0,
    this.rescheduleLimit = 3,
    this.allowReschedule = true,
    this.storeId,
    this.storeName,
    this.storeAddress,
    this.storeLat,
    this.storeLng,
    this.shippingAddressText,
    this.shippingAddressName,
    this.shippingAddressPhone,
  });

  String get statusLabel {
    switch (status) {
      case 'pending_payment':
        return '待支付';
      case 'pending_shipment':
        return '待发货';
      case 'pending_receipt':
        return '待收货';
      case 'pending_appointment':
        return '待预约';
      case 'appointed':
        return '待核销';
      case 'pending_use':
        return '待核销';
      case 'partial_used':
        return '部分核销';
      case 'pending_review':
        return '待评价';
      case 'completed':
        return '已完成';
      case 'expired':
        return '已过期';
      case 'refunding':
        return '退款中';
      case 'refunded':
        return '已退款';
      case 'cancelled':
        return '已取消';
      default:
        return status;
    }
  }

  String get displayStatusLabel {
    if (displayStatus != null && displayStatus!.isNotEmpty) {
      return displayStatus!;
    }
    return statusLabel;
  }

  factory UnifiedOrder.fromJson(Map<String, dynamic> json) {
    return UnifiedOrder(
      id: json['id'] ?? 0,
      orderNo: json['order_no'] ?? '',
      userId: json['user_id'] ?? 0,
      totalAmount: (json['total_amount'] ?? 0).toDouble(),
      paidAmount: (json['paid_amount'] ?? 0).toDouble(),
      pointsDeduction: json['points_deduction'] ?? 0,
      paymentMethod: json['payment_method'],
      couponId: json['coupon_id'],
      couponDiscount: (json['coupon_discount'] ?? 0).toDouble(),
      status: json['status'] ?? 'pending_payment',
      refundStatus: json['refund_status'] ?? 'none',
      shippingAddressId: json['shipping_address_id'],
      shippingInfo: json['shipping_info'],
      serviceAddressId: json['service_address_id'],
      serviceAddressSnapshot: json['service_address_snapshot'],
      trackingNumber: json['tracking_number'],
      trackingCompany: json['tracking_company'],
      notes: json['notes'],
      paymentTimeoutMinutes: json['payment_timeout_minutes'] ?? 15,
      paidAt: json['paid_at']?.toString(),
      shippedAt: json['shipped_at']?.toString(),
      receivedAt: json['received_at']?.toString(),
      completedAt: json['completed_at']?.toString(),
      cancelledAt: json['cancelled_at']?.toString(),
      cancelReason: json['cancel_reason'],
      autoConfirmDays: json['auto_confirm_days'] ?? 7,
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => OrderItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
      displayStatus: json['display_status']?.toString(),
      displayStatusColor: json['display_status_color']?.toString(),
      actionButtons: (json['action_buttons'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      paymentChannelCode: json['payment_channel_code']?.toString(),
      paymentDisplayName: json['payment_display_name']?.toString(),
      paymentMethodText: json['payment_method_text']?.toString(),
      rescheduleCount: json['reschedule_count'] is int
          ? json['reschedule_count'] as int
          : int.tryParse(json['reschedule_count']?.toString() ?? '0') ?? 0,
      rescheduleLimit: json['reschedule_limit'] is int
          ? json['reschedule_limit'] as int
          : int.tryParse(json['reschedule_limit']?.toString() ?? '3') ?? 3,
      allowReschedule: json['allow_reschedule'] == false ? false : true,
      storeId: json['store_id'] is int
          ? json['store_id'] as int
          : int.tryParse(json['store_id']?.toString() ?? ''),
      storeName: json['store_name']?.toString(),
      storeAddress: json['store_address']?.toString(),
      storeLat: json['store_lat'] is num
          ? (json['store_lat'] as num).toDouble()
          : double.tryParse(json['store_lat']?.toString() ?? ''),
      storeLng: json['store_lng'] is num
          ? (json['store_lng'] as num).toDouble()
          : double.tryParse(json['store_lng']?.toString() ?? ''),
      shippingAddressText: json['shipping_address_text']?.toString(),
      shippingAddressName: json['shipping_address_name']?.toString(),
      shippingAddressPhone: json['shipping_address_phone']?.toString(),
    );
  }
}
