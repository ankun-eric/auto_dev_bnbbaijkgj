import 'package:flutter/material.dart';
import '../models/chat_session.dart';
import '../models/chat_message.dart';
import '../services/api_service.dart';

class ChatProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  List<ChatSession> _sessions = [];
  List<ChatMessage> _messages = [];
  ChatSession? _currentSession;
  bool _isLoading = false;
  bool _isSending = false;

  List<ChatSession> get sessions => _sessions;
  List<ChatMessage> get messages => _messages;
  ChatSession? get currentSession => _currentSession;
  bool get isLoading => _isLoading;
  bool get isSending => _isSending;

  Future<void> loadSessions() async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.getChatSessions();
      if (response.statusCode == 200) {
        final list = response.data['data'] as List? ?? [];
        _sessions = list.map((e) => ChatSession.fromJson(e)).toList();
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
  }

  Future<ChatSession?> createSession(String type) async {
    try {
      final response = await _api.createChatSession(type);
      if (response.statusCode == 200) {
        final session = ChatSession.fromJson(response.data['data']);
        _sessions.insert(0, session);
        _currentSession = session;
        _messages = [];
        notifyListeners();
        return session;
      }
    } catch (_) {}
    return null;
  }

  Future<void> loadMessages(String sessionId) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.getChatMessages(sessionId);
      if (response.statusCode == 200) {
        final list = response.data['data'] as List? ?? [];
        _messages = list.map((e) => ChatMessage.fromJson(e)).toList();
      }
    } catch (_) {}

    _isLoading = false;
    notifyListeners();
  }

  void setCurrentSession(ChatSession session) {
    _currentSession = session;
    notifyListeners();
  }

  Future<void> sendMessage(String content, {String type = 'text'}) async {
    if (_currentSession == null || _isSending) return;

    final userMessage = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: _currentSession!.id,
      role: 'user',
      content: content,
      type: type,
      createdAt: DateTime.now().toIso8601String(),
    );
    _messages.add(userMessage);

    final loadingMessage = ChatMessage.loading(_currentSession!.id);
    _messages.add(loadingMessage);
    _isSending = true;
    notifyListeners();

    try {
      final response = await _api.sendMessage(
        _currentSession!.id,
        content,
        type: type,
      );
      _messages.removeWhere((m) => m.id == 'loading');
      if (response.statusCode == 200) {
        final aiMessage = ChatMessage.fromJson(response.data['data']);
        _messages.add(aiMessage);
      }
    } catch (_) {
      _messages.removeWhere((m) => m.id == 'loading');
      _messages.add(ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: _currentSession!.id,
        role: 'assistant',
        content: '抱歉，网络异常，请稍后重试。',
        createdAt: DateTime.now().toIso8601String(),
      ));
    }

    _isSending = false;
    notifyListeners();
  }

  void clearMessages() {
    _messages = [];
    _currentSession = null;
    notifyListeners();
  }
}
