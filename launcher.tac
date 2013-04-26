# Run me with "twistd -ny launcher.tac -l -"

# Add conf directory to python path.
# Configuration file is standard python module.
import os, sys
sys.path = [os.path.join(os.getcwd(), 'conf'),os.path.join(os.getcwd(), 'externals', 'stratum-mining-proxy'),] + sys.path

from twisted.internet import defer

# Run listening when mining service is ready
on_startup = defer.Deferred()

# Bootstrap Stratum framework
import stratum
from stratum import settings
application = stratum.setup(on_startup)

# Load mining service into stratum framework
import mining

from mining.interfaces import Interfaces
from mining.interfaces import WorkerManagerInterface, TimestamperInterface, \
                            ShareManagerInterface, ShareLimiterInterface

if settings.VARIABLE_DIFF == True:
    from mining.basic_share_limiter import BasicShareLimiter
    Interfaces.set_share_limiter(BasicShareLimiter())
else:
    from mining.interfaces import ShareLimiterInterface
    Interfaces.set_share_limiter(ShareLimiterInterface())

Interfaces.set_share_manager(ShareManagerInterface())
Interfaces.set_worker_manager(WorkerManagerInterface())
Interfaces.set_timestamper(TimestamperInterface())

mining.setup(on_startup)

from lib.admin_interface import AdminInterface

if settings.DATABASE_EXTEND == True and settings.BASIC_STATS == True :
    from lib.basic_stats import BasicStats
    BasicStats(on_startup)

if settings.GW_ENABLE == True :
    from lib.getwork_proxy import GetworkProxy
    GetworkProxy(on_startup)

