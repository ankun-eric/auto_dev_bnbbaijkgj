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

  Stream<SseMessage> streamChat(String sessionId, String content, {String type = 'text'}) async* {
    final dio = _api.dio;
    try {
      final response = await dio.post(
        '/api/chat/sessions/$sessionId/stream',
        data: {'content': content, 'message_type': type},
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
}
