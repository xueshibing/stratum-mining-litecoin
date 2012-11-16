'''
This is example configuration for Stratum server.
Please rename it to config.py and fill correct values.
'''

# ******************** GENERAL SETTINGS ***************

# Enable some verbose debug (logging requests and responses).
DEBUG = False

# Destination for application logs, files rotated once per day.
LOGDIR = 'log/'

# Main application log file.
LOGFILE = None		# eg. 'stratum.log'

# Possible values: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOGLEVEL = 'INFO'

# How many threads use for synchronous methods (services).
# 30 is enough for small installation, for real usage
# it should be slightly more, say 100-300.
THREAD_POOL_SIZE = 30

ENABLE_EXAMPLE_SERVICE = True

# ******************** TRANSPORTS *********************

# Hostname or external IP to expose
HOSTNAME = 'localhost'

# Port used for Socket transport. Use 'None' for disabling the transport.
LISTEN_SOCKET_TRANSPORT = 3333

# Port used for HTTP Poll transport. Use 'None' for disabling the transport
LISTEN_HTTP_TRANSPORT = None

# Port used for HTTPS Poll transport
LISTEN_HTTPS_TRANSPORT = None

# Port used for WebSocket transport, 'None' for disabling WS
LISTEN_WS_TRANSPORT = None

# Port used for secure WebSocket, 'None' for disabling WSS
LISTEN_WSS_TRANSPORT = None

# Hostname and credentials for one trusted Bitcoin node ("Satoshi's client").
# Stratum uses both P2P port (which is 8333 already) and RPC port
BITCOIN_TRUSTED_HOST = 'localhost'
BITCOIN_TRUSTED_PORT = 8332
BITCOIN_TRUSTED_USER = 'user'
BITCOIN_TRUSTED_PASSWORD = 'somepassword'

# Use scripts/generateAdminHash.sh <password> to generate the hash
# for calculating SHA256 of your preferred password
ADMIN_PASSWORD_SHA256 = None
#ADMIN_PASSWORD_SHA256 = '9e6c0c1db1e0dfb3fa5159deb4ecd9715b3c8cd6b06bd4a3ad77e9a8c5694219' # SHA256 of the password

IRC_NICK = None

# ******************** Database  *********************

DATABASE_DRIVER = 'sqlite'	# Options: none, sqlite, postgresql or mysql
DATABASE_EXTEND = True		# False = pushpool db layout, True = pushpool + extra columns

# SQLite
DB_SQLITE_FILE = 'pooldb.sqlite'
# Postgresql
DB_PGSQL_HOST = 'localhost'
DB_PGSQL_DBNAME = 'pooldb'
DB_PGSQL_USER = 'pooldb'
DB_PGSQL_PASS = '**empty**'
DB_PGSQL_SCHEMA = 'public'
# MySQL
DB_MYSQL_HOST = 'localhost'
DB_MYSQL_DBNAME = 'pooldb'
DB_MYSQL_USER = 'pooldb'
DB_MYSQL_PASS = '**empty**'

# ******************** Adv. DB Settings *********************
#  Don't change these unless you know what you are doing

DB_LOADER_CHECKTIME = 15	# How often we check to see if we should run the loader
DB_LOADER_REC_MIN = 10		# Min Records before the bulk loader fires
DB_LOADER_REC_MAX = 50		# Max Records the bulk loader will commit at a time

DB_STATS_AVG_TIME = 300		# When using the DATABASE_EXTEND option, average speed over X sec
				#	Note: this is also how often it updates
DB_USERCACHE_TIME = 600		# How long the usercache is good for before we refresh

# ******************** Pool Settings *********************

# User Auth Options
USERS_AUTOADD = True		# Automatically add users to db when they connect.
				# 	This basically disables User Auth for the pool.
USERS_CHECK_PASSWORD = False	# Check the workers password? (Many pools don't)

# Transaction Settings
CENTRAL_WALLET = 'set_valid_addresss_in_config!'	# local bitcoin address where money goes
COINBASE_EXTRAS = '/stratumPool/'			# Extra Descriptive String to incorporate in solved blocks

# Pool Target
POOL_TARGET = 1			# Pool-wide difficulty target int >= 1

# Bitcoind communication polling settings (In Seconds)
PREVHASH_REFRESH_INTERVAL = 5 	# How often to check for new Blocks
				#	If using the blocknotify script (recommended) set = to MERKLE_REFRESH_INTERVAL
				#	(No reason to poll if we're getting pushed notifications)
MERKLE_REFRESH_INTERVAL = 60	# How often check memorypool
				#	This effectively resets the template and incorporates new transactions.
				#	This should be "slow"

INSTANCE_ID = 31		# Not a clue what this is for... :P
