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
	self.dbc.execute("update pool_worker set speed = 0");
	stime = '%.2f' % ( time.time() - averageOverTime );
	self.dbc.execute("select username,SUM(difficulty) from shares where time > FROM_UNIXTIME(%s) group by username", (stime,))
	for name,shares in self.dbc.fetchall():
	    speed = int(int(shares) * pow(2,32)) / ( int(averageOverTime) * 1000 * 1000)
	    self.dbc.execute("update pool_worker set speed = %s where username = %s", (speed,name))
	self.dbh.commit()

    def import_shares(self,data):
	log.debug("Importing Shares")
#	       0           1            2          3          4         5        6  7            8         9
#	data: [worker_name,block_header,block_hash,difficulty,timestamp,is_valid,ip,block_height,prev_hash,invalid_reason]
	checkin_times = {}
	for k,v in enumerate(data):
	    if settings.DATABASE_EXTEND :
		if v[0] in checkin_times:
		    if v[4] > checkin_times[v[0]] :
			checkin_times[v[0]] = v[4]
		else:
		    checkin_times[v[0]] = v[4]

		self.dbc.execute("insert into shares " +\
			"(time,rem_host,username,our_result,upstream_result,reason,solution,block_num,prev_block_hash,useragent,difficulty) " +\
			"VALUES (FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
			(v[4],v[6],v[0],v[5],0,v[9],'',v[7],v[8],'',v[3]) )
	    else :
		self.dbc.execute("insert into shares (time,rem_host,username,our_result,upstream_result,reason,solution) VALUES " +\
			"(FROM_UNIXTIME(%s),%s,%s,%s,%s,%s,%s)",
			(v[4],v[6],v[0],v[5],0,v[9],'') )
	if settings.DATABASE_EXTEND :
	    for k,v in checkin_times.items():
		self.dbc.execute("update pool_worker set last_checkin = FROM_UNIXTIME(%s) where username = %s",(v,k))

	self.dbh.commit()


    def found_block(self,data):
	# Note: difficulty = -1 here
	self.dbc.execute("update shares set upstream_result = %s, solution = %s where time = %s and username = %s",
		(data[5],data[2],data[4],data[0]))
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
	    self.dbc.execute("create table if not exists pool_worker(id serial primary key,username TEXT, password TEXT, speed INTEGER, last_checkin timestamp) ENGINE = MYISAM")
	    if pool_worker_exist == False:
	    	self.dbc.execute("create index pool_worker_username ON pool_worker(username(10))")
	else :
	    self.dbc.execute("create table if not exists shares" + \
		"(id serial,time timestamp,rem_host TEXT, username TEXT, our_result INTEGER, upstream_result INTEGER, reason TEXT, solution TEXT) ENGINE = MYISAM")
	    if shares_exist == False:
	    	self.dbc.execute("create index shares_username ON shares(username(10))")
	    self.dbc.execute("create table if not exists pool_worker(id serial,username TEXT, password TEXT) ENGINE = MYISAM")
	    if pool_worker_exist == False:
	    	self.dbc.execute("create index pool_worker_username ON pool_worker(username(10))")
	self.dbh.commit()
	
