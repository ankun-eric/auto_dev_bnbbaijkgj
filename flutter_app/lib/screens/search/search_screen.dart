import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import '../../services/api_service.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TextEditingController _controller = TextEditingController();
  final ApiService _apiService = ApiService();
  final AudioRecorder _audioRecorder = AudioRecorder();

  List<dynamic> _hotWords = [];
  List<dynamic> _history = [];
  List<dynamic> _suggestions = [];
  bool _showSuggestions = false;
  bool _loadingHot = true;

  Timer? _debounceTimer;
  Timer? _autoSearchTimer;
  String? _asrResult;
  bool _showAutoSearchHint = false;

  @override
  void initState() {
    super.initState();
    _loadInitialData();
    _controller.addListener(_onInputChanged);
  }

  @override
  void dispose() {
    _controller.dispose();
    _debounceTimer?.cancel();
    _autoSearchTimer?.cancel();
    _audioRecorder.dispose();
    super.dispose();
  }

  Future<void> _loadInitialData() async {
    try {
      final results = await Future.wait([
        _apiService.searchHot().catchError((_) => []),
        _apiService.searchHistory().catchError((_) => []),
      ]);
      if (!mounted) return;
      setState(() {
        _hotWords = results[0];
        _history = results[1];
        _loadingHot = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingHot = false);
    }
  }

  void _onInputChanged() {
    setState(() {}); // 确保搜索栏图标状态即时刷新
    final text = _controller.text.trim();
    _debounceTimer?.cancel();
    if (text.isEmpty) {
      setState(() {
        _suggestions = [];
        _showSuggestions = false;
      });
      return;
    }
    _debounceTimer = Timer(const Duration(milliseconds: 300), () async {
      try {
        final items = await _apiService.searchSuggest(text);
        if (!mounted) return;
        setState(() {
          _suggestions = items;
          _showSuggestions = items.isNotEmpty;
        });
      } catch (_) {}
    });
  }

  void _doSearch(String query, {String source = 'text'}) {
    final q = query.trim();
    if (q.isEmpty) return;
    _cancelAutoSearch();
    Navigator.pushNamed(context, '/search-result', arguments: {'query': q, 'source': source});
  }

  void _onTagTap(String keyword) {
    _controller.text = keyword;
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: keyword.length),
    );
    _doSearch(keyword);
  }

  Future<void> _deleteHistory(int id) async {
    try {
      await _apiService.deleteSearchHistory(id);
      setState(() => _history.removeWhere((e) => e['id'] == id));
    } catch (_) {}
  }

  Future<void> _clearHistory() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认清空'),
        content: const Text('确定要清空所有搜索历史吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _apiService.clearSearchHistory();
      setState(() => _history.clear());
    } catch (_) {}
  }

  // ── Voice Recording ──

  Future<void> _startRecording() async {
    final status = await Permission.microphone.request();
    if (!status.isGranted) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('无法访问麦克风，请在系统设置中开启权限')),
      );
      return;
    }

    if (!mounted) return;
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _VoiceRecordDialog(audioRecorder: _audioRecorder, apiService: _apiService),
    );

    if (result != null && result.isNotEmpty && mounted) {
      _controller.text = result;
      _controller.selection = TextSelection.fromPosition(
        TextPosition(offset: result.length),
      );
      setState(() {
        _asrResult = result;
        _showAutoSearchHint = true;
        _showSuggestions = false;
      });
      _startAutoSearchCountdown(result, source: 'voice');
    }
  }

  void _startAutoSearchCountdown(String query, {String source = 'text'}) {
    _autoSearchTimer?.cancel();
    _autoSearchTimer = Timer(const Duration(seconds: 2), () {
      if (!mounted) return;
      _doSearch(query, source: source);
    });
  }

  void _cancelAutoSearch() {
    _autoSearchTimer?.cancel();
    if (mounted) {
      setState(() {
        _showAutoSearchHint = false;
        _asrResult = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF52C41A),
        titleSpacing: 0,
        title: _buildSearchBar(),
        actions: [
          TextButton(
            onPressed: () => _doSearch(_controller.text),
            child: const Text('搜索', style: TextStyle(color: Colors.white, fontSize: 15)),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_showAutoSearchHint) _buildAutoSearchHint(),
          Expanded(
            child: _showSuggestions ? _buildSuggestions() : _buildMainContent(),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Container(
      height: 38,
      margin: const EdgeInsets.only(left: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(19),
      ),
      child: Row(
        children: [
          const SizedBox(width: 12),
          const Icon(Icons.search, color: Color(0xFF999999), size: 20),
          const SizedBox(width: 6),
          Expanded(
            child: TextField(
              controller: _controller,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onSubmitted: _doSearch,
              decoration: const InputDecoration(
                hintText: '搜索症状、疾病、药品',
                hintStyle: TextStyle(color: Color(0xFF999999), fontSize: 14),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.symmetric(vertical: 8),
              ),
              style: const TextStyle(fontSize: 14),
            ),
          ),
          GestureDetector(
            onTap: _startRecording,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: const Color(0xFF52C41A).withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.mic, color: Color(0xFF52C41A), size: 18),
              ),
            ),
          ),
          if (_controller.text.isNotEmpty) ...[
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () {
                _controller.clear();
                _cancelAutoSearch();
              },
              child: const Padding(
                padding: EdgeInsets.only(right: 4),
                child: Icon(Icons.close, size: 18, color: Color(0xFF999999)),
              ),
            ),
          ],
          const SizedBox(width: 4),
        ],
      ),
    );
  }

  Widget _buildAutoSearchHint() {
    return Container(
      color: const Color(0xFFFFF7E6),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 16, color: Color(0xFFFA8C16)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '识别结果："$_asrResult"，2秒后自动搜索',
              style: const TextStyle(fontSize: 13, color: Color(0xFF333333)),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          GestureDetector(
            onTap: _cancelAutoSearch,
            child: const Text('取消', style: TextStyle(fontSize: 13, color: Color(0xFF52C41A))),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestions() {
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 4),
      itemCount: _suggestions.length,
      separatorBuilder: (_, __) => const Divider(height: 1, indent: 16, endIndent: 16),
      itemBuilder: (context, index) {
        final item = _suggestions[index];
        final text = item is String ? item : (item is Map ? item['keyword']?.toString() ?? '' : item.toString());
        return ListTile(
          dense: true,
          leading: const Icon(Icons.search, size: 18, color: Color(0xFF999999)),
          title: Text(text, style: const TextStyle(fontSize: 14)),
          onTap: () => _onTagTap(text),
        );
      },
    );
  }

  Widget _buildMainContent() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHotSearch(),
          const SizedBox(height: 24),
          _buildHistorySection(),
        ],
      ),
    );
  }

  Widget _buildHotSearch() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('热门搜索', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        if (_loadingHot)
          const Center(child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF52C41A)))
        else if (_hotWords.isEmpty)
          const Text('暂无热门搜索', style: TextStyle(fontSize: 13, color: Color(0xFF999999)))
        else
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: _hotWords.map((item) {
              final text = item is String ? item : (item is Map ? item['keyword']?.toString() ?? '' : item.toString());
              return GestureDetector(
                onTap: () => _onTagTap(text),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF5F5F5),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(text, style: const TextStyle(fontSize: 13, color: Color(0xFF666666))),
                ),
              );
            }).toList(),
          ),
      ],
    );
  }

  Widget _buildHistorySection() {
    if (_history.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('搜索历史', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
            GestureDetector(
              onTap: _clearHistory,
              child: const Icon(Icons.delete_outline, size: 20, color: Color(0xFF999999)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: _history.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final item = _history[index];
            final text = item is Map ? item['keyword']?.toString() ?? '' : item.toString();
            final id = item is Map ? item['id'] : index;
            return ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.history, size: 18, color: Color(0xFF999999)),
              title: Text(text, style: const TextStyle(fontSize: 14, color: Color(0xFF333333))),
              trailing: GestureDetector(
                onTap: () => _deleteHistory(id is int ? id : 0),
                child: const Icon(Icons.close, size: 16, color: Color(0xFF999999)),
              ),
              onTap: () => _onTagTap(text),
            );
          },
        ),
      ],
    );
  }
}

// ── Voice Record Dialog ──

class _VoiceRecordDialog extends StatefulWidget {
  final AudioRecorder audioRecorder;
  final ApiService apiService;

  const _VoiceRecordDialog({required this.audioRecorder, required this.apiService});

  @override
  State<_VoiceRecordDialog> createState() => _VoiceRecordDialogState();
}

class _VoiceRecordDialogState extends State<_VoiceRecordDialog> with TickerProviderStateMixin {
  static const int _maxSeconds = 15;

  int _elapsed = 0;
  Timer? _timer;
  Timer? _amplitudeTimer;
  bool _recording = true;
  bool _recognizing = false;
  String? _error;
  String? _filePath;

  late AnimationController _waveController;
  late Animation<double> _pulseAnimation;
  List<double> _amplitudes = List.filled(7, 0.15);
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    _waveController = AnimationController(vsync: this, duration: const Duration(milliseconds: 750));
    _pulseAnimation = Tween<double>(begin: 0.94, end: 1.06).animate(
      CurvedAnimation(parent: _waveController, curve: Curves.easeInOut),
    );
    _waveController.repeat(reverse: true);
    _startRecording();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _amplitudeTimer?.cancel();
    _waveController.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    try {
      final path = '${DateTime.now().millisecondsSinceEpoch}.m4a';
      await widget.audioRecorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: path,
      );

      _timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) return;
        setState(() => _elapsed++);
        if (_elapsed >= _maxSeconds) {
          _stopAndRecognize();
        }
      });

      _amplitudeTimer = Timer.periodic(const Duration(milliseconds: 150), (_) async {
        try {
          final amp = await widget.audioRecorder.getAmplitude();
          if (!mounted) return;
          final normalized = ((amp.current + 50) / 50).clamp(0.1, 1.0);
          setState(() {
            _amplitudes = List.generate(7, (i) {
              final base = normalized * (0.5 + _random.nextDouble() * 0.5);
              return base.clamp(0.15, 1.0);
            });
          });
        } catch (_) {}
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recording = false;
        _error = '录音启动失败';
      });
    }
  }

  Future<void> _stopAndRecognize() async {
    _timer?.cancel();
    _amplitudeTimer?.cancel();

    if (!mounted) return;

    if (_elapsed < 1) {
      setState(() {
        _recording = false;
        _error = '说话时间太短';
      });
      try { await widget.audioRecorder.stop(); } catch (_) {}
      return;
    }

    try {
      final path = await widget.audioRecorder.stop();
      _filePath = path;
    } catch (_) {}

    if (!mounted) return;
    setState(() {
      _recording = false;
      _recognizing = true;
    });

    await _recognize();
  }

  Future<void> _recognize() async {
    if (_filePath == null || _filePath!.isEmpty) {
      if (!mounted) return;
      setState(() {
        _recognizing = false;
        _error = '录音文件异常';
      });
      return;
    }
    try {
      final result = await widget.apiService.asrRecognize(_filePath!, 'm4a');
      if (!mounted) return;
      if (result['success'] == false) {
        setState(() {
          _recognizing = false;
          _error = result['error']?.toString() ?? '未识别到有效内容，请重试';
        });
        return;
      }
      final asrData = result['data'];
      final rawText = (asrData is Map ? asrData['text']?.toString() : null) ?? result['text']?.toString() ?? '';
      final text = _removePunctuation(rawText);
      if (text.isEmpty) {
        setState(() {
          _recognizing = false;
          _error = '未识别到有效内容，请重试';
        });
        return;
      }
      Navigator.pop(context, text);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recognizing = false;
        _error = '识别失败，请重试';
      });
    }
  }

  static String _removePunctuation(String str) {
    return str
        .replaceAll(
          RegExp(
            r'[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:\x27\x22()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]',
          ),
          '',
        )
        .trim();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: EdgeInsets.zero,
      child: GestureDetector(
        onTap: () {
          if (_recording) {
            _stopAndRecognize();
          } else if (_error != null) {
            Navigator.pop(context);
          }
        },
        child: Container(
          width: double.infinity,
          height: double.infinity,
          color: Colors.black.withOpacity(0.6),
          child: Center(child: _buildContent()),
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_error != null) return _buildError();
    if (_recognizing) return _buildRecognizing();
    return _buildRecording();
  }

  Widget _buildRecording() {
    final remaining = _maxSeconds - _elapsed;
    final isWarning = remaining <= 3;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          height: 100,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: List.generate(7, (i) {
              return AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                width: 6,
                height: 100 * _amplitudes[i],
                margin: const EdgeInsets.symmetric(horizontal: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF52C41A),
                  borderRadius: BorderRadius.circular(3),
                ),
              );
            }),
          ),
        ),
        const SizedBox(height: 20),
        Text(
          '${_elapsed}s / ${_maxSeconds}s',
          style: TextStyle(
            color: isWarning ? Colors.redAccent : Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 24),
        GestureDetector(
          onTap: _stopAndRecognize,
          child: ScaleTransition(
            scale: _pulseAnimation,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                border: Border.all(color: const Color(0xFF52C41A), width: 3),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF52C41A).withOpacity(0.35),
                    blurRadius: 14,
                    spreadRadius: 0,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: const Color(0xFF52C41A),
                      borderRadius: BorderRadius.circular(1),
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    '点我结束~',
                    style: TextStyle(
                      fontSize: 16,
                      color: Color(0xFF52C41A),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRecognizing() {
    return const Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircularProgressIndicator(color: Color(0xFF52C41A), strokeWidth: 3),
        SizedBox(height: 20),
        Text('正在识别...', style: TextStyle(color: Colors.white, fontSize: 16)),
      ],
    );
  }

  Widget _buildError() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
        const SizedBox(height: 16),
        Text(_error!, style: const TextStyle(color: Colors.white, fontSize: 16)),
        const SizedBox(height: 20),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭', style: TextStyle(color: Colors.white70, fontSize: 14)),
            ),
            const SizedBox(width: 24),
            TextButton(
              onPressed: () {
                setState(() {
                  _error = null;
                  _recording = true;
                  _elapsed = 0;
                  _amplitudes = List.filled(7, 0.15);
                });
                _startRecording();
              },
              child: const Text('重试', style: TextStyle(color: Color(0xFF52C41A), fontSize: 14)),
            ),
          ],
        ),
      ],
    );
  }
}
