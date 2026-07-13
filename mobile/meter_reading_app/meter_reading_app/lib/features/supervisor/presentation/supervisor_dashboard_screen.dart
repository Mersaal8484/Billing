import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../customers/domain/entities.dart';

class SupervisorDashboardScreen extends ConsumerWidget {
  const SupervisorDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));
    final collectionSummary =
        ref.watch(collectionRepositoryProvider).dailySummary();

    return Scaffold(
      appBar: AppBar(title: const Text('لوحة المشرف')),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: 'تعذر تحميل لوحة المشرف: $e'),
        data: (list) {
          final pendingDecision = list
              .where((a) => a.status == AssignmentStatus.pendingDecision)
              .toList();
          final rejected =
              list.where((a) => a.status == AssignmentStatus.rejected).toList();
          final escalated = list
              .where((a) => a.status == AssignmentStatus.escalated)
              .toList();

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      icon: Icons.rule_folder_outlined,
                      label: 'بانتظار الاعتماد',
                      value: '${pendingDecision.length}',
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricCard(
                      icon: Icons.report_problem_outlined,
                      label: 'مرفوضة',
                      value: '${rejected.length}',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      icon: Icons.build_outlined,
                      label: 'مصعدة لفني',
                      value: '${escalated.length}',
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricCard(
                      icon: Icons.payments_outlined,
                      label: 'تحصيل اليوم',
                      value:
                          '${collectionSummary.collectedAmount.toStringAsFixed(0)} ر.س',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text('قرارات عداد معلقة',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              if (pendingDecision.isEmpty)
                const Card(
                  child: ListTile(
                    leading: Icon(Icons.check_circle_outline),
                    title: Text('لا توجد قراءات معلقة الآن'),
                    subtitle:
                        Text('ستظهر هنا قرارات الكاشفين التي تحتاج اعتمادًا.'),
                  ),
                )
              else
                ...pendingDecision.map((assignment) =>
                    _DecisionReviewTile(assignment: assignment)),
              const SizedBox(height: 20),
              Text('أداء الفرق',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              const _PerformanceTile(
                  name: 'reader01', role: 'كاشف', done: 18, total: 24),
              const _PerformanceTile(
                  name: 'collector01', role: 'متحصل', done: 7, total: 11),
            ],
          );
        },
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _MetricCard(
      {required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 10),
            Text(value,
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800)),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _DecisionReviewTile extends ConsumerWidget {
  final ReadingAssignment assignment;

  const _DecisionReviewTile({required this.assignment});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(assignment.customer.name,
                style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text(
                'عداد ${assignment.meter.meterNumber} · متوسط ${assignment.averageConsumption.toStringAsFixed(0)} kWh'),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed: () => _setStatus(context, ref,
                        AssignmentStatus.rejected, 'تم رفض القرار للمراجعة'),
                    icon: const Icon(Icons.close_rounded),
                    label: const Text('رفض'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => _setStatus(context, ref,
                        AssignmentStatus.read, 'تم اعتماد القراءة'),
                    icon: const Icon(Icons.check_rounded),
                    label: const Text('اعتماد'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _setStatus(BuildContext context, WidgetRef ref,
      AssignmentStatus status, String message) async {
    await ref
        .read(assignmentRepositoryProvider)
        .markStatus(assignment.id, status);
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    }
  }
}

class _PerformanceTile extends StatelessWidget {
  final String name;
  final String role;
  final int done;
  final int total;

  const _PerformanceTile(
      {required this.name,
      required this.role,
      required this.done,
      required this.total});

  @override
  Widget build(BuildContext context) {
    final progress = total == 0 ? 0.0 : done / total;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                    child: Text(name,
                        style: const TextStyle(fontWeight: FontWeight.w800))),
                Text(role),
              ],
            ),
            const SizedBox(height: 10),
            LinearProgressIndicator(value: progress, minHeight: 8),
            const SizedBox(height: 8),
            Text('$done من $total مهمة مكتملة'),
          ],
        ),
      ),
    );
  }
}
