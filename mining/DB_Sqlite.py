import time
from stratum import settings
import stratum.logger
log = stratum.logger.get_logger('DB_Sqlite')

import sqlite3
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
               
class DB_Sqlite():
    def __init__(self):
	log.debug("Connecting to DB")
	self.dbh = sqlite3.connect(settings.DB_SQLITE_FILE)
	self.dbc = self.dbh.cursor()

	self.check_tables()

    def updateStats(self,averageOverTime):
	log.debug("Updating Stats")
	# Note: we are using transactions... so we can set the speed = 0 and it doesn't take affect until we are commited.
	self.dbc.execute("update pool_worker set speed = 0");
	stime = '%.2f' % ( time.time() - averageOverTime );
	self.dbc.execute("select username,SUM(difficulty) from shares where time > :time group by username", {'time':stime})
	total_speed = 0
	sqldata = []
	for name,shares in self.dbc.fetchall():
	    speed = int(int(shares) * pow(2,32)) / ( int(averageOverTime) * 1000 * 1000)
	    total_speed += speed
	    sqldata.append({'speed':speed,'user':name})
	self.dbc.executemany("update pool_worker set speed = :speed where username = :user",sqldata)
	self.dbc.execute("update pool set value = :val where parameter = 'pool_speed'",{'val':total_speed})
	self.dbh.commit()

    def import_shares(self,data):
	log.debug("Importing Shares")
#	       0           1            2          3          4         5        6  7            8         9
#	data: [worker_name,block_header,block_hash,difficulty,timestamp,is_valid,ip,block_height,prev_hash,invalid_reason]
	checkin_times = {}
	total_shares = 0
	sqldata = []
	for k,v in enumerate(data):
	    if settings.DATABASE_EXTEND :
		total_shares += v[3]
		if v[0] in checkin_times:
		    if v[4] > checkin_times[v[0]] :
			checkin_times[v[0]]["time"] = v[4]
		else:
		    checkin_times[v[0]] = {"time": v[4], "shares": 0, "rejects": 0 }

		if v[5] == True :
		    checkin_times[v[0]]["shares"] += v[3]
		else :
		    checkin_times[v[0]]["rejects"] += v[3]

		sqldata.append({'time':v[4],'rem_host':v[6],'username':v[0],'our_result':v[5],'upstream_result':0,'reason':v[9],'solution':'',
			'block_num':v[7],'prev_block_hash':v[8],'ua':'','diff':v[3]} )
	    else :
		sqldata.append({'time':v[4],'rem_host':v[6],'username':v[0],'our_result':v[5],'upstream_result':0,'reason':v[9],'solution':''} )

	if settings.DATABASE_EXTEND :
	    self.dbc.executemany("insert into shares " +\
		"(time,rem_host,username,our_result,upstream_result,reason,solution,block_num,prev_block_hash,useragent,difficulty) " +\
		"VALUES (:time,:rem_host,:username,:our_result,:upstream_result,:reason,:solution,:block_num,:prev_block_hash,:ua,:diff)",sqldata)


	    self.dbc.execute("select value from pool where parameter = 'round_shares'")
	    round_shares = int(self.dbc.fetchone()[0]) + total_shares
	    self.dbc.execute("update pool set value = :val where parameter = 'round_shares'",{'val':round_shares})

	    self.dbc.execute("select value from pool where parameter = 'bitcoin_difficulty'")
	    difficulty = float(self.dbc.fetchone()[0])

	    progress = (round_shares/difficulty)*100
	    self.dbc.execute("update pool set value = :val where parameter = 'round_progress'",{'val':progress})

	    sqldata = []
	    for k,v in checkin_times.items():
		sqldata.append({'last_checkin':v["time"],'addshares':v["shares"],'addrejects':v["rejects"],'user':k})
	    self.dbc.executemany("update pool_worker set last_checkin = :last_checkin, total_shares = total_shares + :addshares, " +\
			"total_rejects = total_rejects + :addrejects where username = :user",sqldata)
	else:
	    self.dbc.executemany("insert into shares (time,rem_host,username,our_result,upstream_result,reason,solution) " +\
		"VALUES (:time,:rem_host,:username,:our_result,:upstream_result,:reason,:solution)",sqldata)

	self.dbh.commit()

    def found_block(self,data):
	# Note: difficulty = -1 here
	self.dbc.execute("update shares set upstream_result = :usr, solution = :sol where time = :time and username = :user",
		{'usr':data[5],'sol':data[2],'time':data[4],'user':data[0]})
	if settings.DATABASE_EXTEND :
	    if data[5] == True:
	    	self.dbc.execute("update pool_worker set total_found = total_found + 1 where username = :user",{'user':data[0]})
	    self.dbc.execute("select value from pool where parameter = 'pool_total_found'")
	    total_found = int(self.dbc.fetchone()[0]) + 1
	    self.dbc.execute("update pool set value = :val where paramter = :parm", [{'val':0,'parm':'round_shares'},
		{'val':0,'parm':'round_progress'},
		{'val':time.time(),'parm':'round_start'},
		{'val':[total_found],'parm':'pool_total_found'}
		])
	self.dbh.commit()

    def delete_user(self,username):
	log.debug("Deleting Username")
	self.dbc.execute("delete from pool_worker where username = :user", {'user':username})	
	self.dbh.commit()

    def insert_user(self,username,password):
	log.debug("Adding Username/Password")
	self.dbc.execute("insert into pool_worker (username,password) VALUES (:user,:pass)", {'user':username,'pass':password})	
	self.dbh.commit()

    def update_user(self,username,password):
	log.debug("Updating Username/Password")
	self.dbc.execute("update pool_worker set password = :pass where username = :user", {'pass':password,'user':username})	
	self.dbh.commit()

    def check_password(self,username,password):
	log.debug("Checking Username/Password")
	self.dbc.execute("select COUNT(*) from pool_worker where username = :user and password = :pass", {'user':username,'pass':password})
	data = self.dbc.fetchone()
	if data[0] > 0 :
	    return True
	return False

    def update_pool_info(self,pi):
	self.dbc.executemany("update pool set value = :val where parameter = :parm",[{'val':pi['blocks'],'parm':"bitcoin_blocks"},
		{'val':pi['balance'],'parm':"bitcoin_balance"},
		{'val':pi['connections'],'parm':"bitcoin_connections"},
		{'val':pi['difficulty'],'parm':"bitcoin_difficulty"}
		])
	self.dbh.commit()

    def get_pool_stats(self):
	self.dbc.execute("select * from pool")
	ret = {}
	for data in self.dbc.fetchall():
	    ret[data[0]] = data[1]
	return ret

    def get_workers_stats(self):
	self.dbc.execute("select username,speed,last_checkin,total_shares,total_rejects,total_found from pool_worker")
	ret = {}
	for data in self.dbc.fetchall():
	    ret[data[0]] = { "username" : data[0],
		"speed" : data[1],
		"last_checkin" : data[2],
		"total_shares" : data[3],
		"total_rejects" : data[4],
		"total_found" : data[5] }
	return ret

    def check_tables(self):
	log.debug("Checking Tables")
	if settings.DATABASE_EXTEND == True :
		self.dbc.execute("create table if not exists shares" +\
			"(time DATETIME,rem_host TEXT, username TEXT, our_result INTEGER, upstream_result INTEGER, reason TEXT, solution TEXT, " +\
			"block_num INTEGER, prev_block_hash TEXT, useragent TEXT, difficulty INTEGER)")
		self.dbc.execute("create table if not exists pool_worker" +\
			"(username TEXT, password TEXT, speed INTEGER, last_checkin DATETIME)")
		self.dbc.execute("create table if not exists pool(parameter TEXT, value TEXT)")

		self.dbc.execute("select COUNT(*) from pool where parameter = 'DB Version'")
		data = self.dbc.fetchone()
		if data[0] <= 0:
		    self.dbc.execute("alter table pool_worker add total_shares INTEGER default 0")
		    self.dbc.execute("alter table pool_worker add total_rejects INTEGER default 0")
		    self.dbc.execute("alter table pool_worker add total_found INTEGER default 0")
		    self.dbc.execute("insert into pool (parameter,value) VALUES ('DB Version',2)")
		self.update_tables()
	else :
		self.dbc.execute("create table if not exists shares" + \
			"(time DATETIME,rem_host TEXT, username TEXT, our_result INTEGER, upstream_result INTEGER, reason TEXT, solution TEXT)")
		self.dbc.execute("create table if not exists pool_worker(username TEXT, password TEXT)")
	self.dbc.execute("create index if not exists shares_username ON shares(username)")
	self.dbc.execute("create index if not exists pool_worker_username ON pool_worker(username)")

    def update_tables(self):
	version = 0
	current_version = 3
	while version < current_version :
	    self.dbc.execute("select value from pool where parameter = 'DB Version'")
	    data = self.dbc.fetchone()
	    version = int(data[0])
	    if version < current_version :
		log.info("Updating Database from %i to %i" % (version, version +1))
		getattr(self, 'update_version_' + str(version) )()
		    

    def update_version_2(self):
	log.info("running update 2")
	self.dbc.executemany("insert into pool (parameter,value) VALUES (?,?)",[('bitcoin_blocks',0),
		('bitcoin_balance',0),
		('bitcoin_connections',0),
		('bitcoin_difficulty',0),
		('pool_speed',0),
		('pool_total_found',0),
		('round_shares',0),
		('round_progress',0),
		('round_start',time.time())
		])
	self.dbc.execute("update pool set value = 3 where parameter = 'DB Version'")
	self.dbh.commit()
	
