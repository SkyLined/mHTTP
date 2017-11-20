import socket, threading;
from cConnectionsToServer import cConnectionsToServer;
from cHTTPRequest import cHTTPRequest;

class cHTTPClient(object):
  def __init__(oSelf):
    oSelf.__oMainLock = threading.Lock(); # Used to control access to .__doConnectionsToServer_by_sProtocolIPPort
    oSelf.__doConnectionsToServer_by_sProtocolIPPort = {};
    oSelf.bDebugOutput = False;

  def foGetResponseForURL(oSelf, sURL):
    asProtocolHostPortRelativeURL = sURL.split("/", 3);
    sProtocol = asProtocolHostPortRelativeURL[0];
    assert len(asProtocolHostPortRelativeURL) > 2 and sProtocol in ["http:", "https:"], \
        "Bad URL: %s" % sURL;
    bSecure = sProtocol == "https:";
    sHostPort = asProtocolHostPortRelativeURL[2];
    sRelativeURL = len(asProtocolHostPortRelativeURL) == 4 and asProtocolHostPortRelativeURL[3] or "/";
    oHTTPRequest = cHTTPRequest(
      sMethod = "GET",
      sURL = sRelativeURL,
      sHTTPVersion = "HTTP/1.1",
      dHeader_sValue_by_sName = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Content-Length": 0,
        "Host": sHostPort,
      },
      sBody = "",
    );
    return oSelf.foGetResponseForRequest(oHTTPRequest, bSecure = bSecure);
  
  def foGetResponseForRequest(oSelf, oHTTPRequest, sIP = None, uPort = None, bSecure = False):
    # NOTE: There are no checks performed on the server's certificate; it could be self-signed and/or completely
    # invalid.
    if sIP is None or uPort is None:
      if type(oHTTPRequest) in (str, unicode):
        # We cannot find out what server to connect to from a string request, but we can use the default port number
        # if it's not specified:
        assert sIP, \
          "You must specify an IP address to send the request to.";
        uPort = bSecure and 443 or 80;
      else:
        # We can parse the "Host" request header to find out what server to connect to and what port to use. If the
        # port is not specified, we will use the default port number.
        sHostNameAndOptionalPort = oHTTPRequest.fsGetHeaderValue("Host");
        assert sHostNameAndOptionalPort, \
            "The request is missing a \"host\" header.";
        if ":" in sHostNameAndOptionalPort:
          sHostName, sPort = sHostNameAndOptionalPort.split(":", 1);
          if uPort is None:
            try:
              uPort = long(sPort);
              assert uPort < 65536, "x";
            except:
              raise AssertionError("Invalid port number %s" % sPort);
        else:
          sHostName = sHostNameAndOptionalPort;
          if uPort is None:
            uPort = bSecure and 443 or 80;
        if sIP is None:
          sIP = socket.gethostbyname(sHostName);
          assert sIP, \
              "Unknown hostname %s" % sHostName;
    # We will reuse connections to the same server (identified by IP address, port and whether or not the connection
    # is secure).
    sProtocolIPPort = "http%s://%s:%d" % (bSecure and "s" or "", sIP, uPort);
    oSelf.__oMainLock.acquire();
    try:
      oConnectionsToServer = oSelf.__doConnectionsToServer_by_sProtocolIPPort.get(sProtocolIPPort);
      if oConnectionsToServer is None:
        # No connections to this server have been made before: create a new object in which to store them:
        oConnectionsToServer = oSelf.__doConnectionsToServer_by_sProtocolIPPort[sProtocolIPPort] = \
            cConnectionsToServer(sIP, uPort, bSecure, oSelf.bDebugOutput);
    finally:
      oSelf.__oMainLock.release();
    return oConnectionsToServer.foGetResponseForRequest(oHTTPRequest);
