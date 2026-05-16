import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'api_service.dart';

class SseMessage {
  final String event;
  final String data;
  SseMessage({required this.event, required this.data});
}

class SseService {
  static final SseService _instance = SseService._internal();
  factory SseService() => _instance;
  SseService._internal();

  final ApiService _api = ApiService();

  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
  // 新增可选 extras：透传 intent / image_urls / button_id / button_type / report_meta
  // 给后端通用 SSE 分发器（与 H5、小程序协议保持一致），用于报告解读 / 识药等场景。
  Stream<SseMessage> streamChat(
    String sessionId,
    String content, {
    String type = 'text',
    String? intent,
    List<String>? imageUrls,
    String? buttonType,
    int? buttonId,
    Map<String, dynamic>? reportMeta,
    int? familyMemberId,
  }) async* {
    final dio = _api.dio;
    try {
      final Map<String, dynamic> body = {
        'content': content,
        'message_type': type,
      };
      if (intent != null && intent.isNotEmpty) body['intent'] = intent;
      if (imageUrls != null && imageUrls.isNotEmpty) body['image_urls'] = imageUrls;
      if (buttonType != null && buttonType.isNotEmpty) body['button_type'] = buttonType;
      if (buttonId != null) body['button_id'] = buttonId;
      if (reportMeta != null && reportMeta.isNotEmpty) body['report_meta'] = reportMeta;
      if (familyMemberId != null) body['family_member_id'] = familyMemberId;
      final response = await dio.post(
        '/api/chat/sessions/$sessionId/stream',
        data: body,
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream'},
        ),
      );

      final stream = response.data.stream as Stream<List<int>>;
      String buffer = '';

      await for (final chunk in stream) {
        buffer += utf8.decode(chunk);
        final lines = buffer.split('\n');
        buffer = lines.removeLast();

        String currentEvent = 'message';
        String currentData = '';

        for (final line in lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            currentData = line.substring(5).trim();
          } else if (line.isEmpty && currentData.isNotEmpty) {
            yield SseMessage(event: currentEvent, data: currentData);
            currentEvent = 'message';
            currentData = '';
          }
        }

        if (currentData.isNotEmpty) {
          yield SseMessage(event: currentEvent, data: currentData);
        }
      }
    } catch (e) {
      yield SseMessage(event: 'error', data: e.toString());
    }
  }

  /// [2026-04-25] 订阅报告解读异步 SSE（GET 方法，auto_start=1）。
  /// 具备简单的指数退避重连（最多 3 次），心跳超时后自动重连。
  Stream<SseMessage> subscribeReportInterpret(String sessionId) async* {
    final dio = _api.dio;
    int attempt = 0;
    while (attempt < 4) {
      try {
        final response = await dio.get(
          '/api/report/interpret/session/$sessionId/stream',
          queryParameters: {'auto_start': 1},
          options: Options(
            responseType: ResponseType.stream,
            headers: {'Accept': 'text/event-stream'},
          ),
        );
        final stream = response.data.stream as Stream<List<int>>;
        String buffer = '';
        String currentEvent = 'message';
        String currentData = '';
        await for (final chunk in stream) {
          buffer += utf8.decode(chunk);
          final lines = buffer.split('\n');
          buffer = lines.removeLast();
          for (final line in lines) {
            if (line.startsWith('event:')) {
              currentEvent = line.substring(6).trim();
            } else if (line.startsWith('data:')) {
              currentData = line.substring(5).trim();
            } else if (line.isEmpty) {
              if (currentData.isNotEmpty || currentEvent != 'message') {
                yield SseMessage(event: currentEvent, data: currentData);
                if (currentEvent == 'done' || currentEvent == 'error') {
                  return;
                }
              }
              currentEvent = 'message';
              currentData = '';
            }
          }
        }
        // 服务端主动关闭，结束
        return;
      } catch (e) {
        attempt += 1;
        if (attempt >= 4) {
          yield SseMessage(event: 'error', data: e.toString());
          return;
        }
        final backoff = Duration(seconds: [1, 2, 4][attempt.clamp(1, 3) - 1]);
        await Future.delayed(backoff);
      }
    }
  }
}
