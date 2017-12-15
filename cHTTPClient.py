import socket, threading;
from cConnectionsToServer import cConnectionsToServer;
from cHTTPRequest import cHTTPRequest;

class cHTTPClient(object):
  def __init__(oSelf):
    oSelf.__oMainLock = threading.Lock(); # Used to control access to .__doConnectionsToServer_by_sProtocolHostPort
    oSelf.__doConnectionsToServer_by_sProtocolHostPort = {};
    oSelf.bDebugOutput = False;
    oSelf.__bProxySecure = None;
    oSelf.__sProxyHost = None;
    oSelf.__uProxyPort = None;

  def fSetProxy(oSelf, sURL):
    asProtocol_sHostPort = sURL.rstrip("/").split("/");
    sProtocol = asProtocol_sHostPort[0];
    assert len(asProtocol_sHostPort) == 3 and sProtocol in ["http:", "https:"], \
        "Bad URL: %s" % sURL;
    oSelf.__bProxySecure = sProtocol == "https:";
    asHost_sPort = asProtocol_sHostPort[2].split(":", 1);
    oSelf.__sProxyHost = asHost_sPort[0];
    if len(asHost_sPort) == 1:    
      oSelf.__uProxyPort = bSecure and 443 or 80;
    else:
      oSelf.__uProxyPort = long(asHost_sPort[1]);

  def foGetResponseForURL(oSelf, sURL, sMethod = "GET", dHeader_sValue_by_sName = None, sContent = None):
    asProtocol_s_sHostPort_sRelativeURL = sURL.split("/", 3);
    if len(asProtocol_s_sHostPort_sRelativeURL) == 3:
      sProtocol, sEmpty, sHostPort = asProtocol_s_sHostPort_sRelativeURL;
    else:
      assert len(asProtocol_s_sHostPort_sRelativeURL) == 4, \
          "Bad URL: %s" % sURL;
      sProtocol, sEmpty, sHostPort, sRelativeURL = asProtocol_s_sHostPort_sRelativeURL;
    sProtocol = asProtocol_s_sHostPort_sRelativeURL[0];
    assert sProtocol in ["http:", "https:"], \
        "Bad protocol in URL: %s" % sURL;
    bSecure = sProtocol == "https:";
    sHostPort = asProtocol_s_sHostPort_sRelativeURL[2];
    sRelativeURL = len(asProtocol_s_sHostPort_sRelativeURL) == 4 and asProtocol_s_sHostPort_sRelativeURL[3] or "/";
    oHTTPRequest = cHTTPRequest(
      sMethod = "GET",
      sURL = sRelativeURL,
      dHeader_sValue_by_sName = dHeader_sValue_by_sName,
      sContent = sContent,
    );
    oHTTPRequest.fSetHeaderValue("Host", sHostPort);
    asHost_sPort = sHostPort.split(":", 1);
    sHost = sHostPort[0];
    uPort = len(sHostPort) == 2 and long(sHostPort[1]);
    return oSelf.foGetResponseForRequest(oHTTPRequest, sHost = sHost, uPort = uPort, bSecure = bSecure);
  
  def foGetResponseForRequest(oSelf, oHTTPRequest, sHost = None, uPort = None, bSecure = False):
    # NOTE: There are no checks performed on the server's certificate; it could be self-signed and/or completely
    # invalid.
    if sHost is None or uPort is None:
      if type(oHTTPRequest) in (str, unicode):
        # We cannot find out what server to connect to from a string request, but we can use the default port number
        # if it's not specified:
        assert sHost, \
          "You must specify a host to send the request to.";
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
        if sHost is None:
          sHost = socket.gethostbyname(sHostName);
          assert sHost, \
              "Unknown hostname %s" % sHostName;
    sProtocolHostPort = "http%s://%s:%d" % (bSecure and "s" or "", sHost, uPort);

    if oSelf.__bProxySecure is not None:
      oHTTPRequest = oHTTPRequest.foClone();
      oHTTPRequest.sURL = sProtocolHostPort + oHTTPRequest.sURL;
      bSecure = oSelf.__bProxySecure;
      sHost = oSelf.__sProxyHost;
      uPort = oSelf.__uProxyPort;
      sProtocolHostPort = "http%s://%s:%d" % (bSecure and "s" or "", sHost, uPort);
    # We will reuse connections to the same server (identified by host name, port and whether or not the connection
    # is secure).
    oSelf.__oMainLock.acquire();
    try:
      oConnectionsToServer = oSelf.__doConnectionsToServer_by_sProtocolHostPort.get(sProtocolHostPort);
      if oConnectionsToServer is None:
        # No connections to this server have been made before: create a new object in which to store them:
        oConnectionsToServer = oSelf.__doConnectionsToServer_by_sProtocolHostPort[sProtocolHostPort] = \
            cConnectionsToServer(sHost, uPort, bSecure, oSelf.bDebugOutput);
    finally:
      oSelf.__oMainLock.release();
    return oConnectionsToServer.foGetResponseForRequest(oHTTPRequest);
