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
    put('resources/stopbalancer.sh', '/tmp/', use_sudo=True)

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
                    hdds = disks['disks']
                    hddnum = len(hdds)

                    if hddnum < 1:
                        print "please provide at lease one hdd for host %s" % host
                        exit(-1)
                    for hdd in hdds:
                        run('dd if=/dev/zero of=%s bs=4M count=1' % (hdd))
                        run('ceph-deploy --overwrite-conf osd create --data %s %s' % (hdd, host))
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

def addOneOsd(hdd):
    run('dd if=/dev/zero of=%s bs=4M count=1' % (hdd))
    run('ceph-deploy --overwrite-conf osd create --data %s %s' % (hdd, env.host))
    

def AddNewDisk(hostname, disk):
    LoadConfig()
    CheckOsdCountBeforeExpand()
    with settings(warn_only=True):
        with cd(DEPLOYDIR):
            with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
                execute(addOneOsd, hdd=disk, host=hostname)
    time.sleep(10)
    CheckExpandResult(True)
    
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
        hdds = disks['disks']
        totaladdedosds += len(hdds)

    if totalosd == uposd == inosd == totaladdedosds:
        n = int((totalosd * 100) / 3.0)
        # n is at least 33.3, so k should be greater than 5
        # 18 is because it's unlikely to have a big cluster with so many osds
        for k in range(5,18):
            if pow(2,k) < n and pow(2,k+1) >= n:
                break

        local("ceph osd pool create volumes %d" % pow(2, k+1))
        time.sleep(5)        
        print ('\33[102m' +  "cluster deployed SUCCESSFULLY" + '\033[0m')
    else:
        print ('\033[91m' + "some osds is FAILED, please double check your configuration" + '\033[0m')

def getexpandresult(onlyone):
    totalosd, uposd, inosd = getosdcount()
    totaladdedosds = 0
    if onlyone:
        totaladdedosds = 1
    else:
        for _, disks in USERDEINEDCONFIG['disks'].items():
            hdds = disks['disks']
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

def CheckExpandResult(onlyone):
    print "waiting for expand results............"
    time.sleep(10)
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(getexpandresult, onlyone=onlyone, host=env.roledefs['monitors'][0])

@parallel
@roles('allnodes')
def all_enablemonitoringservices():
    sudo('systemctl enable node_exporter')
    sudo('systemctl restart node_exporter')
    sudo('systemctl enable ceph_exporter')
    sudo('systemctl restart ceph_exporter')
    sudo('systemctl enable prometheus')
    sudo('systemctl restart prometheus')
    sudo('systemctl enable grafana-server')
    sudo('systemctl restart grafana-server')


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
    CheckExpandResult(False)
    
def startbalancer():
    run("ceph mgr module enable balancer")
    run("ceph config-key set mgr/balancer/max_misplaced .05")
    run("ceph config-key set mgr/balancer/sleep_interval 10")
    run("ceph osd set-require-min-compat-client luminous")
    run("ceph balancer mode upmap")
    run("ceph balancer on")
    run("(sh /tmp/stopbalancer.sh &> /dev/null < /dev/null &) && sleep 1 ", pty=False)
    print("ceph balancer started")

def StartCephBalancer():
    with settings(user=USERDEINEDCONFIG['user'], password=USERDEINEDCONFIG['password']):
        execute(startbalancer, host=env.roledefs['monitors'][0])

if __name__ == "__main__":
    Init()
    SetChronyServers()
    ProcessMonitorHostname()
    CreateMonMgr()
    DeployOsds()
    CheckOsdCount()
    StartCephBalancer()
    if USERDEINEDCONFIG["shouldinstallpromethues"]:
        CleanPrometheus()
        DeployPrometheus()
