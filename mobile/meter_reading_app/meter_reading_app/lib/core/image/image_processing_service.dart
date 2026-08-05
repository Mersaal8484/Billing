import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show compute;
import 'package:image/image.dart' as img;

// ---------------------------------------------------------------------------
// Transfer object for compute() — must be serialisable across Isolate boundary
// ---------------------------------------------------------------------------
class _ProcessArgs {
  final Uint8List bytes;
  const _ProcessArgs(this.bytes);
}

class _ProcessResult {
  final Uint8List bytes;
  final int sizeBytes;
  final bool belowReadabilityFloor;
  final int encodeAttempts;   // for debug logging; remove in prod if desired
  final int elapsedMs;        // Stopwatch measurement inside the Isolate
  const _ProcessResult({
    required this.bytes,
    required this.sizeBytes,
    required this.belowReadabilityFloor,
    required this.encodeAttempts,
    required this.elapsedMs,
  });
}

// ---------------------------------------------------------------------------
// Top-level function — required by compute() (must NOT be a closure or method)
// ---------------------------------------------------------------------------
_ProcessResult _processInIsolate(_ProcessArgs args) {
  final sw = Stopwatch()..start();

  // --- 1. Decode (strips EXIF/GPS automatically when re-encoding as JPEG) ---
  final decoded = img.decodeImage(args.bytes);
  if (decoded == null) {
    throw const ImageProcessingException('تعذر قراءة الصورة الملتقطة');
  }

  const int maxBytes     = ImageProcessingService.maxBytes;
  const int initialWidth = ImageProcessingService.initialMaxWidth;
  const int minWidth     = ImageProcessingService.minWidth;

  // --- 2. Pre-shrink: if original is far larger than initialWidth, shrink
  //        first with linear interpolation (faster than average) to reduce
  //        the cost of every subsequent encodeJpg call. ---
  img.Image working;
  if (decoded.width > initialWidth) {
    working = img.copyResize(
      decoded,
      width: initialWidth,
      interpolation: img.Interpolation.linear, // faster than average; fine for digits
    );
  } else {
    working = decoded;
  }

  // --- 3. Adaptive compression: ≤ 3 encodeJpg calls in the normal path ---
  //
  // Probe at quality=75 on the pre-shrunk image. Use the ratio
  //   r = probeSize / maxBytes
  // to derive a quality or width adjustment in one step, rather than
  // iterating through a fixed ladder exhaustively.
  //
  // Rounds needed (worst case): probe → adjust → verify = 3 calls.

  Uint8List? best;
  bool belowFloor = false;
  int attempts = 0;

  Uint8List _encode(img.Image image, int quality) {
    attempts++;
    return Uint8List.fromList(img.encodeJpg(image, quality: quality));
  }

  // Probe
  final probe = _encode(working, 75);

  if (probe.lengthInBytes <= maxBytes) {
    // Lucky — already within budget on first try.
    best = probe;
  } else {
    // Estimate required quality adjustment using linear approximation:
    //   newQuality ≈ 75 × (maxBytes / probeSize)
    // Clamp to [30, 70] so we don't overshoot in either direction.
    final ratio     = maxBytes / probe.lengthInBytes;
    final estQ      = (75 * ratio).clamp(30.0, 70.0).toInt();

    final attempt2 = _encode(working, estQ);
    best = attempt2; // always keep best seen

    if (attempt2.lengthInBytes > maxBytes) {
      // Still over budget → shrink dimensions by ~30 % and try one more time.
      final narrowW = (working.width * 0.7).clamp(minWidth.toDouble(), initialWidth.toDouble()).toInt();
      if (narrowW < working.width) {
        final narrowed = img.copyResize(
          working,
          width: narrowW,
          interpolation: img.Interpolation.linear,
        );
        final attempt3 = _encode(narrowed, estQ);
        if (attempt3.lengthInBytes < best!.lengthInBytes) best = attempt3;

        // Accept regardless; flag warning if still over budget or too narrow.
        if (attempt3.lengthInBytes > maxBytes || narrowW <= minWidth) {
          belowFloor = true;
        }
      } else {
        belowFloor = true; // already at min width, can't shrink further
      }
    }
  }

  sw.stop();

  return _ProcessResult(
    bytes:                best!,
    sizeBytes:            best!.lengthInBytes,
    belowReadabilityFloor: belowFloor,
    encodeAttempts:       attempts,
    elapsedMs:            sw.elapsedMilliseconds,
  );
}

// ---------------------------------------------------------------------------
// Public service (thin wrapper — all heavy work runs in a separate Isolate)
// ---------------------------------------------------------------------------

/// Compresses a meter-reading photo entirely off the UI Isolate via
/// [compute()].  Guarantees:
///  • No UI jank — the main thread is never blocked by image I/O.
///  • ≤ 3 encodeJpg calls in the normal path (adaptive, not brute-force).
///  • EXIF / GPS stripped (JPEG re-encode discards original metadata).
///  • Output ≤ [maxBytes] with a readability warning when impossible.
class ImageProcessingService {
  static const int maxBytes      = 80 * 1024;   // 80 KB (updated from 60 KB)
  static const int initialMaxWidth = 1600;
  static const int minWidth      = 640;

  Future<ProcessedImage> process(File sourceFile) async {
    // Read bytes on this isolate (fast I/O, no decoding yet).
    final rawBytes = await sourceFile.readAsBytes();

    // Run all CPU-intensive work in a separate Dart Isolate.
    final result = await compute(_processInIsolate, _ProcessArgs(rawBytes));

    // Debug output (visible in flutter logs; harmless in release builds).
    assert(() {
      // ignore: avoid_print
      print('[ImageProcessingService] '
          'attempts=${result.encodeAttempts}  '
          'elapsed=${result.elapsedMs}ms  '
          'size=${(result.sizeBytes / 1024).toStringAsFixed(1)}KB  '
          'floor=${result.belowReadabilityFloor}');
      return true;
    }());

    return ProcessedImage(
      bytes:                result.bytes,
      sizeBytes:            result.sizeBytes,
      belowReadabilityFloor: result.belowReadabilityFloor,
    );
  }
}

// ---------------------------------------------------------------------------
// Value types
// ---------------------------------------------------------------------------

class ProcessedImage {
  final Uint8List bytes;
  final int sizeBytes;

  /// True when the compressor could not meet [ImageProcessingService.maxBytes]
  /// without dropping below [ImageProcessingService.minWidth].  The UI should
  /// prompt the user to retake the photo in this case.
  final bool belowReadabilityFloor;

  const ProcessedImage({
    required this.bytes,
    required this.sizeBytes,
    required this.belowReadabilityFloor,
  });
}

class ImageProcessingException implements Exception {
  final String message;
  const ImageProcessingException(this.message);
  @override
  String toString() => message;
}
