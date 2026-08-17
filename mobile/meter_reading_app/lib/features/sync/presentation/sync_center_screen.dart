import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/theme/app_theme.dart';
import '../../../core/sync/sync_engine.dart';
import '../../../core/sync/sync_settings_service.dart';
import '../../../shared/widgets/state_widgets.dart';

class SyncCenterScreen extends ConsumerWidget {
  const SyncCenterScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final snapshotAsync = ref.watch(syncSnapshotProvider);
    final modeAsync = ref.watch(syncModeProvider);
    final batchSizeAsync = ref.watch(syncBatchSizeProvider);
    final engine = ref.read(syncEngineProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('مركز المزامنة'),
        actions: [
          IconButton(
            tooltip: 'عرض تفاصيل الطابور',
            icon: const Icon(Icons.list_alt_outlined),
            onPressed: () => context.push('/sync/queue'),
          ),
        ],
      ),
      body: snapshotAsync.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: '$e'),
        data: (snapshot) {
          final offline = snapshot.connectivity == ConnectivityState.offline;
          final mode = modeAsync.maybeWhen(
            data: (value) => value,
            orElse: () => SyncMode.batch,
          );
          final batchSize = batchSizeAsync.maybeWhen(
            data: (value) => value,
            orElse: () => 50,
          );
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                color: offline
                    ? StatusColors.offline.withValues(alpha: 0.08)
                    : null,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(
                          offline ? Icons.cloud_off : Icons.cloud_done_outlined,
                          color: offline
                              ? StatusColors.offline
                              : StatusColors.synced),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          offline
                              ? 'غير متصل — العمل مستمر محلياً'
                              : 'متصل بالشبكة',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                      Switch(
                        value: !offline,
                        onChanged: (v) => engine.setConnectivity(v
                            ? ConnectivityState.online
                            : ConnectivityState.offline),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _ModeCard(mode: mode, batchSize: batchSize),
              const SizedBox(height: 16),
              _PipelineCard(
                title: mode == SyncMode.immediate
                    ? 'طابور المزامنة الفردية'
                    : 'طابور المزامنة المجمع (ZIP)',
                subtitle: mode == SyncMode.immediate
                    ? 'رفع كل قراءة وصورتها كطلب مستقل'
                    : 'رفع مجمع للقراءات والصور حتى $batchSize لكل حزمة',
                icon: mode == SyncMode.immediate
                    ? Icons.flash_on_outlined
                    : Icons.archive_outlined,
                stats: snapshot.batchPipeline,
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: offline ? null : () => engine.syncNow(),
                icon: const Icon(Icons.sync_rounded),
                label: const Text('مزامنة الآن'),
              ),
              const SizedBox(height: 12),
              if (snapshot.batchPipeline.failed > 0)
                FilledButton.tonalIcon(
                  onPressed: engine.retryFailed,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('إعادة محاولة العناصر الفاشلة'),
                ),
              const SizedBox(height: 12),
              if (snapshot.lastSuccessfulSync != null)
                Center(
                  child: Text(
                    'آخر مزامنة ناجحة: ${_formatTime(snapshot.lastSuccessfulSync!)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  String _formatTime(DateTime t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')}';
}

class _ModeCard extends StatelessWidget {
  final SyncMode mode;
  final int batchSize;

  const _ModeCard({required this.mode, required this.batchSize});

  @override
  Widget build(BuildContext context) {
    final immediate = mode == SyncMode.immediate;
    return Card(
      child: ListTile(
        leading: Icon(
          immediate ? Icons.flash_on_outlined : Icons.archive_outlined,
          color: Theme.of(context).colorScheme.primary,
        ),
        title: Text(
          immediate
              ? 'الوضع الحالي: مزامنة فردية مباشرة'
              : 'الوضع الحالي: حزم مضغوطة ($batchSize/حزمة)',
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          immediate
              ? 'يرفع كل عنصر فور توفر الاتصال دون انتظار حزمة.'
              : 'يرفع تلقائياً عند اكتمال الحزمة أو يدوياً من زر مزامنة الآن.',
        ),
      ),
    );
  }
}

class _PipelineCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final PipelineStats stats;
  const _PipelineCard(
      {required this.title,
      required this.subtitle,
      required this.icon,
      required this.stats});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(fontWeight: FontWeight.w700)),
                    Text(subtitle,
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                SyncStatusChip(
                    label: '${stats.pending} بالانتظار',
                    color: StatusColors.pending,
                    icon: Icons.hourglass_empty_rounded),
                SyncStatusChip(
                    label: '${stats.succeeded} تم',
                    color: StatusColors.synced,
                    icon: Icons.check_circle_outline),
                SyncStatusChip(
                    label: '${stats.failed} فشل',
                    color: StatusColors.error,
                    icon: Icons.error_outline),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
