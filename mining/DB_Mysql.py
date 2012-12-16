import time
from stratum import settings
import stratum.logger
log = stratum.logger.get_logger('DB_Mysql')

import MySQLdb
                
class DB_Mysql():
    def __init__(self):
	log.debug("Connecting to DB")
	self.dbh = MySQLdb.connect(settings.DB_MYSQL_HOST,settings.DB_MYSQL_USER,settings.DB_MYSQL_PASS,settings.DB_MYSQL_DBNAME)
	self.dbc = self.dbh.cursor()

	self.check_tables()

    def updateStats(self,averageOverTime):
	log.debug("Updating Stats")
	# Note: we are using transactions... so we can set the speed = 0 and it doesn't take affect until we are commited.
	self.dbc.execute("update pool_worker set speed = 0, alive = 0");
	stime = '%.0f' % ( time.time() - averageOverTime );
	self.dbc.execute("select username,SUM(difficulty) from shares where time > FROM_UNIXTIME(%s) group by username", (stime,))
	total_speed = 0
	for name,shares in self.dbc.fetchall():
	    speed = int(int(shares) * pow(2,32)) / ( int(averageOverTime) * 1000 * 1000)
	    total_speed += speed
	    self.dbc.execute("update pool_worker set speed = %s, alive = 1 where username = %s", (speed,name))
	self.dbc.execute("update pool set value = %s where parameter = 'pool_speed'",[total_speed])
	self.dbh.commit()

    def import_shares(self,data):
	log.debug("Importing Shares")
#	       0           1            2          3          4         5        6  7            8         9              10
#	data: [worker_name,block_header,block_hash,difficulty,timestamp,is_valid,ip,block_height,prev_hash,invalid_reason,best_diff]
	checkin_times = {}
	total_shares = 0
	best_diff = 0
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

		if v[10] > best_diff:
		    best_diff = v[10]

		self.dbc.execute("insert into shares " +\
			"(time,rem_host,username,our_result,upstream_result,reason,solution,block_num,prev_block_hash,useragent,difficulty) " +\
			"VALUES (FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
			(v[4],v[6],v[0],v[5],0,v[9],'',v[7],v[8],'',v[3]) )
	    else :
		self.dbc.execute("insert into shares (time,rem_host,username,our_result,upstream_result,reason,solution) VALUES " +\
			"(FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s)",
			(v[4],v[6],v[0],v[5],0,v[9],'') )

	if settings.DATABASE_EXTEND :
	    self.dbc.execute("select value from pool where parameter = 'round_shares'")
	    round_shares = int(self.dbc.fetchone()[0]) + total_shares
	    self.dbc.execute("update pool set value = %s where parameter = 'round_shares'",[round_shares])

	    self.dbc.execute("select value from pool where parameter = 'round_best_share'")
	    round_best_share = int(self.dbc.fetchone()[0])
	    if best_diff > round_best_share:
		self.dbc.execute("update pool set value = %s where parameter = 'round_best_share'",[best_diff])

	    self.dbc.execute("select value from pool where parameter = 'bitcoin_difficulty'")
	    difficulty = float(self.dbc.fetchone()[0])

	    progress = (round_shares/difficulty)*100
	    self.dbc.execute("update pool set value = %s where parameter = 'round_progress'",[progress])
	
	    for k,v in checkin_times.items():
		self.dbc.execute("update pool_worker set last_checkin = FROM_UNIXTIME(%s), total_shares = total_shares + %s, total_rejects = total_rejects + %s where username = %s",
			(v["time"],v["shares"],v["rejects"],k))

	self.dbh.commit()


    def found_block(self,data):
	# Note: difficulty = -1 here
	self.dbc.execute("update shares set upstream_result = %s, solution = %s where time = FROM_UNIXTIME(%s) and username = %s limit 1",
		(data[5],data[2],data[4],data[0]))
	if settings.DATABASE_EXTEND and data[5] == True:
	    self.dbc.execute("update pool_worker set total_found = total_found + 1 where username = %s",(data[0]))
	    self.dbc.execute("select value from pool where parameter = 'pool_total_found'")
	    total_found = int(self.dbc.fetchone()[0]) + 1
	    self.dbc.executemany("update pool set value = %s where parameter = %s",[(0,'round_shares'),
		(0,'round_progress'),
		(0,'round_best_share'),
		(time.time(),'round_start'),
		(total_found,'pool_total_found')
		])
	self.dbh.commit()

    def delete_user(self,username):
	log.debug("Deleting Username")
	self.dbc.execute("delete from pool_worker where username = %s",
		(username ))
	self.dbh.commit()

    def insert_user(self,username,password):
	log.debug("Adding Username/Password")
	self.dbc.execute("insert into pool_worker (username,password) VALUES (%s,%s)",
		(username, password ))
	self.dbh.commit()

    def update_user(self,username,password):
	log.debug("Updating Username/Password")
	self.dbc.execute("update pool_worker set password = %(pass)s where username = %(uname)s",
		(username, password ))
	self.dbh.commit()

    def check_password(self,username,password):
	log.debug("Checking Username/Password")
	self.dbc.execute("select COUNT(*) from pool_worker where username = %s and password = %s",
		(username, password ))
	data = self.dbc.fetchone()
	if data[0] > 0 :
	    return True
	return False

    def update_pool_info(self,pi):
	self.dbc.executemany("update pool set value = %s where parameter = %s",[(pi['blocks'],"bitcoin_blocks"),
		(pi['balance'],"bitcoin_balance"),
		(pi['connections'],"bitcoin_connections"),
		(pi['difficulty'],"bitcoin_difficulty"),
		(time.time(),"bitcoin_infotime")
		])
	self.dbh.commit()

    def get_pool_stats(self):
	self.dbc.execute("select * from pool")
	ret = {}
	for data in self.dbc.fetchall():
	    ret[data[0]] = data[1]
	return ret

    def get_workers_stats(self):
	self.dbc.execute("select username,speed,last_checkin,total_shares,total_rejects,total_found,alive from pool_worker")
	ret = {}
	for data in self.dbc.fetchall():
	    ret[data[0]] = { "username" : data[0],
		"speed" : data[1],
		"last_checkin" : time.mktime(data[2].timetuple()),
		"total_shares" : data[3],
		"total_rejects" : data[4],
		"total_found" : data[5],
		"alive" : data[6] }
	return ret

    def check_tables(self):
	log.debug("Checking Tables")

	shares_exist = False
	self.dbc.execute("select COUNT(*) from INFORMATION_SCHEMA.STATISTICS where table_schema = %(schema)s and table_name = 'shares' and index_name = 'shares_username'",
		{"schema": settings.DB_MYSQL_DBNAME })
	data = self.dbc.fetchone()
	if data[0] > 0 :
	    shares_exist = True

	pool_worker_exist = False
	self.dbc.execute("select COUNT(*) from INFORMATION_SCHEMA.STATISTICS where table_schema = %(schema)s and table_name = 'pool_worker' and index_name = 'pool_worker_username'", 
		{"schema": settings.DB_MYSQL_DBNAME })
	data = self.dbc.fetchone()
	if data[0] > 0 :
	    pool_worker_exist = True

	if settings.DATABASE_EXTEND == True :
	    self.dbc.execute("create table if not exists shares " +\
		"(id serial primary key,time timestamp,rem_host TEXT, username TEXT, our_result BOOLEAN, upstream_result BOOLEAN, reason TEXT, solution TEXT, " +\
		"block_num INTEGER, prev_block_hash TEXT, useragent TEXT, difficulty INTEGER) ENGINE = MYISAM;")
	    if shares_exist == False:
	    	self.dbc.execute("create index shares_username ON shares(username(10))")

	    self.dbc.execute("create table if not exists pool_worker" +\
		"(id serial primary key,username TEXT, password TEXT, speed INTEGER, last_checkin timestamp" +\
		") ENGINE = MYISAM")
	    if pool_worker_exist == False:
	    	self.dbc.execute("create index pool_worker_username ON pool_worker(username(10))")
	
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
		"(id serial,time timestamp,rem_host TEXT, username TEXT, our_result INTEGER, upstream_result INTEGER, reason TEXT, solution TEXT) ENGINE = MYISAM")
	    if shares_exist == False:
	    	self.dbc.execute("create index shares_username ON shares(username(10))")
	    self.dbc.execute("create table if not exists pool_worker(id serial,username TEXT, password TEXT) ENGINE = MYISAM")
	    if pool_worker_exist == False:
	    	self.dbc.execute("create index pool_worker_username ON pool_worker(username(10))")
	self.dbh.commit()
	
    def update_tables(self):
	version = 0
	current_version = 4
	while version < current_version :
	    self.dbc.execute("select value from pool where parameter = 'DB Version'")
	    data = self.dbc.fetchone()
	    version = int(data[0])
	    if version < current_version :
		log.info("Updating Database from %i to %i" % (version, version +1))
		getattr(self, 'update_version_' + str(version) )()
		    

    def update_version_2(self):
	log.info("running update 2")
	self.dbc.executemany("insert into pool (parameter,value) VALUES (%s,%s)",[('bitcoin_blocks',0),
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
	
    def update_version_3(self):
	log.info("running update 3")
	self.dbc.executemany("insert into pool (parameter,value) VALUES (%s,%s)",[
		('round_best_share',0),
		('bitcoin_infotime',0)
		])
	self.dbc.execute("alter table pool_worker add alive BOOLEAN")
	self.dbc.execute("update pool set value = 4 where parameter = 'DB Version'")
	self.dbh.commit()
	
