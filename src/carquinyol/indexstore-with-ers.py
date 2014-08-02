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

import logging
import os
import sys

from ers import ERS

from gi.repository import GObject

import xapian
from xapian import WritableDatabase, Document, Enquire, Query

from carquinyol import layoutmanager
from carquinyol.layoutmanager import MAX_QUERY_LIMIT

_VALUE_UID = 0
_VALUE_TIMESTAMP = 1
_VALUE_TITLE = 2
# 3 reserved for version support
_VALUE_FILESIZE = 4
_VALUE_CREATION_TIME = 5

_PREFIX_NONE = 'N'
_PREFIX_FULL_VALUE = 'F'
_PREFIX_UID = 'Q'
_PREFIX_ACTIVITY = 'A'
_PREFIX_ACTIVITY_ID = 'I'
_PREFIX_MIME_TYPE = 'M'
_PREFIX_KEEP = 'K'

# Force a flush every _n_ changes to the db
_FLUSH_THRESHOLD = 20

# Force a flush after _n_ seconds since the last change to the db
_FLUSH_TIMEOUT = 5

_PROPERTIES_NOT_TO_INDEX = ['timestamp', 'preview', 'launch-times']

_MAX_RESULTS = int(2 ** 31 - 1)

_QUERY_TERM_MAP = {
    'uid': _PREFIX_UID,
    'activity': _PREFIX_ACTIVITY,
    'activity_id': _PREFIX_ACTIVITY_ID,
    'mime_type': _PREFIX_MIME_TYPE,
    'keep': _PREFIX_KEEP,
}

_QUERY_VALUE_MAP = {
    'timestamp': {'number': _VALUE_TIMESTAMP, 'type': float},
    'filesize': {'number': _VALUE_FILESIZE, 'type': int},
    'creation_time': {'number': _VALUE_CREATION_TIME, 'type': float},
}


class TermGenerator (xapian.TermGenerator):

    def index_document(self, document, properties):
        document.add_value(_VALUE_TIMESTAMP,
            xapian.sortable_serialise(float(properties['timestamp'])))
        document.add_value(_VALUE_TITLE, properties.get('title', '').strip())
        if 'filesize' in properties:
            try:
                document.add_value(_VALUE_FILESIZE,
                    xapian.sortable_serialise(int(properties['filesize'])))
            except (ValueError, TypeError):
                logging.debug('Invalid value for filesize property: %s',
                              properties['filesize'])
        if 'creation_time' in properties:
            try:
                document.add_value(
                    _VALUE_CREATION_TIME, xapian.sortable_serialise(
                        float(properties['creation_time'])))
            except (ValueError, TypeError):
                logging.debug('Invalid value for creation_time property: %s',
                              properties['creation_time'])

        self.set_document(document)

        properties = dict(properties)
        self._index_known(document, properties)
        self._index_unknown(document, properties)

    def _index_known(self, document, properties):
        for name, prefix in _QUERY_TERM_MAP.items():
            if (name not in properties):
                continue

            self._index_property(document, name, properties.pop(name), prefix)

    def _index_unknown(self, document, properties):
        for name, value in properties.items():
            self._index_property(document, name, value)

    def _index_property(self, doc, name, value, prefix=''):
        if name in _PROPERTIES_NOT_TO_INDEX or not value:
            return

        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif not isinstance(value, basestring):
            value = str(value)

        # We need to add the full value (i.e. not split into words) so
        # we can enumerate unique values. It also simplifies setting up
        # dictionary-based queries.
        if prefix:
            doc.add_term(_PREFIX_FULL_VALUE + prefix + value)

        self.index_text(value, 1, prefix or _PREFIX_NONE)
        self.increase_termpos()


class QueryParser (xapian.QueryParser):
    """QueryParser that understands dictionaries and Xapian query strings.

    The dictionary contains metadata names as keys and either basic types
    (exact match), 2-tuples (range, only valid for value-stored metadata)
    or a list (multiple exact matches joined with OR) as values.
    An empty dictionary matches everything. Queries from different keys
    (i.e. different metadata names) are joined with AND.
    """

    def __init__(self):
        xapian.QueryParser.__init__(self)

        for name, prefix in _QUERY_TERM_MAP.items():
            self.add_prefix(name, prefix)
            self.add_prefix('', prefix)

        self.add_prefix('', _PREFIX_NONE)

    def _parse_query_term(self, name, prefix, value):
        if isinstance(value, list):
            subqueries = [self._parse_query_term(name, prefix, word)
                for word in value]
            return Query(Query.OP_OR, subqueries)

        elif prefix:
            return Query(_PREFIX_FULL_VALUE + prefix + str(value))
        else:
            return Query(_PREFIX_NONE + str(value))

    def _parse_query_value_range(self, name, info, value):
        if len(value) != 2:
            raise TypeError(
                'Only tuples of size 2 have a defined meaning. '
                'Did you mean to pass a list instead?')

        start, end = value
        return Query(Query.OP_VALUE_RANGE, info['number'],
            self._convert_value(info, start), self._convert_value(info, end))

    def _convert_value(self, info, value):
        if info['type'] in (float, int, long):
            return xapian.sortable_serialise(info['type'](value))

        return str(info['type'](value))

    def _parse_query_value(self, name, info, value):
        if isinstance(value, list):
            subqueries = [self._parse_query_value(name, info, word)
                for word in value]
            return Query(Query.OP_OR, subqueries)

        elif isinstance(value, tuple):
            return self._parse_query_value_range(name, info, value)

        elif isinstance(value, dict):
            # compatibility option for timestamp: {'start': 0, 'end': 1}
            start = value.get('start', 0)
            end = value.get('end', sys.maxint)
            return self._parse_query_value_range(name, info, (start, end))

        else:
            return self._parse_query_value_range(name, info, (value, value))

    def _parse_query_xapian(self, query_str):
        try:
            return xapian.QueryParser.parse_query(
                self, query_str,
                QueryParser.FLAG_PHRASE |
                        QueryParser.FLAG_BOOLEAN |
                        QueryParser.FLAG_LOVEHATE |
                        QueryParser.FLAG_WILDCARD,
                '')

        except xapian.QueryParserError, exception:
            logging.warning('Invalid query string: ' + exception.get_msg())
            return Query()

    # pylint: disable=W0221
    def parse_query(self, query_dict, query_string):
        logging.debug('parse_query %r %r', query_dict, query_string)
        queries = []
        query_dict = dict(query_dict)

        if query_string is not None:
            queries.append(self._parse_query_xapian(str(query_string)))

        for name, value in query_dict.items():
            if name in _QUERY_TERM_MAP:
                queries.append(self._parse_query_term(name,
                    _QUERY_TERM_MAP[name], value))
            elif name in _QUERY_VALUE_MAP:
                queries.append(self._parse_query_value(name,
                    _QUERY_VALUE_MAP[name], value))
            else:
                logging.warning('Unknown term: %r=%r', name, value)

        if not queries:
            queries.append(Query(''))

        logging.debug('queries: %r', [str(q) for q in queries])
        return Query(Query.OP_AND, queries)


class IndexStore(object):
    """Index metadata and provide rich query facilities on it.
    """

    def __init__(self):
        self._database = None
        self._flush_timeout = None
        self._pending_writes = 0
        root_path=layoutmanager.get_instance().get_root_path()
        self._index_updated_path = os.path.join(root_path,
                                                'index_updated')
        self._std_index_path = layoutmanager.get_instance().get_index_path()
        self._index_path = self._std_index_path
        
        # Create an instance of ERS
        self._ers = ERS()        

    def open_index(self, temp_path=False):
        # callers to open_index must be able to
        # handle an exception -- usually caused by
        # IO errors such as ENOSPC and retry putting
        # the index on a temp_path
        if temp_path:
            try:
                # mark the on-disk index stale
                self._set_index_updated(False)
            except:
                pass
            self._index_path = temp_path
        else:
             self._index_path = self._std_index_path
        try:
             self._database = WritableDatabase(self._index_path,
                                               xapian.DB_CREATE_OR_OPEN)
        except Exception as e:
             logging.error('Exception opening database')
             raise

    def close_index(self):
        """Close index database if it is open."""
        if not self._database:
            return

        self._flush(True)
        try:
            # does Xapian write in its destructors?
            self._database = None
        except Exception as e:
            logging.error('Exception tearing down database')
            raise

    def remove_index(self):
        if not os.path.exists(self._index_path):
            return
        for f in os.listdir(self._index_path):
            os.remove(os.path.join(self._index_path, f))

    def contains(self, uid):
        '''
        Check if there is a journal entry with the given UID
        '''
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)

        # Tells if the UID is in the store or not
        return self._ers.contains_entity(entity_name)

    def store(self, uid, properties):
        '''
        Add a document to the index
        '''
        document = Document()
        document.add_value(_VALUE_UID, uid)
        term_generator = TermGenerator()
        term_generator.index_document(document, properties)
        if not self.contains(uid):
            self._database.add_document(document)
        else:
            self._database.replace_document(_PREFIX_FULL_VALUE + \
                _PREFIX_UID + uid, document)
        
        self._flush(True)

    def find(self, query):
        '''
        Get a list of UIDs matching a query
        '''
        logging.warn("Query " + str(query))
        
        offset = query.pop('offset', 0)
        limit = query.pop('limit', MAX_QUERY_LIMIT)
        order_by = query.pop('order_by', [])
        query_string = query.pop('query', None)

        query_parser = QueryParser()
        query_parser.set_database(self._database)
        parsed_query = query_parser.parse_query(query, query_string)
        
        logging.warn("Parsed query " + str(parsed_query))

        # This will assure that the results count is exact.
        check_at_least = offset + limit + 1

        # TODO : Implement order by
        logging.warn('Unsupported property for sorting: %s', order_by)

        results = self._ers.search('uid', 'blah')
        logging.warn("Found " + str(results))
        
        total_count = 0
        uids = []
        return (uids, total_count)

    def delete(self, uid):
        self._database.delete_document(_PREFIX_FULL_VALUE + _PREFIX_UID + uid)
        self._flush(True)

    def get_activities(self):
        activities = []
        prefix = _PREFIX_FULL_VALUE + _PREFIX_ACTIVITY
        for term in self._database.allterms(prefix):
            activities.append(term.term[len(prefix):])
        return activities

    def flush(self):
        self._flush(True)

    def get_index_updated(self):
        return os.path.exists(self._index_updated_path)

    index_updated = property(get_index_updated)

    def _set_index_updated(self, index_updated):
        if self._std_index_path != self._index_path:
             # operating from tmpfs
             return True
        if index_updated != self.index_updated:
            if index_updated:
                index_updated_file = open(self._index_updated_path, 'w')
                # index_updated = True will happen every
                # indexstore._FLUSH_TIMEOUT seconds, so it is ok to fsync
                os.fsync(index_updated_file.fileno())
                index_updated_file.close()
            else:
                os.remove(self._index_updated_path)

    def _flush_timeout_cb(self):
        self._flush(True)
        return False

    def _flush(self, force=False):
        """Called after any database mutation"""
        logging.debug('IndexStore.flush: force=%r _pending_writes=%r',
                force, self._pending_writes)

        self._set_index_updated(False)

        if self._flush_timeout is not None:
            GObject.source_remove(self._flush_timeout)
            self._flush_timeout = None

        self._pending_writes += 1
        if force or self._pending_writes > _FLUSH_THRESHOLD:
            try:
                logging.debug("Start database flush")
                self._database.flush()
                logging.debug("Completed database flush")
            except Exception, e:
                logging.exception(e)
                logging.error("Exception during database.flush()")
                # bail out to trigger a reindex
                sys.exit(1)
            self._pending_writes = 0
            self._set_index_updated(True)
        else:
            self._flush_timeout = GObject.timeout_add_seconds(_FLUSH_TIMEOUT,
                                                      self._flush_timeout_cb)