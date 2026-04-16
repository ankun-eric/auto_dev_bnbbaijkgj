import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  static final TtsService _instance = TtsService._internal();
  factory TtsService() => _instance;

  late FlutterTts _tts;
  bool _isPlaying = false;
  String? _currentPlayingId;

  bool get isPlaying => _isPlaying;
  String? get currentPlayingId => _currentPlayingId;

  Function()? onStateChanged;

  TtsService._internal() {
    _tts = FlutterTts();
    _init();
  }

  Future<void> _init() async {
    await _tts.setLanguage('zh-CN');
    await _tts.setSpeechRate(0.5);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);

    _tts.setCompletionHandler(() {
      _isPlaying = false;
      _currentPlayingId = null;
      onStateChanged?.call();
    });

    _tts.setCancelHandler(() {
      _isPlaying = false;
      _currentPlayingId = null;
      onStateChanged?.call();
    });

    _tts.setErrorHandler((msg) {
      _isPlaying = false;
      _currentPlayingId = null;
      onStateChanged?.call();
    });
  }

  Future<void> speak(String text, {String? messageId}) async {
    if (_isPlaying && _currentPlayingId == messageId) {
      await stop();
      return;
    }

    await stop();

    final cleanText = text
        .replaceAll(RegExp(r'[#*`~>\-|]'), '')
        .replaceAll(RegExp(r'\[.*?\]\(.*?\)'), '')
        .replaceAll('---disclaimer---', '')
        .trim();

    if (cleanText.isEmpty) return;

    _isPlaying = true;
    _currentPlayingId = messageId;
    onStateChanged?.call();

    await _tts.speak(cleanText);
  }

  Future<void> stop() async {
    await _tts.stop();
    _isPlaying = false;
    _currentPlayingId = null;
    onStateChanged?.call();
  }

  void dispose() {
    _tts.stop();
  }
}
