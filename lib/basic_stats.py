from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web import static,server

import time
from datetime import timedelta
import json
from stratum import settings

import stratum.logger
log = stratum.logger.get_logger('Basic Stats')

import mining.DBInterface
dbi = mining.DBInterface.DBInterface()

import locale
locale.setlocale(locale.LC_ALL, '')

class Site(server.Site):
    def log(self, request):
        pass

class StatsPage(Resource):
    isLeaf = False
    cache_html = ""
    cache_json = ""
    last_update = 0

    def getChild(self, name, request):
        if name == '' or name == 'stats':
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        # Cache the results for 30 seconds, takes care of high volume/ddos
        if time.time() - self.last_update < 30 :
            if(request.path == "/stats"):
                return self.cache_json
            return self.cache_html

        # Get info
        pool_stats = dbi.get_pool_stats()
        workers_stats = dbi.get_workers_stats()
        
        # Send in JSON?
        self.cache_json = json.dumps({"pool":pool_stats,"workers":workers_stats})

        #Otherwise build webpage
        r= "<html><head>"
        r+= "<meta http-equiv=\"refresh\" content=\"60\">"
        r+= "<link rel=\"stylesheet\" type=\"text/css\" href=\"basic_stats.css\">"
        r+="</head><BODY>"
        r+="<H1>Stratum Mining Server</H1>"
        r+="<table width=100% vspace=0 hspace=0 cellpadding=1 cellspacing=0>"
        
        pool_speed = pool_stats['pool_speed']
        pool_color="#A00"
        
        pool_speed = 0 if pool_speed is None else int(pool_speed)
        
        if pool_speed > 100 and float(pool_stats['round_progress']) < 200:
            pool_color="#AA0"
        if pool_speed > 100 and float(pool_stats['round_progress']) < 150:
            pool_color="#0A0"
        r+="<tr bgcolor=\""+pool_color+"\"><td><b>Pool Stats:</b>"
        r+="</td><td>Speed: " + str(pool_speed) + "Mhs"
        r+="</td><td>Round Shares: " + format(int(pool_stats['round_shares']),"n") + " (%.2f" % float(pool_stats['round_progress']) + "%)"
        r+="</td><td>Round Duration: " + str(timedelta(0,(time.time() - float(pool_stats['round_start'])))).split(".")[0]
        r+="</td><td>Best Share: " + format(int(pool_stats['round_best_share']),"n")
        r+="</td><td>Total Found: " + format(int(pool_stats['pool_total_found']),"n")
        r+="</td></tr>"

        last_update = time.time() - float(pool_stats['bitcoin_infotime'])
        bitcoin_color="#A00"
        if int(pool_stats['bitcoin_connections']) > 0 and last_update < 660:
            bitcoin_color="yellow"
        if int(pool_stats['bitcoin_connections']) > 10 and last_update < 330:
            bitcoin_color="#0A0"
        r+="<tr bgcolor=\""+bitcoin_color+"\"><td><b>Bitcoin Stats:</b>"
        r+="</td><td>Connections :"+pool_stats['bitcoin_connections']
        r+="</td><td>Difficulty :"+format(int(float(pool_stats['bitcoin_difficulty'])),"n")
        r+="</td><td>Height :"+format(int(pool_stats['bitcoin_blocks']),"n")
        r+="</td><td>Balance :"+pool_stats['bitcoin_balance']
        r+="</td><td>"
        r+="</td></tr></table>"

        r+="<br>"
        
        r+="<table width=100% vspace=0 hspace=0 cellpadding=1 cellspacing=0>"
        size = len(workers_stats)
        if size <= 10:
            r+="<tr><td width=33%>"
            r+="<table width=100% vspace=0 hspace=0 cellpadding=1 cellspacing=0>"
            r+="<tr><td>Worker</td><td>Speed/Diff</td><td>Shares/Rej</td><td>Found</td></tr>"
            for (w, wi) in enumerate(workers_stats):
                wd = workers_stats[wi]
                wc = "#A00"
                if wd["speed"] > 0:
                    wc = "yellow"
                if wd["speed"] > 100:
                    wc = "#0A0"
                r+="<tr bgcolor=\"%s\"><td>%s</td><td>%s/%s</td><td>%s/%s</td><td>%s</td><tr>"%(
                        wc,wi,format(wd["speed"],"n"),wd["difficulty"],format(int(wd["total_shares"]),"n"),
                        format(int(wd["total_rejects"]),"n"),format(int(wd["total_found"]),"n"))
            r+="</table></td><td></td></tr>"
        else :
            colcnt = int(size/3) + 1
            colt = colcnt
            r+="<tr><td width=33% valign=top>"
            r+="<table width=100% vspace=0 hspace=0 cellpadding=1 cellspacing=0>"
            r+="<tr><td>Worker</td><td>Speed</td><td>Shares/Rej</td><td>Found</td></tr>"
            for (w, wi) in enumerate(workers_stats):
                wd = workers_stats[wi]
                wc = "#A00"
                if wd["speed"] > 0:
                    wc = "yellow"
                if wd["speed"] > 100:
                    wc = "#0A0"
                r+="<tr bgcolor=\"%s\"><td>%s</td><td>%s/%s</td><td>%s/%s</td><td>%s</td><tr>"%(
                        wc,wi,format(int(wd["speed"]),"n"),wd["difficulty"],format(int(wd["total_shares"]),"n"),
                        format(int(wd["total_rejects"]),"n"),format(int(wd["total_found"]),"n"))
                colt = colt - 1
                if colt <= 0:
                    r+="</table></td><td width=33% valign=top>"
                    r+="<table width=100% vspace=0 hspace=0 cellpadding=1 cellspacing=0>"
                    r+="<tr><td>Worker</td><td>Speed</td><td>Shares/Rej</td><td>Found</td></tr>"
                    colt = colcnt
            r+="</table></td></tr>"
        r+="</table></body></html>"
        self.cache_html = str(r)
        self.last_update = time.time()

        # Send Results
        if(request.path == "/stats"):
            return self.cache_json
        return self.cache_html


def BasicStats(start_event):
    start_event.addCallback(BasicStats_start)

def BasicStats_start(cb):
    root = StatsPage()
    root.putChild('favicon.ico', static.File('statics/favicon.ico', defaultType='image/vnd.microsoft.icon') )
    root.putChild('basic_stats.css', static.File('statics/basic_stats.css') )
    factory = Site(root)
    reactor.listenTCP(settings.BASIC_STATS_PORT, factory)

