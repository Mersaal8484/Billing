import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../app/providers.dart';
import '../../../app/theme/app_theme.dart';

/// Captures a meter photo, then runs it through [ImageProcessingService]
/// before handing a *local* file path back to the caller.
class PhotoCaptureScreen extends ConsumerStatefulWidget {
  const PhotoCaptureScreen({super.key});
  @override
  ConsumerState<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends ConsumerState<PhotoCaptureScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  Future<void>? _initFuture;
  String? _capturedPath;
  int? _processedSizeBytes;
  bool _processing = false;
  bool _readabilityWarning = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initFuture = _initCamera();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final CameraController? cameraController = _controller;
    if (cameraController == null || !cameraController.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      cameraController.dispose();
      _controller = null;
    } else if (state == AppLifecycleState.resumed) {
      _initFuture = _initCamera();
    }
  }

  Future<void> _initCamera() async {
    try {
      // 1. Explicitly request camera permission first
      final status = await Permission.camera.request();
      if (status.isDenied || status.isPermanentlyDenied) {
        if (mounted) {
          setState(
              () => _error = 'صلاحية الكاميرا مطلوبة لالتقاط قراءة العداد.');
        }
        return;
      }

      // 2. Fetch cameras
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        if (mounted) {
          setState(() => _error = 'لا توجد كاميرا متاحة على هذا الجهاز.');
        }
        return;
      }

      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      // 3. Initialize controller (fallback to medium resolution if high fails)
      final newController =
          CameraController(back, ResolutionPreset.medium, enableAudio: false);
      await newController.initialize();

      if (mounted) {
        setState(() {
          _controller = newController;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'تعذر تشغيل الكاميرا: $e');
      }
    }
  }

  Future<void> _capture() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    try {
      setState(() => _processing = true);
      final xfile = await controller.takePicture();

      final processor = ref.read(imageProcessingServiceProvider);
      final result = await processor.process(File(xfile.path));

      final dir = await getApplicationDocumentsDirectory();
      final destPath = p.join(
          dir.path, 'readings', '${DateTime.now().microsecondsSinceEpoch}.jpg');
      final destFile = File(destPath);
      await destFile.create(recursive: true);
      await destFile.writeAsBytes(result.bytes);

      if (mounted) {
        setState(() {
          _capturedPath = destPath;
          _processedSizeBytes = result.sizeBytes;
          _readabilityWarning = result.belowReadabilityFloor;
          _processing = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _processing = false;
          _error = 'فشل التقاط الصورة: $e';
        });
      }
    }
  }

  void _retake() {
    setState(() {
      _capturedPath = null;
      _processedSizeBytes = null;
      _readabilityWarning = false;
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: const Text('تصوير العداد'),
      ),
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(_error!,
                        style: const TextStyle(color: Colors.white),
                        textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () {
                        setState(() => _error = null);
                        _initFuture = _initCamera();
                      },
                      child: const Text('إعادة المحاولة'),
                    )
                  ],
                ),
              ),
            )
          : _capturedPath != null
              ? _buildReview()
              : _buildLiveCamera(),
    );
  }

  Widget _buildLiveCamera() {
    return FutureBuilder(
      future: _initFuture,
      builder: (context, snapshot) {
        final controller = _controller;
        if (controller == null || !controller.value.isInitialized) {
          return const Center(
              child: CircularProgressIndicator(color: Colors.white));
        }

        // Properly constrain the CameraPreview to avoid black screens on some devices
        final size = MediaQuery.of(context).size;
        final deviceRatio = size.width / size.height;
        // CameraPreview requires its parent to constrain it.
        // We use Transform.scale to fill the screen without letterboxing.
        return Stack(
          fit: StackFit.expand,
          children: [
            Center(
              child: Transform.scale(
                scale: controller.value.aspectRatio / deviceRatio,
                child: Center(
                  child: AspectRatio(
                    aspectRatio: controller.value.aspectRatio,
                    child: CameraPreview(controller),
                  ),
                ),
              ),
            ),
            // Framing guide
            Center(
              child: Container(
                width: size.width * 0.75,
                height: 140,
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.white70, width: 2),
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Text(
                'ضع أرقام العداد داخل الإطار',
                textAlign: TextAlign.center,
                style: TextStyle(
                    color: Colors.white,
                    backgroundColor: Colors.black.withValues(alpha: 0.4)),
              ),
            ),
            Positioned(
              bottom: 32,
              left: 0,
              right: 0,
              child: Center(
                child: _processing
                    ? const CircularProgressIndicator(color: Colors.white)
                    : GestureDetector(
                        onTap: _capture,
                        child: Container(
                          width: 76,
                          height: 76,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 4),
                          ),
                        ),
                      ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildReview() {
    return Column(
      children: [
        Expanded(child: Image.file(File(_capturedPath!), fit: BoxFit.contain)),
        if (_readabilityWarning)
          Container(
            width: double.infinity,
            color: StatusColors.error.withValues(alpha: 0.15),
            padding: const EdgeInsets.all(12),
            child: const Text(
              'تحذير: قد تكون الصورة غير واضحة بما يكفي لقراءة الأرقام. يُفضّل إعادة التصوير.',
              style: TextStyle(color: Colors.white),
              textAlign: TextAlign.center,
            ),
          ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Text(
                  '${((_processedSizeBytes ?? 0) / 1024).toStringAsFixed(1)} KB',
                  style: const TextStyle(color: Colors.white70)),
              const Spacer(),
              OutlinedButton(
                onPressed: _retake,
                style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: Colors.white54)),
                child: const Text('إعادة التصوير'),
              ),
              const SizedBox(width: 12),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(_capturedPath),
                child: const Text('استخدام الصورة'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
