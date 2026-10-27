<?php
/* Remove only the temporary channel created by bootstrap.php. */
require_once('config.inc');require_once('filter.inc');
try{
    if(PHP_SAPI!=='cli'||!is_file('/conf/rsb-platform/initialized'))throw new Exception('Expected an initialized dedicated lab firewall.');
    $rules=[];$count=0;
    foreach(config_get_path('filter/rule',[]) as $rule){
        if(($rule['descr']??'')==='RSB temporary platform provisioning'){
            if(($rule['source']['address']??'')!=='10.0.20.254'||($rule['destination']['port']??'')!=='2222')throw new Exception('Temporary rule scope differs.');
            $count++;continue;
        }
        $rules[]=$rule;
    }
    if($count>1)throw new Exception('Unexpected duplicate preparation rules.');
    config_set_path('filter/rule',$rules);write_config('Close temporary RSB platform preparation access');
    foreach(['provisioning-authorized_keys','provisioning-sshd.conf'] as $name){$path='/conf/rsb-platform/'.$name;if(is_file($path))unlink($path);}
    $pidfile='/var/run/rsb-provisioning-sshd.pid';
    if(is_file($pidfile)){
        $pid=(int)trim(file_get_contents($pidfile));$command=shell_exec('/bin/ps -p '.escapeshellarg((string)$pid).' -o command=');
        if($pid>1&&str_contains($command??'','/usr/sbin/sshd -f /conf/rsb-platform/provisioning-sshd.conf'))mwexec('/bin/kill '.escapeshellarg((string)$pid));
        unlink($pidfile);
    }
    filter_configure();echo "Temporary platform preparation rule/key/daemon removed.\n";
}catch(Throwable $error){fwrite(STDERR,$error->getMessage()."\n");exit(1);}
