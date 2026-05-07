// [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
// 改约失败错误码 → 文案映射 + DioException 解析工具。
// 与后端 backend/app/api/unified_orders.py 的 RESCHEDULE_* 常量保持一致。

import 'package:dio/dio.dart';

const Map<String, String> kRescheduleErrorText = {
  'RESCHEDULE_NO_PERMISSION': '无权操作此订单',
  'RESCHEDULE_ORDER_NOT_FOUND': '订单不存在或无权操作此订单',
  'RESCHEDULE_ORDER_STATUS_INVALID': '当前订单状态不允许改约',
  'RESCHEDULE_LIMIT_EXCEEDED': '该订单已达改约次数上限，无法继续改约',
  'RESCHEDULE_NOT_ALLOWED': '该商品不支持改约',
  'RESCHEDULE_TIME_EXPIRED': '所选时段已过期，请选择未来时间',
  'RESCHEDULE_TIME_OUT_OF_RANGE': '所选日期超出可改约范围',
  'RESCHEDULE_TIME_CONFLICT': '所选时段已被预约满，请选其他时段',
  'RESCHEDULE_REFUND_IN_PROGRESS': '该订单退款处理中，暂不允许调整预约时间',
  'RESCHEDULE_PARTIALLY_USED': '该订单已部分核销，无法修改预约时间',
  'RESCHEDULE_INTERNAL_ERROR': '改约失败，请稍后重试或联系客服',
};

/// 从异常中提取改约失败的具体文案。
///
/// 优先级：
///   1. 结构化 detail（{code, message, detail}）→ 用 code 映射，无映射则用 message
///   2. detail 字符串 → 直接显示
///   3. detail 数组（Pydantic 校验错误）→ 取首条 msg
///   4. 顶层 message / code
///   5. 网络层错误 → "网络异常，请稍后重试"
///   6. 都没有 → "改约失败，请稍后重试或联系客服"
String extractRescheduleErrorText(Object error) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map) {
      final detail = data['detail'];
      if (detail is Map) {
        final code = detail['code'];
        if (code is String && kRescheduleErrorText.containsKey(code)) {
          return kRescheduleErrorText[code]!;
        }
        final message = detail['message'];
        if (message is String && message.isNotEmpty) return message;
        final detailStr = detail['detail'];
        if (detailStr is String && detailStr.isNotEmpty) return detailStr;
      }
      if (detail is String && detail.isNotEmpty) return detail;
      if (detail is List && detail.isNotEmpty) {
        final first = detail.first;
        if (first is String) return first;
        if (first is Map && first['msg'] is String) return first['msg'];
      }
      final code = data['code'];
      if (code is String && kRescheduleErrorText.containsKey(code)) {
        return kRescheduleErrorText[code]!;
      }
      final topMessage = data['message'];
      if (topMessage is String && topMessage.isNotEmpty) return topMessage;
    }
    // 网络层 / 超时
    if (error.response == null) {
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.connectionError:
          return '网络异常，请稍后重试';
        default:
          break;
      }
    }
    // HTTP 状态码兜底
    final status = error.response?.statusCode;
    if (status != null) {
      return '改约失败（$status），请稍后重试或联系客服';
    }
  }
  return '改约失败，请稍后重试或联系客服';
}
