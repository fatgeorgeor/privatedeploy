1、安装ceph-common ceph-osd ceph-mon fabric ceph-deploy等包;  
2、配置config.json，包含的字段包括:
- monitors: 一个数组，集群需要安装的monitor列表;
- osdnodes: 一个数组，集群需要安装的osd服务器列表;
- user: 进行部署的用户, 一般填root即可;
- password: user用户的密码;
- ntpserverip: ntp服务器的ip地址;
- disks: 配置每台服务器的ssd和hdd盘符名称, ceph-deploy会使用ssd来存储wal和rocksdb;  
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
    "ntpserverip": "10.70.140.20",
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
    }
}
```
3、运行部署脚本完成ceph的一键部署:
```
python fabfile.py
```


