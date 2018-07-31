#!/usr/bin/env python
import os
import re
def get_id():
    with open('/etc/ganesha/ganesha.conf', 'r') as f:
        text=f.read()

    pattern = re.compile(r'Export_ID = \d+')
    ids = pattern.findall(text)
    s = set()
    for i in ids:
        s.add(int(i.strip('Export_ID = ')))

    for i in range(1, 65535):
        if i not in s:
            print i
            break;

if __name__ == '__main__':
    get_id()
