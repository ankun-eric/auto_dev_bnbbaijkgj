import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../../services/api_service.dart';

class DigitalHumanCallScreen extends StatefulWidget {
  const DigitalHumanCallScreen({super.key});

  @override
  State<DigitalHumanCallScreen> createState() => _DigitalHumanCallScreenState();
}

class _DigitalHumanCallScreenState extends State<DigitalHumanCallScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _chatScrollController = ScrollController();

  VideoPlayerController? _silentController;
  VideoPlayerController? _speakingController;
  bool _isSpeaking = false;
  bool _isLoading = true;
  bool _isSending = false;
  bool _isConnected = true;

  int? _callId;
  String? _chatSessionId;
  final List<_DialogMessage> _dialogMessages = [];

  late StreamSubscription<List<ConnectivityResult>> _connectivitySub;

  String _silentVideoUrl = '';
  String _speakingVideoUrl = '';

  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

    _connectivitySub = Connectivity().onConnectivityChanged.listen((results) {
      final connected = results.any((r) => r != ConnectivityResult.none);
      if (mounted && _isConnected != connected) {
        setState(() => _isConnected = connected);
        if (!connected) {
          _addSystemMessage('网络已断开，请检查网络连接');
        } else {
          _addSystemMessage('网络已恢复');
        }
      }
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map) {
        _chatSessionId = args['sessionId']?.toString();
      }
      _startCall();
    });
  }

  Future<void> _startCall() async {
    try {
      final response = await _apiService.startVoiceCall(
        chatSessionId: _chatSessionId,
      );
      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = response.data['data'] ?? response.data;
        _callId = data['id'];

        _silentVideoUrl = data['silent_video_url']?.toString() ?? '';
        _speakingVideoUrl = data['speaking_video_url']?.toString() ?? '';

        if (_silentVideoUrl.isNotEmpty) {
          await _initVideoControllers();
        }

        setState(() => _isLoading = false);
        _addSystemMessage('通话已连接');
      } else {
        setState(() => _isLoading = false);
        _addSystemMessage('连接失败，请重试');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      _addSystemMessage('连接失败，请检查网络');
    }
  }

  Future<void> _initVideoControllers() async {
    if (_silentVideoUrl.isNotEmpty) {
      _silentController = VideoPlayerController.networkUrl(Uri.parse(_silentVideoUrl));
      await _silentController!.initialize();
      _silentController!.setLooping(true);
      _silentController!.setVolume(0);
      _silentController!.play();
    }

    if (_speakingVideoUrl.isNotEmpty) {
      _speakingController = VideoPlayerController.networkUrl(Uri.parse(_speakingVideoUrl));
      await _speakingController!.initialize();
      _speakingController!.setLooping(true);
      _speakingController!.setVolume(0);
    }

    if (mounted) setState(() {});
  }

  void _switchToSpeaking() {
    if (_speakingController == null || !_speakingController!.value.isInitialized) return;
    _silentController?.pause();
    _speakingController!.play();
    if (mounted) setState(() => _isSpeaking = true);
  }

  void _switchToSilent() {
    _speakingController?.pause();
    _silentController?.play();
    if (mounted) setState(() => _isSpeaking = false);
  }

  void _addSystemMessage(String text) {
    setState(() {
      _dialogMessages.add(_DialogMessage(role: 'system', content: text));
    });
    _scrollChatToBottom();
  }

  void _scrollChatToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_chatScrollController.hasClients) {
        _chatScrollController.animateTo(
          _chatScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage() async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _isSending || _callId == null) return;

    _inputController.clear();
    setState(() {
      _dialogMessages.add(_DialogMessage(role: 'user', content: text));
      _isSending = true;
    });
    _scrollChatToBottom();

    try {
      final response = await _apiService.sendVoiceCallMessage(_callId!, text);

      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = response.data['data'] ?? response.data;
        final aiText = data['ai_text']?.toString() ?? '';

        if (aiText.isNotEmpty) {
          _switchToSpeaking();
          setState(() {
            _dialogMessages.add(_DialogMessage(role: 'assistant', content: aiText));
          });
          _scrollChatToBottom();

          final wordCount = aiText.length;
          final speakDuration = Duration(milliseconds: (wordCount * 180).clamp(2000, 15000));
          Future.delayed(speakDuration, () {
            if (mounted) _switchToSilent();
          });
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _dialogMessages.add(_DialogMessage(
            role: 'assistant',
            content: '抱歉，网络异常，请稍后重试',
          ));
        });
        _scrollChatToBottom();
      }
    }

    if (mounted) setState(() => _isSending = false);
  }

  Future<void> _endCall() async {
    if (_callId != null) {
      final dialogContent = _dialogMessages
          .where((m) => m.role != 'system')
          .map((m) => {'role': m.role, 'content': m.content})
          .toList();
      try {
        await _apiService.endVoiceCall(_callId!, dialogContent: dialogContent);
      } catch (_) {}
    }

    _silentController?.dispose();
    _speakingController?.dispose();

    if (mounted) {
      SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
      Navigator.of(context).pop();
    }
  }

  @override
  void dispose() {
    _connectivitySub.cancel();
    _inputController.dispose();
    _chatScrollController.dispose();
    _silentController?.dispose();
    _speakingController?.dispose();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      backgroundColor: Colors.black,
      body: _isLoading ? _buildLoadingView() : _buildCallView(),
    );
  }

  Widget _buildLoadingView() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: Color(0xFF52C41A)),
          SizedBox(height: 20),
          Text(
            '正在连接数字人...',
            style: TextStyle(color: Colors.white70, fontSize: 16),
          ),
        ],
      ),
    );
  }

  Widget _buildCallView() {
    return Stack(
      fit: StackFit.expand,
      children: [
        _buildVideoBackground(),
        _buildGradientOverlay(),
        if (!_isConnected) _buildNetworkBanner(),
        _buildTopBar(),
        _buildChatArea(),
        _buildBottomControls(),
      ],
    );
  }

  Widget _buildVideoBackground() {
    final controller = _isSpeaking ? _speakingController : _silentController;
    if (controller == null || !controller.value.isInitialized) {
      return Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF1A3A2A), Color(0xFF0D1F15)],
          ),
        ),
        child: const Center(
          child: Icon(Icons.person, size: 120, color: Colors.white24),
        ),
      );
    }

    return SizedBox.expand(
      child: FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(
          width: controller.value.size.width,
          height: controller.value.size.height,
          child: VideoPlayer(controller),
        ),
      ),
    );
  }

  Widget _buildGradientOverlay() {
    return IgnorePointer(
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Colors.black.withOpacity(0.3),
              Colors.transparent,
              Colors.transparent,
              Colors.black.withOpacity(0.7),
            ],
            stops: const [0.0, 0.2, 0.5, 1.0],
          ),
        ),
      ),
    );
  }

  Widget _buildNetworkBanner() {
    return Positioned(
      top: MediaQuery.of(context).padding.top + 50,
      left: 0,
      right: 0,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 40),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.red.withOpacity(0.85),
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.wifi_off, color: Colors.white, size: 16),
            SizedBox(width: 8),
            Text('网络已断开', style: TextStyle(color: Colors.white, fontSize: 13)),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Positioned(
      top: MediaQuery.of(context).padding.top + 8,
      left: 16,
      right: 16,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          GestureDetector(
            onTap: _endCall,
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.3),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.arrow_back, color: Colors.white, size: 22),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.black.withOpacity(0.3),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: _isConnected ? const Color(0xFF52C41A) : Colors.red,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  _isSpeaking ? '对方说话中...' : '通话中',
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
              ],
            ),
          ),
          const SizedBox(width: 38),
        ],
      ),
    );
  }

  Widget _buildChatArea() {
    return Positioned(
      left: 0,
      right: 0,
      bottom: 130,
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.35,
        child: ShaderMask(
          shaderCallback: (Rect rect) {
            return const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Colors.transparent, Colors.white],
              stops: [0.0, 0.15],
            ).createShader(rect);
          },
          blendMode: BlendMode.dstIn,
          child: ListView.builder(
            controller: _chatScrollController,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            itemCount: _dialogMessages.length,
            itemBuilder: (context, index) {
              final msg = _dialogMessages[index];
              return _buildDialogBubble(msg);
            },
          ),
        ),
      ),
    );
  }

  Widget _buildDialogBubble(_DialogMessage msg) {
    if (msg.role == 'system') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              msg.content,
              style: const TextStyle(color: Colors.white60, fontSize: 12),
            ),
          ),
        ),
      );
    }

    final isUser = msg.role == 'user';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser)
            Container(
              width: 28,
              height: 28,
              margin: const EdgeInsets.only(right: 8),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
                ),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.smart_toy, color: Colors.white, size: 16),
            ),
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser
                    ? const Color(0xFF52C41A).withOpacity(0.85)
                    : Colors.white.withOpacity(0.15),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(14),
                  topRight: const Radius.circular(14),
                  bottomLeft: Radius.circular(isUser ? 14 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 14),
                ),
              ),
              child: Text(
                msg.content,
                style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.4),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomControls() {
    return Positioned(
      left: 0,
      right: 0,
      bottom: 0,
      child: Container(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 12,
          bottom: MediaQuery.of(context).padding.bottom + 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: Colors.white.withOpacity(0.2)),
                    ),
                    child: TextField(
                      controller: _inputController,
                      style: const TextStyle(color: Colors.white, fontSize: 15),
                      decoration: InputDecoration(
                        hintText: '输入消息...',
                        hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                GestureDetector(
                  onTap: _isSending ? null : _sendMessage,
                  child: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: _isSending
                          ? Colors.grey.withOpacity(0.5)
                          : const Color(0xFF52C41A),
                      shape: BoxShape.circle,
                    ),
                    child: _isSending
                        ? const Padding(
                            padding: EdgeInsets.all(12),
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.send, color: Colors.white, size: 20),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            GestureDetector(
              onTap: _endCall,
              child: Container(
                width: 60,
                height: 60,
                decoration: const BoxDecoration(
                  color: Colors.red,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.red,
                      blurRadius: 12,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: const Icon(Icons.call_end, color: Colors.white, size: 28),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DialogMessage {
  final String role;
  final String content;

  _DialogMessage({required this.role, required this.content});
}
