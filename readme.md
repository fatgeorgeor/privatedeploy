# deploy clustered smb/nfs on cephfs

## Prepare
To run this script, you should provide following:
* install fabric
* create a user which have sudo privilege

## How to configure
There is a ```config.json``` file, all parameter must be provided.
* monitors: a list of monitor ip addresses
* osdnodes: a list of osd ip addresses
* user: a system user used to deploy the system
* password: the password of user
* clusterinfo: information of this cluster
* ntpserverip: ip of the ntp server
* vip: the vip to export smb/nfs
* vip_nic: the nic name where ctdb can bind
* disks: a list of disks to install ceph osds

## How to run
After ```config.json``` configed, You can simply run with:
```
python fabfile.py
```

## How to change monitor ip
Note that this script can only be ran ```AFTER``` you changed IP correctly.  

There is a ```changeipconfig.json``` file, all parameter must be provided.
* newmonitors: a list of new monitor IPs
* newosdnodes: a list of new osdnode IPs
* user: a system user used to deploy the system
* password: the password of user
* newvip: the vip to export smb/nfs(you may change the nic, so we provide this option)
* newvip_nic: the nic name where ctdb can bind
After ```changeipconfig.json``` configed, You can simply run with:
```
fab ChangeIp
```

## How to add a view(smb/nfs exporter)
Simply run with:
```
fab AddOneExporter:dirname='test'
```

## How to add a new disk to cluster
Simply run with:
```
fab AddNewDisk:hostname=ceph-bj-beishu-cluster-node-4,diskname=/dev/vdc
```
```hostname``` is the hostname this disk belongs to(you can also use the host ip of the node), diskname is   
the dev name of the disk.

## How to set ntp server
Simply run with:
```
fab SetNtpServer:ip='1.1.1.1'
```
```ip``` is the ip of the ntp server.
