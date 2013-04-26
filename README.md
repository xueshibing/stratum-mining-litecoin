stratum-mining
==============

Basic implementation of bitcoin mining pool using Stratum mining protocol.

This fork includes database optimisations for MySQL and password hashing using a salt.

JSON API
--------

There is also a JSON API, currently just for users (db: pool_workers). Enabled if you set 
ADMIN_PORT to a valid port rather than None. Once enabled, you can perform 
the following on http://localhost:ADMIN_PORT/, provided you have a password set (see after commands).

GET /users - list all users
POST /users - create a user (JSON body: {"username": "username", "password": "password"}). Password will be encrypted using the salt.
                
GET /users/{id_or_username} - Get a JSON object of a specific user
DELETE /users/{id_or_username} - Remove a pool_worker. If using MySQL, any shares associated with that user will be associated with the global system account (ID: 0)
PUT /users/{id_or_username} - Update password for user, send as {"password": "password"}, as with POST /users, the password will be encrypted for you.

### Authentication

Access to the JSON API requires basic auth. The username does not matter; the password is the same as the ADMIN_PASSWORD_SHA256 password which 
can generated using scripts/generateAdminHash.sh .

I would strongly suggested locking down the port as well using iptables or similar.

The Rest
--------

Basic worker stats are provided (and updated)

See the INSTALL file for install instructions.

For more info on Stratum:
http://mining.bitcoin.cz/stratum-mining.

Original version by Slush
Modified version by GeneralFault

This version by Wade Womersley (Media Skunk Works) ( Tips Welcome: 1FxBTbWR15WZp8vnru8N6zVsVBwigPAcdN )
