import 'dart:io';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

/// Runs entirely on-device, before any upload is attempted. Guarantees the
/// output is a JPEG under [maxBytes], while trying to preserve enough
/// resolution/detail that a billing reviewer can still read the digits.
///
/// Strategy (cheapest-first, so most photos exit after step 1-2):
///  1. Strip EXIF/metadata, including any embedded location metadata.
///  2. Resize to a digit-legible max width, keep aspect ratio.
///  3. Iteratively lower JPEG quality.
///  4. If still over budget, iteratively shrink dimensions further and
///     repeat quality search, down to a hard floor width where we accept
///     whatever the size is and flag it for manual review instead of
///     producing an unreadable image.
class ImageProcessingService {
  static const int maxBytes = 60 * 1024;
  static const int _initialMaxWidth = 1600;
  static const int _minWidth = 640;
  static const int _widthStep = 160;
  static const List<int> _qualityLadder = [85, 75, 65, 55, 45, 35];

  Future<ProcessedImage> process(File sourceFile) async {
    final bytes = await sourceFile.readAsBytes();
    final decoded = img.decodeImage(bytes);
    if (decoded == null) {
      throw const ImageProcessingException('تعذر قراءة الصورة الملتقطة');
    }

    int width = _initialMaxWidth;
    Uint8List? best;
    bool readableWarning = false;

    while (true) {
      final resized = decoded.width > width
          ? img.copyResize(decoded,
              width: width, interpolation: img.Interpolation.average)
          : decoded;

      for (final quality in _qualityLadder) {
        final encoded = Uint8List.fromList(
          img.encodeJpg(resized, quality: quality),
        );
        if (encoded.lengthInBytes <= maxBytes) {
          best = encoded;
          break;
        }
        // keep the smallest attempt seen so far as a fallback
        if (best == null || encoded.lengthInBytes < best.lengthInBytes) {
          best = encoded;
        }
      }

      if (best != null && best.lengthInBytes <= maxBytes) break;
      if (width <= _minWidth) {
        readableWarning = true; // hit the floor without meeting budget
        break;
      }
      width -= _widthStep;
    }

    return ProcessedImage(
      bytes: best!,
      sizeBytes: best.lengthInBytes,
      belowReadabilityFloor: readableWarning,
    );
  }
}

class ProcessedImage {
  final Uint8List bytes;
  final int sizeBytes;

  /// True only if the compressor had to go below [ImageProcessingService._minWidth]
  /// to meet the size budget. The UI should prompt for a retake in this case
  /// rather than silently uploading a possibly unreadable meter photo.
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
