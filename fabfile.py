#!/usr/bin/env python
#coding=utf-8 

from fabric.api import *
from fabric.contrib.files import append
import time
import time
import os
import json
import copy
import pdb
import re
import os.path
from jinja2 import Template
import cephfs as libcephfs

# note:
# 1. All functions start with Capital words are called in main function.
# 2. All functions start with local_ are called by deploy node.
# 3. All functions start with monitor_ are called on all monitor nodes.
# 4. All functions start with osd_ are called on all osd nodes.
# 5. All functions start with all_ are called on all nodes(monitors + osds).


USERDEINEDCONFIG = {}
USERHOME = os.getenv('HOME')
SSHDIR = USERHOME + '/.ssh'
SSHPRIFILE = SSHDIR + '/id_rsa'
SSHPUBFILE = SSHDIR + '/id_rsa.pub'
AUTHORIZEDKEYFILE = SSHDIR + '/authorized_keys'
DEPLOYDIR = '/opt/cephdeploy'

SAMBA_CONFIG_TEMPLATE = '''[{{ mountpoint }}]
        path = /{{ mountpoint }}
        vfs objects = ceph
        writable = yes
        browseable = yes
        available = yes
        create mask = 0755
        directory mask = 0755
        valid users = fsuser 
        write list = fsuser\n
'''


def loadConfiguration(file):
    with open(file) as json_file:
        data = json.load(json_file)
        return data

def read_key_file(key_file):
    with open(key_file) as f:
        return f.read()
@parallel
@roles('allnodes')
def all_systemconfig():
    sudo('systemctl stop firewalld')
    sudo('systemctl disable firewalld')
    sudo('setenforce 0')
    sudo("sed -i -e s/SELINUX=enforcing/SELINUX=disabled/g /etc/selinux/config")

@parallel
@roles('osds')
def osd_updatecephdisk():
    put('resoures/main.py', '/usr/lib/python2.7/site-packages/ceph_disk/main.py', use_sudo=True)
    put('resoures/disk.py', '/usr/lib/udev/rules.d/', use_sudo=True)
    put('resoures/99-ceph-osd-remove.rules', DEPLOYDIR, use_sudo=True)

@parallel
@roles('allnodes')
def all_sshnopassword():
    deploynodekey = read_key_file(SSHPUBFILE)
    # note that we need to login to myself to deploy osds, so we auth ourself
    ownkey = run("cat %s" % SSHPUBFILE)
    append(AUTHORIZEDKEYFILE, ownkey.strip());
    append(AUTHORIZEDKEYFILE, deploynodekey.strip());

@parallel
@roles('allnodes')
def all_generateauth():
    append("/etc/ssh/ssh_config", "StrictHostKeyChecking no")
    run("if [ ! -d %s ]; then mkdir -p %s; fi" % (SSHDIR, SSHDIR))
    run("if [ ! -f %s ]; then touch %s; fi" % (AUTHORIZEDKEYFILE, AUTHORIZEDKEYFILE))
    run("if [ ! -f %s ]; then ssh-keygen -o -t rsa -N '' -f %s; fi" % (SSHPUBFILE, SSHPRIFILE))
    sudo("sudo sed -i -e 's/Defaults    requiretty.*/ #Defaults    requiretty/g' /etc/sudoers")

def LoadConfig():
    #pdb.set_trace()
    config = loadConfiguration('config.json')
    user = USERDEINEDCONFIG['user'] = config["user"]
    password = USERDEINEDCONFIG['password'] = config["password"]

    env.roledefs['monitors'] = config["monitors"]
    env.roledefs['osds'] = config["osdnodes"]
    env.roledefs['allnodes'] = copy.copy(config["monitors"])

    # to keep node order
    for i in config["osdnodes"]:
        if i not in config["monitors"]:
            env.roledefs['allnodes'].append(i)
            
    if len(env.roledefs['monitors']) < 1:
        print "please provide at lease one monitor"
        exit(-1)

    USERDEINEDCONFIG['clusterinfo'] = config["clusterinfo"]
    USERDEINEDCONFIG['disks'] = config["disks"]
    USERDEINEDCONFIG['vip'] = config["vip"]
    USERDEINEDCONFIG['ntpserverip'] = config["ntpserverip"]
    USERDEINEDCONFIG['monitorhostnames'] = ''
    USERDEINEDCONFIG['monitorhostnames_sep'] = ''
    USERDEINEDCONFIG['allnodehostnames'] = ''
    USERDEINEDCONFIG['pd_peer'] = ''
    USERDEINEDCONFIG['pd_client_tikv'] = ''
    USERDEINEDCONFIG['pd_client_tidb'] = ''
    USERDEINEDCONFIG['pd_name'] = []
    USERDEINEDCONFIG['ips'] = config["osdnodes"]

    counter = 0
    for i in env.roledefs["allnodes"]:
        if i in config["monitors"]:
            USERDEINEDCONFIG['monitorhostnames'] += "oceanstore-" + USERDEINEDCONFIG['clusterinfo'] + "-node-" + str(counter) + " "
            USERDEINEDCONFIG['monitorhostnames_sep'] += "oceanstore-" + USERDEINEDCONFIG['clusterinfo'] + "-node-" + str(counter) + ","

        counter = counter + 1
    USERDEINEDCONFIG['monitorhostnames_sep'] = USERDEINEDCONFIG['monitorhostnames_sep'].strip(',')

    counter = 0
    for i in env.roledefs["allnodes"]:
        if i in USERDEINEDCONFIG['ips']:
            USERDEINEDCONFIG['pd_peer'] += "pd" + str(counter) + "=http://" + str(i) + ":2380,"
            USERDEINEDCONFIG['pd_client_tikv'] += "\"" + str(i) + ":2379\","
            USERDEINEDCONFIG['pd_client_tidb'] += str(i) + ":2379,"
            USERDEINEDCONFIG['pd_name'].append("pd" + str(counter))

        counter = counter + 1

    USERDEINEDCONFIG['tidb_deploy'] = "/home/tidb/deploy"
    USERDEINEDCONFIG['pd_conf'] = USERDEINEDCONFIG['tidb_deploy'] + "/conf/pd.toml"
    USERDEINEDCONFIG['tikv_conf'] = USERDEINEDCONFIG['tidb_deploy'] + "/conf/tikv.toml"
    USERDEINEDCONFIG['tidb_conf'] = USERDEINEDCONFIG['tidb_deploy'] + "/conf/tidb.toml"
    systemd_conf="/etc/systemd/system"
    USERDEINEDCONFIG['pd_service'] = systemd_conf + "/pd.service"
    USERDEINEDCONFIG['tidb_service'] = systemd_conf + "/tidb-4000.service"
    USERDEINEDCONFIG['tikv_service'] = systemd_conf + "/tikv-20160.service"
    print USERDEINEDCONFIG['pd_name']
    print USERDEINEDCONFIG['pd_client_tikv']
    print USERDEINEDCONFIG['pd_client_tidb']

def Init():
    LoadConfig()
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(all_generateauth)
        execute(all_sshnopassword)
        with settings(warn_only=True):
            execute(all_systemconfig)
            execute(osd_updatecephdisk)

# -------- functions deploy osds begin------------------------------#
@parallel
@roles('osds')
def osd_deployosds():
    with cd(DEPLOYDIR):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            print(USERDEINEDCONFIG['disks'])
            for host,disks in USERDEINEDCONFIG['disks'].items():
                if env.host == host:
                    for disk in disks:
                        run('ceph-deploy --overwrite-conf osd create --zap-disk %s:%s' % (host, disk))
                    break
@parallel
@roles('osds')
def osds_makedeploydir():
    run('rm -rf %s && mkdir -p %s' % (DEPLOYDIR, DEPLOYDIR))

@parallel
@roles('osds')
def osds_copydeployfiles():
    put("*", DEPLOYDIR)
    
def DeployOsds():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(osds_makedeploydir)
        execute(osds_copydeployfiles)
        #execute(osds_passmyself)
        with settings(warn_only=True):
            execute(osd_deployosds)
# -------- functions deploy osds end ------------------------------#
# -------- functions deploy monitors and mgrs begin------------------------------#
@parallel
@roles('allnodes')
def all_copykeyring():
    # note put/append can add use_sudo=True to pass permission issue.
    put("./ceph.client.admin.keyring", "/etc/ceph/", use_sudo=True)
    put("./ceph.conf", "/etc/ceph/", use_sudo=True)

@parallel
@roles('allnodes')
def all_cleancephdatawithmercy():
    sudo('systemctl stop ceph-mon.target')
    sudo('systemctl stop ceph-osd.target')
    sudo('systemctl stop ceph-mgr.target')
    sudo('systemctl stop ceph-mds.target')
    sudo('rm /var/lib/ceph/bootstrap-*/* -f')
    sudo('rm /etc/systemd/system/ceph-osd.target.wants/* -f')
    sudo('rm /etc/systemd/system/ceph-mon.target.wants/* -f')
    sudo('rm /etc/systemd/system/ceph-mds.target.wants/* -f')
    sudo('rm /etc/systemd/system/ceph-mgr.target.wants/* -f')
    sudo('rm /var/lib/ceph/tmp/* -rf')
    sudo('rm /var/lib/ceph/mon/* -rf')
    sudo('rm /var/lib/ceph/mds/* -rf')
    sudo('rm /var/lib/ceph/mgr/* -rf')
    sudo('for i in `ls /var/lib/ceph/osd/`; do umount /var/lib/ceph/osd/$i -l; done')
    time.sleep(5)
    sudo('rm /var/lib/ceph/osd/* -rf')
    sudo('rm /etc/ceph/* -f')

def local_createmonitorsandmgrs(mons):
    local("ceph-deploy --overwrite-conf new " + mons)
    local("ceph-deploy --overwrite-conf mon create " + mons)
    time.sleep(30)
    local("ceph-deploy gatherkeys " +  mons)
    local("ceph-deploy --overwrite-conf mgr create " + mons)
    local("ceph-deploy --overwrite-conf mds create " + mons)

def CreateMonMgrMds():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        with settings(warn_only=True):
            execute(all_cleancephdatawithmercy)
        with cd(os.getcwd()):
            execute(local_createmonitorsandmgrs, mons=USERDEINEDCONFIG['monitorhostnames'])
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        	execute(all_copykeyring)

# -------- functions deploy monitors and mgrs begin------------------------------#

# -------- functions processing hostname and /etc/hosts file begin------------------------------#
# node only deploy node need to know the hostnames of each node
def remote_sethostname(hostname):
    sudo("hostnamectl set-hostname %s" %  hostname)

def local_appendhosts(hostip, hostname):
    sudo('sed -i "/%s/d" /etc/hosts' % hostname)
    append('/etc/hosts', '%s %s' % (hostip, hostname), use_sudo=True)

@parallel
@roles('allnodes')
def all_updatehosts():
    put("/etc/hosts", "/etc/hosts", use_sudo=True)

def UpdateHosts():
    counter = 0
    for i in env.roledefs["allnodes"]:
        hostnametoset = "oceanstore-" + USERDEINEDCONFIG['clusterinfo'] + "-node-" + str(counter)
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            # we must specify host to localhost to run this command locally
            execute(local_appendhosts, host="127.0.0.1", hostip=i, hostname=hostnametoset) 
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(remote_sethostname, host=i, hostname=hostnametoset)
        counter = counter + 1

    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(all_updatehosts)
# -------- functions processing hostname and /etc/hosts file end ------------------------------#

# -------- functions to prepare cephfs begin ------------------------------#
# note this should be running on a single ceph node, we choose leader monitor here
def mon_preparecephfs():
    osdnodes = len(env.roledefs['osds'])

    #(fixme) this is just an workaound for a two-node cluster, remove it after test.
    k = osdnodes - 1
    if k == 1:
        k = 2

    #1. create ec pool and metadata pool
    # always use (n-1, 1) to provide more space
    run("ceph osd erasure-code-profile set fsecprofile k=%d m=1 crush-failure-domain=host" % k)
    run("ceph osd crush rule create-erasure fsecrule fsecprofile") 
    run("ceph osd pool create data 128 128 erasure fsecprofile fsecrule")
    run("ceph osd pool create metadata 128 128")
    run("ceph osd pool set data min_size %d" % k)
    run("ceph osd pool set data allow_ec_overwrites true") 
    #2. create cephfs
    run("ceph fs new newfs metadata data") 
    run("ceph fs set newfs max_file_size 17592186044416") 
    
def PrepareCephfs():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        with settings(warn_only=True):
            execute(mon_preparecephfs, host=env.roledefs['monitors'][0])
    #waiting for cephfs work
    time.sleep(5)
# -------- functions to prepare cephfs begin ------------------------------#

# -------- functions to add nfs and smb user start ------------------------------#
@parallel
@roles("allnodes")
def all_adduser():
    sudo("groupadd fsuser -g 10099")
    sudo("useradd -u 10099 fsuser -g fsuser  -s /sbin/nologin")
    sudo('echo -ne "fspassword\nfspassword\n" | smbpasswd -a  fsuser')

def AddUser():
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(all_adduser)
# -------- functions to add nfs and smb user end ------------------------------#

# -------- functions to add nfs and smb add one exporter begin------------------------------#
@parallel
@roles("allnodes")
def addOneExporter(dirname):
    append('/etc/exports', '/fs/%s *(rw,sync,no_subtree_check,all_squash,anonuid=10099,anongid=10099)' % dirname, use_sudo=True)
    sudo('exportfs -a')
    t = Template(SAMBA_CONFIG_TEMPLATE)
    content = t.render(mountpoint=dirname)
    sudo('echo "%s" >> /etc/samba/smb.conf' % content)
    sudo('systemctl reload smb')

def AddOneExporter(dirname):
    LoadConfig()
    #create dir using cephfs API
    try:
        cephfs = libcephfs.LibCephFS(conffile='')
        cephfs.mount()
        try:
            cephfs.stat(dirname)
        except libcephfs.ObjectNotFound:
            cephfs.mkdir(dirname, 0o777)
        cephfs.shutdown()
    except Exception as e:
        print(e)
        return
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(addOneExporter, dirname=dirname)
# -------- functions to add nfs and smb add one exporter end------------------------------#


# -------- functions to change monitor ip begin------------------------------#
def loadNewConfig():
    config = loadConfiguration('changeipconfig.json')
    user = USERDEINEDCONFIG['user'] = config["user"]
    password = USERDEINEDCONFIG['password'] = config["password"]
    USERDEINEDCONFIG['newvip'] = config["newvip"]

    env.roledefs['newmonitors'] = config["newmonitors"]
    env.roledefs['newosdnodes'] = config["newosdnodes"]
    env.roledefs['allnodes'] = copy.copy(config["newmonitors"])

    s = ''
    for i in config["newmonitors"]:
        s += i + ','

    USERDEINEDCONFIG['monitorip_sep'] = s[:-1]

    # to keep node order
    for i in config["newosdnodes"]:
        if i not in config["newmonitors"]:
            env.roledefs['allnodes'].append(i)
            
    if len(env.roledefs['newmonitors']) < 1:
        print "please provide at lease one monitor"
        exit(-1)

    USERDEINEDCONFIG['vip'] = config["newvip"]



iphostnamedict = {}
moniphostnamedict = {}

def whoami():
    hostname=run('hostname -s')
    iphostnamedict[env.host] = hostname
    if env.host in env.roledefs['newmonitors']:
        moniphostnamedict[env.host] = hostname
        
@roles('allnodes')
def stopotherservices():
    sudo("systemctl stop nier")
    sudo("systemctl stop niergui")
    sudo("systemctl stop automata")
    sudo("systemctl stop smb")
    sudo("systemctl stop nfs")

@roles('allnodes')
def startotherservices():
    sudo("systemctl start nier")
    sudo("systemctl start niergui")
    sudo("systemctl start automata")
    sudo('systemctl start smb')
    sudo('systemctl start nfs')

@parallel
@roles('allnodes')
def stopcephservice():
    sudo("systemctl stop ceph-mds.target")
    sudo("systemctl stop ceph-osd.target")
    sudo("systemctl stop ceph-mgr.target")
    sudo("systemctl stop ceph-mon.target")

@parallel
@roles('allnodes')
def startcephservice():
    sudo('sed -i "/mon_host/d" /etc/ceph/ceph.conf')
    append('/etc/ceph/ceph.conf', 'mon_host = %s' % USERDEINEDCONFIG['monitorip_sep'], use_sudo=True)
    # in case to many failed times for these targets
    sudo("systemctl reset-failed ceph-mon@%s.service" % env.host)
    sudo("systemctl reset-failed ceph-mgr@%s.service" % env.host)
    sudo("systemctl reset-failed ceph-osd@%s.service" % env.host)
    sudo("systemctl reset-failed ceph-mds@%s.service" % env.host)

    sudo("systemctl start ceph-mds.target")
    sudo("systemctl start ceph-mon.target")
    sudo("systemctl start ceph-mgr.target")
    sudo("systemctl start ceph-osd.target")
    sudo("systemctl start ceph-mds.target")

@parallel
@roles('allnodes')
def modifyhosts():
    for ip, hostname in iphostnamedict.items():
        sudo('sed -i "/%s/d" /etc/hosts' % hostname)
        append('/etc/hosts', ip + " " + hostname, use_sudo=True)

@parallel
@roles('newmonitors')
def changemonitorconfig():
    fsid=run('ceph-conf fsid')
    myhostname=run('hostname -s')
    monnum = len(env.roledefs['newmonitors'])
    run('monmaptool --clobber --create --fsid %s /tmp/monmap' % fsid)

    for monip, monhostname in moniphostnamedict.items():
        run('monmaptool --add ' + monhostname + ' ' + monip +  ' /tmp/monmap')

    for monip, monhostname in moniphostnamedict.items():
        if monhostname == myhostname:
            print("injecter monmap")
            sudo('ceph-mon -i ' + myhostname + ' --inject-monmap /tmp/monmap')

@parallel
@roles('allnodes')
def updateconfigfile(oconfig):
    oconfig['monitors'] = env.roledefs['newmonitors']
    oconfig['osdnodes'] = env.roledefs['newosdnodes']
    oconfig['vip'] = USERDEINEDCONFIG['newvip']

    f=open('config.json.new', 'w')
    json.dump(oconfig, f, indent=2)
    f.close()
    put('config.json.new', DEPLOYDIR + '/config.json')

def loadOldConfig():
    return loadConfiguration('config.json')


def ChangeIp():
    loadNewConfig()
    oconfig = loadOldConfig()
    if len(oconfig['monitors']) != len(env.roledefs['newmonitors']) \
        or len(oconfig['osdnodes']) != len(env.roledefs['newosdnodes']):
        print("must have same size of monitors and osds")
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(stopcephservice)
            for i in env.roledefs['allnodes']:
                execute(whoami, host=i)
            execute(modifyhosts)
            for i in env.roledefs['allnodes']:
                execute(config_keepalived_interface, host=i)
            execute(changemonitorconfig)
            execute(startcephservice)
            execute(updateconfigfile, oconfig=oconfig)

    Prometheus()
    
# -------- functions to change monitor ip end------------------------------#
@roles('allnodes')
def StopOtherServicesIfAny():
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(stopotherservices)

@roles('allnodes')
def StartOtherServices():
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(startotherservices)
    time.sleep(5)

@roles('allnodes')
def reboot():
    sudo("sudo reboot")

@roles('allnodes')
def Reboot():
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(reboot)


@parallel
@roles('allnodes')
def getdate():
    sudo("date")

def GetDate():
    LoadConfig()
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(getdate)


# -------- functions to add new disk as new osd begin------------------------------#
def addOneOsd(hostname, diskname):
    run('dd if=/dev/zero of=%s bs=128M count=1' % diskname)
    run('ceph-deploy --overwrite-conf osd create --zap-disk %s:%s' % (hostname, diskname))
    

def AddNewDisk(hostname, diskname):
    LoadConfig()
    with settings(warn_only=True):
        with cd(DEPLOYDIR):
            with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
                execute(addOneOsd, hostname=hostname, diskname=diskname, host=hostname)
    
# -------- functions to add new disk as new osd end ------------------------------#

# -------- functions to add new disk as new osd begin------------------------------#
@parallel
@roles('allnodes')
def setNtp(ip):
    sudo('sed -i "/server /d" /etc/ntp.conf')
    sudo('sed -i "/ntpserver /d" /etc/hosts')
    sudo('sed -i "/ntpserver/d" /usr/lib/systemd/system/ntpd.service')
    append('/etc/ntp.conf', 'server ntpserver iburst', use_sudo=True)
    append('/etc/hosts', '%s ntpserver' % ip, use_sudo=True)
    append('/etc/sysconfig/ntpd', 'SYNC_HWCLOCK=yes', use_sudo=True)
    append('/etc/sysconfig/ntpd', 'NTPDATE_OPTIONS=""', use_sudo=True)
    append('/etc/sysconfig/ntpd', 'OPTIONS="-g"', use_sudo=True)
    sudo('sed -i "/ExecStart/aExecStartPre=/usr/sbin/ntpdate ntpserver" /usr/lib/systemd/system/ntpd.service')
    sudo('sed -i "/ExecStartPre/aExecStopPost=/usr/sbin/ntpdate ntpserver" /usr/lib/systemd/system/ntpd.service')
    sudo('systemctl daemon-reload')
    sudo('systemctl restart ntpd')
    

def SetNtpServer(ip):
    LoadConfig()
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(setNtp, ip=ip)
# -------- functions to add new disk as new osd end ------------------------------#


@roles("allnodes")
def Prometheus_node():
            put('resoures/prometheus.yaml', '/etc/prometheus/', use_sudo=True)
            put('resoures/node_targets.yaml', '/etc/prometheus/', use_sudo=True)
            for ip in USERDEINEDCONFIG['ips']: 
                sudo("echo '" + "    - \"" + ip + ":9100\"' >> /etc/prometheus/node_targets.yaml");

            sudo("systemctl restart prometheus");
            #tricky bug maybe, have to restart ceph_exporter
            sudo("systemctl restart ceph_exporter");

@roles("allnodes")
def config_snmpd():
    put('resoures/snmpd.conf', '/etc/snmp/snmpd.conf', use_sudo=True)


def Prometheus():
    print "Configure Prometheus"
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(Prometheus_node)
            execute(config_snmpd)

    print "Configure Prometheus end"

@parallel
@roles("allnodes")
def stop_keepalived():
    sudo('systemctl stop keepalived')

@parallel
@roles("allnodes")
def start_keepalived():
    sudo('systemctl restart keepalived')

@roles("allnodes")
def config_keepalivedbasic_smbnfs():
    put('resoures/keepalived.conf', '/etc/keepalived/keepalived.conf', use_sudo=True)
    sudo('systemctl enable keepalived')
    sudo('systemctl enable smb')
    sudo('systemctl enable nfs')
    put('resoures/smb.conf', '/etc/samba/smb.conf', use_sudo=True)
    put('resoures/getnic.sh', '/tmp/getnic.sh', use_sudo=True)
    sudo('echo -n > /etc/exports')

@parallel
@roles("allnodes")
def config_keepalived_interface():
    nic=sudo("sh /tmp/getnic.sh " + env.host)
    sudo("augtool set /files/etc/keepalived/keepalived.conf/vrrp_instance/interface %s " % (nic))
    sudo("augtool set /files/etc/keepalived/keepalived.conf/vrrp_instance/virtual_ipaddress/ipaddr %s " % (USERDEINEDCONFIG["vip"]))
    hostname=sudo("hostname -s")

    #first server set to MASTER
    if int(hostname[-1]) == 0:
        sudo("augtool set /files/etc/keepalived/keepalived.conf/vrrp_instance/state MASTER") 

    sudo("augtool set /files/etc/keepalived/keepalived.conf/vrrp_instance/priority %d" % (100-int(hostname[-1])))

def StopKeepalivedIfAny():
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(stop_keepalived)

def StartKeepalived():
    print "Configure Keepalived"
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(config_keepalivedbasic_smbnfs)
            execute(config_keepalived_interface)
            execute(start_keepalived)

if __name__ == "__main__":
    Init()
    SetNtpServer(ip=USERDEINEDCONFIG['ntpserverip'])
    StopOtherServicesIfAny()
    StopKeepalivedIfAny()
    UpdateHosts()

    # only after ceph and smb installed can we add user
    AddUser()
    CreateMonMgrMds()
    DeployOsds()
    PrepareCephfs()
    StartKeepalived() 
    #remove this default export
    #AddOneExporter('test')
    Prometheus()
    StartOtherServices()
