try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mHTTPConnections import cHTTPConnection, cHTTPConnectionsToServerPool, cURL;
from mMultiThreading import cLock, cWithCallbacks;
try: # SSL support is optional.
  from mSSL import cCertificateStore as czCertificateStore;
except:
  czCertificateStore = None; # No SSL support

from .mNotProvided import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class iHTTPClient(cWithCallbacks):
  u0DefaultMaxNumberOfConnectionsToServer = 10;
  n0zDefaultConnectTimeoutInSeconds = 10;
  n0zDefaultSecureTimeoutInSeconds = 5;
  n0zDefaultTransactionTimeoutInSeconds = 10;
  
  @property
  def bStopping(oSelf):
    raise NotImplementedError();
  
  def fo0GetProxyServerURLForURL(oSelf):
    raise NotImplementedError();
  
  @ShowDebugOutput
  def fo0GetResponseForURL(oSelf,
    oURL,
    szMethod = zNotProvided, szVersion = zNotProvided, o0zHeaders = zNotProvided, s0Body = None, s0Data = None, a0sBodyChunks = None,
    u0zMaxStatusLineSize = zNotProvided,
    u0zMaxHeaderNameSize = zNotProvided,
    u0zMaxHeaderValueSize = zNotProvided,
    u0zMaxNumberOfHeaders = zNotProvided,
    u0zMaxBodySize = zNotProvided,
    u0zMaxChunkSize = zNotProvided,
    u0zMaxNumberOfChunks = zNotProvided,
    u0MaxNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    oRequest = oSelf.foGetRequestForURL(
      oURL, szMethod, szVersion, o0zHeaders, s0Body, s0Data, a0sBodyChunks
    );
    o0Response = oSelf.fo0GetResponseForRequestAndURL(
      oRequest, oURL,
      u0zMaxStatusLineSize = u0zMaxStatusLineSize,
      u0zMaxHeaderNameSize = u0zMaxHeaderNameSize,
      u0zMaxHeaderValueSize = u0zMaxHeaderValueSize,
      u0zMaxNumberOfHeaders = u0zMaxNumberOfHeaders,
      u0zMaxBodySize = u0zMaxBodySize,
      u0zMaxChunkSize = u0zMaxChunkSize,
      u0zMaxNumberOfChunks = u0zMaxNumberOfChunks,
      u0MaxNumberOfChunksBeforeDisconnecting = u0MaxNumberOfChunksBeforeDisconnecting,
    );
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert o0Response, \
        "Expected a response but got %s" % repr(o0Response);
    return o0Response;
  
  @ShowDebugOutput
  def fto0GetRequestAndResponseForURL(oSelf,
    oURL,
    szMethod = zNotProvided, szVersion = zNotProvided, o0zHeaders = zNotProvided, s0Body = None, s0Data = None, a0sBodyChunks = None,
    u0zMaxStatusLineSize = zNotProvided,
    u0zMaxHeaderNameSize = zNotProvided,
    u0zMaxHeaderValueSize = zNotProvided,
    u0zMaxNumberOfHeaders = zNotProvided,
    u0zMaxBodySize = zNotProvided,
    u0zMaxChunkSize = zNotProvided,
    u0zMaxNumberOfChunks = zNotProvided,
    u0MaxNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return (None, None);
    oRequest = oSelf.foGetRequestForURL(
      oURL, szMethod, szVersion, o0zHeaders, s0Body, s0Data, a0sBodyChunks
    );
    o0Response = oSelf.fo0GetResponseForRequestAndURL(
      oRequest, oURL,
      u0zMaxStatusLineSize = u0zMaxStatusLineSize,
      u0zMaxHeaderNameSize = u0zMaxHeaderNameSize,
      u0zMaxHeaderValueSize = u0zMaxHeaderValueSize,
      u0zMaxNumberOfHeaders = u0zMaxNumberOfHeaders,
      u0zMaxBodySize = u0zMaxBodySize,
      u0zMaxChunkSize = u0zMaxChunkSize,
      u0zMaxNumberOfChunks = u0zMaxNumberOfChunks,
      u0MaxNumberOfChunksBeforeDisconnecting = u0MaxNumberOfChunksBeforeDisconnecting,
    );
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return (None, None);
    assert o0Response, \
        "Expected a response but got %s" % repr(o0Response);
    return (oRequest, o0Response);
  
  @ShowDebugOutput
  def foGetRequestForURL(oSelf,
    oURL, 
    szMethod = zNotProvided, szVersion = zNotProvided, o0zHeaders = zNotProvided, s0Body = None, s0Data = None, a0sBodyChunks = None,
    o0AdditionalHeaders = None, bAutomaticallyAddContentLengthHeader = False
  ):
    o0ProxyServerURL = oSelf.fo0GetProxyServerURLForURL(oURL);
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    if o0ProxyServerURL is not None and fbIsProvided(o0zHeaders) and o0zHeaders is not None:
      for sName in ["Proxy-Authenticate", "Proxy-Authorization", "Proxy-Connection"]:
        o0Header = o0zHeaders.fo0GetUniqueHeaderForName(sName);
        assert o0Header is None, \
            "%s header is not implemented!" % repr(o0Header.sName);
    oRequest = cHTTPConnection.cHTTPRequest(
      # When sending requests to a proxy, secure requests are forwarded directly to the server (after an initial
      # CONNECT request), so the URL in the request must be relative. Non-secure requests are made to the proxy,
      # which most have the absolute URL.
      sURL = oURL.sRelative if o0ProxyServerURL is None or oURL.bSecure else oURL.sAbsolute,
      szMethod = szMethod,
      szVersion = szVersion,
      o0zHeaders = o0zHeaders,
      s0Body = s0Body,
      s0Data = s0Data,
      a0sBodyChunks = a0sBodyChunks,
      o0AdditionalHeaders = o0AdditionalHeaders,
      bAutomaticallyAddContentLengthHeader = bAutomaticallyAddContentLengthHeader
    );
    if not oRequest.oHeaders.fo0GetUniqueHeaderForName("Host"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Host", oURL.sHostnameAndPort);
    if not oRequest.oHeaders.fo0GetUniqueHeaderForName("Accept-Encoding"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Accept-Encoding", ", ".join(oRequest.asSupportedCompressionTypes));
    return oRequest;
  
  @ShowDebugOutput
  def fo0GetResponseForRequestAndURL(oSelf,
    oRequest, oURL,
    u0zMaxStatusLineSize = zNotProvided,
    u0zMaxHeaderNameSize = zNotProvided,
    u0zMaxHeaderValueSize = zNotProvided,
    u0zMaxNumberOfHeaders = zNotProvided,
    u0zMaxBodySize = zNotProvided,
    u0zMaxChunkSize = zNotProvided,
    u0zMaxNumberOfChunks = zNotProvided,
    u0MaxNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    raise NotImplementedError();
  
  def fasGetDetails(oSelf):
    raise NotImplementedError();
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));
