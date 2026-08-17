import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../core/printing/thermal_printer_service.dart';
import '../../../core/sync/sync_settings_service.dart';
import '../../collections/presentation/thermal_printer_picker_sheet.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentUser = ref.watch(authServiceProvider).currentUser;
    final userName = currentUser?.name ?? currentUser?.login ?? '—';
    final userLogin = currentUser?.login ?? '';
    final roles = currentUser?.roles;

    // تحديد الوصف بناءً على الدور
    String roleDesc = 'موظف ميداني';
    if (roles != null) {
      final parts = <String>[];
      if (roles['is_meter_reader'] == true) parts.add('كاشف');
      if (roles['is_collector'] == true) parts.add('محصل');
      if (roles['is_supervisor'] == true) parts.add('مشرف');
      if (parts.isNotEmpty) roleDesc = parts.join(' / ');
    }

    return Scaffold(
      appBar: AppBar(title: const Text('الإعدادات')),
      body: ListView(
        children: [
          const _SectionHeader('الحساب'),
          ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text(userName),
            subtitle: Text('$roleDesc — المؤسسة العامة للكهرباء'),
          ),
          const _SectionHeader('التحصيل'),
          _ThermalPrinterSettingsTile(
            printerService: ref.watch(thermalPrinterServiceProvider),
          ),
          const _SectionHeader('المزامنة'),
          const _SyncSettingsSection(),
          const _SectionHeader('حول التطبيق'),
          const ListTile(
              title: Text('الإصدار'), trailing: Text('0.1.0')),
          ListTile(
            title: const Text('حالة التكامل مع Odoo'),
            subtitle: Text(userLogin.isNotEmpty
                ? 'متصل — $userLogin'
                : 'غير متصل'),
          ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: OutlinedButton.icon(
              onPressed: () {
                ref.read(authStateProvider.notifier).state = false;
                context.go('/login');
              },
              icon: const Icon(Icons.logout_rounded),
              label: const Text('تسجيل الخروج'),
            ),
          ),
        ],
      ),
    );
  }
}

class _SyncSettingsSection extends ConsumerStatefulWidget {
  const _SyncSettingsSection();

  @override
  ConsumerState<_SyncSettingsSection> createState() =>
      _SyncSettingsSectionState();
}

class _SyncSettingsSectionState extends ConsumerState<_SyncSettingsSection> {
  SyncMode _mode = SyncMode.batch;
  int _batchSize = 50;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final settings = ref.read(syncSettingsServiceProvider);
    final mode = await settings.getSyncMode();
    final batchSize = await settings.getBatchSize();
    if (!mounted) return;
    setState(() {
      _mode = mode;
      _batchSize = batchSize;
      _loading = false;
    });
  }

  Future<void> _setMode(SyncMode mode) async {
    if (mode == _mode) return;
    final previous = _mode;
    setState(() => _mode = mode);
    try {
      await ref.read(syncSettingsServiceProvider).setSyncMode(mode);
      ref.invalidate(syncModeProvider);
    } catch (error) {
      if (!mounted) return;
      setState(() => _mode = previous);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  Future<void> _setBatchSize(int batchSize) async {
    if (batchSize == _batchSize) return;
    final previous = _batchSize;
    setState(() => _batchSize = batchSize);
    try {
      await ref.read(syncSettingsServiceProvider).setBatchSize(batchSize);
      ref.invalidate(syncBatchSizeProvider);
    } catch (error) {
      if (!mounted) return;
      setState(() => _batchSize = previous);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const ListTile(
        leading: SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        title: Text('جاري تحميل إعدادات المزامنة'),
      );
    }

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Row(
            children: [
              const Expanded(
                child: Text(
                  'وضع المزامنة',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              SegmentedButton<SyncMode>(
                segments: const [
                  ButtonSegment(
                    value: SyncMode.immediate,
                    icon: Icon(Icons.flash_on_outlined),
                    label: Text('فردية'),
                  ),
                  ButtonSegment(
                    value: SyncMode.batch,
                    icon: Icon(Icons.archive_outlined),
                    label: Text('حزم ZIP'),
                  ),
                ],
                selected: {_mode},
                onSelectionChanged: (values) => _setMode(values.first),
              ),
            ],
          ),
        ),
        ListTile(
          leading: Icon(
            _mode == SyncMode.immediate
                ? Icons.flash_on_outlined
                : Icons.archive_outlined,
          ),
          title: Text(
            _mode == SyncMode.immediate
                ? 'مزامنة فردية مباشرة'
                : 'حزم مضغوطة ZIP',
          ),
          subtitle: Text(
            _mode == SyncMode.immediate
                ? 'رفع كل قراءة وصورتها فوراً عند توفر الاتصال'
                : 'تجميع القراءات حسب حجم الحزمة أو عند المزامنة اليدوية',
          ),
        ),
        if (_mode == SyncMode.batch)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'حجم الحزمة',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                SegmentedButton<int>(
                  segments: const [
                    ButtonSegment(value: 30, label: Text('30')),
                    ButtonSegment(value: 50, label: Text('50')),
                    ButtonSegment(value: 100, label: Text('100')),
                  ],
                  selected: {_batchSize},
                  onSelectionChanged: (values) => _setBatchSize(values.first),
                ),
              ],
            ),
          ),
        if (_mode == SyncMode.batch)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Align(
              alignment: AlignmentDirectional.centerStart,
              child: Text(
                '$_batchSize صورة لكل حزمة',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Text(title,
          style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: Theme.of(context).colorScheme.primary)),
    );
  }
}

class _ThermalPrinterSettingsTile extends StatefulWidget {
  final ThermalPrinterService printerService;

  const _ThermalPrinterSettingsTile({required this.printerService});

  @override
  State<_ThermalPrinterSettingsTile> createState() =>
      _ThermalPrinterSettingsTileState();
}

class _ThermalPrinterSettingsTileState
    extends State<_ThermalPrinterSettingsTile> {
  ThermalPrinterDevice? _saved;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final saved = await widget.printerService.savedDevice();
    if (mounted) setState(() => _saved = saved);
  }

  Future<void> _pickPrinter() async {
    try {
      final device = await showThermalPrinterPickerSheet(
        context,
        printerService: widget.printerService,
        selected: _saved,
      );
      if (device == null) return;
      await widget.printerService.saveDevice(device);
      if (mounted) setState(() => _saved = device);
    } on ThermalPrinterException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.print_outlined),
      title: const Text('الطابعة الحرارية'),
      subtitle: Text(_saved?.name ?? 'لم يتم اختيار طابعة Bluetooth'),
      trailing: const Icon(Icons.chevron_left),
      onTap: _pickPrinter,
    );
  }
}
