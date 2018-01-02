# samba and nfs on cephfs
## 零、环境准备
1.使用标准版centos 7内核(3.10), 如果是较低版本的centos 7.2，会出现feature mismatch，(7.4的内核则不会），解决办法：
```
ceph osd crush tunables hammer
ceph osd crush reweight-all
```
2.关闭selinux: 将```/etc/selinux/config```修改为：
```
SELINUX=disabled
```
3.systemctl disable firewalld
4.reboot服务器
5.在三台服务器上(此处以ceph136,ceph137,ceph140为例)先部署好ceph, ceph-mgr, client.admin必须有访问mds的权限
6.创建ecpool的方法：
```
#1. 创建一个ec的profile:
ceph osd erasure-code-profile set isaprofile k=3 m=2 crush-failure-domain=host

#2. 创建一个ec的crush rule:
ceph osd crush rule create-erasure isarule isaprofile

#3. 根据profile和rule创建一个pool：
ceph osd pool create ecpool 128 128 erasure isaprofile isarule

#4.设置pool允许ec overwrite：
ceph osd pool set data allow_ec_overwrites true
```

## 一、部署cephfs
```
# 1.依次创建三个mds:
ceph-deploy mds create ceph140
# 2.在各服务器上并启动服务:
systemctl enable ceph-mds@ceph140
systemctl start ceph-mds@ceph140
# 3.验证mds集群是否成功工作:
ceph node ls mds
# 4.创建一个fs:
ceph fs new newfs metadata ceph136
# 5.修改cephfs的单个文件的最大size:
ceph fs set newfs  max_file_size 17592186044416
# 6.使用kernel cephfs module来mount到本地(三台机器上都需要mount，后面ctdb会用到):
mkdir /mnt/mycephfs
mkdir /nfstoexport
mount -t ceph ceph136:6789:/ /mnt/mycephfs -o name=admin,secret=AQAH4sBZeZkjDRAA/LKX2NfV/jR2LUMFa5fLXQ==
```

## 二、编译支持cephfs的samba,安装ctdb,nfs-utils等工具
因为cluster的samba需要用到cephfs这个vfs，而centos 7打包的samba编译时并没有把cephfs编译选项打开，所以需要重新打包。
已经编译的源如下：
```
http://sambarepo.los-cn-north-1.lecloudapis.com/
```
在三台服务器上安装:
```
yum install samba samba-vfs-cephfs ctdb samba-client nfs-utils -y
```

## 三、创建samba和nfs导出的用户：
samba和nfs要使用相同的用户体系，所以下面的命令行需要在三个机器上运行，密码要设为一致：
```
groupadd shareduser -g 8888
useradd -u 8888 shareduser  -g shareduser  -s /sbin/nologin
smbpasswd -a shareduser
```

## 四、配置ctdb
1.首先在cephfs上建立一个共享目录和一个锁文件:
```
mkdir /mnt/mycephfs/srv/
touch /mnt/mycephfs/srv/.lockfile
```

2.然后配置```/etc/ctdb/ctdbd.conf```:

```
CTDB_RECOVERY_LOCK=/mnt/mycephfs/srv/.lockfile
CTDB_PUBLIC_ADDRESSES=/etc/ctdb/public_addresses
CTDB_MANAGES_SAMBA=yes
CTDB_MANAGES_NFS=yes
CTDB_NODES=/etc/ctdb/nodes
```

3.在```/etc/ctdb/public_addresses```配置vip，10.72.84.110即用于对外提供服务的浮动ip:

```
10.72.84.110/24 bond0
```

4.在```/etc/ctdb/nodes```中配置需要运行nfs和samba的节点ip:
```
10.72.84.136
10.72.84.137
10.72.84.140
```

5.配置在ctdb启动时，判断是否需要mount cephfs, 修改```/usr/lib/systemd/system/ctdb.service```，添加一行:
```
ExecStartPre=/etc/ctdb/mountcephfs.sh
```
添加```etc/ctdb/mountcephfs.sh```文件如下：
```
#!/bin/sh
mkdir -p /toexport
FOLDER=/mnt/mycephfs
NFSEXPORTFOLDER=/nfstoexport
if [[ $(findmnt "$FOLDER") ]]; then
    exit 0
else
    mount -t ceph ceph135:6789:/ $FOLDER -o name=admin,secret=AQAH4sBZeZkjDRAA/LKX2NfV/jR2LUMFa5fLXQ==
    if [[ $(findmnt "$NFSEXPORTFOLDER") ]]; then
        mount --bind $FOLDER/toexport $NFSEXPORTFOLDER
    fi
    exit 0
fi

```
重新load一下配置文件：
```
systemctl daemon-reload
```

## 五、配置samba server

1.默认情况下client.admin没有管理mds的权限，需要先加一下权限, 改成下面：
```
[client.admin]
    key = AQAH4sBZeZkjDRAA/LKX2NfV/jR2LUMFa5fLXQ==
    caps mds = "allow *"
    caps mon = "allow *"
    caps osd = "allow *"
    caps mgr = "allow *"
```
在import进去即可。

2.在```/etc/samba/smb.conf```中添加：
```
[toexport]
        path = /toexport
        vfs objects = ceph
        ceph:config_file = /etc/ceph/ceph.conf
        ceph:user_id = client.admin
        writable = yes
        browseable = yes
        available = yes
        create mask = 0755
        directory mask = 0755
        valid users = shareduser
        write list = shareduser
```
3.因为samba要由ctdb管理，所以需要disable掉自动启动：
```
systemctl disable smbd
```

4.因为ctdb的一个bug，会去查找是否存在，此处创建一下这个目录， 当然最好是放到```etc/ctdb/mountcephfs.sh```中：
```
mkdir /toexport -p
```

## 六、配置nfs server
1. 需修改```/etc/sysconfig/nfs```:

```
RPCNFSDARGS="-N 4"
BLKMAPDARGS=""
NFS_HOSTNAME="ctdb" #这里的ctdb即vip所对应的hostname，应该写到/etc/hosts文件中。
RPCNFSDCOUNT=32
STATD_PORT=595
STATD_OUTGOING_PORT=596
MOUNTD_PORT=597
RQUOTAD_PORT=598
LOCKD_UDPPORT=599
LOCKD_TCPPORT=599
STATD_HOSTNAME="ctdb"
STATD_HA_CALLOUT="/etc/ctdb/statd-callout"
```

2. 配置```/etc/exports```文件:
```
/nfstoexport 10.72.84.110/255.255.255.0(rw,sync,no_subtree_check,all_squash,anonuid=8888,anongid=8888)
```
3. 因为nfs要由ctdb管理，所以需要disable掉自动启动：
```
systemctl disable nfs
```

## 七、启动ctdb服务：
```
systemctl enable ctdb
systemctl start ctdb
```

查看ctdb服务是否正常：
```
ctdb status
```

## 八、功能验证

1. 挂载cifs和nfs，测试是否能正常mount上:
```
mkdir /cifsexport /nfsexport -p
mount -t cifs -o username=shareduser,password=password //10.72.84.110/toexport /cifsexport
mount.nfs 10.72.84.110:/nfstoexport /nfsexport
```

2. 读写操作是否正常：
```
dd if=/dev/zero of=/nfsexport/asdf bs=4M count=100
```

3. vip切换测试：
3.1. 找到当前vip所在的服务器，关闭其ctdb服务，查看vip是否正常漂移，/nfsexport和/cifsexport这两个挂载是否正常工作。
3.2. 重启服务器，查看ctdb是否能正常挂载cephfs，ctdb状态是否正常。
