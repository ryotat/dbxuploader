#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from datetime import datetime
import glob

import exifread
import parsequicktime
import dropbox

config={}
with open('config') as f:
    for line in f:
        if '=' not in line:
            continue
        k, v=line.split('=')
        config[k]=v.strip('\n')

def format_file_name(date, ext):
    return date_taken.strftime('%Y-%m-%d %H.%M.%S')+'.'+ext

def format_original_dest(date, ext):
    return config['camera_upload_folder']+'/'+format_file_name(date, ext)

def format_final_dest(date, ext):
    filename=format_file_name(date, ext)
    final_dest_format = '/Photos/%d/%02d/'+filename
    return final_dest_format % (date.year, date.month)

def check_path_exist(dbx, path):
    try:
        md=dbx.files_get_metadata(path)
        return md
    except dropbox.exceptions.ApiError:
        return None

def getext(fn):
    return fn.split('.')[-1].lower()

def getexifdatetime(fn):
    with open(fn,'rb') as f:
        tags=exifread.process_file(f, details=False)
    if 'Image DateTime' in tags:
        return datetime.strptime(tags['Image DateTime'].printable, '%Y:%m:%d %H:%M:%S')
    elif 'EXIF DateTimeOriginal' in tags:
        dtstring=tags['EXIF DateTimeOriginal'].printable
        return datetime.strptime(dtstring, '%Y:%m:%d %H:%M:%S')
    else:
        print 'Exif does not contain datetime.'
        return None

def getwpdatetime(fn):
    basename=os.path.basename(fn)
    dtstring='_'.join(basename.split('.')[0].split('_')[1:-1])
    return datetime.strptime(dtstring, '%Y%m%d_%H_%M_%S')

if __name__ == '__main__':
    dir = sys.argv[1]
    dbx=dropbox.Dropbox(config['token'])

    jpeg_file_exts=['jpg']
    mov_file_exts=['mov','mp4']
    if os.path.isdir(dir):
        files=[]
        for dirpath, dirs, fns in os.walk(dir):
            files += [dirpath+'/'+fn for fn in fns
                      if getext(fn) in jpeg_file_exts
                      or getext(fn) in mov_file_exts]
    else:
        files = [dir]
    print len(files)
    que = {}
    for file in files:
        print file
        basename=os.path.basename(file)
        ext=getext(file)
        if ext in jpeg_file_exts:
            date_taken=getexifdatetime(file)
            if date_taken is None:
                continue
        elif ext in mov_file_exts:
            if basename.startswith('WP_'):
                date_taken=getwpdatetime(file)
            else:
                date_taken=parsequicktime.get_local_modified_time(file)
        orig_path = format_original_dest(date_taken, ext)
        final_path = format_final_dest(date_taken, ext)
        # print 'orig_path=%s' % orig_path
        # print 'final_path=%s' % final_path
        if check_path_exist(dbx, orig_path) is not None:
            print 'Found %s' % orig_path
            continue
        if check_path_exist(dbx, final_path) is not None:
            print 'Found %s' % final_path
            continue
        if getext(file) in mov_file_exts:
            search_pattern = date_taken.strftime('%Y-%m-%d')+'*.'+ext
            out=dbx.files_search(config['camera_upload_folder'], search_pattern)
            local_file_size = os.path.getsize(file)
            matches = [m for m in out.matches if m.metadata.size==local_file_size]
            if len(matches)>0:
                m=matches[0]
                print 'Found %s with the same size' % m.metadata.name
                continue
        print '%s does not exist.' % os.path.basename(file)
        que[final_path]=file # there might be more than one file with the same content

    if len(que)==0:
        sys.exit(0)

    num_jpegs=len([k for k in que.keys() if getext(k) in jpeg_file_exts])
    num_movs=len([k for k in que.keys() if getext(k) in mov_file_exts])
    res=raw_input('%d files (%d images and %d movies) to be uploaded. Proceed (y/n)?' % (len(que), num_jpegs, num_movs))
    if res=='y':
        for path in que:
            file = que[path]
            file_size = os.path.getsize(file)
            print file_size
            if 'file_size_limit' in config:
                file_size_limit = int(config['file_size_limit'])
                if file_size>file_size_limit:
                    print 'Skipping %s because its size is above %d MB' % (file, file_size_limit/1024/1024)
                    continue
            folder_path = '/'.join(path.split('/')[:-1])
            if check_path_exist(dbx, folder_path) is None:
                dbx.files_create_folder(folder_path)
            print 'Uploading %s as %s' % (file, path)
            with open(file,'rb') as f:
                dbx.files_upload(f, path)
