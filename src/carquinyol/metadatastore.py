import logging
import dbus

from ers import ERS
from carquinyol import layoutmanager

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
        Create or update an entry to the journal
        '''
        logging.warn("Add {}".format(uid))
        logging.warn("Add {}".format(metadata))
        
        # Name of the entry
        entity_name = layoutmanager.get_instance().get_entity_name(uid)

        # Get or create the entity
        entity = None
        if self._ers.entity_exist(entity_name):
            entity = self._ers.get_entity(entity_name)
        else:
            entity = self._ers.create_entity(entity_name)
    
        # Update the description of the entity
        metadata['uid'] = str(uid)
        for key, value in metadata.items():
            entity.set_property_value(key, value, private=True)
            #if type(value) == dbus.Int32 or type(value) == dbus.String or (str(type(value)) in ["<type 'str'>", "<type 'int'>"]):
            #    entity.set_property_value(key, value, private=True)
            #else:
            #    logging.warn("Skipped " + key + "(" + str(type(value)) + ")")
    
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

        # Set new value
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif not isinstance(value, basestring):
            value = str(value)
        entity.set_property_value(key, value, private=True)
        
        # Persist
        self._ers.persist_entity(entity)