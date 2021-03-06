0、注意本版本之后的重大变更:  
从此版本开始，在部署时，无需显示填写每个osd的databasesize，这个值由系统根据ssd和hdd的配比情况自动计算而来, 另外，  
0.1 一个ssd最多匹配三个hdd，超过的hdd不会被部署，因为database不足的情况下，会影响osd的性能；  
0.2 为考虑后续扩容，引入ssd预留机制：在部署osd时，会按照ssd:hdd=1:3的比例进行ssd的预留，比如一次只上线1个ssd和1个hdd，系统并不会将全部的ssd分配给这个hdd做database，而是只分配一个约1/3的ssd空间, 后续还可以继续扩容两个hdd；  
0.3 处于成本考虑, 稍微放宽了database必须占到hdd大小的4%这个要求，在本版本中，只要ssd与hdd的容量比大于3.84%即可。  
0.4 后续硬件上线时，需要满足hdd总容量小于ssd总容量的25倍。  

1、安装ceph-common ceph-osd ceph-mon fabric ceph-deploy等包, 并给各台服务器配置各不相同的hostname;   
2、配置config.json，包含的字段包括:
- monitors: 一个数组，集群需要安装的monitor列表;
- osdnodes: 一个数组，集群需要安装的osd服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- chronyservers: chrony服务器的ip地址;
- disks: 配置服务器的ip, ssd和hdd盘符名称, 如果多台服务器的磁盘列表一致，则可以统一填在ips数组里。  
- shouldinstallpromethues: 是否要在服务器上安装监控组件
典型的配置示例如下：  
```
{
    "monitors": [
        "172.20.13.242",
        "172.20.13.245"
    ],
    "osdnodes": [
        "172.20.13.242",
        "172.20.13.245"
    ],
    "user": "root",
    "password": "123456",
    "chronyservers": ["51.75.17.219", "202.108.6.95"],
    "disks": [{
            "ips": ["172.20.13.242"],
             "ssds": ["/dev/vdm"],
             "hdds": ["/dev/vdj", "/dev/vdk", "/dev/vdl"]
        },{
            "ips": ["172.20.13.245"],
             "ssds": ["/dev/vda"],
             "hdds": ["/dev/vdb"]
        }
    ],
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
fab AddNewDisk:hostname=ceph174,ssd=/dev/vdb,hdd=/dev/vda,databasesize=50,isfirstrun=True,user=root,password=test
```
在上面的命令行中，AddNewDisk是扩容时执行的函数，hostname是扩容磁盘所在的机器的hostname(或者是IP),   
ssd是存储rocksdb的wal和db的位置，hdd是存储osd数据的磁盘  
databasesize是rocksdb的db的大小, **注意**，扩容单个磁盘时，请参考集群中中其它节点上的databasesize, 也可以通过5中的计算准则自行计算。
isfirstrun代表是否是本服务器的第一次扩容，因为第一次扩容时会对该服务器进行初始化,  
user是服务器的用户名, password是服务器的密码

如果在结束之后，打印出下面的绿色字样说明部署成功: 
```
cluster deployed SUCCESSFULLY
```
如果在部署结束之后，打印出下面的红色字样说明部署失败了，需要具体查看失败原因: 
```
some osds is FAILED, please double check your configuration
```

5、关于databasesize的计算准则
为了提升ceph的性能，我们使用ssd来存储bluestore的rocksdb的db和wal，用hdd来存储osd的数据。因为ssd空间有限，所以我们会将ssd划分为多个分区来使用。根据ceph官网的推荐，存储rocksdb的db的分区大小应至少达到hdd容量的4%(本系统对这个要求适当放宽到3.84%)，即一个6TB的hdd大概需要对应240G的ssd空间来存储rocksdb的db, 另外还需要1GB来存储rocksdb的wal。  
在进行常规初始化部署和osd扩容时，都需要根据这个准则来计算databasesize, 计算公式如下:   
```
walsize = 1073741824
reserved_size = 536870912
databasesize = int(float((ssdsize - reserved_size - 3 * walsize) / 3)
```
其中，walsize是每个osd的wal的大小，为1GiB, 考虑到磁盘初始部分空间存分区表等元数据，系统额外预留了一部分空间(512MiB)用于防止后面的分区因空间不足创建失败的情况.  databasesize为每个ssd总容量减去预留空间，再减去三个wal的空间之后，再除以3，得到每个database的大小, 转化为int，相当于对下取整数，目的也是为了稍微预留一点空间以备不时之需。  
例如，假设有一块ssd的空间为960GB(换算后大概就是894.1GiB, GiB中的1k是1024，而GB中的1k是1000), 而对应的三块hdd的大小是8TB(即约7450.58GiB).  
那么套公式：  
```
databasesize = int(float(894.1 - 1 - 3* 1) /3) = 296
```
接下来计算一下296/7450.58=0.0397，满足我们稍加放宽之后的大于0.38的条件,因此此值合法。  
部署之后，磁盘状况形如：  
```
[root@oceanstore-wuxingyi-node-246 ~]# lsblk
NAME                                                                                                  MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sda                                                                                                     8:0    0   100G  0 disk
├─sda1                                                                                                  8:1    0   500M  0 part /boot
└─sda2                                                                                                  8:2    0  99.5G  0 part
  ├─centos-root                                                                                       253:0    0    50G  0 lvm  /
  ├─centos-swap                                                                                       253:1    0   7.9G  0 lvm  [SWAP]
  └─centos-home                                                                                       253:2    0  41.6G  0 lvm  /home
vda                                                                                                   252:0    0 894.1G  0 disk
├─vda1                                                                                                252:1    0   296G  0 part
├─vda2                                                                                                252:2    0     1G  0 part
├─vda3                                                                                                252:3    0   296G  0 part
└─vda4                                                                                                252:4    0     1G  0 part
vdb                                                                                                   252:16   0   7.3T  0 disk
└─ceph--e0bbb471--ee1f--41a8--b05a--c6fa7b65f491-osd--block--76c854b6--c2c6--4d6c--b4e4--a137b01f9417 253:3    0   7.3T  0 lvm
vdc                                                                                                   252:32   0   7.3T  0 disk
└─ceph--cdf7b1f9--93a2--448c--9038--6f416dc3f268-osd--block--a57a5281--aa6d--4bc9--99fc--e5598a348720 253:4    0   7.3T  0 lvm
vdd                                                                                                   252:48   0   7.3T  0 disk
```

6、批量扩容服务器:  
**注意在运行中的集群中批量扩容服务器是一个非常危险的操作，可能会造成集群状态抖动和大量数据迁移，批量扩容服务器功能通常仅适合在一个负载很轻的集群或者在一个刚刚创建不久的集群中添加另外一批机器。扩容一个有一定负载的集群，请使用第4点钟提到的一个一个扩容osd。**  
编辑expand.json,重点配置项如下:
- monitors: 一个数组，被扩容集群的monitor列表;
- newosdnodes: 一个数组，需要扩容的服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- chronyservers: chrony服务器的ip地址;
- disks: 配置服务器的ip, ssd和hdd盘符名称, 如果多台服务器的磁盘列表一致，则可以统一填在ips数组里。  
典型配置如下:  
```
{
    "monitors": [
        "172.20.13.245"
    ],
    "newosdnodes": [
        "172.20.13.242"
    ],
    "user": "root",
    "password": "123456",
    "chronyservers": ["51.75.17.219", "202.108.6.95"],
    "disks": [{
            "ips": ["172.20.13.242"],
             "ssds": ["/dev/vdm"],
             "hdds": ["/dev/vdj", "/dev/vdk"]
    }]
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

7、磁盘替换的方法
当系统中的一块磁盘坏掉之后，我们要执行磁盘磁盘替换流程, 当坏掉一个hdd之后，受其影响，对应的osd将不能启动，当坏掉一个ssd之后，将可能导致多个ssd不能启动。  
接下来，根据坏盘是hdd还是ssd，有不同的处理方法:  
7、1 如果坏的是hdd:  
零、关闭数据迁移：  
```
ceph osd set norecover
ceph osd set nobackfill
```
一、在进行磁盘替换之前，应该首先确保ceph集群中所有的pg都是active状态。  
二、首先进入这个磁盘所在的服务器，得到这个磁盘对应的osd所匹配的ssd和hdd的编号:  
比如如下的典型场景中:
```
[root@ceph171 ceph-5]# ls -al
total 48
drwxrwxrwt  2 ceph ceph 340 Mar 28 18:51 .
drwxr-x---. 4 ceph ceph  32 Mar 28 18:51 ..
-rw-r--r--  1 ceph ceph 411 Mar 28 18:51 activate.monmap
lrwxrwxrwx  1 ceph ceph  93 Mar 28 18:51 block -> /dev/ceph-b4a80454-d5ea-440e-80a2-489b375c10e5/osd-block-1b416e79-3ef6-437e-a5d8-c3d95cc301d1
lrwxrwxrwx  1 ceph ceph   9 Mar 28 18:51 block.db -> /dev/vdc3
lrwxrwxrwx  1 ceph ceph   9 Mar 28 18:51 block.wal -> /dev/vdc4
-rw-r--r--  1 ceph ceph   2 Mar 28 18:51 bluefs
-rw-r--r--  1 ceph ceph  37 Mar 28 18:51 ceph_fsid
-rw-r--r--  1 ceph ceph  37 Mar 28 18:51 fsid
-rw-------  1 ceph ceph  55 Mar 28 18:51 keyring
-rw-r--r--  1 ceph ceph   8 Mar 28 18:51 kv_backend
-rw-r--r--  1 ceph ceph  21 Mar 28 18:51 magic
-rw-r--r--  1 ceph ceph   4 Mar 28 18:51 mkfs_done
-rw-r--r--  1 ceph ceph  41 Mar 28 18:51 osd_key
-rw-r--r--  1 ceph ceph   6 Mar 28 18:51 ready
-rw-r--r--  1 ceph ceph  10 Mar 28 18:51 type
-rw-r--r--  1 ceph ceph   2 Mar 28 18:51 whoami
```
通过上面的ls -al命令可以看出/dev/vdc为这个osd对应的ssd(看block.db和block.wal这两个软链接指向的磁盘);  
再看lsblk的输出:  
```
[root@ceph171 ceph-5]# lsblk
NAME                                                                                                  MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
sda                                                                                                     8:0    0  100G  0 disk
├─sda1                                                                                                  8:1    0  500M  0 part /boot
└─sda2                                                                                                  8:2    0 99.5G  0 part
  ├─centos-root                                                                                       253:0    0   50G  0 lvm  /
  ├─centos-swap                                                                                       253:1    0  3.9G  0 lvm  [SWAP]
  └─centos-home                                                                                       253:2    0 45.6G  0 lvm  /home
vda                                                                                                   252:0    0  100G  0 disk
├─vda1                                                                                                252:1    0   40G  0 part
└─vda2                                                                                                252:2    0   1G  0 part
vdb                                                                                                   252:16   0  100G  0 disk
└─ceph--b4a80454--d5ea--440e--80a2--489b375c10e5-osd--block--1b416e79--3ef6--437e--a5d8--c3d95cc301d1 253:4    0  100G  0 lvm
vdc                                                                                                   252:32   0  100G  0 disk
├─vdc1                                                                                                252:33   0   20G  0 part
├─vdc2                                                                                                252:34   0   1G  0 part
├─vdc3                                                                                                252:35   0   20G  0 part
└─vdc4                                                                                                252:36   0   1G  0 part
vdd                                                                                                   252:48   0  100G  0 disk
└─ceph--584dd760--e50d--45b9--af29--47a145e06075-osd--block--30211c4b--7ee8--4dca--8ca1--06dc54fd5eef 253:3    0  100G  0 lvm
```
而对应的hdd则可以通过lsblk看出这个osd对应的磁盘是/dev/vdb, 方法是ceph-5的block指向的设备有osd-block-1b416e79-3ef6-437e-a5d8-c3d95cc301d1, 而vdb也有.  

三、进入这个磁盘所在的服务器，并对这个osd的目录进行umount操作:
```
umount /var/lib/ceph/osd/ceph-5
```
然后将此osd进行purge操作:
```
ceph osd purge 5 --yes-i-really-mean-it
```

四、插入新盘，得到其盘符假设为vde;  
五、清除掉ssd(此处为vdc)的block.db和block.wal上的元数据(这些元数据一般位于128M以内):  
```
dd if=/dev/zero of=/dev/vdc3 bs=128M count=1
dd if=/dev/zero of=/dev/vdc4 bs=128M count=1
```
六、在这个磁盘上添加一个新的osd:
```
#得到monitor的ip地址, 即$moips
ceph-deploy gatherkeys $monips
#在这里block-db使用的是vdc的第三个分区, block-wal使用的是vdc的第四个分区, 数据则存储在/dev/vde。
#data是数据盘，存储在新插入的/dev/vde上，ceph171则是此次坏盘的服务器。
ceph-deploy osd create --block-db /dev/vdc3 --block-wal /dev/vdc4 --data /dev/vde ceph171
```

七、通过ceph -s查看是否新增了一个osd，如果成功则需要等待所有pg都是active状态:  
八、所以pg都是active之后，且osd都添加完成之后，重启数据迁移:
```
ceph osd unset norecover
ceph osd unset nobackfill
```

7.2 如果坏的是sdd:  
坏一个ssd一般会造成多个osd损坏，因为ssd上存放了多个osd的元数据.    
```
[root@ceph171 ceph-5]# lsblk
NAME                                                                                                  MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
sda                                                                                                     8:0    0  100G  0 disk
├─sda1                                                                                                  8:1    0  500M  0 part /boot
└─sda2                                                                                                  8:2    0 99.5G  0 part
  ├─centos-root                                                                                       253:0    0   50G  0 lvm  /
  ├─centos-swap                                                                                       253:1    0  3.9G  0 lvm  [SWAP]
  └─centos-home                                                                                       253:2    0 45.6G  0 lvm  /home
vda                                                                                                   252:0    0  100G  0 disk
├─vda1                                                                                                252:1    0   40G  0 part
└─vda2                                                                                                252:2    0   1G  0 part
vdb                                                                                                   252:16   0  100G  0 disk
└─ceph--b4a80454--d5ea--440e--80a2--489b375c10e5-osd--block--1b416e79--3ef6--437e--a5d8--c3d95cc301d1 253:4    0  100G  0 lvm
vdc                                                                                                   252:32   0  100G  0 disk
├─vdc1                                                                                                252:33   0   20G  0 part
├─vdc2                                                                                                252:34   0   1G  0 part
├─vdc3                                                                                                252:35   0   20G  0 part
└─vdc4                                                                                                252:36   0   1G  0 part
vdd                                                                                                   252:48   0  100G  0 disk
└─ceph--584dd760--e50d--45b9--af29--47a145e06075-osd--block--30211c4b--7ee8--4dca--8ca1--06dc54fd5eef 253:3    0  100G  0 lvm
```
在上面这个环境里，vdc存储了两个osd的元数据，因此vdc损坏将造成vdb和vdd两个osd的数据全部丢失, 下面是处理方式:
零、关闭数据迁移：
```
ceph osd set norecover
ceph osd set nobackfill
```
一、在进行磁盘替换之前，应该首先确保ceph集群中所有的pg都是active状态。 
二、进入这个磁盘所在的服务器，并对这个osd的目录进行umount操作:
```
umount /var/lib/ceph/osd/ceph-2
umount /var/lib/ceph/osd/ceph-5
```
三、跟上面的方式类似，并全部purge掉两个osd。  
```
ceph osd purge 2 --yes-i-really-mean-it
ceph osd purge 5 --yes-i-really-mean-it
```
四、插入新盘，得到其盘符假设为vde;  
五、在vde上创建符合大小要求的分区供各个osd使用, 这里我们创建4个，大小分别是20G,1G,20G,1G，跟一开始的大小一致:  
```
sgdisk -n 0:0:+20G /dev/vde
sgdisk -n 0:0:+1G /dev/vde
sgdisk -n 0:0:+20G /dev/vde
sgdisk -n 0:0:+1G /dev/vde
```
六、在vdb上添加一个新的osd:  
```
#以下操作在tmp目录进行
cd /tmp
#得到monitor的ip地址, 即$moips
ceph-deploy gatherkeys $monips
#在这里block-db使用的是vde的第一个分区, block-wal使用的是vdc的第二个分区, 数据则存储在/dev/vde。
#data是数据盘，存储在新插入的/dev/vdb上，ceph171则是此次坏盘的服务器。
ceph-deploy osd create --block-db /dev/vde1 --block-wal /dev/vde2 --data /dev/vdb ceph171
```

七、通过ceph -s查看是否新增了一个osd，如果成功则需要等待所有pg都是active.  
八、在vdd上添加一个新的osd:  
```
#以下操作在tmp目录进行
cd /tmp
#在这里block-db使用的是vde的第三个分区, block-wal使用的是vdc的第四个分区, 数据则存储在/dev/vde。
#data是数据盘，存储在新插入的/dev/vdb上，ceph171则是此次坏盘的服务器。
ceph-deploy osd create --block-db /dev/vde3 --block-wal /dev/vde4 --data /dev/vdd ceph171
```
九、通过ceph -s查看是否新增了一个osd，如果成功则需要等待所有pg都是active.  
十、所以pg都是active之后，且osd都添加完成之后，重启数据迁移:   
```
ceph osd unset norecover
ceph osd unset nobackfill
```

8、在创建pool之后，适时关闭ceph balancer
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
在最新的版本中，会在脚本中创建一个名为volumes的pool，并根据osd的个数计算合适的pg个数，balancer会自动打开并在一个小时后自动关闭，因此无需用户手动关闭balancer了。
