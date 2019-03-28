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
