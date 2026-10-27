#!/usr/bin/env python3
"""Seed only recorded clean OS clones; generated guest credentials stay private."""
import argparse
import base64
import copy
import json
import secrets
from pathlib import Path
from provider import Deployment,ROOT,wait,vim

WINDOWS={'AD':('RSBAD01',10,'10.0.10.2'),'Corporate':('RSB-WS01',10,'10.0.10.3'),
         'Jump':('RSB-WS03',20,'10.0.20.11'),'Engineering':('RSB-WS02',40,'10.0.40.12')}


def guest(d,role):
    record=d.data['vms'][role]
    vm=next(v for v in d.host.vm if v._moId==record['id']);d.own(vm)
    return vm,record


def credentials(d,path):
    path=Path(path).resolve()
    if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT/'.local'):raise ValueError('Keep credentials in ignored .local or outside this checkout')
    if path.exists():
        value=json.loads(path.read_text())
        if value['owner']!=d.data['owner']:raise ValueError('Credentials belong to another deployment')
    else:
        value={'owner':d.data['owner'],'roles':{role:{'username':'rsbadmin' if role=='Docker' else ('admin' if role=='Firewall' else 'Administrator'),
            'password':'RSB!'+secrets.token_hex(16)} for role in d.data['vms']},
            'dsrm':'RSB!'+secrets.token_hex(16),'agent_service':'RSB!'+secrets.token_hex(16)}
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n');path.chmod(0o600)
    return value


def windows(d,private):
    for role,(name,zone,address) in WINDOWS.items():
        vm,record=guest(d,role)
        if record.get('windows_customization_ready'):print(role,'customization already recorded');continue
        if record.get('windows_customization_task'):raise RuntimeError('Inspect the recorded pending customization task before retrying')
        if str(vm.runtime.powerState)!='poweredOff':raise RuntimeError('Customize only powered-off OS clones')
        if len([x for x in vm.config.hardware.device if isinstance(x,vim.vm.device.VirtualEthernetCard)])!=1:raise RuntimeError('Windows clone must have exactly one lab adapter')
        identity=vim.vm.customization.Sysprep(
            guiUnattended=vim.vm.customization.GuiUnattended(password=vim.vm.customization.Password(value=private['roles'][role]['password'],plainText=True),timeZone=110,autoLogon=True,autoLogonCount=1),
            userData=vim.vm.customization.UserData(fullName='RSB Lab',orgName='RSB Lab',computerName=vim.vm.customization.FixedName(name=name),productId=''),
            identification=vim.vm.customization.Identification(joinWorkgroup='WORKGROUP'))
        ip=vim.vm.customization.IPSettings(ip=vim.vm.customization.FixedIp(ipAddress=address),subnetMask='255.255.255.0',gateway=['10.0.'+str(zone)+'.1'],dnsServerList=['10.0.10.2'],dnsDomain='rs.brew')
        spec=vim.vm.customization.Specification(identity=identity,options=vim.vm.customization.WinOptions(changeSID=True,deleteAccounts=False),
            globalIPSettings=vim.vm.customization.GlobalIPSettings(dnsServerList=['10.0.10.2'],dnsSuffixList=['rs.brew']),nicSettingMap=[vim.vm.customization.AdapterMapping(adapter=ip)])
        task=vm.CustomizeVM_Task(spec=spec);record['windows_customization_task']=task._moId;d.save();wait(task)
        record['windows_customization_ready']=True;d.save();print(role,'private customization staged; OS remains powered off')


def linux(d,private,public_key=None):
    vm,record=guest(d,'Docker')
    if record.get('linux_seed_ready'):raise RuntimeError('Linux seed already recorded; do not replace a running installation')
    if str(vm.runtime.powerState)!='poweredOff':raise RuntimeError('Seed only a powered-off clean Ubuntu OS clone')
    nics=[x for x in vm.config.hardware.device if isinstance(x,vim.vm.device.VirtualEthernetCard)];ethernets={};build=None
    for nic in nics:
        if nic.backing.deviceName==d.spec['upstream_port_group']:name='build0';cfg={'dhcp4':True,'dhcp6':False,'accept-ra':False,'optional':True};build=nic
        else:
            zone=next(z for z,n in d.networks.items() if n==nic.backing.deviceName)
            name='ot'+str(zone);cfg={'dhcp4':False,'dhcp6':False,'link-local':[],'optional':True}
        ethernets[name]={'match':{'macaddress':nic.macAddress},'set-name':name,**cfg}
    if set(ethernets)!={'build0','ot20','ot30','ot40','ot50'}:raise RuntimeError('Unexpected Docker adapter mapping')
    network={'version':2,'ethernets':ethernets}
    user={'name':'rsbadmin','groups':['adm','sudo'],'shell':'/bin/bash','sudo':'ALL=(ALL) NOPASSWD:ALL','lock_passwd':False}
    if public_key:
        key=Path(public_key).read_text().strip()
        if not key.startswith(('ssh-ed25519 ','ssh-rsa ')) or '\n' in key:raise ValueError('Supply one administrator public SSH key')
        user['ssh_authorized_keys']=[key]
    data={'hostname':'rsb-docker01','manage_etc_hosts':True,'disable_root':True,'ssh_pwauth':False,'users':[user],
        'chpasswd':{'expire':False,'users':[{'name':'rsbadmin','password':private['roles']['Docker']['password'],'type':'text'}]},
        'package_update':True,'packages':['open-vm-tools','ca-certificates','curl','git','python3','python3-pip','unzip','docker.io','docker-compose-v2'],
        'write_files':[{'path':'/etc/netplan/60-rsb.yaml','permissions':'0600','content':json.dumps({'network':network})},
            {'path':'/etc/sysctl.d/90-rsb-isolation.conf','content':'net.ipv6.conf.all.disable_ipv6=1\nnet.ipv6.conf.default.disable_ipv6=1\n'}],
        'runcmd':[['netplan','apply'],['sysctl','--system'],['usermod','-aG','docker','rsbadmin'],['systemctl','enable','--now','docker'],
            ['bash','-c','iptables -I DOCKER-USER 1 -i build0 -j DROP; iptables -I DOCKER-USER 1 -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN'],
            ['bash','-c','printf ready > /var/lib/rsb-bootstrap-ready']]}
    encoded=base64.b64encode(('#cloud-config\n'+json.dumps(data)).encode()).decode()
    metadata={'instance-id':d.data['owner']+'-docker','local-hostname':'rsb-docker01','redact':['userdata'],'network':network}
    properties=[]
    for prop in vm.config.vAppConfig.property if vm.config.vAppConfig else []:
        if prop.id in ['user-data','instance-id','hostname']:
            item=copy.deepcopy(prop);item.value={'user-data':encoded,'instance-id':d.data['owner']+'-docker','hostname':'rsb-docker01'}[prop.id]
            properties.append(vim.vApp.PropertySpec(operation='edit',info=item))
    build.connectable.startConnected=True;build.connectable.allowGuestControl=False
    cfg=vim.vm.ConfigSpec(vAppConfig=vim.vApp.VmConfigSpec(property=properties),extraConfig=[
        vim.option.OptionValue(key='guestinfo.userdata',value=encoded),vim.option.OptionValue(key='guestinfo.userdata.encoding',value='base64'),
        vim.option.OptionValue(key='guestinfo.metadata',value=base64.b64encode(json.dumps(metadata).encode()).decode()),vim.option.OptionValue(key='guestinfo.metadata.encoding',value='base64')],
        deviceChange=[vim.vm.device.VirtualDeviceSpec(operation='edit',device=build)])
    wait(vm.ReconfigVM_Task(cfg));record['linux_seed_ready']=True;d.save()
    print('Ubuntu seed staged; temporary build adapter connects at boot. No exercise applications were started.')


def clear_seed(d):
    vm,record=guest(d,'Docker')
    if vm.guest.toolsRunningStatus!='guestToolsRunning':raise RuntimeError('Guest Tools must be ready; verify cloud-init completed before clearing its seed')
    properties=[]
    for prop in vm.config.vAppConfig.property if vm.config.vAppConfig else []:
        if prop.id=='user-data':item=copy.deepcopy(prop);item.value='';properties.append(vim.vApp.PropertySpec(operation='edit',info=item))
    wait(vm.ReconfigVM_Task(vim.vm.ConfigSpec(vAppConfig=vim.vApp.VmConfigSpec(property=properties),extraConfig=[vim.option.OptionValue(key='guestinfo.'+key,value='') for key in ['userdata','userdata.encoding','metadata','metadata.encoding']])))
    record['linux_seed_cleared']=True;d.save();print('VMware seed credential copies cleared; private operator credential file retained.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['windows','linux','clear-seed','start','disconnect-build'])
    parser.add_argument('--spec',type=Path,required=True);parser.add_argument('--state',type=Path,default=ROOT/'.local/vmware/deployment.json')
    parser.add_argument('--credentials',type=Path);parser.add_argument('--ssh-public-key',type=Path);parser.add_argument('--role',choices=['Firewall','Docker',*WINDOWS])
    args=parser.parse_args();d=Deployment(json.loads(args.spec.read_text()),args.state)
    if not d.data or d.data['phase']!='os-clones-ready':raise RuntimeError('Create all six recorded OS clones first')
    d.audit();private_path=args.credentials or args.state.with_name(args.state.stem+'.guests.private.json')
    if args.action in ['windows','linux']:
        private=credentials(d,private_path)
        if args.action=='windows':windows(d,private)
        else:linux(d,private,args.ssh_public_key)
    elif args.action=='clear-seed':clear_seed(d)
    elif args.action=='start':
        if not args.role:raise ValueError('Select one recorded role with --role')
        vm,_=guest(d,args.role)
        if str(vm.runtime.powerState)=='poweredOff':wait(vm.PowerOnVM_Task(host=d.host))
        print(args.role,'powered on; continue guest configuration and readiness checks')
    else:
        vm,_=guest(d,'Docker');nic=next(x for x in vm.config.hardware.device if isinstance(x,vim.vm.device.VirtualEthernetCard) and x.backing.deviceName==d.spec['upstream_port_group'])
        nic.connectable.connected=False;nic.connectable.startConnected=False;nic.connectable.allowGuestControl=False
        wait(vm.ReconfigVM_Task(vim.vm.ConfigSpec(deviceChange=[vim.vm.device.VirtualDeviceSpec(operation='edit',device=nic)])))
        print('Recorded Docker build adapter disconnected, including at boot')
    d.audit()


if __name__=='__main__':main()
