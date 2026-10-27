#!/usr/bin/env python3
"""Create independent RSB VMs from clean OS templates; never edit a source template."""
import argparse
import copy
import getpass
import json
import os
import re
import secrets
import ssl
import time
from pathlib import Path
from pyVim.connect import SmartConnect
from pyVmomi import vim

ROOT=Path(__file__).resolve().parents[2]
ZONES={10:'Corporate',20:'DMZ',30:'Operations',40:'Engineering',50:'Field'}
MACHINES=[
    ('Firewall','FW',[0,10,20,30,40,50],2,2048),
    ('Docker','Docker01',[0,20,30,40,50],6,12288),
    ('AD','AD01',[10],2,4096),('Corporate','WS01',[10],2,4096),
    ('Jump','WS03',[20],2,4096),('Engineering','WS02',[40],2,4096)]


def wait(task,timeout=1800):
    end=time.monotonic()+timeout
    while task.info.state not in ['success','error']:
        if time.monotonic()>end:raise TimeoutError('vCenter task still pending; inspect before retrying')
        time.sleep(2)
    if task.info.state=='error':raise RuntimeError(task.info.error.localizedMessage)
    return task.info.result


def objects(content,kind):
    view=content.viewManager.CreateContainerView(content.rootFolder,[kind],True)
    try:return list(view.view)
    finally:view.Destroy()


def unique(items,name):
    result=[x for x in items if x.name==name]
    if len(result)!=1:raise RuntimeError('Expected one inventory object named '+name)
    return result[0]


class Deployment:
    def __init__(self,spec,state_path):
        self.spec=spec;self.path=Path(state_path).resolve()
        if spec.get('schema_version')!=1:raise ValueError('Unsupported specification')
        for key in ['instance','vm_prefix','port_group_prefix','switch']:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,50}',spec[key]):raise ValueError('Invalid '+key)
        if self.path.is_relative_to(ROOT) and not self.path.is_relative_to(ROOT/'.local'):
            raise ValueError('Keep deployment state under ignored .local or outside this checkout')
        self.data=json.loads(self.path.read_text()) if self.path.exists() else None
        if self.data and self.data['spec']!=spec:raise RuntimeError('Specification differs from the saved deployment')
        cert=spec.get('vcenter_certificate')
        # Trust only the operator-selected leaf for discovery and SOAP, including
        # self-signed installations. Never disable certificate verification.
        tls=ssl.create_default_context();kwargs={}
        if cert:
            pem=Path(cert).read_text()
            if pem.count('-----BEGIN CERTIFICATE-----')!=1:raise ValueError('Supply one trusted vCenter leaf certificate')
            tls=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            tls.check_hostname=False  # Exact leaf trust replaces name matching.
            tls.load_verify_locations(cadata=pem)
            tls.verify_flags|=ssl.VERIFY_X509_PARTIAL_CHAIN
            kwargs={'serverPemCert':pem}
        self.si=SmartConnect(host=spec['vcenter'],user=os.environ.get('VCENTER_USER') or input('vCenter user: '),
            pwd=os.environ.get('VCENTER_PASSWORD') or getpass.getpass('vCenter password: '),
            sslContext=tls,**kwargs)
        self.tls_context=tls
        self.c=self.si.RetrieveContent()
        self.host=unique(objects(self.c,vim.HostSystem),spec['host'])
        self.ds=unique(self.host.datastore,spec['datastore'])
        self.parent=unique(objects(self.c,vim.Folder),spec['parent_folder'])
        root_pool=self.host.parent.resourcePool
        def pools(pool):
            return [pool]+[item for child in pool.resourcePool for item in pools(child)]
        self.parent_pool=unique(pools(root_pool),spec['resource_pool_parent'])
        self.networks={z:spec['port_group_prefix']+'-'+str(z)+'-'+name for z,name in ZONES.items()}

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(self.data,indent=2)+'\n');self.path.chmod(0o600)

    def own(self,vm):
        if not self.data or vm._moId not in [r['id'] for r in self.data['vms'].values()]:raise RuntimeError('VM is not recorded in this deployment')
        if vm.parent._moId!=self.data['folder_id'] or self.data['owner'] not in (vm.config.annotation or ''):
            raise RuntimeError('VM ownership/folder check failed')
        if vm.runtime.host._moId!=self.host._moId:raise RuntimeError('VM left the selected host')

    def inventory_baseline(self):
        return {'switches':{s.name:{'mtu':s.mtu,'pnics':list(s.pnic or []),'groups':list(s.portgroup or [])} for s in self.host.config.network.vswitch},
            'groups':{p.spec.name:str(p.spec) for p in self.host.config.network.portgroup},
            'vms':{v._moId:{'version':v.config.changeVersion,'folder':v.parent._moId} for v in self.host.vm if v.config}}

    def audit(self):
        before=self.data['baseline'];now=self.inventory_baseline()
        for category in ['switches','groups','vms']:
            for key,value in before[category].items():
                if now[category].get(key)!=value:raise RuntimeError('Outside-resource audit differs: '+category+'/'+key)
        print('Existing switches, port groups and outside VM configurations unchanged.')

    def plan(self):
        templates={role:unique(self.host.vm,name) for role,name in self.spec['templates'].items()}
        for source in templates.values():
            if not source.config.template or str(source.runtime.powerState)!='poweredOff':raise RuntimeError('Sources must be powered-off OS templates')
        unique(self.host.network,self.spec['upstream_port_group'])
        print('Target folder:',self.spec['parent_folder']+'/'+self.spec['instance'])
        print('New uplink-free switch:',self.spec['switch'])
        for role,suffix,zones,cpu,ram in MACHINES:
            print(self.spec['vm_prefix']+'-'+suffix,role,'CPU',cpu,'RAM MiB',ram,'networks',zones)
        print('Only new instance resources will be created. Source templates remain unchanged.')
        return templates

    def create(self):
        templates=self.plan()
        if self.data:
            self.audit()
            if self.data['phase']=='creating-network':
                raise RuntimeError('Initial network creation was interrupted; inspect the recorded owned resources before recovering. No resources were adopted or replaced.')
            folder=next(f for f in self.parent.childEntity if f._moId==self.data['folder_id'])
            pool=next(p for p in self.parent_pool.resourcePool if p._moId==self.data['pool_id'])
        else:
            if any(f.name==self.spec['instance'] for f in self.parent.childEntity):raise RuntimeError('Instance folder already exists; refusing adoption')
            if any(s.name==self.spec['switch'] for s in self.host.config.network.vswitch):raise RuntimeError('Switch name already exists')
            if any(n.name in self.networks.values() for n in self.host.network):raise RuntimeError('Port-group name already exists')
            if any(p.name=='RSB-'+self.spec['instance'] for p in self.parent_pool.resourcePool):raise RuntimeError('Resource-pool name already exists')
            if self.ds.summary.freeSpace<250*2**30:raise RuntimeError('Require at least 250 GiB free datastore headroom')
            baseline=self.inventory_baseline();folder=self.parent.CreateFolder(self.spec['instance'])
            self.data={'spec':self.spec,'owner':'rsb-lab:'+secrets.token_hex(16),'folder_id':folder._moId,'vms':{},'baseline':baseline,'phase':'creating-network'};self.save()
            self.host.configManager.networkSystem.AddVirtualSwitch(vswitchName=self.spec['switch'],spec=vim.host.VirtualSwitch.Specification(numPorts=128,mtu=1500))
            for zone,name in self.networks.items():
                # Corporate also carries the bridged student VPN's extra MAC addresses.
                policy=vim.host.NetworkPolicy(security=vim.host.NetworkPolicy.SecurityPolicy(allowPromiscuous=True,macChanges=True,forgedTransmits=True))
                self.host.configManager.networkSystem.AddPortGroup(portgrp=vim.host.PortGroup.Specification(name=name,vlanId=zone,vswitchName=self.spec['switch'],policy=policy))
            def allocation(limit):return vim.ResourceAllocationInfo(reservation=0,expandableReservation=True,limit=limit,shares=vim.SharesInfo(level='low'))
            pool=self.parent_pool.CreateResourcePool('RSB-'+self.spec['instance'],vim.ResourceConfigSpec(cpuAllocation=allocation(self.spec['cpu_limit_mhz']),memoryAllocation=allocation(self.spec['memory_limit_mib'])))
            self.data['pool_id']=pool._moId;self.data['phase']='cloning';self.save()
        for role,suffix,zones,cpu,ram in MACHINES:
            if role in self.data['vms']:
                vm=next(v for v in folder.childEntity if v._moId==self.data['vms'][role]['id']);self.own(vm);continue
            self.audit();source=templates[role];name=self.spec['vm_prefix']+'-'+suffix
            if any(v.name==name for v in self.host.vm):raise RuntimeError('VM name already exists; refusing replacement: '+name)
            changes=[]
            for device in source.config.hardware.device:
                if isinstance(device,vim.vm.device.VirtualEthernetCard):changes.append(vim.vm.device.VirtualDeviceSpec(operation='remove',device=device))
                elif isinstance(device,vim.vm.device.VirtualCdrom):
                    cd=copy.deepcopy(device);cd.connectable=vim.vm.device.VirtualDevice.ConnectInfo(connected=False,startConnected=False,allowGuestControl=False)
                    changes.append(vim.vm.device.VirtualDeviceSpec(operation='edit',device=cd))
                elif role=='Docker' and isinstance(device,vim.vm.device.VirtualDisk):
                    disk=copy.deepcopy(device)
                    if disk.capacityInKB<120*1024*1024:
                        disk.capacityInKB=120*1024*1024
                        changes.append(vim.vm.device.VirtualDeviceSpec(operation='edit',device=disk))
            for i,zone in enumerate(zones):
                network=unique(self.host.network,self.spec['upstream_port_group'] if zone==0 else self.networks[zone])
                nic=vim.vm.device.VirtualVmxnet3(key=-4000-i,addressType='generated',
                    backing=vim.vm.device.VirtualEthernetCard.NetworkBackingInfo(network=network,deviceName=network.name),
                    connectable=vim.vm.device.VirtualDevice.ConnectInfo(connected=False,startConnected=zone!=0,allowGuestControl=False))
                changes.append(vim.vm.device.VirtualDeviceSpec(operation='add',device=nic))
            cfg=vim.vm.ConfigSpec(name=name,memoryMB=ram,numCPUs=cpu,numCoresPerSocket=cpu,
                annotation=self.data['owner']+' | '+role+' | Independent clean OS full clone',deviceChange=changes)
            spec=vim.vm.CloneSpec(template=False,powerOn=False,config=cfg,
                location=vim.vm.RelocateSpec(host=self.host,datastore=self.ds,pool=pool,diskMoveType='moveAllDiskBackingsAndDisallowSharing',transform='sparse'))
            print('Creating independent full clone:',name,flush=True)
            vm=wait(source.CloneVM_Task(folder=folder,name=name,spec=spec))
            nics=[d for d in vm.config.hardware.device if isinstance(d,vim.vm.device.VirtualEthernetCard)]
            self.data['vms'][role]={'id':vm._moId,'name':name,'source_id':source._moId,'adapters':[
                {'mac':d.macAddress,'network':d.backing.deviceName,'key':d.key} for d in nics]};self.save();self.own(vm)
        self.data['phase']='os-clones-ready';self.save();self.audit()
        print('Six independent OS clones ready; upstream adapters remain disconnected. Continue guest configuration before starting exercises.')

    def status(self):
        if not self.data:raise RuntimeError('No deployment state')
        self.audit();vms={v._moId:v for v in self.host.vm}
        for role,r in self.data['vms'].items():
            vm=vms[r['id']];self.own(vm);print(role,vm.name,str(vm.runtime.powerState),vm.guest.toolsRunningStatus)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['plan','create','status'])
    p.add_argument('--spec',type=Path,required=True);p.add_argument('--state',type=Path,default=ROOT/'.local/vmware/deployment.json')
    a=p.parse_args();d=Deployment(json.loads(a.spec.read_text()),a.state)
    getattr(d,a.action)()


if __name__=='__main__':main()
