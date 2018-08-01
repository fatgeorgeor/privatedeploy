#!/usr/bin/env python
import os
import sys
import re
def get_id(dirname):
    with open('/etc/ganesha/ganesha.conf', 'r') as f:
        text=f.read()

    pattern = re.compile(r'%s \d+' % dirname)
    ids = pattern.findall(text)
    if len(ids) != 1:
        return
    print ids[0].split(" ")[1]


if __name__ == '__main__':
    if len(sys.argv) != 2:
        exit(-1)
    get_id(sys.argv[1])
