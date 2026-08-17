import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/database/app_database.dart';
import '../core/image/image_processing_service.dart';
import '../core/network/auth_service.dart';
import '../core/network/billing_api_service.dart';
import '../core/network/odoo_api_client.dart';
import '../core/network/reading_api_service.dart';
import '../core/printing/thermal_printer_service.dart';
import '../core/sync/sync_engine.dart';
import '../core/sync/sync_settings_service.dart';
import '../features/collections/data/mock_collection_repository.dart';
import '../features/collections/domain/collection_models.dart';
import '../features/customers/data/mock_assignment_repository.dart' show AssignmentRepository;
import '../features/customers/data/odoo_assignment_repository.dart';
import '../features/customers/domain/entities.dart';
import '../features/readings/data/drift_reading_repository.dart';
import '../features/readings/domain/reading.dart';

final odooApiClientProvider = Provider<OdooApiClient>((ref) {
  throw UnimplementedError('odooApiClientProvider must be overridden in main.dart.');
});

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.watch(odooApiClientProvider));
});

final readingApiServiceProvider = Provider<ReadingApiService>((ref) {
  return ReadingApiService(ref.watch(odooApiClientProvider));
});

final billingApiServiceProvider = Provider<BillingApiService>((ref) {
  return BillingApiService(ref.watch(odooApiClientProvider));
});

final databaseProvider = Provider<AppDatabase>((ref) {
  final db = AppDatabase();
  ref.onDispose(db.close);
  return db;
});

final readingRepositoryProvider = Provider<DriftReadingRepository>((ref) {
  return DriftReadingRepository(ref.watch(databaseProvider));
});

final assignmentRepositoryProvider = Provider<AssignmentRepository>((ref) {
  final repo = OdooAssignmentRepository(ref.watch(odooApiClientProvider));
  ref.onDispose(repo.dispose);
  return repo;
});

final collectionRepositoryProvider = Provider<CollectionRepository>((ref) {
  final repo = MockCollectionRepository();
  ref.onDispose(repo.dispose);
  return repo;
});

final imageProcessingServiceProvider = Provider<ImageProcessingService>((ref) {
  return ImageProcessingService();
});

final thermalPrinterServiceProvider = Provider<ThermalPrinterService>((ref) {
  return ThermalPrinterService();
});

final syncSettingsServiceProvider = Provider<SyncSettingsService>((ref) {
  return SyncSettingsService();
});

final syncEngineProvider = Provider<SyncEngine>((ref) {
  final engine = SyncEngine(
    ref.watch(readingRepositoryProvider),
    ref.watch(databaseProvider),
    ref.watch(syncSettingsServiceProvider),
    ref.watch(readingApiServiceProvider),
  );
  engine.start();
  ref.onDispose(engine.dispose);
  return engine;
});

final assignmentsProvider = StreamProvider.autoDispose
    .family<List<ReadingAssignment>, AssignmentQuery>((ref, query) {
  return ref
      .watch(assignmentRepositoryProvider)
      .watchAssignments(query: query.text, filter: query.status);
});

class AssignmentQuery {
  final String? text;
  final AssignmentStatus? status;
  const AssignmentQuery({this.text, this.status});
  @override
  bool operator ==(Object other) =>
      other is AssignmentQuery && other.text == text && other.status == status;
  @override
  int get hashCode => Object.hash(text, status);
}

final readingsProvider = StreamProvider.autoDispose<List<MeterReading>>((ref) {
  return ref.watch(readingRepositoryProvider).watchReadingsForPeriod(0);
});

final collectionAccountsProvider = StreamProvider.autoDispose
    .family<List<CollectionAccount>, String?>((ref, query) {
  return ref.watch(collectionRepositoryProvider).watchAccounts(query: query);
});

final syncSnapshotProvider = StreamProvider.autoDispose<SyncSnapshot>((ref) {
  return ref.watch(syncEngineProvider).snapshots;
});

final syncModeProvider = FutureProvider.autoDispose<SyncMode>((ref) {
  return ref.watch(syncSettingsServiceProvider).getSyncMode();
});

final syncBatchSizeProvider = FutureProvider.autoDispose<int>((ref) {
  return ref.watch(syncSettingsServiceProvider).getBatchSize();
});

final authStateProvider = StateProvider<bool>((ref) => false);
