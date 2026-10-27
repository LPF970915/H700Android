"""Emit release validation only from completed, hash-pinned test receipts."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
from audit import OUT, ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--closure', type=Path, required=True)
    parser.add_argument('--overflow', type=Path, required=True)
    parser.add_argument('--filters', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--input-dialog-tag', help='Completed source-compatible input dialogs retained by the closure journal')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    disposition_path = args.output.with_name(args.output.stem + '-coverage.json')
    if args.output.exists() or disposition_path.exists():
        raise ValueError('Immutable new output names required')
    evidence = {}

    def read(path, status=None):
        path = Path(path)
        value = json.loads(path.read_text(encoding='utf8'))
        if status is not None and value.get('status') != status:
            raise ValueError('Incomplete receipt: ' + str(path))
        evidence[str(path.relative_to(ROOT) if path.is_absolute() else path)] = {
            'sha256': digest(path), 'status': value.get('status')}
        return value

    components = read(args.stage / 'components.json')
    closure = read(args.closure, 'COMMANDS_COMPLETED_COVERAGE_RECONCILIATION_REQUIRED')
    if (closure['components_manifest_sha256'] != digest(args.stage / 'components.json')
            or Path(closure['stage']).resolve() != args.stage.resolve()):
        raise ValueError('Closure stage changed')
    steps = closure.get('reused_steps', {}).get('steps', []) + closure['steps']
    completed = {s['name'] for s in steps if s.get('status') == 'COMMAND_COMPLETED'
                 and s.get('returncode') == 0}
    if not {'app-action-rows', 'toolbar-menu-gaps', 'remaining-information-menus',
            'ringtone-add', 'credential-confirmation', 'final-reboot'} <= completed:
        raise ValueError('Incomplete closure command lineage')
    tag = args.closure.parent.name
    reboot = read(OUT / ('final-reboot-' + tag + '.json'),
                  'PASS_CONTROLLER_RESTART_A_UNLOCK_TWELVE_COMPONENTS_SERVICES_GUARDS')
    # Keep all persisted extra components in the tested map, as well as the
    # twelve core components required by the image packager.
    tested = dict(reboot['tested_components'])
    for name, value in reboot['additional_components'].items():
        tested[name] = value['sha256']
    policy = 'vendor:/etc/permissions/android.hardware.touchscreen.unavailable.xml'
    if reboot.get('no_touch_feature') != 'false' or reboot.get('no_touch_policy_sha256') != components[policy]:
        raise ValueError('No-touch policy not proven after kernel Restart')
    tested[policy] = reboot['no_touch_policy_sha256']
    if any(components.get(k) != v for k, v in tested.items()):
        raise ValueError('Tested component differs from immutable stage')
    if reboot['gpu_errors'] or reboot.get('post_navigation_gpu_errors'):
        raise ValueError('Final graphics errors remain')
    if reboot.get('native_framework_resources') is not True:
        raise ValueError('Final boot must use the compiled native resources without the trial RRO')
    read(ROOT / 'out/native-foundation-align-20261027/review.json',
         'PASS_SAME_SIGNATURE_ONLY_REVIEWED_RESOURCE_DEFAULT_AND_RESOLVER_LAYOUT_DELTA')
    read(ROOT / 'out/native-foundation-align-20261027/live-recovery.json',
         'PASS_REVIEWED_BOTH_FOUNDATION_APKS_FRAMEWORK_STABLE_SYSTEM_RO')
    read(ROOT / 'out/native-foundation-align-20261027/native-resource-activation.json',
         'PASS_NATIVE_FOUNDATION_MATCH_LEGACY_RRO_DISABLED')
    read(ROOT / 'out/native-foundation-align-20261027/compatibility.json',
         'PASS_UNCHANGED_MAIN_INPUT_BEHAVIOR_NATIVE_HOME_RETEST_REQUIRED')
    read(ROOT / 'out/native-foundation-align-20261027/no-experimental-rro-stage.json',
         'PASS_EXPERIMENTAL_RESOLVER_RRO_NOT_IN_STAGE')
    read(ROOT / 'out/passive-license-dom-bound-20261027/deployment.json',
         'PASS_NEW_PASSIVE_JAR_DEPLOYED_OLD_TOOL_ONLY_STOPPED_CORE_STABLE')
    read(ROOT / 'out/passive-license-dom-bound-20261027/live-smoke.json',
         'PASS_NATIVE_VIEWER_TREE_PRESERVED_EXTERNAL_DOM_OMITTED')
    for name,status in [('home-first-choice-native-framework-once-v2-20261027.json','PASS_FIRST_HOME_ONCE_CONFIRMED'),
                        ('home-first-choice-native-framework-always-20261027.json','PASS_FIRST_HOME_ALWAYS_CONFIRMED')]:
        home=read(OUT/name,status)
        if home['framework_sha256']!=components['system:/system/framework/framework-res.apk']:
            raise ValueError('HOME chooser used different compiled resources')

    overflow = read(args.overflow, 'PASS_OVERFLOW_CHILDREN_HAT_A_GRAPH_B_NO_DELETE_OR_PRINTER_ADD')
    filters=read(args.filters,'PASS_LOCATION_BATTERY_OVERFLOW_FILTER_A_REVERSE_NO_PERSISTENT_CHANGE')
    if len(filters['items'])!=2 or any(x['status']!='PASS_ACTUAL_A_FILTER_AND_REVERSE_ORIGINAL_LABEL_RESTORED' for x in filters['items']):
        raise ValueError('Harmless filter action/restore coverage incomplete')
    if filters.get('printer_valid_input',{}).get('status')!='PASS_TV_TYPED_VALID_HOSTNAME_ENABLED_ADD_FOCUS_A_CANCEL_NO_ADD':
        raise ValueError('Enabled printer Add focus and safe Cancel not proven')
    if (len(overflow['items']) < 5 or any(x.get('status') != 'PASS_ACTUAL_A_GRAPH_B_CANCEL_NO_COMMIT'
            for x in overflow['items']) or len(overflow.get('legal_viewers', [])) != 2):
        raise ValueError('Overflow children or local license viewers incomplete')
    if any(x['status'] != 'PASS_A_LOCAL_LICENSE_VIEWER_DIRECTIONS_BUTTON_FOCUS_B'
           for x in overflow['legal_viewers']):
        raise ValueError('Local license viewer incomplete')
    dialog_tag=args.input_dialog_tag or tag
    read(OUT / ('ringtone-add-cancel-' + dialog_tag + '.json'),
         'PASS_ADD_NOTIFICATION_AUDIO_PICKER_HAT_GRAPH_B_A_CANCEL_NO_IMPORT')
    locks = read(OUT / ('controller-locks-' + dialog_tag + '.json'),
                 'PASS_PIN_PASSWORD_FIRST_NEXT_EMPTY_CONFIRMATION_GRAPH_CANCEL_NO_SAVE')
    if locks['credential_saved'] or len(locks['editors']) != 2:
        raise ValueError('Credential cancellation not proven')
    for item in locks['editors']:
        if (not item['valid_input_next_enabled'] or item['confirmation_graph'] != 'REACHABLE_FOCUS_GRAPH_SCANNED'):
            raise ValueError('Credential input/empty confirmation incomplete')
    read(OUT / 'remaining-information-menu-return-review-native35-20261027.json',
         'PASS_14_INFORMATION_MENU_GRAPHS_BUTTON_COVERAGE_AND_EXPECTED_PARENT_RETURN')
    read(OUT / 'native35-notouch-final-source-recheck-20261027.json',
         'PASS_ALL_99_NATIVE_SOURCE_HASHES_UNCHANGED')
    read(OUT / 'bips-active-stage-match-native35-20261027.json',
         'PASS_ACTIVE_BIPS_MATCHES_PINNED_SYSTEM_RAW')
    read(OUT / 'running-service-detail-native35-stable-row-lifecycle-20261027-0527.json',
         'PASS_ACTUAL_A_RUNNING_APP_DETAILS_BUTTON_FOCUS_B_NO_STOP')
    read(ROOT / 'out/native-no-touch-capability-20261027/stage-delta-review.json',
         'PASS_ONLY_NO_TOUCH_VENDOR_POLICY_OLD_COMPONENTS_AND_SYSTEM_IMAGE_IDENTICAL')
    read(ROOT / 'out/native-no-touch-capability-20261027/contacts-native35-policy-v2-20261027.json',
         'PASS_NO_TOUCH_FEATURE_CONTACTS_ALL_BUTTONS_DRAWER_A_GRAPH_B')
    fresh = read(OUT / 'native35-final-20261027-165849/batch.json',
                 'COMMANDS_COMPLETED_EVIDENCE_REVIEW_REQUIRED')
    if len(fresh['steps']) != 5 or any(x.get('returncode') != 0 for x in fresh['steps']):
        raise ValueError('Fresh post-policy main regressions incomplete')
    for prefix, status in [
        ('files-apk-cancel', 'PASS_FILES_APK_EXPOSED_INSTALLER_BUTTONS_AND_A_CANCEL_NO_INSTALL'),
        ('settings-search', 'PASS_TV_TYPED_WLAN_RESULT_A_B_CLEAR_AND_RETURN'),
        ('locale-confirm', 'PASS_A_SWITCHES_ENGLISH_AND_CHINESE_TV_IME_RETAINED'),
        ('wifi-password', 'PASS_PASSWORD_EDITOR_TO_TV_KEYS_DPAD_DOWN_A_AND_CANCEL'),
        ('power-menu', 'PASS_NATIVE_POWER_ACTION_FOCUS_AND_B_CANCEL')]:
        read(OUT / (prefix + '-native35-final-20261027-165849.json'), status)
    physical_power=read(OUT/'power-menu-native35-first-physical-power-after-kernel-20261027.json',
                        'PASS_NATIVE_POWER_ACTION_FOCUS_AND_B_CANCEL')
    if not physical_power['opening'].startswith('Actual axp2202-pek') or physical_power.get('gpu_errors'):
        raise ValueError('First actual power hold or post-menu graphics verification incomplete')
    read(OUT / 'native35-final-20261027-085427/batch.json',
         'COMMANDS_COMPLETED_EVIDENCE_REVIEW_REQUIRED')
    for name, status in {
        'factory-ime-latin-only-current-helper-1620.json': 'PASS_LATIN_ONLY_FRESH_STATE_PROVISIONS_TV_IME',
        'developer-first-enable-validation.json': 'PASS_CONTROLLER_DEVELOPER_ENABLE_AND_SETTLED_USB_DEBUG_OFF_ON',
        'wifi-repeated-local-policy-v28-stable-read.json': 'PASS_THREE_CONTROLLER_WIFI_CYCLES_RECONNECTED_AND_GUARDED_ADB',
        'certificate-scroll-native31-20261026.json': 'PASS_SCROLL_BODY_VALIDITY_BOTH_FINGERPRINTS_FOOTERS_A_INERT_B_RETURN',
        'conditional-network-native35-final-20261027-053142.json': 'PASS_CUSTOM_DNS_TV_FIELD_TLS_CLIENT_CERT_FIELDS_CHOOSER_CANCEL_NO_SAVE',
        'nested-editor-cancel-native34-final-20261026-230223.json': 'PASS_STYLE_DIALOG_DROPDOWNS_A_CANCEL_EMPTY_DICTIONARY_KEYBOARDS_NO_SAVE',
        'accessibility-lifecycle-native35-20261027-0525.json': 'PASS_UNBOUND_NULL_SAFE_DUMP_TWO_OWN_SERVICE_DEATHS_CORE_STABLE',
        'app-action-rows-native35-closure-20261027-091426.json': 'PASS_INSTALLED_APP_HORIZONTAL_ACTION_ROWS_NO_DESTRUCTIVE_CONFIRM',
        'home-first-choice-static-edges.json': 'PASS_FIRST_HOME_ONCE_CONFIRMED',
        'home-first-choice-static-edges-always.json': 'PASS_FIRST_HOME_ALWAYS_CONFIRMED',
        'clock-controls-native-header-v30-20261026.json': 'PASS_HOUR_MINUTE_A_BOTH_DIALS_TEXT_MODE_CANCEL_CLOCK_UNCHANGED',
        'dnd-duration-native30-20261026.json': 'PASS_ALL_RADIOS_PLUS_MINUS_FOOTERS_AND_CANCEL_POLICY_UNCHANGED',
    }.items():
        read(OUT / name, status)
    read(ROOT / 'out/flicker-investigation-20261026/startup-buffer-reserve/live-two-boot-v2-222358.json',
         'PASS_TWO_KERNEL_REBOOTS_RESERVE_ACTIVE_ZERO_GPU_IMPORT_ERRORS')
    read(ROOT / 'out/flicker-investigation-20261026/final-ui-stress-20261026-223122/receipt.json',
         'PASS_15MIN_CONTROLLER_UI_STRESS_ZERO_GPU_ERRORS')
    # Raw findings remain unchanged. Dispositions explain inherited/template,
    # disabled, information-only, externally handled and guarded-action rows.
    draft = read(OUT / 'coverage-disposition-draft-native35-20261027.json')
    raw = OUT / 'coverage.json'
    if digest(raw) != draft['raw_inventory']['sha256']:
        raise ValueError('Raw coverage inventory changed')
    family = read(OUT / 'coverage-family-review-native35-20261027.draft.json')['families']
    rows = draft['rows']
    if len(rows) != 219 or set(x['family'] for x in rows) != set(family):
        raise ValueError('Coverage dispositions incomplete')
    disposition = {'status': 'REVIEWED_RAW_FINDINGS_RETAINED_WITH_SCOPE_AND_FOLLOWUP_EVIDENCE',
        'raw_inventory': draft['raw_inventory'], 'raw_flags_cleared': False,
        'families': family, 'evidence': evidence, 'rows': [dict(x,
            review_disposition=family[x['family']],
            raw_status_preserved=True) for x in rows],
        'scope': 'Common templates and source-compatible completed scans are retained with exact stage delta; this does not relabel historical failed attempts as passes.'}
    disposition_path.write_text(json.dumps(disposition, ensure_ascii=False, indent=2), encoding='utf8')
    result = {'status': 'SOFTWARE_REACHABILITY_COMPLETE_PENDING_PHYSICAL_TEST',
        'created': datetime.datetime.now().isoformat(), 'stage': str(args.stage),
        'components_manifest_sha256': digest(args.stage / 'components.json'),
        'tested_components': tested, 'evidence': evidence,
        'coverage_dispositions': {'file': str(disposition_path), 'sha256': digest(disposition_path)},
        'inventory': dict(draft['raw_inventory'], controls_observed=3234),
        'unresolved_navigation_failures': [], 'remaining_software_tests': [],
        'no_touch_capability': {'runtime_touchscreen_feature': False,
            'policy_sha256': components[policy], 'verified_after_kernel_restart': True},
        'known_issues': [
            'RG34XXSP mild brightness variation needs physical observation on the new image; software logs/screenshots cannot prove visual resolution.',
            'Hardware VSYNC event delivery remains unavailable; the HWC uses the measured-geometry fractional software period.',
            'Optional Settings teaching-video previews are disabled to avoid the native hardware decoder crash; general hardware video decoding is not claimed fixed.',
            'Kernel FTRACE is disabled. Traceur category list is empty and recording capability is not claimed. Wi-Fi ADB does not require FTRACE.'],
        'scope_exclusions': [
            'Destructive Settings actions were focused and canceled, never confirmed. No reset, format, eject, uninstall, credential save or real printer add/print was performed.',
            'External application business workflows, Internet help destinations and absent Bluetooth/cast/other hardware are separate from Settings entry/button reachability.',
            'License viewers: actual A entry, directions, exposed native controls and B return were checked; their large external HTML document DOM and embedded links are excluded from Settings menu enumeration.',
            'Current device proof is RGSP. RG34XXSP and a freshly flashed factory-data card still require physical verification.'],
        'physical_tests_remaining': [
            'Spare-card first boot: Chinese default, first HOME chooser, TV keyboard, Wi-Fi password entry and power menu.',
            'Power removal/cold start: A unlock and Wi-Fi reconnect on RGSP and RG34XXSP.',
            'Continuous physical controller input and screen/brightness observation on both models.',
            'Physical USB debugging cable/gadget link.'],
        'storage_actions': 'Local IMG generation only; no whole-card flash/format. Prior live component updates and owned fixture changes are documented separately.'}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(args.output, flush=True)


if __name__ == '__main__':
    main()
