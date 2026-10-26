<?php
/* Dedicated lab pfSense only. Default is preview. Requires console access. */
require_once('config.inc');
require_once('filter.inc');
require_once('shaper.inc');

$policy = json_decode(file_get_contents(__DIR__ . '/policy.json'), true);
$map = [10 => 'lan', 20 => 'opt1', 30 => 'opt2', 40 => 'opt3', 50 => 'opt4'];
if (!$policy || ($policy['schema_version'] ?? null) !== 1) {
    throw new Exception('Invalid policy file');
}
foreach ($map as $vlan => $interface) {
    if (!isset($config['interfaces'][$interface])) {
        throw new Exception("Missing interface $interface for VLAN $vlan; assign interfaces first");
    }
    $expected = "10.0.$vlan.1";
    if (($config['interfaces'][$interface]['ipaddr'] ?? '') !== $expected ||
        (string)($config['interfaces'][$interface]['subnet'] ?? '') !== '24') {
        throw new Exception("Expected $expected/24 on $interface; review interface mapping");
    }
}
$rules = [];
foreach (($config['filter']['rule'] ?? []) as $rule) {
    if (!in_array($rule['interface'] ?? '', array_values($map), true)) {
        $rules[] = $rule;
    }
}
$tracker = 1900000000;
foreach ($map as $vlan => $interface) {
    foreach ($policy['rules'] as $row) {
        if ($row['vlan'] !== $vlan) continue;
        $rules[] = ['type' => 'pass', 'interface' => $interface, 'ipprotocol' => 'inet',
            'protocol' => $row['protocol'], 'source' => ['address' => $row['source']],
            'destination' => ['address' => $row['destination'], 'port' => $row['port']],
            'descr' => 'RSB public - ' . $row['description'], 'log' => 'on',
            'tracker' => (string)$tracker++, 'statetype' => 'keep state'];
    }
    $rules[] = ['type' => 'block', 'interface' => $interface, 'ipprotocol' => 'inet46',
        'source' => ['any' => ''], 'destination' => ['any' => ''], 'log' => 'on',
        'tracker' => (string)$tracker++, 'descr' => "RSB public - VLAN$vlan default deny"];
}
echo 'Resulting rules: ' . count($rules) . "\n";
foreach ($rules as $rule) {
    echo ($rule['interface'] ?? '') . ' ' . ($rule['type'] ?? '') . ' ' . ($rule['descr'] ?? '') . "\n";
}
if (!in_array('--apply', $argv, true)) {
    echo "Preview only. Use --apply on a dedicated lab firewall after reviewing the policy.\n";
    exit(0);
}
$backup = '/conf/backup/config-rsb-public-before-' . date('Ymd-His') . '.xml';
if (!copy('/conf/config.xml', $backup)) throw new Exception('Could not save pre-change configuration');
$config['filter']['rule'] = $rules;
write_config('Apply RSB public lab policy');
filter_configure();
echo "Policy applied. Backup: $backup. Verify pfctl -nf /tmp/rules.debug and the network acceptance tests.\n";
?>
