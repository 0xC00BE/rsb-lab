<?php
/* Dedicated clean lab firewall only. Settings/media are private operator inputs. */
require_once('config.inc');require_once('interfaces.inc');require_once('system.inc');
$do_not_include_config_gui_inc=true;require_once('auth.inc');
try {
    if(PHP_SAPI!=='cli'||!str_starts_with(trim(file_get_contents('/etc/version')),'2.9.'))throw new Exception('Requires pfSense CE 2.9 CLI.');
    $settings=json_decode(file_get_contents(__DIR__.'/settings.json'),true,512,JSON_THROW_ON_ERROR);
    if(($settings['schema_version']??0)!==1||!preg_match('/^[A-Za-z][A-Za-z0-9-]{1,31}$/',$settings['hostname']??'')||strlen($settings['admin_password']??'')<16)throw new Exception('Invalid private bootstrap settings.');
    $logical=['wan','lan','opt1','opt2','opt3','opt4'];
    if(array_keys($settings['macs'])!==$logical||count(array_unique($settings['macs']))!==6)throw new Exception('Provide exactly six unique, ordered logical MAC mappings.');
    $found=[];$current=null;
    foreach(explode("\n",shell_exec('/sbin/ifconfig -a')) as $line){
        if(preg_match('/^([A-Za-z][A-Za-z0-9_.]*):/',$line,$m))$current=$m[1];
        if($current&&preg_match('/^\s+ether\s+([a-f0-9:]{17})/i',$line,$m))$found[strtolower($m[1])]=$current;
    }
    foreach($settings['macs'] as $name=>$mac){
        if(!preg_match('/^[a-f0-9:]{17}$/i',$mac)||!isset($found[strtolower($mac)]))throw new Exception('A required preparation MAC is absent from this guest.');
        echo $name.' -> '.$found[strtolower($mac)]."\n";
    }
    if(config_get_path('openvpn/openvpn-server',[])||config_get_path('openvpn/openvpn-client',[])||config_get_path('bridges/bridged',[]))throw new Exception('Bootstrap requires a clean OS without VPNs or bridges.');
    $directory='/conf/rsb-platform';
    if(is_dir($directory))throw new Exception('Platform bootstrap directory already exists; inspect before retrying.');
    $key=$settings['provisioning_public_key']??null;
    if($key!==null&&!preg_match('/^ssh-ed25519 [A-Za-z0-9+\/=]+(?: [^\r\n]*)?$/',$key))throw new Exception('Supply one valid public Ed25519 provisioning key.');
    if(!in_array('--apply',$argv,true)){echo "Preview only; use --apply on this dedicated clean lab clone.\n";exit(0);}
    mkdir($directory,0700);copy('/conf/config.xml',$directory.'/config-before-bootstrap.xml');chmod($directory.'/config-before-bootstrap.xml',0600);
    $zones=['lan'=>10,'opt1'=>20,'opt2'=>30,'opt3'=>40,'opt4'=>50];
    $names=['lan'=>'Corporate','opt1'=>'DMZ','opt2'=>'Operations','opt3'=>'Engineering','opt4'=>'Field'];
    $interfaces=['wan'=>['if'=>$found[strtolower($settings['macs']['wan'])],'descr'=>'WAN','enable'=>'','ipaddr'=>'dhcp','blockpriv'=>'','blockbogons'=>'']];
    foreach($zones as $name=>$zone)$interfaces[$name]=['if'=>$found[strtolower($settings['macs'][$name])],'descr'=>$names[$name],'enable'=>'','ipaddr'=>"10.0.$zone.1",'subnet'=>'24'];
    config_set_path('interfaces',$interfaces);config_del_path('dhcpd');config_del_path('dhcpdv6');config_del_path('radvd');
    config_set_path('system/hostname',$settings['hostname']);config_set_path('system/domain','rs.brew');config_set_path('system/timezone','Etc/UTC');
    config_set_path('system/webgui/protocol','https');config_del_path('system/ssh');
    $admin=getUserEntry('admin');if(!$admin)throw new Exception('Factory administrator is missing.');
    local_user_set_password($admin,$settings['admin_password']);local_user_set($admin['item']);
    write_config('Initialize dedicated RSB lab interfaces and private administrator');
    foreach($zones as $name=>$zone)interface_configure($name);
    require(__DIR__.'/apply-policy.php');
    foreach(['policy.json','apply-policy.php','vpn.php','finalize-provisioning.php'] as $file){copy(__DIR__.'/'.$file,$directory.'/'.$file);chmod($directory.'/'.$file,0600);}
    if($key!==null){
        $rule=['type'=>'pass','interface'=>'opt1','ipprotocol'=>'inet','protocol'=>'tcp','source'=>['address'=>'10.0.20.254'],
            'destination'=>['address'=>'10.0.20.1','port'=>'2222'],'descr'=>'RSB temporary platform provisioning','tracker'=>'1920000000','statetype'=>'keep state'];
        config_set_path('filter/rule',array_merge([$rule],config_get_path('filter/rule',[])));
        file_put_contents($directory.'/provisioning-authorized_keys',$key."\n");chmod($directory.'/provisioning-authorized_keys',0600);
        $daemon="Port 2222\nListenAddress 10.0.20.1\nHostKey /etc/ssh/ssh_host_ed25519_key\nPidFile /var/run/rsb-provisioning-sshd.pid\nAuthorizedKeysFile /conf/rsb-platform/provisioning-authorized_keys\nPermitRootLogin prohibit-password\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nUsePAM no\n";
        file_put_contents($directory.'/provisioning-sshd.conf',$daemon);chmod($directory.'/provisioning-sshd.conf',0600);
        mwexec('/usr/bin/ssh-keygen -A');write_config('Add temporary key-only lab preparation channel');filter_configure();
        mwexec('/usr/sbin/sshd -f /conf/rsb-platform/provisioning-sshd.conf');
        passthru('/usr/bin/ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub');
    }
    file_put_contents($directory.'/initialized','Dedicated lab bootstrap applied.\n');
    echo "BOOTSTRAP APPLIED: five static zones, WAN DHCP, private admin, base policy. Reboot before acceptance; remove preparation access/media before exercises.\n";
}catch(Throwable $error){fwrite(STDERR,$error->getMessage()."\n");exit(1);}
