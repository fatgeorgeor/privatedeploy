#!/usr/bin/env python

import sys
import re
import subprocess
import time


def get_osd(name):
    prefix = r'/dev/{name} /var/lib/ceph/osd/ceph-'.format(name=name)
    pattern = prefix+"[0-9]+"
    with open('/proc/mounts','r') as fn:
        content = fn.read()
	match = re.search(pattern,content)
	return match.group()[len(prefix):]

def stop_osd(name):
    osd = get_osd(name) 
    cmd = "systemctl stop ceph-osd@{osd}.service".format(osd=osd)
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
    print(process.communicate(),process.returncode)

def umount_disk(name):
    cmd = "umount -l /dev/{name}".format(name=name)  
    print(cmd)
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
    print(process.communicate(),process.returncode)

if __name__ == '__main__':
    print(len(sys.argv),sys.argv[0])
    if len(sys.argv) != 2:
        print("Usage:\t\tpython disk.py devname\nFor examaple:\tpython disk.py vdb1")
	sys.exit(1)
    stop_osd(sys.argv[1])
