import util
from twisted.internet import defer

import settings

import lib.logger
log = lib.logger.get_logger('coinbaser')

# TODO: Add on_* hooks in the app
    
class SimpleCoinbaser(object):
    '''This very simple coinbaser uses constant bitcoin address
    for all generated blocks.'''
    
    def __init__(self, bitcoin_rpc, pubkey):
        self.pubkey = pubkey
        # Fire callback when coinbaser is ready
        self.on_load = defer.Deferred()
        self.on_load.callback(True)
    
    #def on_new_block(self):
    #    pass
    
    #def on_new_template(self):
    #    pass
    
    def get_script_pubkey(self):
        return util.script_to_pubkey(self.pubkey)    
                   
    def get_coinbase_data(self):
        return ''
