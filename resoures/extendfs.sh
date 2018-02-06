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
	#size is good enough,
	VG_SIZE_KB=$(vgdisplay --colon systemVG| awk -F: {'print $12'})
	if [[ ${VG_SIZE_KB} -gt 100000000 ]] ; then
		echo "systemVG is ${VG_SIZE_KB}KB, big enough"
		exit 0
	fi

	pvcreate -ff ${DEVNAME}

	if [[ $? = 0 ]] ;then
		vgextend systemVG ${DEVNAME}

		lvextend -l+50%FREE /dev/systemVG/LVRoot
		xfs_growfs /

		lvextend -l+100%FREE /dev/systemVG/var
		xfs_growfs /var
	else
		echo "${DEVNAME} is already a PV"
	fi
else
	echo "NO SUCH DEVICE: ${DEVNAME}"
fi
