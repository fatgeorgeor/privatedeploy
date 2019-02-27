#!/usr/bin/env python
#coding=utf-8 

from fabric.api import *
from fabric.contrib.files import append
import time
import time
import os
import json
import copy
import re
import random
import os.path
import pdb

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
ORIGINALTOTAL = 0
ORIGINALUP = 0
ORIGINALIN = 0


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
@roles('allnodes')
def all_copyscripts():
    put('resources/clearcephlvm.sh', '/tmp/', use_sudo=True)

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
    with settings(warn_only=True):
    	append("/etc/ssh/ssh_config", "StrictHostKeyChecking no", use_sudo=True)
    	run("if [ ! -d %s ]; then mkdir -p %s; fi" % (SSHDIR, SSHDIR))
    	run("if [ ! -f %s ]; then touch %s; fi" % (AUTHORIZEDKEYFILE, AUTHORIZEDKEYFILE))
    	run("if [ ! -f %s ]; then ssh-keygen -o -t rsa -N '' -f %s; fi" % (SSHPUBFILE, SSHPRIFILE))
    	sudo("sudo sed -i -e 's/Defaults    requiretty.*/ #Defaults    requiretty/g' /etc/sudoers")

def LoadConfig():
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

    USERDEINEDCONFIG['disks'] = config["disks"]
    USERDEINEDCONFIG['chronyservers'] = config["chronyservers"]
    USERDEINEDCONFIG['monitorhostnames'] = ''
    USERDEINEDCONFIG['databasesize'] = config['databasesize']
    USERDEINEDCONFIG['shouldinstallpromethues'] = config['shouldinstallpromethues']

def LoadExpandConfig():
    config = loadConfiguration('expand.json')
    user = USERDEINEDCONFIG['user'] = config["user"]
    password = USERDEINEDCONFIG['password'] = config["password"]

    env.roledefs['monitors'] = config["monitors"]
    env.roledefs['osds'] = config["newosdnodes"]
    env.roledefs['allnodes'] = config["newosdnodes"]
            
    if len(env.roledefs['monitors']) < 1:
        print "please provide at lease one monitor"
        exit(-1)

    USERDEINEDCONFIG['disks'] = config["disks"]
    USERDEINEDCONFIG['chronyservers'] = config["chronyservers"]
    USERDEINEDCONFIG['databasesize'] = config['databasesize']

moniphostnamedict = {}

def whoami():
    hostname = run('hostname -s')
    moniphostnamedict[env.host] = hostname

def ProcessMonitorHostname():
    for i in env.roledefs['monitors']:
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(whoami, host=i)

    local('cp /etc/hosts /tmp/hosts')
    local('cp resources/hosts /etc/hosts')

    for ip, hostname in moniphostnamedict.items():
        USERDEINEDCONFIG['monitorhostnames'] += hostname + " "
        local("echo %s %s >> /etc/hosts" % (ip, hostname))

def Init():
    LoadConfig()
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(all_generateauth)
        execute(all_sshnopassword)
        with settings(warn_only=True):
            execute(all_systemconfig)
        execute(all_copyscripts)
    local("rm *keyring* -f")

# -------- functions deploy osds begin------------------------------#
@parallel
@roles('osds')
def osd_deployosds():
    with cd(DEPLOYDIR):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            for host, disks in USERDEINEDCONFIG['disks'].items():
                if env.host == host:
                    ssds = disks['ssds']
                    hdds = disks['hdds']
                    ssdnum = len(ssds)
                    hddnum = len(hdds)

                    if ssdnum < 1 or hddnum < 1:
                        print "please provide at lease one ssd/hdd for host %s" % host
                        exit(-1)

                    partitionmap = {}
                    # clear patitions of every ssd
                    for i in ssds + hdds:
                        sudo('sgdisk -o %s' % i)
                        sudo('partprobe %s' % i)

                    for i in ssds:
                        partitionmap[i] = 1
                    for index, hdd in enumerate(hdds):
                        sudo('dd if=/dev/zero of=%s bs=128M count=1' % hdd)
                        ssd = ssds[index % ssdnum]
                        sudo('sgdisk -n 0:0:+%dG %s' % (USERDEINEDCONFIG['databasesize'], ssd))
                        sudo('sgdisk -n 0:0:+10G %s' % (ssd))
                        sudo('partprobe %s' % (ssd))
                        partitionmap[ssd] += 2
                        dbpath = ssd + "%s" % (partitionmap[ssd]-2)
                        walpath = ssd + "%s" % (partitionmap[ssd]-1)
                        run('ceph-deploy --overwrite-conf osd create --block-db %s --block-wal %s --data %s %s' % (dbpath, walpath, hdd, host))
                    break
@parallel
@roles('osds')
def osds_makedeploydir():
    with settings(warn_only=True):
    	sudo('rm -rf %s && mkdir -p %s' % (DEPLOYDIR, DEPLOYDIR))

@parallel
@roles('osds')
def osds_copydeployfiles():
    put("*", DEPLOYDIR, use_sudo=True)
    put("/etc/ceph/ceph.conf", DEPLOYDIR, use_sudo=True)
    
def DeployOsds():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(osds_makedeploydir)
        execute(osds_copydeployfiles)
        with settings(warn_only=True):
            execute(osd_deployosds)
# -------- functions deploy osds end ------------------------------#
@parallel
@roles('osds')
def all_copykeyring():
    # note put/append can add use_sudo=True to pass permission issue.
    put("./ceph.client.admin.keyring", "/etc/ceph/", use_sudo=True)

@parallel
@roles('allnodes')
def all_copyconf():
    put("./ceph.conf", "/etc/ceph/", use_sudo=True)

@parallel
@roles('allnodes')
def all_cleancephdatawithmercy():
    sudo('systemctl stop ceph-mon.target')
    sudo('systemctl stop ceph-osd.target')
    sudo('systemctl stop ceph-mgr.target')
    sudo('rm /var/lib/ceph/bootstrap-*/* -f')
    sudo('rm /etc/systemd/system/ceph-osd.target.wants/* -f')
    sudo('rm /etc/systemd/system/ceph-mon.target.wants/* -f')
    sudo('rm /etc/systemd/system/ceph-mgr.target.wants/* -f')
    sudo('rm /var/lib/ceph/tmp/* -rf')
    sudo('rm /var/lib/ceph/mon/* -rf')
    sudo('rm /var/lib/ceph/mgr/* -rf')
    sudo('for i in `ls /var/lib/ceph/osd/`; do umount /var/lib/ceph/osd/$i -l; done')
    sudo('sh /tmp/clearcephlvm.sh')
    time.sleep(5)
    sudo('rm /var/lib/ceph/osd/* -rf')
    sudo('rm /etc/ceph/* -f')

def local_createmonitorsandmgrs(mons):
    local("ceph-deploy --overwrite-conf new " + mons)
    local("ceph-deploy --overwrite-conf mon create " + mons)
    time.sleep(30)
    local("ceph-deploy gatherkeys " +  mons)
    local("ceph-deploy --overwrite-conf mgr create " + mons)
    local("cp /tmp/hosts /etc/hosts")

def CreateMonMgr():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        with settings(warn_only=True):
            execute(all_cleancephdatawithmercy)
        with cd(os.getcwd()):
            execute(local_createmonitorsandmgrs, mons=USERDEINEDCONFIG['monitorhostnames'])
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        	execute(all_copykeyring)
        	execute(all_copyconf)

@parallel
@roles('allnodes')
def stopcephservice():
    sudo("systemctl stop ceph-osd.target")
    sudo("systemctl stop ceph-mgr.target")
    sudo("systemctl stop ceph-mon.target")

def addOneOsd(ssd, hdd, databasesize):
    s = sudo("blkid | grep %s | awk -F':' '{print $1}' | awk -F'%s' '{print $2}'" %(ssd, ssd))
    partset = set()
    for i in s:
        if i != '\r' and i != '\n':
            partset.add(i)

    sudo('sgdisk -n 0:0:+%sG %s' % (databasesize, ssd))
    sudo('partprobe %s' % (ssd))

    s = sudo("blkid | grep %s | awk -F':' '{print $1}' | awk -F'%s' '{print $2}'" %(ssd, ssd))
    partset_afterdb = set()
    for i in s:
        if i != '\r' and i != '\n':
            partset_afterdb.add(i)
    dbpartnum = int((partset_afterdb - partset).pop())

    sudo('sgdisk -n 0:0:+10G %s' % (ssd))
    sudo('partprobe %s' % (ssd))
    s = sudo("blkid | grep %s | awk -F':' '{print $1}' | awk -F'%s' '{print $2}'" %(ssd, ssd))
    partset_afterwal = set()
    for i in s:
        if i != '\r' and i != '\n':
            partset_afterwal.add(i)

    walnum = int((partset_afterwal - partset_afterdb).pop())

    run('ceph-deploy --overwrite-conf osd create --block-db %s%d --block-wal %s%d --data %s %s' % (ssd, dbpartnum, ssd, walnum, hdd, env.host))
    

def AddNewDisk(hostname, ssd, hdd, databasesize):
    LoadConfig()
    with settings(warn_only=True):
        with cd(DEPLOYDIR):
            with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
                execute(addOneOsd, ssd=ssd, hdd=hdd, databasesize=databasesize, host=hostname)
    
@parallel
@roles('allnodes')
def setChrony():
    #chrony is supposed to be install in this iso
    #sudo('yum install chrony -y')
    sudo('sed -i "/server /d" /etc/chrony.conf')

    for ip in USERDEINEDCONFIG['chronyservers']:
        append('/etc/chrony.conf', 'server %s iburst' % ip, use_sudo=True)

    sudo('systemctl enable chronyd')
    sudo('systemctl restart chronyd')

def SetChronyServers():
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(setChrony)

def getosdcount():
    s = json.loads(run('ceph osd stat -f json-pretty'))

    return s["num_osds"], s["num_up_osds"], s["num_in_osds"]

def getdeployresult():
    totalosd, uposd, inosd = getosdcount()
    totaladdedosds = 0
    for _, disks in USERDEINEDCONFIG['disks'].items():
        hdds = disks['hdds']
        totaladdedosds += len(hdds)

    if totalosd == uposd == inosd == totaladdedosds:
        print ('\33[102m' +  "cluster deployed SUCCESSFULLY" + '\033[0m')
    else:
        print ('\033[91m' + "some osds is FAILED, please double check your configuration" + '\033[0m')

def getexpandresult():
    totalosd, uposd, inosd = getosdcount()
    totaladdedosds = 0
    for _, disks in USERDEINEDCONFIG['disks'].items():
        hdds = disks['hdds']
        totaladdedosds += len(hdds)

    if totalosd-ORIGINALTOTAL == uposd-ORIGINALIN == inosd-ORIGINALUP == totaladdedosds:
        print ('\33[102m' +  "cluster expanded SUCCESSFULLY" + '\033[0m')
    else:
        print ('\033[91m' + "some osds is FAILED, please double check your configuration" + '\033[0m')

def CheckOsdCount():
    print "waiting for deploy results............"
    time.sleep(10)
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(getdeployresult, host=env.roledefs['monitors'][0])

def expandgetosdcount():
    global ORIGINALTOTAL, ORIGINALUP, ORIGINALIN
    ORIGINALTOTAL, ORIGINALUP, ORIGINALIN = getosdcount()

def CheckOsdCountBeforeExpand():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(expandgetosdcount, host=env.roledefs['monitors'][0])

def CheckExpandResult():
    print "waiting for expand results............"
    time.sleep(10)
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(getexpandresult, host=env.roledefs['monitors'][0])

@parallel
@roles('allnodes')
def all_enablemonitoringservices():
    sudo('systemctl enable node_exporter')
    sudo('systemctl restart node_exporter')
    sudo('systemctl enable ceph_exporter')
    sudo('systemctl restart ceph_exporter')
    sudo('systemctl enable prometheus')
    sudo('systemctl restart prometheus')


def DeployPrometheus():
    LoadConfig()
    with settings(warn_only=True):
        with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
            execute(all_enablemonitoringservices)

    local("echo '  - job_name: \"ceph\"' >> /etc/prometheus/prometheus.yml")
    local("echo '    static_configs: ' >> /etc/prometheus/prometheus.yml")
    local("echo '    - targets: [\'localhost:9128\']' >> /etc/prometheus/prometheus.yml")
    

    local("systemctl restart ceph_exporter")
    local("systemctl restart prometheus")

    for i in env.roledefs["allnodes"]:
        local("echo '  - job_name: \"%s\"' >> /etc/prometheus/prometheus.yml" % i)
        local("echo '    static_configs: ' >> /etc/prometheus/prometheus.yml")
        local("echo '    - targets: [%s:9100]' >> /etc/prometheus/prometheus.yml" % i)

def CleanPrometheus():
    with settings(warn_only=True):
        local("cp resources/prometheus.yml /etc/prometheus/")
        local("systemctl stop prometheus")
        local("rm /var/lib/prometheus/data -rf")

def AddNewHostsToCluster():
    LoadExpandConfig()
    SetChronyServers()
    local("rm *keyring* -f")
    local("ceph-deploy gatherkeys " +  env.roledefs['monitors'][0])
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(all_generateauth)
        execute(all_sshnopassword)
        with settings(warn_only=True):
            execute(all_systemconfig)
        execute(all_copyscripts)
        with settings(warn_only=True):
            execute(all_cleancephdatawithmercy)
        execute(all_copykeyring)
    CheckOsdCountBeforeExpand()
    DeployOsds()
    CheckExpandResult()
    

if __name__ == "__main__":
    Init()
    SetChronyServers()
    ProcessMonitorHostname()
    CreateMonMgr()
    DeployOsds()
    CheckOsdCount()
    if USERDEINEDCONFIG["shouldinstallpromethues"]:
        CleanPrometheus()
        DeployPrometheus()
