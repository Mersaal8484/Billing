import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:workmanager/workmanager.dart';

import 'app/app.dart';
import 'core/database/app_database.dart';
import 'core/sync/sync_engine.dart';
import 'core/sync/sync_settings_service.dart';
import 'features/readings/data/mock_reading_repository.dart';

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    if (task == 'sync_batch_task') {
      final db = AppDatabase();
      final repo =
          MockReadingRepository(); // In production, we'd use a real repository
      final syncEngine = SyncEngine(repo, db, SyncSettingsService());
      await syncEngine.syncNow();
      // Keep db connection open during sync, then we'd close it or rely on isolate exit
    }
    return Future.value(true);
  });
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  Workmanager().initialize(callbackDispatcher);
  // Register periodic task (minimum is 15 minutes on Android)
  Workmanager().registerPeriodicTask(
    'sync-task-id',
    'sync_batch_task',
    frequency: const Duration(minutes: 15),
    constraints: Constraints(
      networkType: NetworkType.connected,
    ),
  );

  runApp(const ProviderScope(child: MeterReadingApp()));
}
