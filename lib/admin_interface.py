from zope.interface import implements

from twisted.cred.portal import IRealm, Portal
from twisted.web import server, static
from twisted.web.resource import Resource
from twisted.internet import reactor
import twisted.web.error as weberror

import json
import datetime
import hashlib
from pprint import pprint

from stratum import settings

import stratum.logger
log = stratum.logger.get_logger('Admin Interface')

import mining.DBInterface
import sha
dbi = mining.DBInterface.DBInterface()


class JSONDateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)
        
        
        
class RestResource(Resource):
    path_or_id = '';
    
    def __init__(self):
        Resource.__init__(self)
        self.putChild("", self)
        self.putChild('favicon.ico', static.File('statics/bitcoin.ico', defaultType='image/vnd.microsoft.icon') )
        
    def get_path_id(self, request):
        return request.path.replace('/' + "/".join(request.prepath), '').strip('/')
    
    def render(self, request):
        request.setHeader('Content-Type', 'application/json; charset=utf8')
        
        user = request.getUser()
        passwd = request.getPassword()
        
        m = hashlib.sha256()
        m.update(passwd)
        
        if m.hexdigest() != settings.ADMIN_PASSWORD_SHA256:
            request.setResponseCode(401)
            return '"Authorisation required!"'
        
        links = []
        
        for c in self.children:
            if isinstance(self.children[c], RestResource) and c != '':
                links.append('</%s>; rel="%s"' % (c, c))
                
        if len(links) > 0:
            request.setHeader('Link', ", ".join(links))
        
        self.path_or_id = self.get_path_id(request)
        
        if request.method == 'PUT' or request.method == 'DELETE' and self.path_or_id == '':
            request.setResponseCode(405)
            return '"Cannot call PUT or DELETE without an identifier"'
        
        return Resource.render(self, request)
        
        
    def output_item(self, request, item):
        if item is None:
            request.setResponseCode(404)
            request.write('"The resource %s was not found"' % request.path)
            return ''
        
        request.setHeader('Allow', 'GET PUT DELETE')
        
        output = json.dumps(item, cls=JSONDateTimeEncoder)
        request.write(output)
        return ''
    
    
    def output_list(self, request, callback):
        request.setHeader('Allow', 'GET POST')
        
        request.write('[')
        
        isFirst = True
        for item in callback():
            if isFirst == False:
                request.write(',')
            isFirst = False
                
            item = json.dumps(item, cls=JSONDateTimeEncoder)
            request.write(item)
        
        request.write(']')
        
        return ''



class AdminInterface(RestResource):
    isLeaf = False
    
    def __init__(self):
        RestResource.__init__(self)
        self.putChild("users", UsersResource())
    
    
    def render_GET(self, request):
        return ''
    
    
    
class UsersResource(RestResource):
    isLeaf = True
    
    def render_GET(self, request):
        if self.path_or_id == '':
            return self.output_list(request, dbi.list_users)
        else:
            user = dbi.get_user(self.path_or_id)
            return self.output_item(request, user)
        
    def render_DELETE(self, request):
        dbi.delete_user(self.path_or_id)
        return '"OK"'
    
        

if settings.ADMIN_PORT is not None:
    root = AdminInterface()
    factory = server.Site(root)
    reactor.listenTCP(settings.ADMIN_PORT, factory)
    
    
    
    
    