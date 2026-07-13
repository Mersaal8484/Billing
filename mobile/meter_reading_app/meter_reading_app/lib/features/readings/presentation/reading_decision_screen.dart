import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../customers/domain/entities.dart';

enum ReadingDecision { approve, approveWithNote, reject, escalate }

class ReadingDecisionScreen extends ConsumerStatefulWidget {
  final String assignmentId;
  final double currentReading;

  const ReadingDecisionScreen({
    super.key,
    required this.assignmentId,
    required this.currentReading,
  });

  @override
  ConsumerState<ReadingDecisionScreen> createState() =>
      _ReadingDecisionScreenState();
}

class _ReadingDecisionScreenState extends ConsumerState<ReadingDecisionScreen> {
  ReadingDecision _decision = ReadingDecision.approve;
  String? _reason;
  final _notesCtrl = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));

    return Scaffold(
      appBar: AppBar(title: const Text('قرار العداد')),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: '$e'),
        data: (list) {
          final matches =
              list.where((assignment) => assignment.id == widget.assignmentId);
          if (matches.isEmpty) {
            return const EmptyState(
                icon: Icons.error_outline, title: 'المهمة غير موجودة');
          }
          final assignment = matches.first;
          final previous = assignment.customer.lastReadingValue ?? 0;
          final consumption = widget.currentReading - previous;
          final variance = assignment.averageConsumption == 0
              ? 0.0
              : ((consumption - assignment.averageConsumption) /
                      assignment.averageConsumption) *
                  100;

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(assignment.customer.name,
                          style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 8),
                      _MetricRow(
                          label: 'القراءة السابقة',
                          value: '${previous.toStringAsFixed(0)} kWh'),
                      _MetricRow(
                          label: 'القراءة الحالية',
                          value:
                              '${widget.currentReading.toStringAsFixed(0)} kWh'),
                      _MetricRow(
                          label: 'استهلاك هذا الشهر',
                          value: '${consumption.toStringAsFixed(0)} kWh'),
                      _MetricRow(
                          label: 'متوسط سابق',
                          value:
                              '${assignment.averageConsumption.toStringAsFixed(0)} kWh'),
                      const SizedBox(height: 12),
                      _VarianceBanner(variance: variance),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              RadioGroup<ReadingDecision>(
                groupValue: _decision,
                onChanged: (decision) {
                  if (decision != null) {
                    _setDecision(decision);
                  }
                },
                child: const Column(
                  children: [
                    _DecisionOption(
                      value: ReadingDecision.approve,
                      icon: Icons.check_circle_outline,
                      title: 'اعتماد القراءة',
                      subtitle: 'القراءة طبيعية ويمكن إرسالها للاعتماد.',
                    ),
                    _DecisionOption(
                      value: ReadingDecision.approveWithNote,
                      icon: Icons.warning_amber_rounded,
                      title: 'اعتماد مع ملاحظة',
                      subtitle: 'استهلاك شاذ لكن الصورة والقراءة صحيحتان.',
                    ),
                    _DecisionOption(
                      value: ReadingDecision.reject,
                      icon: Icons.cancel_outlined,
                      title: 'رفض / تعذر القراءة',
                      subtitle: 'عداد تالف، لا يمكن الوصول، أو شبهة تلاعب.',
                    ),
                    _DecisionOption(
                      value: ReadingDecision.escalate,
                      icon: Icons.build_outlined,
                      title: 'تصعيد لفني صيانة',
                      subtitle: 'تحتاج الحالة زيارة فنية قبل الاعتماد.',
                    ),
                  ],
                ),
              ),
              if (_decision == ReadingDecision.reject ||
                  _decision == ReadingDecision.escalate) ...[
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _reason,
                  decoration: const InputDecoration(labelText: 'سبب القرار'),
                  items: const [
                    DropdownMenuItem(
                        value: 'meter_damaged', child: Text('عداد تالف')),
                    DropdownMenuItem(
                        value: 'no_access', child: Text('تعذر الوصول')),
                    DropdownMenuItem(
                        value: 'tamper_suspected', child: Text('شبهة تلاعب')),
                    DropdownMenuItem(
                        value: 'unsafe_site', child: Text('الموقع غير آمن')),
                  ],
                  onChanged: (value) => setState(() => _reason = value),
                ),
              ],
              if (_decision == ReadingDecision.approveWithNote ||
                  _decision == ReadingDecision.escalate) ...[
                const SizedBox(height: 12),
                TextField(
                  controller: _notesCtrl,
                  maxLines: 3,
                  decoration:
                      const InputDecoration(labelText: 'ملاحظات القرار'),
                ),
              ],
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => _submitDecision(context, assignment),
                icon: const Icon(Icons.done_all_rounded),
                label: const Text('حفظ القرار'),
              ),
            ],
          );
        },
      ),
    );
  }

  void _setDecision(ReadingDecision decision) {
    setState(() {
      _decision = decision;
      if (decision == ReadingDecision.approve ||
          decision == ReadingDecision.approveWithNote) {
        _reason = null;
      }
    });
  }

  Future<void> _submitDecision(
      BuildContext context, ReadingAssignment assignment) async {
    final requiresReason = _decision == ReadingDecision.reject ||
        _decision == ReadingDecision.escalate;
    if (requiresReason && _reason == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('اختر سببًا قبل حفظ الرفض أو التصعيد')),
      );
      return;
    }

    final nextStatus = switch (_decision) {
      ReadingDecision.approve ||
      ReadingDecision.approveWithNote =>
        AssignmentStatus.read,
      ReadingDecision.reject => AssignmentStatus.rejected,
      ReadingDecision.escalate => AssignmentStatus.escalated,
    };

    await ref
        .read(assignmentRepositoryProvider)
        .markStatus(assignment.id, nextStatus);
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('تم حفظ قرار العداد')));
      context.go('/dashboard');
    }
  }
}

class _MetricRow extends StatelessWidget {
  final String label;
  final String value;

  const _MetricRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _VarianceBanner extends StatelessWidget {
  final double variance;

  const _VarianceBanner({required this.variance});

  @override
  Widget build(BuildContext context) {
    final abnormal = variance.abs() > 35;
    final color =
        abnormal ? Colors.orange : Theme.of(context).colorScheme.primary;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
              abnormal
                  ? Icons.warning_amber_rounded
                  : Icons.check_circle_outline,
              color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              abnormal
                  ? 'الاستهلاك يختلف عن المتوسط بنسبة ${variance.toStringAsFixed(0)}%. راجع الصورة قبل القرار.'
                  : 'الاستهلاك ضمن النطاق الطبيعي مقارنة بالمتوسط السابق.',
              style: TextStyle(color: color, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _DecisionOption extends StatelessWidget {
  final ReadingDecision value;
  final IconData icon;
  final String title;
  final String subtitle;

  const _DecisionOption({
    required this.value,
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: RadioListTile<ReadingDecision>(
        value: value,
        title: Row(
          children: [
            Icon(icon, size: 20),
            const SizedBox(width: 8),
            Expanded(
                child: Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w700))),
          ],
        ),
        subtitle: Text(subtitle),
      ),
    );
  }
}
