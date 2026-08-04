import 'dart:convert';
import 'dart:io';

import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meter_reading_app/core/sync/reading_archive_builder.dart';
import 'package:meter_reading_app/features/readings/domain/reading.dart';

void main() {
  test('splits archives and maps images using stable UUIDs', () async {
    final directory = await Directory.systemTemp.createTemp('reading_archive_');
    addTearDown(() => directory.delete(recursive: true));

    final firstImage =
        File('${directory.path}${Platform.pathSeparator}one.jpg');
    final secondImage =
        File('${directory.path}${Platform.pathSeparator}two.jpg');
    await firstImage.writeAsBytes([1, 2, 3]);
    await secondImage.writeAsBytes([4, 5, 6]);

    final builder = ReadingArchiveBuilder();
    final archives = await builder.build(
      destination: directory,
      policy: const SyncBatchPolicy(
        maxImagesPerArchive: 1,
        maxArchiveBytes: 1024,
        maxImageBytes: 60 * 1024,
      ),
      items: [
        ArchiveReadingItem(
          cycleId: 7,
          customerId: 11,
          meterNumber: 'MTR-1',
          reading: MeterReading(
            id: 'reading-one',
            photoUuid: 'photo-one',
            meterRemoteId: 21,
            readingValue: 100,
            readingDate: DateTime.utc(2026, 8, 4),
            imageLocalPath: firstImage.path,
          ),
        ),
        ArchiveReadingItem(
          cycleId: 7,
          customerId: 12,
          meterNumber: 'MTR-2',
          reading: MeterReading(
            id: 'reading-two',
            photoUuid: 'photo-two',
            meterRemoteId: 22,
            readingValue: 200,
            readingDate: DateTime.utc(2026, 8, 4),
            imageLocalPath: secondImage.path,
          ),
        ),
      ],
    );

    expect(archives, hasLength(2));
    final decoded = ZipDecoder().decodeBytes(
      await archives.first.archiveFile.readAsBytes(),
    );
    final manifestFile = decoded.findFile('manifest.json');
    final manifest =
        jsonDecode(utf8.decode(manifestFile!.content as List<int>));

    expect(manifest['readings'].single['client_uuid'], 'reading-one');
    expect(manifest['readings'].single['photo_uuid'], 'photo-one');
    expect(decoded.findFile('images/photo-one.jpg'), isNotNull);
    expect(manifest.toString(), isNot(contains('gps')));
  });
}
