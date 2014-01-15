import os
import logging
import dbus

from ers import ERS
from carquinyol import layoutmanager
from carquinyol import metadatareader

MAX_SIZE = 256
_INTERNAL_KEYS = ['checksum']


class MetadataStore(object):
    def __init__(self):
        '''
        Constructor
        '''
        # Create an instance of ERS
        self._ers = ERS()        

    
    def store(self, uid, metadata):
        '''
        Store a new entry to the journal
        '''
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)

        # If already existing, erase the previous version
        if self._ers.contains_entity(entity_name):
            self._ers.delete_entity(entity_name)
    
        # Update the description of the entity
        entity = self._ers.create_entity(entity_name)
        metadata['uid'] = uid
        for key, value in metadata.items():
            #if isinstance(value, unicode):
            #    value = value.encode('utf-8')
            #elif not isinstance(value, basestring):
            #    value = str(value)
            if type(value) == dbus.Int32 or type(value) == dbus.String:
                entity.add_property(key, value)
            else:
                logging.warn("Skipped " + key + "(" + str(type(value)) + ")")
    
        # Persist the result
        self._ers.persist_entity(entity)
        
    def retrieve(self, uid, properties=None):
        '''
        Retrieve some properties of a journal entry
        '''
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)
        
        # Get all the (accessible) documents describing that identifier
        entity = self._ers.get_entity(entity_name)
        
        # Get all the properties
        description = entity.get_properties()
        
        # TODO if properties != None filter the output
        return description

    def delete(self, uid):
        '''
        Delete a journal entry
        '''
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)
        
        # Delete
        self._ers.delete_entity(entity_name)

    def get_property(self, uid, key):
        '''
        Get a single property
        '''
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)
        
        # Get all the (accessible) documents describing that identifier
        entity = self._ers.get_entity(entity_name)
        
        # Get all the properties
        description = entity.get_properties()

        # Return the result
        return description[key]
    
    def set_property(self, uid, key, value):
        '''
        Set a single property
        '''
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)

        # Get all the (accessible) documents describing that identifier
        entity = self._ers.get_entity(entity_name)

        # Get all the properties
        description = entity.get_properties()
        
        # Remove previous values
        if key in description:
            for v in description[key]:
                entity.delete_property(key, v)
        
        # Set new value
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif not isinstance(value, basestring):
            value = str(value)
        entity.add_property(key, value)
        
        # Persist
        self._ers.persist_entity(entity)