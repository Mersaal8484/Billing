import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

part 'app_database.g.dart';

/// Mirrors utility.customer (utility_core). Local cache, refreshed on
/// assignment sync. `remoteId` is the authoritative Odoo record id.
class Customers extends Table {
  IntColumn get remoteId => integer()();
  TextColumn get accountNumber => text()();
  TextColumn get name => text()();
  TextColumn get address => text().nullable()();
  IntColumn get routeId => integer().nullable()();
  DateTimeColumn get lastReadingDate => dateTime().nullable()();
  RealColumn get lastReadingValue => real().nullable()();
  DateTimeColumn get lastSyncedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {remoteId};
}

/// Mirrors utility.meter (utility_core).
class Meters extends Table {
  IntColumn get remoteId => integer()();
  TextColumn get meterNumber => text()();
  TextColumn get serialNumber => text().nullable()();
  IntColumn get customerRemoteId =>
      integer().references(Customers, #remoteId)();
  TextColumn get meterType => text().nullable()();
  TextColumn get paymentType => text()(); // postpaid | prepaid | manual
  TextColumn get communicationType => text().nullable()();
  IntColumn get routeId => integer().nullable()();
  BoolColumn get isCouplingMeter =>
      boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {remoteId};
}

/// A reader's assignment for the active billing period — the working set
/// downloaded before going offline into the field. Mirrors what
/// utility.route + date.range imply for "who reads what, this period".
class Assignments extends Table {
  TextColumn get id => text()(); // uuid, local
  IntColumn get meterRemoteId => integer().references(Meters, #remoteId)();
  IntColumn get periodId => integer()(); // date.range id
  TextColumn get status =>
      text().withDefault(const Constant('pending'))(); // pending|read|skipped
  DateTimeColumn get downloadedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Local billing periods cache, mirrors date.range (type_id.billing_period=true).
class Periods extends Table {
  IntColumn get id => integer()();
  TextColumn get name => text()();
  DateTimeColumn get dateStart => dateTime().nullable()();
  DateTimeColumn get dateEnd => dateTime().nullable()();
  BoolColumn get isCurrent => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}

/// Local draft/synced meter readings. This is the primary working record —
/// created offline, then synced via Pipeline A. Field set mirrors
/// utility.reading's STATE_EDITABLE contract on the ERP side so that
/// nothing captured here becomes unwritable once uploaded.
class Readings extends Table {
  TextColumn get id => text()(); // uuid, local primary key
  IntColumn get remoteId =>
      integer().nullable()(); // set once ERP creates utility.reading
  IntColumn get meterRemoteId => integer().references(Meters, #remoteId)();
  RealColumn get readingValue => real()();
  DateTimeColumn get readingDate => dateTime()();
  TextColumn get readingCategory =>
      text().withDefault(const Constant('customer'))();
  BoolColumn get isEstimated => boolean().withDefault(const Constant(false))();
  TextColumn get remarks => text().nullable()();
  TextColumn get imageLocalPath =>
      text().nullable()(); // processed JPEG, local disk
  TextColumn get imageSecondaryLocalPath => text().nullable()();
  IntColumn get imageAttachmentRemoteId =>
      integer().nullable()(); // ir.attachment id once uploaded
  TextColumn get syncStatus => text().withDefault(const Constant('draft'))();
  // draft -> pending_data_sync -> data_synced -> pending_image_sync -> synced -> error
  IntColumn get dataSyncAttempts => integer().withDefault(const Constant(0))();
  IntColumn get imageSyncAttempts => integer().withDefault(const Constant(0))();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Pipeline A — reading-data sync queue. Independent from image uploads,
/// highest priority, small payloads, near-immediate flush.
class SyncQueueItems extends Table {
  TextColumn get id => text()();
  TextColumn get readingId => text().references(Readings, #id)();
  TextColumn get status => text().withDefault(const Constant('pending'))();
  // pending | in_progress | success | failed
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get enqueuedAt => dateTime()();
  DateTimeColumn get lastAttemptAt => dateTime().nullable()();
  TextColumn get idempotencyKey => text()(); // stable across retries

  @override
  Set<Column> get primaryKey => {id};
}

/// Pipeline B — image upload queue. Resumable, retry-tolerant, never blocks
/// or is blocked by Pipeline A.
class ImageUploadQueueItems extends Table {
  TextColumn get id => text()();
  TextColumn get readingId => text().references(Readings, #id)();
  TextColumn get localPath => text()();
  IntColumn get sizeBytes => integer()();
  TextColumn get status => text().withDefault(const Constant('pending'))();
  // pending | uploading | success | failed
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get enqueuedAt => dateTime()();
  DateTimeColumn get lastAttemptAt => dateTime().nullable()();
  TextColumn get idempotencyKey => text()();

  @override
  Set<Column> get primaryKey => {id};
}

@DriftDatabase(tables: [
  Customers,
  Meters,
  Assignments,
  Periods,
  Readings,
  SyncQueueItems,
  ImageUploadQueueItems,
])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'meter_reading.sqlite'));
    return NativeDatabase.createInBackground(file);
  });
}
