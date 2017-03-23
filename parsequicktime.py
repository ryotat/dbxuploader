#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- mode: python -*-

# This program is free software. It comes without any warranty, to the extent
# permitted by applicable law. You can redistribute it and/or modify it under
# the terms of the Do What The Fuck You Want To Public License, Version 2, as
# published by Sam Hocevar. See http://sam.zoy.org/wtfpl/COPYING for more
# details.

# Some useful resources:
# - http://atomicparsley.sourceforge.net/mpeg-4files.html
# - http://developer.apple.com/library/mac/#documentation/QuickTime/QTFF/QTFFChap2/qtff2.html
# - http://www.sno.phy.queensu.ca/~phil/exiftool/TagNames/QuickTime.html

from __future__ import print_function
import datetime
import os.path
import struct
import iso8601
import pytz

EPOCH_ADJUSTER = 2082844800

def adjust_epoch_time(time):
    return datetime.datetime.utcfromtimestamp(time - EPOCH_ADJUSTER)

def parse_mvhd(f, length):
    fmt='>4xII'
    ctime, mtime = struct.unpack(fmt, f.read(12))
    # Ignore the rest
    f.read(length-12)
    created_time = adjust_epoch_time(ctime)
    modified_time = adjust_epoch_time(mtime)
    print('Created at %s: (%d)' %(created_time, ctime))
    print('Modified at %s: (%d)' %(modified_time, mtime))

    return modified_time.replace(tzinfo=pytz.utc)

def parse_meta_keys(f, length):
    fmt='>B3xI'
    version, entry_count = struct.unpack(fmt, f.read(8))
    # print 'version={}, entry_count={}'.format(version, entry_count)
    keys=[]
    for i in range(entry_count):
        size, keyns = struct.unpack('>II', f.read(8))
        size -=8
        key_value = struct.unpack('>'+'%ds'%size, f.read(size))
        keys.append(key_value[0])
        # print 'key=%s' % key_value
    return keys

def parse_meta_ilst(f, length, keys):
    n=0
    while n < length:
        item_atom_len, key=struct.unpack('>II', f.read(8))
        al, adata=struct.unpack('>I4s', f.read(8))
        type, locale, val=struct.unpack('>I4s%ds'%(al-16), f.read(al-8))
        print(key, type, locale, val)
        if keys[int(key)-1]=='com.apple.quicktime.creationdate':
            ctime=iso8601.parse_date(val)
        n += item_atom_len
    return ctime.tzinfo

def parse(f, length, atom, depth, verbose=False):
    modified_time=None
    tzinfo=None
    keys=[]
    n=0
    while n < length:
        al, an = struct.unpack(">I4s", f.read(8))
        an = an.decode()
        if verbose:
            print("{}Atom: {} ({} bytes)".format('-'*depth, an, al))
        if an=='moov':
            modified_time = parse(f, al-8, an, depth+1)
        elif an=='meta':
            tzinfo = parse(f, al-8, an, depth+1)
        elif an=='mvhd':
            modified_time = parse_mvhd(f, al-8)
        elif an=='keys':
            keys=parse_meta_keys(f, al-8)
        elif an=='ilst' and 'com.apple.quicktime.creationdate' in keys:
            tzinfo = parse_meta_ilst(f, al-8, keys)
        else:
            f.read(al-8)
        n += al
    if atom=='meta':
        # Inside 'meta'
        return tzinfo
    elif atom=='moov':
        # Inside 'moov'
        if tzinfo is not None:
            return modified_time.astimezone(tzinfo)
        else:
            return modified_time
    elif depth==0:
        # Root
        return modified_time
    else:
        return None

def get_local_modified_time(fn):
    fsize = os.path.getsize(fn)
    with open(fn, "rb") as f:
        mtime_local=parse(f, fsize, 'root', 0, True)
    return mtime_local
