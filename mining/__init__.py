from service import MiningService
from subscription import MiningSubscription
from twisted.internet import defer
import time
import simplejson as json
from twisted.internet import reactor

@defer.inlineCallbacks
def setup(on_startup):
    '''Setup mining service internal environment.
    You should not need to change this. If you
    want to use another Worker manager or Share manager,
    you should set proper reference to Interfaces class
    *before* you call setup() in the launcher script.'''

    from stratum import settings

    # Get logging online as soon as possible
    import stratum.logger
    log = stratum.logger.get_logger('mining')

    from interfaces import Interfaces
    
    from lib.block_updater import BlockUpdater
    from lib.template_registry import TemplateRegistry
    from lib.bitcoin_rpc_manager import BitcoinRPCManager
    from lib.block_template import BlockTemplate
    from lib.coinbaser import SimpleCoinbaser
    
    bitcoin_rpc = BitcoinRPCManager()
    
    # Check bitcoind
    #         Check we can connect (sleep)
    # Check the results:
    #         - getblocktemplate is avalible        (Die if not)
    #         - we are not still downloading the blockchain        (Sleep)
    log.info("Connecting to bitcoind...")
    while True:
        try:
            result = (yield bitcoin_rpc.getblocktemplate())
            if isinstance(result, dict):
                if result['version'] == 2:
                    break
        except Exception, e:
            if isinstance(e[2], str):
                if isinstance(json.loads(e[2])['error']['message'], str):
                    error = json.loads(e[2])['error']['message']
                    if error == "Method not found":
                        log.error("Bitcoind does not support getblocktemplate!!! (time to upgrade.)")
                        reactor.stop()
                    elif error == "Bitcoin is downloading blocks...":
                        log.error("Bitcoind downloading blockchain... will check back in 30 sec")
                        time.sleep(29)
                    else:
                        log.error("Bitcoind Error: %s", error)
        time.sleep(1)  # If we didn't get a result or the connect failed
        
    log.info('Connected to bitcoind - Ready to GO!')

    # Start the coinbaser
    coinbaser = SimpleCoinbaser(bitcoin_rpc, settings.CENTRAL_WALLET)
    (yield coinbaser.on_load)
    
    registry = TemplateRegistry(BlockTemplate,
                                coinbaser,
                                bitcoin_rpc,
                                settings.INSTANCE_ID,
                                MiningSubscription.on_template,
                                Interfaces.share_manager.on_network_block)
    
    # Template registry is the main interface between Stratum service
    # and pool core logic
    Interfaces.set_template_registry(registry)
    
    # Set up polling mechanism for detecting new block on the network
    # This is just failsafe solution when -blocknotify
    # mechanism is not working properly    
    BlockUpdater(registry, bitcoin_rpc)
    
    log.info("MINING SERVICE IS READY")
    on_startup.callback(True)





