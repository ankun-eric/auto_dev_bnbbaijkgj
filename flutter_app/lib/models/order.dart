class Order {
  final String id;
  final String orderNo;
  final String? serviceName;
  final String? serviceImage;
  final double amount;
  final String status;
  final String? payMethod;
  final String? verifyCode;
  final String? appointmentTime;
  final String? expertName;
  final String? location;
  final String? remark;
  final String? logistics;
  final String? createdAt;
  final String? paidAt;

  Order({
    required this.id,
    required this.orderNo,
    this.serviceName,
    this.serviceImage,
    required this.amount,
    required this.status,
    this.payMethod,
    this.verifyCode,
    this.appointmentTime,
    this.expertName,
    this.location,
    this.remark,
    this.logistics,
    this.createdAt,
    this.paidAt,
  });

  String get statusLabel {
    switch (status) {
      case 'pending':
        return '待支付';
      case 'paid':
        return '已支付';
      case 'confirmed':
        return '已确认';
      case 'in_progress':
        return '进行中';
      case 'completed':
        return '已完成';
      case 'cancelled':
        return '已取消';
      case 'refunded':
        return '已退款';
      default:
        return '未知';
    }
  }

  factory Order.fromJson(Map<String, dynamic> json) {
    return Order(
      id: json['id']?.toString() ?? '',
      orderNo: json['order_no'] ?? '',
      serviceName: json['service_name'],
      serviceImage: json['service_image'],
      amount: (json['amount'] ?? 0).toDouble(),
      status: json['status'] ?? 'pending',
      payMethod: json['pay_method'],
      verifyCode: json['verify_code'],
      appointmentTime: json['appointment_time'],
      expertName: json['expert_name'],
      location: json['location'],
      remark: json['remark'],
      logistics: json['logistics'],
      createdAt: json['created_at'],
      paidAt: json['paid_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'order_no': orderNo,
      'service_name': serviceName,
      'service_image': serviceImage,
      'amount': amount,
      'status': status,
      'pay_method': payMethod,
      'verify_code': verifyCode,
      'appointment_time': appointmentTime,
      'expert_name': expertName,
      'location': location,
      'remark': remark,
      'logistics': logistics,
      'created_at': createdAt,
      'paid_at': paidAt,
    };
  }
}
