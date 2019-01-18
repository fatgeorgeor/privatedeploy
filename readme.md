1、安装ceph-common ceph-osd ceph-mon fabric ceph-deploy等包;  
2、配置config.json，包含的字段包括:
- monitors: 一个数组，集群需要安装的monitor列表;
- osdnodes: 一个数组，集群需要安装的osd服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- chronyservers: chrony服务器的ip地址;
- disks: 配置每台服务器的ssd和hdd盘符名称, ceph-deploy会使用ssd来存储wal和rocksdb;  
- databasesize: 每个osd的rocksdb大小, 单位是GiB.  
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
    "databasesize": 10,
    "disks": {
        "192.168.0.154": {
        "ssds": ["/dev/vdb", "/dev/vdc"],
        "hdds": ["/dev/vde", "/dev/vdd", "/dev/vdg", "/dev/vdh", "/dev/vdf"]
    },
        "192.168.0.155": {
        "ssds": ["/dev/vdb", "/dev/vdc"],
        "hdds": ["/dev/vde", "/dev/vdd", "/dev/vdg", "/dev/vdh", "/dev/vdf"]
    },
        "192.168.0.156": {
        "ssds": ["/dev/vdb", "/dev/vdc"],
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
fab AddNewDisk:hostname=ceph168,ssd=/dev/vdb,hdd=/dev/vdd,databasesize=10
```
在上面的命令行中，AddNewDisk是扩容时执行的函数，hostname是扩容磁盘所在的机器的hostname(或者是IP),   
ssd是存储rocksdb的wal和db的位置，hdd是存储osd数据的磁盘，databasesize是rocksdb的db的大小。  

5、关于databasesize的计算准则
为了提升ceph的性能，我们使用ssd来存储bluestore的rocksdb的db和wal，用hdd来存储osd的数据。因为ssd有限，所以我们  
会将ssd划分为多个分区来使用。根据ceph官网的推荐，存储rocksdb的db的分区大小应至少达到hdd容量的4%，即一个6TB的hdd大概  
需要对应240G的ssd空间来存储rocksdb的db, 另外还需要10GB来存储rocksdb的wal。  
在进行常规初始化部署和osd扩容时，都需要根据这个准则来计算databasesize.  
比如在一个典型应用场景中，有两块896G的ssd和6块6T的HDD，那么每三个hdd需要共享一个ssd，首先，三个hdd需要占用3个10GB来存储  
wal，剩下的ssd空间就是866GB, 存在rocksdb的db的空间就是866/3=288，也就是说databasesize应配置为288.

6、批量扩容服务器:
编辑expand.json,重点配置项如下:
- monitors: 一个数组，被扩容集群的monitor列表;
- newosdnodes: 一个数组，需要扩容的服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- chronyservers: chrony服务器的ip地址;
- disks: 配置每台服务器的ssd和hdd盘符名称, ceph-deploy会使用ssd来存储wal和rocksdb;  
- databasesize: 每个osd的rocksdb大小, 单位是GiB, 计算方式跟新部署一致。 
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
    "databasesize": 40,
    "disks": {
        "172.20.13.168": {
		"ssds": ["/dev/vda", "/dev/vdc"],
		"hdds": ["/dev/vdb", "/dev/vdd"]
	    },
        "172.20.13.169": {
		"ssds": ["/dev/vda"],
		"hdds": ["/dev/vdb"]
	    },
        "172.20.13.170": {
		"ssds": ["/dev/vda"],
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
