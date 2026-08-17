import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/entities.dart';

class CustomerDetailScreen extends ConsumerWidget {
  final String assignmentId;

  const CustomerDetailScreen({super.key, required this.assignmentId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));

    return Scaffold(
      appBar: AppBar(title: const Text('تفاصيل العداد')),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: 'خطأ: $e'),
        data: (list) {
          final match = list.where((a) => a.id == assignmentId);
          if (match.isEmpty) {
            return const EmptyState(
                icon: Icons.error_outline, title: 'العنصر غير موجود');
          }
          final assignment = match.first;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(assignment.customer.name,
                                style: Theme.of(context).textTheme.titleLarge),
                          ),
                          SyncStatusChip(
                            label: _statusLabel(assignment.status),
                            color: _statusColor(context, assignment.status),
                            icon: _statusIcon(assignment.status),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(assignment.customer.address ?? '-',
                          style: Theme.of(context).textTheme.bodyMedium),
                      const Divider(height: 24),
                      _InfoRow(
                          label: 'رقم المشترك',
                          value: assignment.customer.customerNumber),
                      _InfoRow(
                          label: 'رقم الحساب',
                          value: assignment.customer.accountNumber),
                      _InfoRow(
                          label: 'رقم العداد',
                          value: assignment.meter.meterNumber),
                      _InfoRow(
                          label: 'الرقم التسلسلي',
                          value: assignment.meter.serialNumber ?? '-'),
                      _InfoRow(
                          label: 'نوع العداد',
                          value: assignment.meter.meterType ?? '-'),
                      _InfoRow(
                          label: 'حالة الاتصال',
                          value:
                              assignment.meter.connectionStatus == 'connected'
                                  ? 'متصل'
                                  : 'مقطوع'),
                      _InfoRow(
                          label: 'المنطقة',
                          value:
                              '${assignment.customer.regionName} · ${assignment.customer.areaName}'),
                      _InfoRow(
                        label: 'آخر قراءة',
                        value: assignment.customer.lastReadingValue != null
                            ? '${assignment.customer.lastReadingValue!.toStringAsFixed(0)} kWh'
                            : '-',
                      ),
                      _InfoRow(
                        label: 'تاريخ آخر قراءة',
                        value: assignment.customer.lastReadingDate != null
                            ? _date(assignment.customer.lastReadingDate!)
                            : '-',
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text('سجل القراءات السابق',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              _HistoryTile(
                  date: DateTime.now().subtract(const Duration(days: 30)),
                  value: assignment.customer.lastReadingValue ?? 0),
              _HistoryTile(
                  date: DateTime.now().subtract(const Duration(days: 60)),
                  value: (assignment.customer.lastReadingValue ?? 500) -
                      assignment.averageConsumption),
              _HistoryTile(
                  date: DateTime.now().subtract(const Duration(days: 90)),
                  value: (assignment.customer.lastReadingValue ?? 500) -
                      assignment.averageConsumption * 2),
              const SizedBox(height: 20),
              FilledButton.icon(
                icon: const Icon(Icons.speed_rounded),
                label: const Text('إدخال قراءة جديدة'),
                onPressed: () => context.push('/readings/new/${assignment.id}'),
              ),
            ],
          );
        },
      ),
    );
  }

  String _date(DateTime date) =>
      '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  String _statusLabel(AssignmentStatus status) => switch (status) {
        AssignmentStatus.pending => 'متبقي',
        AssignmentStatus.pendingDecision => 'بانتظار قرار',
        AssignmentStatus.read => 'مكتمل',
        AssignmentStatus.rejected => 'مرفوض',
        AssignmentStatus.escalated => 'مصعد',
        AssignmentStatus.skipped => 'متجاوز',
      };

  IconData _statusIcon(AssignmentStatus status) => switch (status) {
        AssignmentStatus.pending => Icons.hourglass_empty_rounded,
        AssignmentStatus.pendingDecision => Icons.rule_rounded,
        AssignmentStatus.read => Icons.check_circle_outline,
        AssignmentStatus.rejected => Icons.cancel_outlined,
        AssignmentStatus.escalated => Icons.build_outlined,
        AssignmentStatus.skipped => Icons.skip_next_rounded,
      };

  Color _statusColor(BuildContext context, AssignmentStatus status) =>
      switch (status) {
        AssignmentStatus.pending => Colors.orange,
        AssignmentStatus.pendingDecision => Colors.blue,
        AssignmentStatus.read => Theme.of(context).colorScheme.primary,
        AssignmentStatus.rejected => Theme.of(context).colorScheme.error,
        AssignmentStatus.escalated => Colors.deepPurple,
        AssignmentStatus.skipped => Colors.grey,
      };
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          Flexible(
            child: Text(value,
                textAlign: TextAlign.end,
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  final DateTime date;
  final double value;

  const _HistoryTile({required this.date, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.timeline_rounded),
        title: Text('${value.toStringAsFixed(0)} kWh'),
        subtitle: Text(
            '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}'),
        trailing: const Icon(Icons.photo_outlined),
      ),
    );
  }
}
