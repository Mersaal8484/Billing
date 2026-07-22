import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../core/printing/thermal_printer_service.dart';
import '../../collections/presentation/thermal_printer_picker_sheet.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: const Text('الإعدادات')),
      body: ListView(
        children: [
          const _SectionHeader('الحساب'),
          const ListTile(
            leading: CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text('kasher01'),
            subtitle: Text('كاشف عدادات كهرباء — المؤسسة العامة للكهرباء — صنعاء'),
          ),
          const _SectionHeader('التحصيل'),
          _ThermalPrinterSettingsTile(
            printerService: ref.watch(thermalPrinterServiceProvider),
          ),
          const _SectionHeader('المزامنة'),
          SwitchListTile(
            value: true,
            onChanged: (_) {},
            title: const Text('مزامنة تلقائية في الخلفية'),
            subtitle: const Text(
                'يستخدم WorkManager لجدولة المزامنة عند توفر الشبكة'),
          ),
          SwitchListTile(
            value: false,
            onChanged: (_) {},
            title: const Text('المزامنة عبر بيانات الجوال'),
            subtitle: const Text(
                'افتراضياً تتم المزامنة عبر Wi-Fi فقط لتوفير الباقة'),
          ),
          const _SectionHeader('حول التطبيق'),
          const ListTile(
              title: Text('الإصدار'), trailing: Text('0.1.0 (مرحلة الواجهة)')),
          const ListTile(
            title: Text('حالة التكامل مع Odoo'),
            subtitle:
                Text('المؤسسة العامة للكهرباء — بيانات محاكاة محلية'),
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

class _ThermalPrinterSettingsTileState extends State<_ThermalPrinterSettingsTile> {
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
