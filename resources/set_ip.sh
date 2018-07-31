#!/bin/bash

usage(){
    echo "Usage:"
    echo "$0 IPADDR GATEWAT"
}

if [ $# -lt 2 ]; then
    usage
    exit
fi

CFG=ifcfg-ens802f0
cp -p $CFG /etc/sysconfig/network-scripts
#IPADDR=10.16.0.XXX
IPADDR=$1
#GATEWAY=10.16.0.YYY
GATEWAY=$2

augtool -s set /files/etc/sysconfig/network-scripts/$CFG/IPADDR $1
augtool -s set /files/etc/sysconfig/network-scripts/$CFG/GATEWAY $2
