import 'dart:io';

import 'package:dio/dio.dart';

import 'odoo_api_client.dart';

/// One meter reading item as expected inside `data.readings[]` by
/// `utility.reading.batch.service.process_batch` — field names and
/// defaults are matched exactly to the server-side parsing logic.
class MeterReadingPayload {
  /// Authoritative Odoo `utility.meter` identifier. This remains available
  /// even for readings that were captured offline and restored from Drift.
  final int meterId;

  /// Optional human-readable meter number for display and audit. The server
  /// uses [meterId] as the authoritative identifier when both are provided.
  final String? meterNumber;

  /// Existing rejected `utility.reading` to correct and return for review.
  /// A non-null value never creates a second reading for the same period.
  final int? resubmitReadingId;

  /// The reading value itself. Defaults to 0.0 server-side if omitted,
  /// but always send it explicitly.
  final double readingValue;

  /// ISO-8601 datetime string. Defaults to "now" server-side if omitted.
  final DateTime? readingDate;

  /// Defaults to 'customer' server-side.
  final String? readingCategory;

  /// Defaults to 'periodic' server-side.
  final String? readingPurpose;

  /// Client-generated uuid for this reading (use the same id as your
  /// local Drift `Reading.id`). Pass the SAME value as `reading_uuid`
  /// when calling [ReadingApiService.uploadImageMultipart] for this
  /// reading's photo — that's how the server links image <-> reading.
  final String? clientReadingUuid;

  /// Alternative link: the `asset_uuid` returned directly by the
  /// multipart image upload response, if you already have it.
  final String? assetUuid;

  /// Legacy fallback link by filename — prefer [clientReadingUuid].
  final String? imageFilename;

  final int? seq;

  const MeterReadingPayload({
    required this.meterId,
    this.meterNumber,
    this.resubmitReadingId,
    required this.readingValue,
    this.readingDate,
    this.readingCategory,
    this.readingPurpose,
    this.clientReadingUuid,
    this.assetUuid,
    this.imageFilename,
    this.seq,
  });

  Map<String, dynamic> toJson() => {
        'meter_id': meterId,
        if (meterNumber?.isNotEmpty == true) 'meter_number': meterNumber,
        if (resubmitReadingId != null)
          'resubmit_reading_id': resubmitReadingId,
        'reading_value': readingValue,
        if (readingDate != null)
          'reading_date': readingDate!.toIso8601String(),
        if (readingCategory != null) 'reading_category': readingCategory,
        if (readingPurpose != null) 'reading_purpose': readingPurpose,
        if (clientReadingUuid != null)
          'client_reading_uuid': clientReadingUuid,
        if (assetUuid != null) 'asset_uuid': assetUuid,
        if (imageFilename != null) 'image_filename': imageFilename,
        if (seq != null) 'seq': seq,
      };
}

/// Wraps the `/api/v1/utility/reading/*` routes found in
/// custom_addons/utility_billing/controllers/utility_reader_api.py
class ReadingApiService {
  final OdooApiClient _client;
  ReadingApiService(this._client);

  /// Creates a new reading batch on the server, returns the batch id
  /// the server expects you to attach subsequent uploads/images to.
  ///
  /// [dateRangeId] maps to Odoo's `date.range` record (required — this is
  /// the reading period, e.g. "July 2026"). [regionId] and
  /// [totalReadingsHint] are optional.
  Future<Map<String, dynamic>> createBatch({
    required int dateRangeId,
    int? regionId,
    int? totalReadingsHint,
  }) {
    return _client.postJson('/api/v1/utility/reading/batch/create', {
      'date_range_id': dateRangeId,
      if (regionId != null) 'region_id': regionId,
      if (totalReadingsHint != null) 'total_readings': totalReadingsHint,
    });
  }

  /// Uploads the JSON payload of readings for a batch already created via
  /// [createBatch]. The server expects `data` to be a dict shaped like
  /// `{"readings": [...]}` — this wraps it for you. Pass typed
  /// [MeterReadingPayload] items so field names always match the server.
  Future<Map<String, dynamic>> uploadData({
    required int batchId,
    required List<MeterReadingPayload> readings,
  }) {
    return _client.postJson('/api/v1/utility/reading/batch/upload_data', {
      'batch_id': batchId,
      'data': {'readings': readings.map((r) => r.toJson()).toList()},
    });
  }

  /// Uploads a single meter photo as multipart/form-data — this is the
  /// ONLY production-enabled image upload path (the JSON/base64 route is
  /// disabled by default via `utility.media_backend` config).
  ///
  /// This hits the `type='http'` route, so the response is a plain JSON
  /// object (not the JSON-RPC `{result: ...}` envelope), and errors come
  /// back as non-2xx HTTP status codes with a `{success: false, error}`
  /// body — handled here rather than via [OdooApiClient.postJson].
  ///
  /// [readingUuid] lets the server associate this photo with a specific
  /// reading inside the batch (recommended if you track readings by a
  /// client-generated uuid, as your local Drift `Reading.id` already does).
  Future<Map<String, dynamic>> uploadImageMultipart({
    required int batchId,
    required File imageFile,
    String? readingUuid,
    String? filename,
  }) async {
    final formData = FormData.fromMap({
      'batch_id': batchId.toString(),
      if (readingUuid != null) 'reading_uuid': readingUuid,
      if (filename != null) 'filename': filename,
      'file': await MultipartFile.fromFile(
        imageFile.path,
        filename: filename ?? imageFile.uri.pathSegments.last,
      ),
    });

    final response = await _client.dio.post(
      '/api/v1/utility/reading/batch/upload_image_multipart',
      data: formData,
    );

    final body = response.data;
    final map = body is Map<String, dynamic> ? body : <String, dynamic>{};

    final status = response.statusCode ?? 0;
    if (status >= 400 || map['success'] == false) {
      final message = (map['error'] as String?) ??
          'Image upload failed with status $status';
      throw OdooApiException(message, code: status);
    }
    return map;
  }

  /// Confirms a batch after data + images are uploaded. This is what
  /// hands the batch off to the server-side cron for processing — the
  /// batch must be in `state == 'uploaded'` before this point, and
  /// nothing can be added to it after confirming.
  Future<Map<String, dynamic>> confirmBatch(int batchId) {
    return _client.postJson('/api/v1/utility/reading/batch/confirm', {
      'batch_id': batchId,
    });
  }

  /// Polls the processing status of a submitted batch.
  Future<Map<String, dynamic>> getBatchStatus(int batchId) {
    return _client.postJson('/api/v1/utility/reading/batch/status', {
      'batch_id': batchId,
    });
  }

  /// Returns up to 12 recent billing-eligible periods, each with an
  /// `is_current` flag. Use [getCurrentPeriodId] for automatic selection.
  Future<Map<String, dynamic>> getReadingPeriods() {
    return _client.postJson('/api/v1/utility/reading/periods', {});
  }

  /// Convenience wrapper: fetches periods and returns the `date_range_id`
  /// of the one flagged `is_current == true`. Falls back to the most
  /// recent period (first in the list, since server orders by
  /// `date_start desc`) if none is explicitly marked current.
  /// Throws [OdooApiException] if the server returns no periods at all
  /// (e.g. no open reading period configured for the collector's region).
  Future<int> getCurrentPeriodId() async {
    final result = await getReadingPeriods();
    final periods = (result['periods'] as List?) ?? const [];
    if (periods.isEmpty) {
      throw OdooApiException(
        'No open reading period available for this collector/region',
      );
    }
    final current = periods.cast<Map<String, dynamic>>().firstWhere(
          (p) => p['is_current'] == true,
          orElse: () => periods.first as Map<String, dynamic>,
        );
    return current['id'] as int;
  }

  Future<Map<String, dynamic>> lookupMeter(String meterCode) {
    return _client.postJson('/api/v1/utility/reading/meter/lookup', {
      'meter_code': meterCode,
    });
  }

  /// Lists batches created by the currently authenticated collector.
  Future<Map<String, dynamic>> myBatches() {
    return _client.postJson('/api/v1/utility/reading/batch/my', {});
  }
}
