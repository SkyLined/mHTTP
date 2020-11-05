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

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

def fxFirstNonNone(*txArguments):
  for xArgument in txArguments:
    if xArgument is not None:
      return xArgument;
  return None;

class iHTTPClient(cWithCallbacks):
  uzDefaultMaxNumberOfConnectionsToServer = None;
  nzDefaultConnectTimeoutInSeconds = None;
  nzDefaultSecureTimeoutInSeconds = None;
  nzDefaultTransactionTimeoutInSeconds = None;
  
  @property
  def bStopping(oSelf):
    raise NotImplementedError();
  
  def foGetProxyServerURLForURL(oSelf):
    raise NotImplementedError();
  
  @ShowDebugOutput
  def fozGetResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    uzMaxStatusLineSize = None,
    uzMaxHeaderNameSize = None,
    uzMaxHeaderValueSize = None,
    uzMaxNumberOfHeaders = None,
    uzMaxBodySize = None,
    uzMaxChunkSize = None,
    uzMaxNumberOfChunks = None,
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    oRequest = oSelf.foGetRequestForURL(
      oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks
    );
    ozResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest, oURL,
      uzMaxStatusLineSize = uzMaxStatusLineSize,
      uzMaxHeaderNameSize = uzMaxHeaderNameSize,
      uzMaxHeaderValueSize = uzMaxHeaderValueSize,
      uzMaxNumberOfHeaders = uzMaxNumberOfHeaders,
      uzMaxBodySize = uzMaxBodySize,
      uzMaxChunkSize = uzMaxChunkSize,
      uzMaxNumberOfChunks = uzMaxNumberOfChunks,
      uzMaximumNumberOfChunksBeforeDisconnecting = uzMaximumNumberOfChunksBeforeDisconnecting,
    );
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert ozResponse, \
        "Expected a response but got %s" % repr(ozResponse);
    return ozResponse;
  
  @ShowDebugOutput
  def ftozGetRequestAndResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    uzMaxStatusLineSize = None,
    uzMaxHeaderNameSize = None,
    uzMaxHeaderValueSize = None,
    uzMaxNumberOfHeaders = None,
    uzMaxBodySize = None,
    uzMaxChunkSize = None,
    uzMaxNumberOfChunks = None,
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return (None, None);
    oRequest = oSelf.foGetRequestForURL(
      oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks
    );
    ozResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest, oURL,
      uzMaxStatusLineSize = uzMaxStatusLineSize,
      uzMaxHeaderNameSize = uzMaxHeaderNameSize,
      uzMaxHeaderValueSize = uzMaxHeaderValueSize,
      uzMaxNumberOfHeaders = uzMaxNumberOfHeaders,
      uzMaxBodySize = uzMaxBodySize,
      uzMaxChunkSize = uzMaxChunkSize,
      uzMaxNumberOfChunks = uzMaxNumberOfChunks,
      uzMaximumNumberOfChunksBeforeDisconnecting = uzMaximumNumberOfChunksBeforeDisconnecting,
    );
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return (None, None);
    assert ozResponse, \
        "Expected a response but got %s" % repr(ozResponse);
    return (oRequest, ozResponse);
  
  @ShowDebugOutput
  def foGetRequestForURL(oSelf,
    oURL, 
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    ozAdditionalHeaders = None, bAutomaticallyAddContentLengthHeader = False
  ):
    oProxyServerURL = oSelf.foGetProxyServerURLForURL(oURL);
    if oSelf.bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    if oProxyServerURL is not None and ozHeaders is not None:
      for sName in ["Proxy-Authenticate", "Proxy-Authorization", "Proxy-Connection"]:
        ozHeader = oHeaders.fozGetUniqueHeaderForName(sName);
        assert ozHeader is None, \
            "%s header is not implemented!" % repr(ozHeader.sName);
    oRequest = cHTTPConnection.cHTTPRequest(
      # When sending requests to a proxy, secure requests are forwarded directly to the server (after an initial
      # CONNECT request), so the URL in the request must be relative. Non-secure requests are made to the proxy,
      # which most have the absolute URL.
      sURL = oURL.sRelative if oProxyServerURL is None or oURL.bSecure else oURL.sAbsolute,
      szMethod = szMethod,
      szVersion = szVersion,
      ozHeaders = ozHeaders,
      szBody = szBody,
      szData = szData,
      azsBodyChunks = azsBodyChunks,
      ozAdditionalHeaders = ozAdditionalHeaders,
      bAutomaticallyAddContentLengthHeader = bAutomaticallyAddContentLengthHeader
    );
    if not oRequest.oHeaders.fozGetUniqueHeaderForName("Host"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Host", oURL.sHostnameAndPort);
    if not oRequest.oHeaders.fozGetUniqueHeaderForName("Accept-Encoding"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Accept-Encoding", ", ".join(oRequest.asSupportedCompressionTypes));
    return oRequest;
  
  @ShowDebugOutput
  def fozGetResponseForRequestAndURL(oSelf,
    oRequest, oURL,
    uzMaxStatusLineSize = None,
    uzMaxHeaderNameSize = None,
    uzMaxHeaderValueSize = None,
    uzMaxNumberOfHeaders = None,
    uzMaxBodySize = None,
    uzMaxChunkSize = None,
    uzMaxNumberOfChunks = None,
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    raise NotImplementedError();
  
  def fasGetDetails(oSelf):
    raise NotImplementedError();
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));
