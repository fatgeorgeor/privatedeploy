0、这个分支维护了纯hdd的部署,这种环境下，没有ssd，所有osd的数据全部存储在hdd上, 部署方式跟有ssd的稍有不同。  
1、安装ceph-common ceph-osd ceph-mon fabric ceph-deploy等包, 并给各台服务器配置各不相同的hostname;  
2、配置config.json，包含的字段包括:
- monitors: 一个数组，集群需要安装的monitor列表;
- osdnodes: 一个数组，集群需要安装的osd服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- chronyservers: chrony服务器的ip地址;
- disks: 配置每台服务器的hdd盘符名称
- shouldinstallpromethues: 是否要在服务器上安装监控组件
典型的配置示例如下：
```
{
    "monitors": [
        "192.168.0.154",
        "192.168.0.155",
        "192.168.0.156"
    ],
    "osdnodes": [
        "192.168.0.154",
        "192.168.0.155",
        "192.168.0.156"
    ],
    "user": "root",
    "password": "test",
    "chronyservers": "10.70.140.20",
    "disks": {
        "192.168.0.154": {
        "hdds": ["/dev/vde", "/dev/vdd", "/dev/vdg", "/dev/vdh", "/dev/vdf"]
    },
        "192.168.0.155": {
        "hdds": ["/dev/vde", "/dev/vdd", "/dev/vdg", "/dev/vdh", "/dev/vdf"]
    },
        "192.168.0.156": {
        "hdds": ["/dev/vde", "/dev/vdd", "/dev/vdg", "/dev/vdh", "/dev/vdf"]
    }
    },
    "shouldinstallpromethues": true
}
```

3、运行部署脚本完成ceph的一键部署:
```
python fabfile.py
```
如果在部署结束之后，打印出下面的绿色字样说明部署成功: 
```
cluster deployed SUCCESSFULLY
```
如果在部署结束之后，打印出下面的红色字样说明部署失败了，需要具体查看失败原因: 
```
some osds is FAILED, please double check your configuration
```

4、通过集群本脚本扩容一个磁盘:  
```
fab AddNewDisk:hostname=ceph168,hdd=/dev/vdd
```
在上面的命令行中，AddNewDisk是扩容时执行的函数，hostname是扩容磁盘所在的机器的hostname(或者是IP), hdd是存储osd数据的磁盘.
如果在结束之后，打印出下面的绿色字样说明部署成功: 
```
cluster deployed SUCCESSFULLY
```
如果在部署结束之后，打印出下面的红色字样说明部署失败了，需要具体查看失败原因: 
```
some osds is FAILED, please double check your configuration
```

5、批量扩容服务器:  
**注意在运行中的集群中批量扩容服务器是一个非常危险的操作，可能会造成集群状态抖动和大量数据迁移，批量扩容服务器功能通常仅适合在一个负载很轻的集群或者在一个刚刚创建不久的集群中添加另外一批机器。扩容一个有一定负载的集群，请使用第4点中提到的方式一个一个扩容osd。**  
编辑expand.json,重点配置项如下:
- monitors: 一个数组，被扩容集群的monitor列表;
- newosdnodes: 一个数组，需要扩容的服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- chronyservers: chrony服务器的ip地址;
- disks: 配置每台服务器的hdd盘符名称 
典型配置如下:  
```
{
    "monitors": [
        "172.20.13.171",
        "172.20.13.172",
        "172.20.13.173"
    ],
    "newosdnodes": [
        "172.20.13.168",
        "172.20.13.169",
        "172.20.13.170"
    ],
    "user": "root",
    "password": "1qaz@WSX",
    "chronyservers": ["51.75.17.219", "202.108.6.95"],
    "disks": {
        "172.20.13.168": {
		"hdds": ["/dev/vdb", "/dev/vdd"]
	    },
        "172.20.13.169": {
		"hdds": ["/dev/vdb"]
	    },
        "172.20.13.170": {
		"hdds": ["/dev/vdb"]
	    }
    }
}
```
扩容方式为运行一下命令:
```
fab AddNewHostsToCluster
```
如果在扩容结束之后，打印出下面的绿色字样说明部署成功: 
```
cluster expanded SUCCESSFULLY
```
如果在部署结束之后，打印出下面的红色字样说明部署失败了，需要具体查看失败原因: 
```
some osds is FAILED, please double check your configuration
```

6、磁盘替换的方法
当系统中的一块磁盘坏掉之后，我们要执行磁盘磁盘替换流程, 当坏掉一个hdd之后，受其影响，对应的osd将不能启动.
零、关闭数据迁移：  
```
ceph osd set norecover
ceph osd set nobackfill
```
一、在进行磁盘替换之前，应该首先确保ceph集群中所有的pg都是active状态。  
二、首先进入这个磁盘所在的服务器，得到这个磁盘对应的osd所匹配的hdd的盘符:  
比如如下的典型场景中:
```
[root@ceph171 ceph-9]# ls -al
total 48
drwxrwxrwt  2 ceph ceph 300 Mar 28 21:51 .
drwxr-x---. 6 ceph ceph  58 Mar 28 21:51 ..
-rw-r--r--  1 ceph ceph 411 Mar 28 21:51 activate.monmap
lrwxrwxrwx  1 ceph ceph  93 Mar 28 21:51 block -> /dev/ceph-86fdc0a8-2152-4e47-8c92-4ae442a33c10/osd-block-ab2e0b89-3209-462b-8b80-46383f7113c4
-rw-r--r--  1 ceph ceph   2 Mar 28 21:51 bluefs
-rw-r--r--  1 ceph ceph  37 Mar 28 21:51 ceph_fsid
-rw-r--r--  1 ceph ceph  37 Mar 28 21:51 fsid
-rw-------  1 ceph ceph  55 Mar 28 21:51 keyring
-rw-r--r--  1 ceph ceph   8 Mar 28 21:51 kv_backend
-rw-r--r--  1 ceph ceph  21 Mar 28 21:51 magic
-rw-r--r--  1 ceph ceph   4 Mar 28 21:51 mkfs_done
-rw-r--r--  1 ceph ceph  41 Mar 28 21:51 osd_key
-rw-r--r--  1 ceph ceph   6 Mar 28 21:51 ready
-rw-r--r--  1 ceph ceph  10 Mar 28 21:51 type
-rw-r--r--  1 ceph ceph   2 Mar 28 21:51 whoami
```
再看lsblk的输出:  
```
[root@ceph171 ceph-9]# lsblk
NAME                                                                                                  MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
sda                                                                                                     8:0    0  100G  0 disk
├─sda1                                                                                                  8:1    0  500M  0 part /boot
└─sda2                                                                                                  8:2    0 99.5G  0 part
  ├─centos-root                                                                                       253:0    0   50G  0 lvm  /
  ├─centos-swap                                                                                       253:1    0  3.9G  0 lvm  [SWAP]
  └─centos-home                                                                                       253:2    0 45.6G  0 lvm  /home
vda                                                                                                   252:0    0  100G  0 disk
└─ceph--c2762328--df0a--4c0a--8259--df1060257c1f-osd--block--2df0cce0--573c--469d--bf4d--65dfa6de2adb 253:5    0  100G  0 lvm
vdb                                                                                                   252:16   0  100G  0 disk
└─ceph--6f11a723--fc6e--4ce0--90df--7263f571573c-osd--block--c878c72c--167a--4ccb--9451--eea101b268dd 253:4    0  100G  0 lvm
vdc                                                                                                   252:32   0  100G  0 disk
└─ceph--86fdc0a8--2152--4e47--8c92--4ae442a33c10-osd--block--ab2e0b89--3209--462b--8b80--46383f7113c4 253:6    0  100G  0 lvm
vdd                                                                                                   252:48   0  100G  0 disk
└─ceph--532714d2--ade7--4519--a74a--26c46abb9d50-osd--block--34743ed1--0ec7--464e--b352--856f279134dd 253:3    0  100G  0 lvm
```
而对应的hdd则可以通过lsblk看出这个osd对应的磁盘是/dev/vdc, 方法是ceph-9的block指向的设备有osd-block-ab2e0b89-3209-462b-8b80-46383f7113c4, 而vdc也有.  

三、进入这个磁盘所在的服务器，并对这个osd的目录进行umount操作:
```
umount /var/lib/ceph/osd/ceph-9
```
然后将此osd进行purge操作:
```
ceph osd purge 9 --yes-i-really-mean-it
```

四、插入新盘，得到其盘符假设为vde;  
五、清除掉vde上可能存在的数据(这些数据一般位于128M以内):  
```
dd if=/dev/zero of=/dev/vde bs=128M count=1
```
六、在这个磁盘上添加一个新的osd:
```
#得到monitor的ip地址, 即$moips
ceph-deploy gatherkeys $monips
#data是数据盘，存储在新插入的/dev/vde上，ceph171则是此次坏盘的服务器。
ceph-deploy osd create --data /dev/vde ceph171
```

七、通过ceph -s查看是否新增了一个osd，如果成功则需要等待所有pg都是active状态  
八、所以pg都是active之后，且osd都添加完成之后，重启数据迁移:
```
ceph osd unset norecover
ceph osd unset nobackfill
```

7、在创建pool之后，适时关闭ceph balancer
ceph在luminous版本中引入了mgr的balancer plugin，可以对集群中的pg进行均衡，从而让集群中的每个osd数据量均等，提高
集群的性能和数据均匀性. 在最新版本的ceph部署脚本中，添加了对ceph balancer的支持，并且在脚本中开启了ceph balancer.   
在创建完一个pool之后，balancer开始工作，通过调整pool的位置来均衡每个osd上的pg，我们可以通过一下命令查看调整的过程：
```
root@ceph103:~# ceph balancer eval
current cluster score 0.004180 (lower is better)
```
当```ceph balancer eval的输出```基本不变时，我们可以通过```ceph osd df```查看每个osd上的pg个数(最后一列):
```
root@ceph103:~# ceph osd df
ID CLASS WEIGHT  REWEIGHT SIZE    USE     AVAIL   %USE VAR  PGS
 1   ssd 7.27640  1.00000 7.28TiB 1.00GiB 7.28TiB 0.01 0.05  43
 3   ssd 7.27640  1.00000 7.28TiB 1.00GiB 7.28TiB 0.01 0.05  43
 0   ssd 7.27640  1.00000 7.28TiB 28.6GiB 7.25TiB 0.38 1.35  43
 5   ssd 7.27640  1.00000 7.28TiB 28.5GiB 7.25TiB 0.38 1.35  43
 7   ssd 7.27640  1.00000 7.28TiB 27.9GiB 7.25TiB 0.37 1.32  42
 2   ssd 7.27640  1.00000 7.28TiB 27.6GiB 7.25TiB 0.37 1.30  43
 4   ssd 7.27640  1.00000 7.28TiB 27.6GiB 7.25TiB 0.37 1.31  43
 6   ssd 7.27640  1.00000 7.28TiB 27.0GiB 7.25TiB 0.36 1.28  42
                    TOTAL 58.2TiB  169GiB 58.0TiB 0.28
MIN/MAX VAR: 0.05/1.35  STDDEV: 0.16
```
这说明每个osd上的pg个数已经基本均匀了，根据经验，一般这个自动的数据均衡过程需要五分钟左右。
在pg均匀了之后，最重要的一步是，我们需要手工关闭balancer，这一步必须要做。
```
ceph balancer off
```
