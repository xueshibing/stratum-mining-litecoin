# Installation Instructions
The installation is pretty easy, but there are some depenencies for stratum-mining. Below we refer to the coin daemon as *litecoind*, but more coins will work. Please see the README.md for a list of tested coins.

## Install Requirements

    sudo apt-get install git mysql-server python python-twisted python-mysqldb

## Install the Software

0. Setup and configure the litecoind instance, noting the *rpcuser* and *rpcpass* for use later. 
    **NOTE:** Make sure to use a strong username and password for the coin daemon. Make sure to backup the wallet

1. Clone the newest copy of stratum-mining-litecoin

	git clone https://github.com/moopless/stratum-mining-litecoin.git

2. Update submodules
This should pull new changes for *stratum* and *litecoin_scrypt*

    ./update_submodules

3. Install stratum core. 
   The can be acomplished by using *easy_install* or installing from git. 
    a. Install from with *easy_install*
   
	sudo easy_install stratum

    b. Install from git
    
	git pull https://github.com/slush0/stratum.git
    sudo python stratum/setup.py install

4. Install *Litecoin_scrypt* from git

	git pull  https://github.com/Tydus/litecoin_scrypt.git
    sudo python litecoin_scrypt/setup.py install

5. Configuration of stratum-mining-litecoin
First copy the sample configuration.

	cp conf/config_sample.py conf/config.py

Now edit config/config.py and make the changes for your environment. 
**NOTE:** Future updates to stratum-mining-litecoin may introduce new configuration options, so check the git log on updates.

6. Set up the database
stratum-mining-litecoin requires MySQL. First make sure the database has been created and you have a user with the correct permissions. Next, either install the databse from mmcfe, mmcfe-ng, or stratum-mining-litecoin. See the sql/README for more information about the stratum-mining-litecoin database

    mysql -u user -p database < sql/stratum_default_layout.sql

7. Start stratum-mining-litecoin

	twistd -ny launcher.tac -l log/debug.log

You can now set the URL on your stratum miner:

    stratum+tcp://YOURHOSTNAME:3333

8. Additional Steps
Increase the ulimit:

For the session
    ulimit -n 10240

Persitantly 
    sysctl -w fs.file-max=10240
    
Bitcoind blocknotify Setup
=========================
Although scary (for me), this is actually pretty easy.

Step 1: Set Admin Password
        Ensure that you have set the ADMIN_PASSWORD_SHA256 parameter in conf/config.py
        To make life easy you can run the generateAdminHash script to make the hash
                ./scripts/generateAdminHash.sh <password>

Step 2: Test It
        Restart the pool if it's already running
        run ./scripts/blocknotify.sh --password <password> --host localhost --port 3333
        Ensure everything is ok.

Step 3: Run bitcoind with blocknotify
        Stop bitcoind if it's already running
        bitcoind stop
        Wait till it ends
        bitcoind -blocknotify="/absolute/path/to/scripts/blocknotify.sh --password <password> --host localhost --port 3333"

Step 4: Adjust pool polling
        Now you should be able to watch the pools debug messages for awhile and see the blocknotify come in
        once you are sure it's working edit conf/config.py and set
                PREVHASH_REFRESH_INTERVAL = to the same value as MERKLE_REFRESH_INTERVAL
        restart the pool
