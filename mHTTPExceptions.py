# Passdown from mHTTPConnections (and mHTTPProtocol by extension)
from mHTTPConnections.mHTTPExceptions import *;

class cHTTPProxyConnectFailedException(cHTTPException):
  pass; # The proxy server did not respond to our CONNECT request with a 200 OK.

