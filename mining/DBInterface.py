from twisted.internet import reactor, defer
import time
import Queue

from stratum import settings

import stratum.logger
log = stratum.logger.get_logger('DBInterface')

class DBInterface():
    def __init__(self):
	self.q = Queue.Queue()
        self.queueclock = None

	self.usercache = {}
        self.clearusercache()

	self.nextStatsUpdate = 0

	self.dbi = self.connectDB()

        self.scheduleImport()

    def set_bitcoinrpc(self,bitcoinrpc):
	self.bitcoinrpc=bitcoinrpc

    def connectDB(self):
	# Choose our database driver and put it in self.dbi
	if settings.DATABASE_DRIVER == "sqlite":
		log.debug('DB_Sqlite INIT')
		import DB_Sqlite
		return DB_Sqlite.DB_Sqlite()
	elif settings.DATABASE_DRIVER == "mysql":
		log.debug('DB_Mysql INIT')
		import DB_Mysql
		return DB_Mysql.DB_Mysql()
	elif settings.DATABASE_DRIVER == "postgresql":
		log.debug('DB_Postgresql INIT')
		import DB_Postgresql
		return DB_Postgresql.DB_Postgresql()
	elif settings.DATABASE_DRIVER == "none":
		log.debug('DB_None INIT')
		import DB_None
		return DB_None.DB_None()
	else:
		log.error('Invalid DATABASE_DRIVER -- using NONE')
		log.debug('DB_None INIT')
		import DB_None
		return DB_None.DB_None()

    def clearusercache(self):
	self.usercache = {}
        self.usercacheclock = reactor.callLater( settings.DB_USERCACHE_TIME , self.clearusercache)

    def scheduleImport(self):
	# This schedule's the Import
	# If you don't want to use threads change 
	#	self.run_import_thread to self.run_import
        self.queueclock = reactor.callLater( settings.DB_LOADER_CHECKTIME , self.run_import_thread)
    
    def run_import_thread(self):
	if self.q.qsize() >= settings.DB_LOADER_REC_MIN:	# Don't incur thread overhead if we're not going to run
		reactor.callInThread(self.import_thread)
	self.scheduleImport()

    def run_import(self):
	self.do_import(self.dbi,False)
	if settings.DATABASE_EXTEND and time.time() > self.nextStatsUpdate :
	    dbi.updateStats(settings.DB_STATS_AVG_TIME)
            d = self.bitcoinrpc.getinfo()
            d.addCallback(self._update_pool_info)
	    self.nextStatsUpdate = time.time() + settings.DB_STATS_AVG_TIME
	self.scheduleImport()

    def import_thread(self):
	# Here we are in the thread.
	dbi = self.connectDB()	
	self.do_import(dbi,False)
	if settings.DATABASE_EXTEND and time.time() > self.nextStatsUpdate :
	    dbi.updateStats(settings.DB_STATS_AVG_TIME)
            d = self.bitcoinrpc.getinfo()
            d.addCallback(self._update_pool_info)
	    self.nextStatsUpdate = time.time() + settings.DB_STATS_AVG_TIME

    def _update_pool_info(self,data):
	self.dbi.update_pool_info({ 'blocks' : data['blocks'], 'balance' : data['balance'], 
		'connections' : data['connections'], 'difficulty' : data['difficulty'] })

    def do_import(self,dbi,force):
	# Only run if we have data
	while force == True or self.q.qsize() >= settings.DB_LOADER_REC_MIN:
	    force = False
	    # Put together the data we want to import
	    sqldata = []
	    datacnt = 0
	    while self.q.empty() == False and datacnt < settings.DB_LOADER_REC_MAX :
		datacnt += 1
		data = self.q.get()
		sqldata.append(data)
		self.q.task_done()
	    # try to do the import, if we fail, log the error and put the data back in the queue
	    try:
		log.info("Inserting %s Share Records",datacnt)
		dbi.import_shares(sqldata)
	    except Exception as e:
		log.error("Insert Share Records Failed: %s", e.args[0])
		for k,v in enumerate(sqldata):
		    self.q.put(v)
		break		# Allows us to sleep a little

    def queue_share(self,data):
	self.q.put( data )

    def found_block(self,data):
	try:
	    log.info("Updating Found Block Share Record")
	    self.do_import(self.dbi,True)	# We can't Update if the record is not there.
	    self.dbi.found_block(data)
	except Exception as e:
	    log.error("Update Found Block Share Record Failed: %s", e.args[0])

    def check_password(self,username,password):
	wid = username+":-:"+password
	if wid in self.usercache :
	    return True
	elif self.dbi.check_password(username,password) :
	    self.usercache[wid] = 1
	    return True
	elif settings.USERS_AUTOADD == True :
	    self.insert_user(username,password)
	    self.usercache[wid] = 1
	    return True
	return False

    def insert_user(self,username,password):	
	return self.dbi.insert_user(username,password)

    def delete_user(self,username):
	self.usercache = {}
	return self.dbi.delete_user(username)
	
    def update_user(self,username,password):
	self.usercache = {}
	return self.dbi.update_user(username,password)

    def get_pool_stats(self):
	return self.dbi.get_pool_stats()
    
    def get_workers_stats(self):
	return self.dbi.get_workers_stats()
