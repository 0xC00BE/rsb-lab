#!/usr/bin/env python3
"""Prepare private firewall bootstrap media for the recorded owned VMware clone."""
import argparse
import copy
import hashlib
import io
import json
import ssl
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from pathlib import Path
import pycdlib
from provider import Deployment,ROOT,wait,vim
from customize import credentials,guest


def create(d,output,private_path,public_key,upload):
    vm,record=guest(d,'Firewall')
    if str(vm.runtime.powerState)!='poweredOff':raise RuntimeError('Prepare media only for the powered-off clean firewall clone')
    if record.get('bootstrap_media'):raise RuntimeError('Recorded bootstrap media already exists; inspect/clean it before creating another')
    output=Path(output).resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'.local'):raise ValueError('Keep private media in ignored .local or outside the checkout')
    if output.exists():raise ValueError('Output already exists; refusing to overwrite it')
    private=credentials(d,private_path)
    nics=[x for x in vm.config.hardware.device if isinstance(x,vim.vm.device.VirtualEthernetCard)]
    networks={'wan':d.spec['upstream_port_group'],**{name:d.networks[zone] for name,zone in [('lan',10),('opt1',20),('opt2',30),('opt3',40),('opt4',50)]}}
    macs={}
    for name,network in networks.items():
        matches=[n for n in nics if n.backing.deviceName==network]
        if len(matches)!=1:raise RuntimeError('Unexpected firewall adapter mapping')
        macs[name]=matches[0].macAddress
    settings={'schema_version':1,'hostname':'RSB-FW','macs':macs,'admin_password':private['roles']['Firewall']['password'],
        'provisioning_public_key':Path(public_key).read_text().strip() if public_key else None}
    folder=ROOT/'provisioning/firewall'
    files={'BOOT.PHP':('bootstrap.php',(folder/'bootstrap.php').read_bytes()),
        'SETTINGS.JSN':('settings.json',json.dumps(settings).encode()),'POLICY.JSN':('policy.json',(folder/'policy.json').read_bytes()),
        'APPLY.PHP':('apply-policy.php',(folder/'apply-policy.php').read_bytes()),'VPN.PHP':('vpn.php',(folder/'vpn.php').read_bytes()),
        'FINAL.PHP':('finalize-provisioning.php',(folder/'finalize-provisioning.php').read_bytes())}
    iso=pycdlib.PyCdlib();iso.new(vol_ident='RSB-PRIVATE',joliet=3,rock_ridge='1.09')
    for short,(name,data) in files.items():iso.add_fp(io.BytesIO(data),len(data),iso_path='/'+short+';1',rr_name=name,joliet_path='/'+name)
    output.parent.mkdir(parents=True,exist_ok=True);iso.write(str(output));iso.close();output.chmod(0o600)
    digest=hashlib.sha256(output.read_bytes()).hexdigest();print('Private bootstrap ISO created; it contains an administrator secret and must not be published.')
    if not upload:return
    vmx=vm.config.files.vmPathName;datastore,relative=vmx[1:].split('] ',1)
    if datastore!=d.ds.name:raise RuntimeError('Firewall datastore differs from the specification')
    filename='rsb-bootstrap-'+d.data['owner'].split(':')[-1][:12]+'.private.iso'
    relative=relative.rsplit('/',1)[0]+'/'+filename;target='['+datastore+'] '+relative
    record['bootstrap_media']={'path':target,'local_path':str(output),'sha256':digest,'phase':'upload-planned'};d.save()
    cookie=SimpleCookie();cookie.load(d.si._stub.cookie)
    url='https://'+d.spec['vcenter']+'/folder/'+urllib.parse.quote(relative,safe='/')+'?'+urllib.parse.urlencode({'dcPath':next(x for x in ancestors(vm) if isinstance(x,vim.Datacenter)).name,'dsName':datastore})
    request=urllib.request.Request(url,data=output.read_bytes(),method='PUT',headers={'Cookie':'vmware_soap_session='+cookie['vmware_soap_session'].value,'Content-Type':'application/octet-stream'})
    tls=ssl.create_default_context()
    if d.spec.get('vcenter_certificate'):
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);tls.check_hostname=False
        tls.load_verify_locations(cafile=d.spec['vcenter_certificate']);tls.verify_flags|=ssl.VERIFY_X509_PARTIAL_CHAIN
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=tls))
    with opener.open(request,timeout=60) as response:
        if response.status not in [200,201,204]:raise RuntimeError('Private media upload rejected')
    cds=[x for x in vm.config.hardware.device if isinstance(x,vim.vm.device.VirtualCdrom)]
    if len(cds)!=1:raise RuntimeError('Expected one bootstrap optical device')
    cd=copy.deepcopy(cds[0]);cd.backing=vim.vm.device.VirtualCdrom.IsoBackingInfo(fileName=target)
    cd.connectable=vim.vm.device.VirtualDevice.ConnectInfo(connected=False,startConnected=True,allowGuestControl=False)
    wait(vm.ReconfigVM_Task(vim.vm.ConfigSpec(deviceChange=[vim.vm.device.VirtualDeviceSpec(operation='edit',device=cd)])))
    record['bootstrap_media']['phase']='attached';record['bootstrap_media']['device_key']=cd.key;d.save()
    print('Private media attached only to the recorded firewall clone; unmount and remove it before exercises.')


def ancestors(obj):
    while obj:
        yield obj;obj=getattr(obj,'parent',None)


def cleanup(d):
    vm,record=guest(d,'Firewall');media=record.get('bootstrap_media')
    if not media or media['phase']!='attached':raise RuntimeError('No attached owned media is recorded')
    if str(vm.runtime.powerState)!='poweredOff':raise RuntimeError('Unmount media and cleanly power off this firewall before removing its optical device')
    prefix=vm.config.files.vmPathName.rsplit('/',1)[0]+'/'
    if not media['path'].startswith(prefix) or '/..' in media['path'] or not media['path'].endswith('.private.iso'):raise RuntimeError('Media is outside the owned VM directory')
    cd=next(x for x in vm.config.hardware.device if isinstance(x,vim.vm.device.VirtualCdrom) and x.key==media['device_key'])
    if getattr(cd.backing,'fileName',None)!=media['path']:raise RuntimeError('Optical backing differs from the recorded private media')
    wait(vm.ReconfigVM_Task(vim.vm.ConfigSpec(deviceChange=[vim.vm.device.VirtualDeviceSpec(operation='remove',device=cd)])))
    dc=next(x for x in ancestors(vm) if isinstance(x,vim.Datacenter))
    wait(d.c.fileManager.DeleteDatastoreFile_Task(name=media['path'],datacenter=dc))
    media['phase']='removed';d.save();print('Owned private ISO and its temporary optical device removed; local private media remains for operator cleanup.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['create','cleanup'])
    parser.add_argument('--spec',type=Path,required=True);parser.add_argument('--state',type=Path,default=ROOT/'.local/vmware/deployment.json')
    parser.add_argument('--credentials',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--ssh-public-key',type=Path);parser.add_argument('--upload',action='store_true')
    args=parser.parse_args();d=Deployment(json.loads(args.spec.read_text()),args.state)
    if not d.data or d.data['phase']!='os-clones-ready':raise RuntimeError('Create the six recorded OS clones first')
    d.audit()
    if args.action=='create':create(d,args.output or args.state.parent/'firewall-bootstrap.private.iso',args.credentials or args.state.with_name(args.state.stem+'.guests.private.json'),args.ssh_public_key,args.upload)
    else:cleanup(d)
    d.audit()


if __name__=='__main__':main()
