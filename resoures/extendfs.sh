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

if [[ -b ${DEVNAME} ]]
then
	pvcreate ${DEVNAME}
	vgextend systemVG ${DEVNAME}

	lvextend -l+50%FREE /dev/systemVG/LVRoot
	xfs_growfs /

	lvextend -l+100%FREE /dev/systemVG/var
	xfs_growfs /var
else
	echo "NO SUCH DEVICE: ${DEVNAME}"
fi

