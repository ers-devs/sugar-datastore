# Copyright (C) 2008, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Transform one DataStore directory in a newer format.
""" 

import os
import logging
import shutil
import time
import traceback

import cjson

from carquinyol import layoutmanager

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'

def migrate_from_0():
    logging.info('Migrating datastore from version 0 to version 1')

    root_path = layoutmanager.get_instance().get_root_path()
    old_root_path = os.path.join(root_path, 'store')
    if not os.path.exists(old_root_path):
        return

    for f in os.listdir(old_root_path):
        uid, ext = os.path.splitext(f)
        if ext != '.metadata':
            continue

        logging.debug('Migrating entry %r' % uid)
        try:
            _migrate_metadata(root_path, old_root_path, uid)
            _migrate_file(root_path, old_root_path, uid)
            _migrate_preview(root_path, old_root_path, uid)
        except Exception:
            logging.error('Error while migrating entry %r: %s\n' % \
                          (uid, traceback.format_exc()))

    # Just be paranoid, it's cheap.
    if old_root_path.endswith('datastore/store'):
        shutil.rmtree(old_root_path)

    logging.info('Migration finished')

def _migrate_metadata(root_path, old_root_path, uid):
    dir_path = layoutmanager.get_instance().get_entry_path(uid)
    metadata_path = os.path.join(dir_path, 'metadata')
    os.makedirs(metadata_path)

    old_metadata_path = os.path.join(old_root_path, uid + '.metadata')
    metadata = cjson.decode(open(old_metadata_path, 'r').read())

    if 'uid' not in metadata:
        metadata['uid'] = uid

    if 'timestamp' not in metadata and 'mtime' in metadata:
        metadata['timestamp'] = \
                time.mktime(time.strptime(metadata['mtime'], DATE_FORMAT))

    for key, value in metadata.items():
        try:
            f = open(os.path.join(metadata_path, key), 'w')
            try:
                if isinstance(value, unicode):
                    value = value.encode('utf-8')
                if not isinstance(value, basestring):
                    value = str(value)
                f.write(value)
            finally:
                f.close()
        except Exception:
            logging.error(
                    'Error while migrating property %s of entry %s: %s\n' % \
                    (key, uid, traceback.format_exc()))

def _migrate_file(root_path, old_root_path, uid):
    if os.path.exists(os.path.join(old_root_path, uid)):
        dir_path = layoutmanager.get_instance().get_entry_path(uid)
        os.rename(os.path.join(old_root_path, uid),
                  os.path.join(dir_path, 'data'))

def _migrate_preview(root_path, old_root_path, uid):
    dir_path = layoutmanager.get_instance().get_entry_path(uid)
    metadata_path = os.path.join(dir_path, 'metadata')
    os.rename(os.path.join(old_root_path, 'preview', uid),
              os.path.join(metadata_path, 'preview'))
