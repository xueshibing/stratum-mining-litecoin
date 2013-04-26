import time
import hashlib
from stratum import settings
import stratum.logger
log = stratum.logger.get_logger('DB_Mysql')

import MySQLdb
                
class DB_Mysql():
    def __init__(self):
        log.debug("Connecting to DB")
        
        self.dbh = MySQLdb.connect(settings.DB_MYSQL_HOST, 
            settings.DB_MYSQL_USER, settings.DB_MYSQL_PASS, 
            settings.DB_MYSQL_DBNAME)
        self.dbc = self.dbh.cursor()
        
        if hasattr(settings, 'PASSWORD_SALT'):
            self.salt = settings.PASSWORD_SALT
        else:
            raise ValueError("PASSWORD_SALT isn't set, please set in config.py")
        
    def hash_pass(self, password):
        m = hashlib.sha1()
        m.update(password)
        m.update(self.salt)
        
        return m.hexdigest()

    def updateStats(self, averageOverTime):
        log.debug("Updating Stats")
        # Note: we are using transactions... so we can set the speed = 0 and it doesn't take affect until we are commited.
        self.dbc.execute(
            """
            UPDATE `pool_worker`
            SET `speed` = 0, 
              `alive` = 0
            """
        );
        
        stime = '%.0f' % (time.time() - averageOverTime);
        
        self.dbc.execute(
            """
            UPDATE `pool_worker` pw
            LEFT JOIN (
                SELECT `worker`, ROUND(ROUND(SUM(`difficulty`)) * 4294967296) / %(average)s AS 'speed'
                FROM `shares`
                WHERE `time` > FROM_UNIXTIME(%(time)s)
                GROUP BY `worker`
            ) AS leJoin
            ON leJoin.`worker` = pw.`id`
            SET pw.`alive` = 1, 
              pw.`speed` = leJoin.`speed`
            WHERE pw.`id` = leJoin.`worker`
            """,
            {
                "time": stime,
                "average": int(averageOverTime) * 1000000
            }
        )
            
        self.dbc.execute(
            """
            UPDATE `pool`
            SET `value` = (
                SELECT IFNULL(SUM(`speed`), 0)
                FROM `pool_worker`
                WHERE `alive` = 1
            )
            WHERE `parameter` = 'pool_speed'
            """
        )
        
        self.dbh.commit()
    
    def archive_check(self):
        # Check for found shares to archive
        self.dbc.execute(
            """
            SELECT `time`
            FROM `shares` 
            WHERE `upstream_result` = 1
            ORDER BY `time` 
            LIMIT 1
            """
        )
        
        data = self.dbc.fetchone()
        
        if data is None or (data[0] + settings.ARCHIVE_DELAY) > time.time() :
            return False
        
        return data[0]

    def archive_found(self, found_time):
        self.dbc.execute(
            """
            INSERT INTO `shares_archive_found`
            SELECT s.`id`, s.`time`, s.`rem_host`, pw.`id`, s.`our_result`, 
              s.`upstream_result`, s.`reason`, s.`solution`, s.`block_num`, 
              s.`prev_block_hash`, s.`useragent`, s.`difficulty`
            FROM `shares` s 
            LEFT JOIN `pool_worker` pw
              ON s.`worker` = pw.`id`
            WHERE `upstream_result` = 1
              AND `time` <= FROM_UNIXTIME(%(time)s)
            """,
            {
                "time": found_time
            }
        )
        
        self.dbh.commit()

    def archive_to_db(self, found_time):
        self.dbc.execute(
            """
            INSERT INTO `shares_archive`
            SELECT s.`id`, s.`time`, s.`rem_host`, pw.`id`, s.`our_result`, 
              s.`upstream_result`, s.`reason`, s.`solution`, s.`block_num`, 
              s.`prev_block_hash`, s.`useragent`, s.`difficulty`
            FROM `shares` s 
            LEFT JOIN `pool_worker` pw
              ON s.`worker` = pw.`id`
            WHERE `time` <= FROM_UNIXTIME(%(time)s)
            """,
            {
                "time": found_time
            }
        )
        
        self.dbh.commit()

    def archive_cleanup(self, found_time):
        self.dbc.execute(
            """
            DELETE FROM `shares` 
            WHERE `time` <= FROM_UNIXTIME(%(time)s)
            """,
            {
                "time": found_time
            }
        )
        
        self.dbh.commit()

    def archive_get_shares(self, found_time):
        self.dbc.execute(
            """
            SELECT *
            FROM `shares` 
            WHERE `time` <= FROM_UNIXTIME(%(time)s)
            """,
            {
                "time": found_time
            }
        )
        
        return self.dbc

    def import_shares(self, data):
        log.debug("Importing Shares")
#               0           1            2          3          4         5        6  7            8         9              10
#        data: [worker_name,block_header,block_hash,difficulty,timestamp,is_valid,ip,block_height,prev_hash,invalid_reason,best_diff]
        checkin_times = {}
        total_shares = 0
        best_diff = 0
        
        for k, v in enumerate(data):
            if settings.DATABASE_EXTEND :
                total_shares += v[3]
                
                if v[0] in checkin_times:
                    if v[4] > checkin_times[v[0]] :
                        checkin_times[v[0]]["time"] = v[4]
                else:
                    checkin_times[v[0]] = {
                        "time": v[4], 
                        "shares": 0, 
                        "rejects": 0
                    }

                if v[5] == True :
                    checkin_times[v[0]]["shares"] += v[3]
                else :
                    checkin_times[v[0]]["rejects"] += v[3]

                if v[10] > best_diff:
                    best_diff = v[10]

                self.dbc.execute(
                    """
                    INSERT INTO `shares` 
                    (time, rem_host, worker, our_result, upstream_result, 
                      reason, solution, block_num, prev_block_hash, 
                      useragent, difficulty) 
                    VALUES
                    (FROM_UNIXTIME(%(time)s), %(host)s, 
                      (SELECT `id` FROM `pool_worker` WHERE `username` = %(uname)s), 
                      %(lres)s, 0, %(reason)s, '', 
                      %(blocknum)s, %(hash)s, '', %(difficulty)s)
                    """,
                    {
                        "time": v[4],
                        "host": v[6],
                        "uname": v[0],
                        "lres": v[5],
                        "reason": v[9],
                        "blocknum": v[7],
                        "hash": v[8],
                        "difficulty": v[3]
                    }
                )
            else:
                self.dbc.execute(
                    """
                    INSERT INTO `shares`
                    (time, rem_host, worker, our_result, 
                      upstream_result, reason, solution)
                    VALUES 
                    (FROM_UNIXTIME(%(time)s), %(host)s, 
                      (SELECT `id` FROM `pool_worker` WHERE `username` = %(uname)s), 
                      %(lres)s, 0, %(reason)s, '')
                    """,
                    {
                        "time": v[4], 
                        "host": v[6], 
                        "uname": v[0], 
                        "lres": v[5], 
                        "reason": v[9]
                    }
                )

        if settings.DATABASE_EXTEND:
            self.dbc.execute(
                """
                SELECT `parameter`, `value` 
                FROM `pool` 
                WHERE `parameter` = 'round_best_share'
                  OR `parameter` = 'round_shares'
                  OR `parameter` = 'bitcoin_difficulty'
                  OR `parameter` = 'round_progress'
                """
            )
            
            current_parameters = {}
            
            for data in self.dbc.fetchall():
                current_parameters[data[0]] = data[1]
            
            round_best_share = int(current_parameters['round_best_share'])
            difficulty = float(current_parameters['bitcoin_difficulty'])
            round_shares = int(current_parameters['round_shares']) + total_shares
                
            updates = [
                {
                    "param": "round_shares",
                    "value": round_shares
                },
                {
                    "param": "round_progress",
                    "value": 0 if difficulty == 0 else (round_shares / difficulty) * 100
                }
            ]
            
            if best_diff > round_best_share:
                updates.append({
                    "param": "round_best_share",
                    "value": best_diff
                })
            
            self.dbc.executemany(
                """
                UPDATE `pool` 
                SET `value` = %(value)s
                WHERE `parameter` = %(param)s
                """,
                updates
            )
        
            for k, v in checkin_times.items():
                self.dbc.execute(
                    """
                    UPDATE `pool_worker`
                    SET `last_checkin` = FROM_UNIXTIME(%(time)s), 
                      `total_shares` = `total_shares` + %(shares)s,
                      `total_rejects` = `total_rejects` + %(rejects)s
                    WHERE `username` = %(uname)s
                    """,
                    {
                        "time": v["time"],
                        "shares": v["shares"],
                        "rejects": v["rejects"], 
                        "uname": k
                    }
                )
            
        self.dbh.commit()


    def found_block(self, data):
        # Note: difficulty = -1 here
        self.dbc.execute(
            """
            UPDATE `shares`
            SET `upstream_result` = %(result)s,
              `solution` = %(solution)s
            WHERE `time` = FROM_UNIXTIME(%(time)s)
              AND `username` = (
                  SELECT `id` 
                  FROM `pool_worker` 
                  WHERE `username` = %(uname)s
              )
            LIMIT 1
            """,
            {
                "result": data[5], 
                "solution": data[2], 
                "time": data[4], 
                "uname": data[0]
            }
        )
        
        if settings.DATABASE_EXTEND and data[5] == True:
            self.dbc.execute(
                """
                UPDATE `pool_worker`
                SET `total_found` = `total_found` + 1
                WHERE `username` = %(uname)s
                """,
                {
                    "uname": data[0]
                }
            )
            self.dbc.execute(
                """
                SELECT `value`
                FROM `pool`
                WHERE `parameter` = 'pool_total_found'
                """
            )
            total_found = int(self.dbc.fetchone()[0]) + 1
            
            self.dbc.executemany(
                """
                UPDATE `pool`
                SET `value` = %(value)s
                WHERE `parameter` = %(param)s
                """,
                [
                    {
                        "param": "round_shares",
                        "value": "0"
                    },
                    {
                        "param": "round_progress",
                        "value": "0"
                    },
                    {
                        "param": "round_best_share",
                        "value": "0"
                    },
                    {
                        "param": "round_start",
                        "value": time.time()
                    },
                    {
                        "param": "pool_total_found",
                        "value": total_found
                    }
                ]
            )
            
        self.dbh.commit()
        
    def list_users(self):
        cursor = self.dbh.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            """
            SELECT *
            FROM `pool_worker`
            WHERE `id`> 0
            """
        )
        
        while True:
            results = cursor.fetchmany()
            if not results:
                break
            
            for result in results:
                yield result
                
        cursor.close()
                
    def get_user(self, id_or_username):
        log.debug("Finding user with id or username of %s", id_or_username)
        cursor = self.dbh.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute(
            """
            SELECT *
            FROM `pool_worker`
            WHERE `id` = %(id)s
              OR `username` = %(uname)s
            """,
            {
                "id": id_or_username if id_or_username.isdigit() else -1,
                "uname": id_or_username
            }
        )
        
        user = cursor.fetchone()
        cursor.close()
        return user
        

    def delete_user(self, id_or_username):
        if id_or_username.isdigit() and id_or_username == '0':
            raise Exception('You cannot delete that user')
        
        log.debug("Deleting user with id or username of %s", id_or_username)
        
        self.dbc.execute(
            """
            UPDATE `shares`
            SET `worker` = 0
            WHERE `worker` = (
                SELECT `id` 
                FROM `pool_worker` 
                WHERE `id` = %(id)s 
                  OR `username` = %(uname)s
                LIMIT 1
            )
            """,
            {
                "id": id_or_username if id_or_username.isdigit() else -1,
                "uname": id_or_username
            }
        )
        
        self.dbc.execute(
            """
            DELETE FROM `pool_worker`
            WHERE `id` = %(id)s
              OR `username` = %(uname)s
            """, 
            {
                "id": id_or_username if id_or_username.isdigit() else -1,
                "uname": id_or_username
            }
        )
        
        self.dbh.commit()

    def insert_user(self, username, password):
        log.debug("Adding new user %s", username)
        
        self.dbc.execute(
            """
            INSERT INTO `pool_worker`
            (`username`, `password`)
            VALUES
            (%(uname)s, %(pass)s)
            """,
            {
                "uname": username, 
                "pass": self.hash_pass(password)
            }
        )
        
        self.dbh.commit()
        
        return str(username)

    def update_user(self, id_or_username, password):
        log.debug("Updating password for user %s", id_or_username);
        
        self.dbc.execute(
            """
            UPDATE `pool_worker`
            SET `password` = %(pass)s
            WHERE `id` = %(id)s
              OR `username` = %(uname)s
            """,
            {
                "id": id_or_username if id_or_username.isdigit() else -1,
                "uname": id_or_username,
                "pass": self.hash_pass(password)
            }
        )
        
        self.dbh.commit()

    def update_worker_diff(self, username, diff):
        log.debug("Setting difficulty for %s to %s", username, diff)
        
        self.dbc.execute(
            """
            UPDATE `pool_worker`
            SET `difficulty` = %(diff)s
            WHERE `username` = %(uname)s
            """,
            {
                "uname": username, 
                "diff": diff
            }
        )
        
        self.dbh.commit()
    
    def clear_worker_diff(self):
        if settings.DATABASE_EXTEND == True:
            log.debug("Resetting difficulty for all workers")
            
            self.dbc.execute(
                """
                UPDATE `pool_worker`
                SET `difficulty` = 0
                """
            )
            
            self.dbh.commit()

    def check_password(self, username, password):
        log.debug("Checking username/password for %s", username)
        
        self.dbc.execute(
            """
            SELECT COUNT(*) 
            FROM `pool_worker`
            WHERE `username` = %(uname)s
              AND `password` = %(pass)s
            """,
            {
                "uname": username, 
                "pass": self.hash_pass(password)
            }
        )
        
        data = self.dbc.fetchone()
        
        if data[0] > 0:
            return True
        
        return False

    def update_pool_info(self, pi):
        self.dbc.executemany(
            """
            UPDATE `pool`
            SET `value` = %(value)s
            WHERE `parameter` = %(param)s
            """,
            [
                {
                    "param": "bitcoin_blocks",
                    "value": pi['blocks']
                },
                {
                    "param": "bitcoin_balance",
                    "value": pi['balance']
                },
                {
                    "param": "bitcoin_connections",
                    "value": pi['connections']
                },
                {
                    "param": "bitcoin_difficulty",
                    "value": pi['difficulty']
                },
                {
                    "param": "bitcoin_infotime",
                    "value": time.time()
                }
            ]
        )
        
        self.dbh.commit()

    def get_pool_stats(self):
        self.dbc.execute(
            """
            SELECT * FROM `pool`
            """
        )
        
        ret = {}
        
        for data in self.dbc.fetchall():
            ret[data[0]] = data[1]
            
        return ret

    def get_workers_stats(self):
        self.dbc.execute(
            """
            SELECT `username`, `speed`, `last_checkin`, `total_shares`,
              `total_rejects`, `total_found`, `alive`, `difficulty`
            FROM `pool_worker`
            WHERE `id` > 0
            """
        )
        
        ret = {}
        
        for data in self.dbc.fetchall():
            ret[data[0]] = {
                "username" : data[0],
                "speed" : int(data[1]),
                "last_checkin" : time.mktime(data[2].timetuple()),
                "total_shares" : int(data[3]),
                "total_rejects" : int(data[4]),
                "total_found" : int(data[5]),
                "alive" : True if data[6] is 1 else False,
                "difficulty" : int(data[7])
            }
            
        return ret

    def close(self):
        self.dbh.close()

    def check_tables(self):
        log.debug("Checking Tables")

        # Do we have our tables?
        shares_exist = False
        
        self.dbc.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE `table_schema` = %(schema)s
              AND `table_name` = 'shares'
            """,
            {
                "schema": settings.DB_MYSQL_DBNAME
            }
        )
        
        data = self.dbc.fetchone()
        
        if data[0] <= 0 :
            self.update_version_1()        # no, we don't, so create them
            
        if settings.DATABASE_EXTEND == True :
            self.update_tables()
        
    def update_tables(self):
        version = 0
        current_version = 7
        
        while version < current_version:
            self.dbc.execute(
                """
                SELECT `value`
                FROM `pool`
                WHERE parameter = 'DB Version'
                """
            )
            
            data = self.dbc.fetchone()
            version = int(data[0])
            
            if version < current_version:
                log.info("Updating Database from %i to %i" % (version, version +1))
                getattr(self, 'update_version_' + str(version) )()

    def update_version_1(self):
        if settings.DATABASE_EXTEND == True:
            self.dbc.execute(
                """
                CREATE TABLE IF NOT EXISTS `shares`
                (
                    `id` SERIAL PRIMARY KEY,
                    `time` TIMESTAMP,
                    `rem_host` TEXT,
                    `username` TEXT,
                    `our_result` BOOLEAN,
                    `upstream_result` BOOLEAN,
                    `reason` TEXT,
                    `solution` TEXT,
                    `block_num` INTEGER,
                    `prev_block_hash` TEXT,
                    `useragent` TEXT,
                    `difficulty` INTEGER
                )
                ENGINE=MYISAM
                """
            )
            
            self.dbc.execute(
                """
                CREATE INDEX `shares_username` ON `shares`(`username`(10))
                """
            )
            
            self.dbc.execute(
                """
                CREATE TABLE IF NOT EXISTS `pool_worker`
                (
                    `id` SERIAL PRIMARY KEY,
                    `username` TEXT,
                    `password` TEXT,
                    `speed` INTEGER,
                    `last_checkin` TIMESTAMP
                )
                ENGINE=MYISAM
                """
            )
            
            self.dbc.execute(
                """
                CREATE INDEX `pool_worker_username` ON `pool_worker`(`username`(10))
                """
            )
            
            self.dbc.execute(
                """
                CREATE TABLE IF NOT EXISTS `pool`
                (
                    `parameter` TEXT,
                    `value` TEXT
                )
                """
            )
            
            self.dbc.execute(
                """
                ALTER TABLE `pool_worker` ADD `total_shares` INTEGER DEFAULT 0
                """
            )
            
            self.dbc.execute(
                """
                ALTER TABLE `pool_worker` ADD `total_rejects` INTEGER DEFAULT 0
                """
            )
            
            self.dbc.execute(
                """
                ALTER TABLE `pool_worker` ADD `total_found` INTEGER DEFAULT 0
                """
            )
            
            self.dbc.execute(
                """
                INSERT INTO `pool`
                (parameter, value)
                VALUES
                ('DB Version', 2)
                """
            )
        else:
            self.dbc.execute(
                """
                CREATE TABLE IF NOT EXISTS `shares`
                (
                    `id` SERIAL,
                    `time` TIMESTAMP,
                    `rem_host` TEXT,
                    `username` TEXT,
                    `our_result` INTEGER,
                    `upstream_result` INTEGER,
                    `reason` TEXT,
                    `solution` TEXT
                )
                ENGINE=MYISAM
                """
            )
            
            self.dbc.execute(
                """
                CREATE INDEX `shares_username` ON `shares`(`username`(10))
                """
            )
            
            self.dbc.execute(
                """
                CREATE TABLE IF NOT EXISTS `pool_worker`
                (
                    `id` SERIAL,
                    `username` TEXT, 
                    `password` TEXT
                )
                ENGINE=MYISAM
                """
            )
            
            self.dbc.execute(
                """
                CREATE INDEX `pool_worker_username` ON `pool_worker`(`username`(10))
                """
            )
            
        self.dbh.commit()
                    

    def update_version_2(self):
        log.info("running update 2")
        
        self.dbc.executemany(
            """
            INSERT INTO `pool` (`parameter`, `value`) VALUES (%s, %s)
            """,
            [
                ('bitcoin_blocks', 0),
                ('bitcoin_balance', 0),
                ('bitcoin_connections', 0),
                ('bitcoin_difficulty', 0),
                ('pool_speed', 0),
                ('pool_total_found', 0),
                ('round_shares', 0),
                ('round_progress', 0),
                ('round_start', time.time())
            ]
        )
        
        self.dbc.execute(
            """
            UPDATE `pool`
            SET `value` = 3
            WHERE `parameter` = 'DB Version'
            """
        )
        
        self.dbh.commit()
        
    def update_version_3(self):
        log.info("running update 3")
        
        self.dbc.executemany(
            """
            INSERT INTO `pool` (`parameter`, `value`) VALUES (%s, %s)
            """,
            [
                ('round_best_share', 0),
                ('bitcoin_infotime', 0)
            ]
        )
        
        self.dbc.execute(
             """
             ALTER TABLE `pool_worker` ADD `alive` BOOLEAN
             """
        )
        
        self.dbc.execute(
            """
            UPDATE `pool`
            SET `value` = 4
            WHERE `parameter` = 'DB Version'
            """
        )
        
        self.dbh.commit()
        
    def update_version_4(self):
        log.info("running update 4")
        
        self.dbc.execute(
            """
            ALTER TABLE `pool_worker`
            ADD `difficulty` INTEGER DEFAULT 0
            """
        )
        
        self.dbc.execute(
            """
            CREATE TABLE IF NOT EXISTS `shares_archive`
            (
                `id` SERIAL PRIMARY KEY,
                `time` TIMESTAMP,
                `rem_host` TEXT,
                `username` TEXT,
                `our_result` BOOLEAN,
                `upstream_result` BOOLEAN,
                `reason` TEXT,
                `solution` TEXT,
                `block_num` INTEGER,
                `prev_block_hash` TEXT,
                `useragent` TEXT,
                `difficulty` INTEGER
            )
            ENGINE = MYISAM
            """
        )
        
        self.dbc.execute(
            """
            CREATE TABLE IF NOT EXISTS `shares_archive_found`
            (
                `id` SERIAL PRIMARY KEY,
                `time` TIMESTAMP,
                `rem_host` TEXT,
                `username` TEXT,
                `our_result` BOOLEAN,
                `upstream_result` BOOLEAN,
                `reason` TEXT,
                `solution` TEXT,
                `block_num` INTEGER,
                `prev_block_hash` TEXT,
                `useragent` TEXT,
                `difficulty` INTEGER
            )
            ENGINE = MYISAM
            """
        )
        
        self.dbc.execute(
            """
            UPDATE `pool`
            SET `value` = 5
            WHERE `parameter` = 'DB Version'
            """
        )
        
        self.dbh.commit()

    def update_version_5(self):
        log.info("running update 5")
        
        self.dbc.execute(
            """
            ALTER TABLE `pool`
            ADD PRIMARY KEY (`parameter`(100))
            """
        )
        
        # Adjusting indicies on table: shares
        self.dbc.execute(
            """
            DROP INDEX `shares_username` ON `shares`
            """
        )
        
        self.dbc.execute(
            """
            CREATE INDEX `shares_time_username` ON `shares`(`time`, `username`(10))
            """
        )
        
        self.dbc.execute(
            """
            CREATE INDEX `shares_upstreamresult` ON `shares`(`upstream_result`)
            """
        )
        
        self.dbc.execute(
            """
            UPDATE `pool`
            SET `value` = 6
            WHERE `parameter` = 'DB Version'
            """
        )
        
        self.dbh.commit()
        
    def update_version_6(self):
        log.info("running update 6")
        
        self.dbc.execute(
            """
            ALTER TABLE `pool`
            CHARACTER SET = utf8,
            COLLATE = utf8_general_ci,
            ENGINE = InnoDB,
            CHANGE COLUMN `parameter` `parameter` VARCHAR(128) CHARACTER SET 'utf8' COLLATE 'utf8_general_ci' NOT NULL,
            CHANGE COLUMN `value` `value` VARCHAR(512) CHARACTER SET 'utf8' COLLATE 'utf8_general_ci' NULL,
            DROP PRIMARY KEY, ADD PRIMARY KEY (`parameter`)
            """
        )
        
        self.dbc.execute(
            """
            UPDATE `pool_worker`
            SET `password` = SHA1(CONCAT(password, %(salt)s))
            WHERE id > 0
            """,
            {
                "salt": self.salt
            }
        )
        
        self.dbc.execute(
            """
            ALTER TABLE `pool_worker`
            CHARACTER SET = utf8,
            COLLATE = utf8_general_ci,
            ENGINE = InnoDB,
            CHANGE COLUMN `username` `username` VARCHAR(512) CHARACTER SET 'utf8' COLLATE 'utf8_general_ci' NOT NULL,
            CHANGE COLUMN `password` `password` CHAR(40) CHARACTER SET 'utf8' COLLATE 'utf8_bin' NOT NULL,
            CHANGE COLUMN `speed` `speed` INT(10) UNSIGNED NOT NULL DEFAULT '0',
            CHANGE COLUMN `total_shares` `total_shares` INT(10) UNSIGNED NOT NULL DEFAULT '0',
            CHANGE COLUMN `total_rejects` `total_rejects` INT(10) UNSIGNED NOT NULL DEFAULT '0',
            CHANGE COLUMN `total_found` `total_found` INT(10) UNSIGNED NOT NULL DEFAULT '0',
            CHANGE COLUMN `alive` `alive` TINYINT(1) UNSIGNED NOT NULL DEFAULT '0',
            CHANGE COLUMN `difficulty` `difficulty` INT(10) UNSIGNED NOT NULL DEFAULT '0',
            ADD UNIQUE INDEX `pool_worker-username` (`username`(128) ASC),
            ADD INDEX `pool_worker-alive` (`alive`),
            DROP INDEX `pool_worker_username`,
            DROP INDEX `id`
            """
        )
        
        self.dbc.execute(
            """
            ALTER TABLE `shares`
            ADD COLUMN `worker` BIGINT(20) UNSIGNED NOT NULL DEFAULT 0 AFTER `username`,
            DROP INDEX `id`,
            ENGINE = InnoDB;
            """
        )
        
        self.dbc.execute(
            """
            UPDATE `shares`
            JOIN `pool_worker`
              ON `pool_worker`.`username` = `shares`.`username`
            SET `worker` = `pool_worker`.`id`
            """
        )
        
        self.dbc.execute(
            """
            SET SESSION sql_mode='NO_AUTO_VALUE_ON_ZERO';
            """
        )
        
        self.dbc.execute(
            """
            INSERT INTO `pool_worker`
            (`id`, `username`, `password`)
            VALUES
            (0, SHA1(RAND(CURRENT_TIMESTAMP)), SHA1(CURRENT_TIMESTAMP))
            """
        )
        
        self.dbc.execute(
            """
            SET SESSION sql_mode='';
            """
        )
        
        self.dbc.execute(
            """
            ALTER TABLE `shares` 
              ADD CONSTRAINT `workerid`
              FOREIGN KEY (`worker` )
              REFERENCES `pool_worker` (`id`)
              ON DELETE NO ACTION
              ON UPDATE NO ACTION,
            DROP INDEX `shares_time_username`,
            ADD INDEX `shares_time_worker` (`time` ASC, `worker` ASC),
            ADD INDEX `shares_worker` (`worker` ASC),
            DROP COLUMN `username`
            """
        )
        
        self.dbc.execute(
            """
            UPDATE `pool` 
            SET `value` = 7
            WHERE `parameter` = 'DB Version'
            """
        )
        
        self.dbh.commit()

