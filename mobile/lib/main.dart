import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

void main() {
  runApp(const ResqApp());
}

class ResqApp extends StatelessWidget {
  const ResqApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: true,
      title: 'ResQAI',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xffb8db45),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xff10151a),
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool offline = false;
  bool submitting = false;
  bool emergencyActive = false;

  String status = 'No active emergency';

  String? sosId;
  String? priority;
  String? riskLabel;
  double? unsafeProbability;
  String? assignedTeam;
  String? shelter;
  String? hospital;
  int? etaMinutes;
  String? routeAlgorithm;
  String? emergencyType;
  int peopleAffected = 1;
  bool medicalAssistance = false;

  @override
  void initState() {
    super.initState();
    _watchConnectivity();
  }

  Future<void> _watchConnectivity() async {
    try {
      final result = await Connectivity().checkConnectivity();

      if (!mounted) return;

      setState(() {
        offline = result.contains(ConnectivityResult.none);
      });

      Connectivity().onConnectivityChanged.listen((results) {
        if (!mounted) return;

        setState(() {
          offline = results.contains(ConnectivityResult.none);
        });
      });
    } catch (_) {
      // Connectivity status should never prevent the app from working.
    }
  }

  Future<void> _openEmergencyForm() async {
    if (submitting || emergencyActive) return;

    String? selectedType;
    var selectedPeople = 1;
    var selectedMedical = false;

    final details = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final emergencyTypes = [
              ('Flood', '🌊'),
              ('Fire', '🔥'),
              ('Medical', '🚑'),
              ('Accident', '🚗'),
              ('Building Collapse', '🏚️'),
              ('Other', '⚠️'),
            ];

            return SafeArea(
              child: Padding(
                padding: EdgeInsets.only(
                  left: 16,
                  right: 16,
                  bottom: MediaQuery.of(context).viewInsets.bottom + 16,
                ),
                child: Material(
                  color: const Color(0xff182127),
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(24),
                  ),
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Center(
                          child: Container(
                            width: 42,
                            height: 4,
                            decoration: BoxDecoration(
                              color: Colors.white24,
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                        const SizedBox(height: 20),
                        const Text(
                          'Emergency Details',
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 7),
                        Text(
                          'Tell us what is happening so ResQAI can coordinate the right response.',
                          style: TextStyle(color: Colors.grey.shade400),
                        ),
                        const SizedBox(height: 22),
                        const Text(
                          'What happened?',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: emergencyTypes.map((type) {
                            final isSelected = selectedType == type.$1;
                            return ChoiceChip(
                              label: Text('${type.$2} ${type.$1}'),
                              selected: isSelected,
                              onSelected: (_) => setSheetState(
                                () => selectedType = type.$1,
                              ),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 22),
                        const Text(
                          'How many people need help?',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            IconButton.filledTonal(
                              onPressed: selectedPeople > 1
                                  ? () => setSheetState(() => selectedPeople--)
                                  : null,
                              icon: const Icon(Icons.remove),
                              tooltip: 'Fewer people',
                            ),
                            SizedBox(
                              width: 64,
                              child: Center(
                                child: Text(
                                  '$selectedPeople',
                                  style: const TextStyle(
                                    fontSize: 24,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ),
                            IconButton.filledTonal(
                              onPressed: selectedPeople < 20
                                  ? () => setSheetState(() => selectedPeople++)
                                  : null,
                              icon: const Icon(Icons.add),
                              tooltip: 'More people',
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          'Medical assistance required?',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        SegmentedButton<bool>(
                          segments: const [
                            ButtonSegment(value: false, label: Text('No')),
                            ButtonSegment(value: true, label: Text('Yes')),
                          ],
                          selected: {selectedMedical},
                          onSelectionChanged: (selection) => setSheetState(
                            () => selectedMedical = selection.first,
                          ),
                        ),
                        const SizedBox(height: 24),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            onPressed: selectedType == null
                                ? null
                                : () => Navigator.of(sheetContext).pop({
                                      'emergency_type': selectedType,
                                      'people_affected': selectedPeople,
                                      'medical_assistance': selectedMedical,
                                    }),
                            icon: const Icon(Icons.send),
                            label: const Padding(
                              padding: EdgeInsets.symmetric(vertical: 13),
                              child: Text('CONFIRM SOS'),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    if (!mounted || details == null) return;

    await _submitSos(
      emergencyType: details['emergency_type'] as String,
      selectedPeople: details['people_affected'] as int,
      selectedMedical: details['medical_assistance'] as bool,
    );
  }

  Future<void> _submitSos({
    required String emergencyType,
    required int selectedPeople,
    required bool selectedMedical,
  }) async {
    if (submitting) return;

    setState(() {
      submitting = true;
      status = 'Preparing your emergency request...';
    });

    // The citizen demo intentionally uses the fixed scenario location.
    const latitude = 12.9716;
    const longitude = 77.5946;

    final payload = {
      'emergency_type': emergencyType,
      'medical_assistance': selectedMedical,
      'people_affected': selectedPeople,
      'description': '$emergencyType emergency reported from ResQAI citizen app',
      'latitude': latitude,
      'longitude': longitude,

      // Demo scenario inputs for the AI engine.
      'flood_level': 'high',
      'rainfall': 'high',
      'river_proximity': 'high',
      'flood_reports': 3,
    };

    if (offline) {
      await _saveOfflineSos(payload);

      if (!mounted) return;

      setState(() {
        submitting = false;
        status = 'SOS saved locally. Waiting for connection.';
      });

      return;
    }

    final uri = Uri.parse('$apiBaseUrl/api/sos');

    try {
      setState(() {
        status = 'Contacting emergency response center...';
      });

      debugPrint('========== RESQAI SOS ==========');
      debugPrint('API URL: $uri');
      debugPrint('Payload: ${jsonEncode(payload)}');

      final response = await http
          .post(
            uri,
            headers: {
              'Content-Type': 'application/json',
              'X-Demo-Role': 'CITIZEN',
            },
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 15));

      debugPrint('HTTP STATUS: ${response.statusCode}');
      debugPrint('HTTP RESPONSE: ${response.body}');
      debugPrint('================================');

      // Any 2xx response is a successful HTTP request.
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(response.body);

        final data = decoded is Map<String, dynamic>
            ? decoded['data'] as Map<String, dynamic>?
            : null;

        final aiDecision = data?['ai_decision'] is Map<String, dynamic>
            ? data!['ai_decision'] as Map<String, dynamic>
            : null;

        final risk = aiDecision?['risk'] is Map<String, dynamic>
            ? aiDecision!['risk'] as Map<String, dynamic>
            : null;

        final route = data?['route'] is Map<String, dynamic>
          ? data!['route'] as Map<String, dynamic>
          : aiDecision?['route'] is Map<String, dynamic>
            ? aiDecision!['route'] as Map<String, dynamic>
            : null;

        if (!mounted) return;

        setState(() {
          submitting = false;
          emergencyActive = true;
          this.emergencyType = data?['emergency_type']?.toString() ?? emergencyType;
          peopleAffected = selectedPeople;
          medicalAssistance = selectedMedical;

          sosId = data?['id']?.toString();
          priority = data?['priority']?.toString() ??
              aiDecision?['priority']?.toString();

          riskLabel = risk?['label']?.toString();

          final probability = risk?['unsafe_probability'];

          if (probability is num) {
            unsafeProbability = probability.toDouble();
          }

          assignedTeam = data?['assigned_team']?.toString() ??
              aiDecision?['recommended_team']?.toString();

          shelter = data?['recommended_shelter']?.toString() ??
              aiDecision?['recommended_shelter']?.toString();

          hospital = data?['recommended_hospital']?.toString() ??
              aiDecision?['recommended_hospital']?.toString();

          final eta = route?['eta_minutes'];

          if (eta is num) {
            etaMinutes = eta.toInt();
          }

          routeAlgorithm = route?['algorithm']?.toString();

          status = 'SOS acknowledged. Rescue assessment started.';
        });

        return;
      }

      // The server responded, but with an error.
      await _saveOfflineSos(payload);

      if (!mounted) return;

      setState(() {
        submitting = false;
        status =
            'Response center returned HTTP ${response.statusCode}. SOS saved locally.';
      });
    } catch (error, stackTrace) {
      debugPrint('========== RESQAI SOS ERROR ==========');
      debugPrint('URL: $uri');
      debugPrint('ERROR: $error');
      debugPrint('$stackTrace');
      debugPrint('======================================');

      await _saveOfflineSos(payload);

      if (!mounted) return;

      setState(() {
        submitting = false;
        status =
            'Connection failed. SOS saved locally. Check the response center.';
      });
    }
  }

  Future<void> _saveOfflineSos(Map<String, dynamic> payload) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('queued_sos', jsonEncode(payload));
    } catch (error) {
      debugPrint('Could not save SOS locally: $error');
    }
  }

  void _resetDemo() {
    setState(() {
      emergencyActive = false;
      status = 'No active emergency';
      sosId = null;
      priority = null;
      riskLabel = null;
      unsafeProbability = null;
      assignedTeam = null;
      shelter = null;
      hospital = null;
      etaMinutes = null;
      routeAlgorithm = null;
      emergencyType = null;
      peopleAffected = 1;
      medicalAssistance = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('ResQAI'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Icon(
              offline ? Icons.cloud_off : Icons.cloud_done,
              color: offline
                  ? Colors.orange
                  : const Color(0xffb8db45),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text(
            'GOOD AFTERNOON, CITIZEN',
            style: TextStyle(
              fontSize: 11,
              letterSpacing: 1.4,
              color: Colors.grey,
            ),
          ),

          const SizedBox(height: 8),

          const Text(
            'Emergency support,\nwhen every second matters.',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w600,
            ),
          ),

          const SizedBox(height: 24),

          Card(
            color: const Color(0xff372427),
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Row(
                children: [
                  const Icon(
                    Icons.warning_amber_rounded,
                    color: Color(0xffff8c82),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Text(
                      'FLOOD WARNING\n'
                      'Sector 04 response perimeter active',
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 25),

          Center(
            child: GestureDetector(
                onTap: submitting || emergencyActive
                  ? null
                  : _openEmergencyForm,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                height: 190,
                width: 190,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: emergencyActive
                      ? const Color(0xffa63e3a)
                      : const Color(0xffd95d58),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xffd95d58)
                          .withValues(alpha: .22),
                      blurRadius: 34,
                      spreadRadius: 12,
                    ),
                  ],
                ),
                child: Center(
                  child: submitting
                      ? const Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            SizedBox(
                              height: 35,
                              width: 35,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 3,
                              ),
                            ),
                            SizedBox(height: 12),
                            Text(
                              'CONNECTING',
                              style: TextStyle(
                                fontSize: 11,
                                letterSpacing: 1.2,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        )
                      : Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.sos, size: 48),
                            const SizedBox(height: 5),
                            Text(
                              emergencyActive ? 'ACTIVE' : 'SOS',
                              style: const TextStyle(
                                fontSize: 31,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              emergencyActive
                                  ? 'HELP REQUESTED'
                                  : 'TAP TO SELECT DETAILS',
                              style: const TextStyle(
                                fontSize: 10,
                                letterSpacing: 1.2,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 12),

          Center(
            child: Text(
              emergencyActive
                  ? 'Emergency response is being coordinated'
                  : 'Hold for 2 seconds to request help',
              style: TextStyle(
                color: Colors.grey.shade400,
              ),
              textAlign: TextAlign.center,
            ),
          ),

          const SizedBox(height: 25),

          _StatusCard(
            status: status,
            active: emergencyActive,
          ),

          if (emergencyActive) ...[
            const SizedBox(height: 16),
            _EmergencyDetailsCard(
              sosId: sosId,
              priority: priority,
              riskLabel: riskLabel,
              unsafeProbability: unsafeProbability,
              assignedTeam: assignedTeam,
              shelter: shelter,
              hospital: hospital,
              etaMinutes: etaMinutes,
              routeAlgorithm: routeAlgorithm,
              emergencyType: emergencyType,
              peopleAffected: peopleAffected,
              medicalAssistance: medicalAssistance,
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _resetDemo,
              icon: const Icon(Icons.refresh),
              label: const Text('Reset Demo Emergency'),
            ),
          ],

          const SizedBox(height: 16),

          Row(
            children: [
              Expanded(
                child: _QuickAction(
                  icon: Icons.location_on_outlined,
                  label: 'Nearby shelters',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _QuickAction(
                  icon: Icons.local_hospital_outlined,
                  label: 'Hospitals',
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          _QuickAction(
            icon: Icons.report_problem_outlined,
            label: 'Report a hazard',
            wide: true,
          ),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final String status;
  final bool active;

  const _StatusCard({
    required this.status,
    required this.active,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xff182127),
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'RESPONSE STATUS',
              style: TextStyle(
                fontSize: 10,
                letterSpacing: 1.2,
                color: Colors.grey,
              ),
            ),

            const SizedBox(height: 9),

            Text(
              status,
              style: TextStyle(
                fontSize: 15,
                color: active
                    ? const Color(0xffb8db45)
                    : Colors.white,
                fontWeight:
                    active ? FontWeight.w600 : FontWeight.normal,
              ),
            ),

            const SizedBox(height: 16),

            Row(
              children: [
                Icon(
                  active
                      ? Icons.emergency
                      : Icons.check_circle,
                  color: active
                      ? const Color(0xffff7b72)
                      : const Color(0xffb8db45),
                  size: 17,
                ),
                const Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(left: 8),
                    child: Text(
                      'Location permission handled securely',
                    ),
                  ),
                ),
                const Icon(
                  Icons.chevron_right,
                  color: Colors.grey,
                  size: 18,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _EmergencyDetailsCard extends StatelessWidget {
  final String? sosId;
  final String? emergencyType;
  final int peopleAffected;
  final bool medicalAssistance;
  final String? priority;
  final String? riskLabel;
  final double? unsafeProbability;
  final String? assignedTeam;
  final String? shelter;
  final String? hospital;
  final int? etaMinutes;
  final String? routeAlgorithm;

  const _EmergencyDetailsCard({
    required this.sosId,
    required this.emergencyType,
    required this.peopleAffected,
    required this.medicalAssistance,
    required this.priority,
    required this.riskLabel,
    required this.unsafeProbability,
    required this.assignedTeam,
    required this.shelter,
    required this.hospital,
    required this.etaMinutes,
    required this.routeAlgorithm,
  });

  @override
  Widget build(BuildContext context) {
    final probability = unsafeProbability == null
        ? '--'
        : '${(unsafeProbability! * 100).round()}%';

    return Card(
      color: const Color(0xff182127),
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'AI RESPONSE ASSESSMENT',
              style: TextStyle(
                fontSize: 10,
                letterSpacing: 1.2,
                color: Colors.grey,
              ),
            ),

            const SizedBox(height: 14),

            _DetailRow(
              icon: Icons.confirmation_number_outlined,
              label: 'SOS ID',
              value: sosId ?? '--',
            ),

            _DetailRow(
              icon: Icons.emergency_outlined,
              label: 'Emergency',
              value: emergencyType ?? '--',
            ),

            _DetailRow(
              icon: Icons.groups_outlined,
              label: 'People Affected',
              value: '$peopleAffected',
            ),

            _DetailRow(
              icon: Icons.medical_services_outlined,
              label: 'Medical Assistance',
              value: medicalAssistance ? 'Required' : 'Not Required',
            ),

            _DetailRow(
              icon: Icons.priority_high,
              label: 'Priority',
              value: priority ?? '--',
            ),

            _DetailRow(
              icon: Icons.warning_amber_rounded,
              label: 'Risk',
              value: riskLabel == null
                  ? '--'
                  : '$riskLabel ($probability unsafe)',
            ),

            _DetailRow(
              icon: Icons.groups_outlined,
              label: 'Rescue Team',
              value: assignedTeam ?? '--',
            ),

            _DetailRow(
              icon: Icons.home_work_outlined,
              label: 'Shelter',
              value: shelter ?? '--',
            ),

            _DetailRow(
              icon: Icons.local_hospital_outlined,
              label: 'Hospital',
              value: hospital ?? '--',
            ),

            _DetailRow(
              icon: Icons.timer_outlined,
              label: 'Estimated ETA',
              value: etaMinutes == null
                  ? '--'
                  : '$etaMinutes minutes',
            ),

            _DetailRow(
              icon: Icons.route_outlined,
              label: 'Route',
              value: routeAlgorithm ?? '--',
              last: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final bool last;

  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
    this.last = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: last ? 0 : 12,
      ),
      child: Row(
        children: [
          Icon(
            icon,
            size: 18,
            color: const Color(0xffb8db45),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                color: Colors.grey.shade400,
                fontSize: 12,
              ),
            ),
          ),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool wide;

  const _QuickAction({
    required this.icon,
    required this.label,
    this.wide = false,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xff182127),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          mainAxisAlignment:
              wide ? MainAxisAlignment.start : MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              color: const Color(0xffb8db45),
            ),
            const SizedBox(width: 9),
            Flexible(
              child: Text(label),
            ),
          ],
        ),
      ),
    );
  }
}