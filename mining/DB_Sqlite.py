import time
from stratum import settings
import stratum.logger
log = stratum.logger.get_logger('DB_Sqlite')

import sqlite3
                
class DB_Sqlite():
    def __init__(self):
	log.debug("Connecting to DB")
	self.dbh = sqlite3.connect(settings.DB_SQLITE_FILE)
	self.dbc = self.dbh.cursor()

	self.check_tables()

    def updateStats(self,averageOverTime):
	log.debug("Updating Stats")
	stime = '%.2f' % ( time.time() - averageOverTime );
	self.dbc.execute("select username,SUM(difficulty) from shares where time > ? group by username", (stime,))
	for name,shares in self.dbc.fetchall():
	    speed = int(int(shares) * pow(2,32)) / ( int(averageOverTime) * 1000 * 1000)
	    self.dbc.execute("update pool_worker set speed = ? where username = ?",(speed,name))
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
			"VALUES (?,?,?,?,?,?,?,?,?,?,?)",
			(v[4],v[6],v[0],v[5],0,v[9],'',v[7],v[8],'',v[3]) )
	    else :
		self.dbc.execute("insert into shares (time,rem_host,username,our_result,upstream_result,reason,solution) VALUES (?,?,?,?,?,?,?)",
			(v[4],v[6],v[0],v[5],0,v[9],'') )
	if settings.DATABASE_EXTEND :
	    for k,v in checkin_times.items():
		self.dbc.execute("update pool_worker set last_checkin = ? where username = ?",(v,k))

	self.dbh.commit()


    def found_block(self,data):
	# Note: difficulty = -1 here
	self.dbc.execute("update shares set upstream_result = ?, solution = ? where time = ? and username = ?",
		(data[5],data[2],data[4],data[0]))
	self.dbh.commit()

    def delete_user(self,username):
	log.debug("Deleting Username")
	self.dbc.execute("delete from pool_worker where username = ?", (username))	
	self.dbh.commit()

    def insert_user(self,username,password):
	log.debug("Adding Username/Password")
	self.dbc.execute("insert into pool_worker (username,password) VALUES (?,?)", (username,password))	
	self.dbh.commit()

    def update_user(self,username,password):
	log.debug("Updating Username/Password")
	self.dbc.execute("update pool_worker set password = ? where username = ?", (password,username))	
	self.dbh.commit()

    def check_password(self,username,password):
	log.debug("Checking Username/Password")
	self.dbc.execute("select COUNT(*) from pool_worker where username = ? and password = ?",(username,password))
	data = self.dbc.fetchone()
	if data[0] > 0 :
	    return True
	return False

    def check_tables(self):
	log.debug("Checking Tables")
	if settings.DATABASE_EXTEND == True :
		self.dbc.execute("create table if not exists shares" +\
			"(time DATETIME,rem_host TEXT, username TEXT, our_result INTEGER, upstream_result INTEGER, reason TEXT, solution TEXT, " +\
			"block_num INTEGER, prev_block_hash TEXT, useragent TEXT, difficulty INTEGER)")
		self.dbc.execute("create table if not exists pool_worker(username TEXT, password TEXT, speed INTEGER, last_checkin DATETIME)")
	else :
		self.dbc.execute("create table if not exists shares" + \
			"(time DATETIME,rem_host TEXT, username TEXT, our_result INTEGER, upstream_result INTEGER, reason TEXT, solution TEXT)")
		self.dbc.execute("create table if not exists pool_worker(username TEXT, password TEXT)")
	self.dbc.execute("create index if not exists shares_username ON shares(username)")
	self.dbc.execute("create index if not exists pool_worker_username ON pool_worker(username)")
	
