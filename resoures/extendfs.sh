#!/bin/bash

function usage() {
	echo "If root/var is too small, use this script to extend logic volume"
	echo "extendfs.sh <DEV NAME>"
}

if [[ $# != 1 ]]
then
	usage
	exit -1
fi

DEVNAME=$1

pvcreate ${DEVNAME}
vgextend centos ${DEVNAME}

lvextend -L+500G /dev/centos/root
xfs_growfs /

lvextend -L+500G /dev/centos/var
xfs_growfs /var
