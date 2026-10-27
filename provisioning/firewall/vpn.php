<?php
/* Dedicated pfSense CE 2.9 lab adapter. Generated keys/profiles stay in /conf. */
require_once('config.inc');
require_once('interfaces.inc');
require_once('filter.inc');
require_once('certs.inc');
require_once('openvpn.inc');

function rsb_vpn_store($path, $value) {
    file_put_contents($path, json_encode($value, JSON_PRETTY_PRINT) . "\n");
    chmod($path, 0600);
}
function rsb_vpn_rule($interface, $type, $source, $destination, $port, $description, $protocol = null) {
    static $tracker = 1910000000;
    $rule = ['type'=>$type, 'interface'=>$interface, 'ipprotocol'=>'inet',
        'source'=>['address'=>$source], 'destination'=>['address'=>$destination],
        'descr'=>'RSB VPN - '.$description, 'tracker'=>(string)$tracker++,
        'log'=>'on', 'statetype'=>'keep state'];
    if ($source === 'any') $rule['source']=['any'=>''];
    if ($destination === 'any') $rule['destination']=['any'=>''];
    if ($destination === 'self') $rule['destination']=['network'=>'(self)'];
    if ($port !== null) $rule['destination']['port']=(string)$port;
    if ($protocol !== null) $rule['protocol']=$protocol;
    // A bridged student's replies can leave through the LAN member interface.
    if (in_array($interface,['lan','opt1','opt6'],true) && $type==='pass') $rule['statepolicy']='floating';
    return $rule;
}
function rsb_vpn_initialize($settings, $directory) {
    global $config;
    if (config_get_path('openvpn/openvpn-server', []) || config_get_path('openvpn/openvpn-client', []) || config_get_path('bridges/bridged', [])) {
        throw new Exception('This initializer requires a dedicated lab firewall without existing VPNs or bridges.');
    }
    if (is_dir($directory)) throw new Exception('Private VPN directory already exists; inspect before retrying.');
    $map=[10=>'lan',20=>'opt1',30=>'opt2',40=>'opt3',50=>'opt4'];
    foreach ($map as $zone=>$if) {
        if (config_get_path("interfaces/$if/ipaddr") !== "10.0.$zone.1" ||
            (string)config_get_path("interfaces/$if/subnet") !== '24') throw new Exception('Lab interface mapping differs from the reference.');
    }
    if (($settings['schema_version']??0)!==1 || !preg_match('/^[a-zA-Z0-9.-]+$/',$settings['endpoint']??'') ||
        $settings['endpoint']==='vpn.example.org') throw new Exception('Set an actual VPN endpoint in the private settings file.');
    foreach (['admin_port','student_port'] as $key) {
        if (!is_int($settings[$key]) || $settings[$key]<1024 || $settings[$key]>65535) throw new Exception('Invalid listener port.');
    }
    if ($settings['admin_port']===$settings['student_port'] || $settings['admin_network']!=='10.254.10.0/24' ||
        $settings['student_start']!=='10.0.10.160' || $settings['student_end']!=='10.0.10.190') {
        throw new Exception('This tested adapter requires distinct ports and the documented role address ranges.');
    }
    if (isset($config['interfaces']['opt5']) || isset($config['interfaces']['opt6'])) throw new Exception('Reserved VPN interface slots are already used.');
    foreach(config_get_path('aliases/alias',[]) as $alias) if(($alias['name']??'')==='RSB_VPN_STUDENTS') throw new Exception('Reserved student address alias already exists.');
    foreach (config_get_path('filter/rule',[]) as $rule) {
        if (isset($rule['floating']) || (($rule['interface']??'')==='wan' && ($rule['type']??'')==='pass')) {
            throw new Exception('Remove or review existing WAN/floating allowances on the dedicated firewall before VPN initialization.');
        }
    }
    if (config_get_path('nat/rule',[]) || config_get_path('installedpackages/miniupnpd/config/0/enable',false)) {
        throw new Exception('Existing forwarding or UPnP configuration needs operator review.');
    }
    echo "Administrator: routed access; student: Corporate bridge; two independent certificate authorities.\n";
    if (!in_array('--apply',$GLOBALS['argv'],true)) {echo "Preview only; use --apply to create local keys and configure the dedicated firewall.\n";return;}
    mkdir($directory,0700,true);
    copy('/conf/config.xml',$directory.'/config-before-vpn.xml');chmod($directory.'/config-before-vpn.xml',0600);
    $state=['schema_version'=>1,'endpoint'=>$settings['endpoint'],'roles'=>[]];
    // Use individual hosts so the reserved .191 address is never allowed.
    config_set_path('aliases/alias/',['name'=>'RSB_VPN_STUDENTS','type'=>'host',
        'address'=>implode(' ',array_map(fn($n)=>'10.0.10.'.$n,range(160,190))),
        'descr'=>'RSB student VPN exact address pool']);
    foreach (['admin','student'] as $role) {
        $ca=['refid'=>uniqid('rsbca'),'descr'=>'RSB VPN '.$role.' CA'];
        if (!ca_create($ca,3072,3650,['commonName'=>'RSB '.$role.' VPN CA'])) throw new Exception('CA generation failed.');
        config_set_path('ca/',$ca);
        $cert=['refid'=>uniqid('rsbcrt'),'descr'=>'RSB VPN '.$role.' server'];
        if (!cert_create($cert,$ca['refid'],3072,825,['commonName'=>'rsb-'.$role.'-vpn'],'server')) throw new Exception('Server certificate generation failed.');
        config_set_path('cert/',$cert);
        $crl=['refid'=>uniqid('rsbcrl')];
        if (!crl_create($crl,$ca['refid'],'RSB '.$role.' revocations')) throw new Exception('CRL generation failed.');
        $vpnid=openvpn_vpnid_next();
        $vpn=['vpnid'=>$vpnid,'mode'=>'server_tls','protocol'=>'UDP4','dev_mode'=>$role==='admin'?'tun':'tap',
            'interface'=>'wan','ipaddr'=>'','local_port'=>$settings[$role.'_port'],'description'=>'RSB '.$role.' VPN',
            'caref'=>$ca['refid'],'certref'=>$cert['refid'],'crlref'=>$crl['refid'],'dh_length'=>'none',
            'ecdh_curve'=>'none','cert_depth'=>'1','remote_cert_tls'=>true,
            'tls'=>base64_encode(openvpn_create_key()),'tls_type'=>'crypt','digest'=>'SHA256',
            'data_ciphers'=>'AES-256-GCM,AES-128-GCM','data_ciphers_fallback'=>'AES-256-GCM',
            'allow_compression'=>'no','compression'=>'','topology'=>'subnet','verbosity_level'=>'3',
            'maxclients'=>'20','keepalive_interval'=>'10','keepalive_timeout'=>'60',
            'local_network'=>$role==='admin'?'10.0.10.0/24,10.0.20.0/24,10.0.30.0/24,10.0.40.0/24,10.0.50.0/24':'10.0.30.40/32',
            'dns_server1'=>'10.0.10.2','dns_domain'=>'rs.brew',
            'custom_options'=>'tls-version-min 1.2'];
        if ($role==='admin') $vpn['tunnel_network']=$settings['admin_network'];
        else $vpn+=['serverbridge_dhcp'=>'yes','serverbridge_interface'=>'lan','serverbridge_routegateway'=>'yes',
            'serverbridge_dhcp_start'=>$settings['student_start'],'serverbridge_dhcp_end'=>$settings['student_end']];
        if($role==='student') $vpn['custom_options'].=';ifconfig-pool-persist '.$directory.'/student-pool.txt 30';
        config_set_path('openvpn/openvpn-server/',$vpn);
        $if=$role==='admin'?'opt5':'opt6';
        config_set_path('interfaces/'.$if,['enable'=>'','if'=>'ovpns'.$vpnid,'descr'=>'RSB_'.strtoupper($role).'_VPN']);
        $state['roles'][$role]=['caref'=>$ca['refid'],'certref'=>$cert['refid'],'crlref'=>$crl['refid'],
            'vpnid'=>$vpnid,'interface'=>$if,'port'=>$vpn['local_port'],'dev'=>$vpn['dev_mode']];
    }
    config_set_path('bridges/bridged/',['bridgeif'=>'bridge0','members'=>'lan,opt6','descr'=>'RSB Corporate student VPN']);
    // Filter both bridge member interfaces: the student ingress enforces its pool.
    $tunables=config_get_path('sysctl/item',[]);
    foreach (['net.link.bridge.pfil_member'=>'1','net.link.bridge.pfil_bridge'=>'0'] as $key=>$value) {
        $tunables=array_values(array_filter($tunables,fn($r)=>($r['tunable']??'')!==$key));
        $tunables[]=['tunable'=>$key,'value'=>$value,'descr'=>'RSB VPN bridge filtering'];
        mwexec('/sbin/sysctl '.escapeshellarg($key.'='.$value));
    }
    config_set_path('sysctl/item',$tunables);
    config_set_path('system/webgui/noantilockout',true);
    if ($settings['allow_private_wan_clients']??false) config_del_path('interfaces/wan/blockpriv');
    $rules=[];
    foreach (['admin','student'] as $role) {
        $rules[]=rsb_vpn_rule('wan','pass','any','self',$settings[$role.'_port'],$role.' listener','udp');
    }
    foreach (array_keys($map) as $zone) $rules[]=rsb_vpn_rule('opt5','pass','10.254.10.0/24',"10.0.$zone.0/24",null,'administrator zone access');
    $rules[]=rsb_vpn_rule('opt5','block','any','any',null,'administrator default deny');
    $rules[]=rsb_vpn_rule('opt6','block','any','self',null,'student firewall protection');
    $rules[]=rsb_vpn_rule('lan','pass','10.0.10.0/24','RSB_VPN_STUDENTS',null,'Corporate to student bridge');
    $rules[]=rsb_vpn_rule('lan','pass','10.0.10.0/24','224.0.0.252',5355,'Corporate discovery multicast','udp');
    foreach ([137,138] as $port) $rules[]=rsb_vpn_rule('lan','pass','10.0.10.0/24','10.0.10.255',$port,'Corporate discovery broadcast','udp');
    $rules[]=rsb_vpn_rule('opt6','pass','RSB_VPN_STUDENTS','10.0.10.0/24',null,'student Corporate access');
    $rules[]=rsb_vpn_rule('opt6','pass','RSB_VPN_STUDENTS','224.0.0.252',5355,'student discovery multicast','udp');
    foreach ([22,80,443,3389] as $port) {
        $rules[]=rsb_vpn_rule('opt1','pass','10.0.20.11','RSB_VPN_STUDENTS',$port,'Jump client callback','tcp');
        // Routed egress and bridged return use different member interfaces.
        $egress=rsb_vpn_rule('lan,opt6','pass','10.0.20.11','RSB_VPN_STUDENTS',$port,'callback bridge egress','tcp');
        $egress+=['floating'=>'yes','direction'=>'out','quick'=>'yes','statepolicy'=>'floating'];
        $rules[]=$egress;
    }
    $rules[]=rsb_vpn_rule('opt6','pass','RSB_VPN_STUDENTS','10.0.30.40',8088,'student status board','tcp');
    $rules[]=rsb_vpn_rule('opt6','block','any','any',null,'student default deny');
    foreach ($rules as &$rule) if ($rule['type']==='block') $rule['ipprotocol']='inet46';
    unset($rule);
    config_set_path('filter/rule',array_merge($rules,config_get_path('filter/rule',[])));
    write_config('Configure separate RSB administrator and student VPN roles');
    rsb_vpn_store($directory.'/state.json',$state);
    foreach (config_get_path('openvpn/openvpn-server',[]) as $vpn) openvpn_resync('server',$vpn);
    interfaces_bridge_configure();filter_configure();
    echo "VPN roles configured. Private CA/configuration backup remains in $directory.\n";
}
function rsb_vpn_client($role,$name,$directory,$action) {
    if (!in_array($role,['admin','student'],true) || !preg_match('/^[a-z][a-z0-9-]{1,31}$/',$name)) throw new Exception('Use role admin/student and a lowercase client identifier.');
    $state=json_decode(file_get_contents($directory.'/state.json'),true,512,JSON_THROW_ON_ERROR);
    $r=$state['roles'][$role];$cn='rsb-'.$role.'-'.$name;
    $found=[];
    foreach (config_get_path('cert',[]) as $cert) if (($cert['descr']??'')===$cn && ($cert['caref']??'')===$r['caref']) $found[]=$cert;
    if ($action==='revoke') {
        if (count($found)!==1) throw new Exception('Expected one existing client certificate.');
        $crl=lookup_crl($r['crlref']);
        if (!cert_revoke($found[0],$crl,1)) throw new Exception('Revocation failed.');
        write_config('Revoke RSB VPN client '.$cn);
        foreach (config_get_path('openvpn/openvpn-server',[]) as $vpn) if ((string)$vpn['vpnid']===(string)$r['vpnid']) openvpn_resync('server',$vpn);
        echo "Client revoked; role sessions restarted so the revocation takes effect.\n";return;
    }
    if ($action==='export') {
        if (count($found)!==1 || is_cert_revoked($found[0])) throw new Exception('Expected one valid existing client identity.');
        $cert=$found[0];
    } else {
        if ($found || file_exists($directory.'/'.$cn.'.ovpn')) throw new Exception('Client already exists; use export to refresh its profile without replacing its identity.');
        $cert=['refid'=>uniqid('rsbclient'),'descr'=>$cn];
        if (!cert_create($cert,$r['caref'],3072,365,['commonName'=>$cn],'user')) throw new Exception('Client certificate generation failed.');
        config_set_path('cert/',$cert);write_config('Issue RSB VPN client '.$cn);
    }
    $ca=lookup_ca($r['caref']);$ca=$ca['item'];
    $servers=config_get_path('openvpn/openvpn-server',[]);
    $matching=array_values(array_filter($servers,fn($s)=>(string)$s['vpnid']===(string)$r['vpnid']));
    if(count($matching)!==1 || !str_contains(base64_decode($matching[0]['tls']??''),'BEGIN OpenVPN Static key V1')) throw new Exception('Expected one server with a valid TLS control key.');
    $server=$matching[0];
    $profile="client\ndev {$r['dev']}\nproto udp4\nremote {$state['endpoint']} {$r['port']}\nresolv-retry infinite\nnobind\npersist-key\npersist-tun\nremote-cert-tls server\nverify-x509-name rsb-$role-vpn name\ntls-version-min 1.2\nauth SHA256\ndata-ciphers AES-256-GCM:AES-128-GCM\nallow-compression no\nverb 3\n";
    // Stable per-person TAP MAC avoids stale peer ARP after a client reconnect.
    if($role==='student') $profile.='lladdr 02:'.implode(':',str_split(substr(hash('sha256',$cn),0,10),2))."\n";
    foreach (['ca'=>$ca['crt'],'cert'=>$cert['crt'],'key'=>$cert['prv'],'tls-crypt'=>$server['tls']] as $tag=>$value) $profile.="<$tag>\n".base64_decode($value)."\n</$tag>\n";
    file_put_contents($directory.'/'.$cn.'.ovpn',$profile);chmod($directory.'/'.$cn.'.ovpn',0600);
    echo "Issued private profile: $directory/$cn.ovpn\n";
}
try {
    if (PHP_SAPI!=='cli' || !str_starts_with(trim(file_get_contents('/etc/version')),'2.9.')) throw new Exception('This adapter is for pfSense CE 2.9 CLI.');
    $directory='/conf/rsb-vpn';$action=$argv[1]??'';
    if ($action==='initialize') rsb_vpn_initialize(json_decode(file_get_contents($argv[2]??''),true,512,JSON_THROW_ON_ERROR),$directory);
    elseif (in_array($action,['issue','export','revoke'],true)) rsb_vpn_client($argv[2]??'',$argv[3]??'',$directory,$action);
    else throw new Exception('Usage: php vpn.php initialize PRIVATE-SETTINGS.json [--apply] | issue|export|revoke admin|student CLIENT-NAME');
} catch (Throwable $error) {fwrite(STDERR,$error->getMessage()."\n");exit(1);}
