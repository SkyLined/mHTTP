try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mHTTPConnections import cHTTPConnection, cHTTPConnectionsToServerPool;
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

class cHTTPClient(cWithCallbacks):
  uzDefaultMaxNumerOfConnectionsToServer = 10;
  nzDefaultConnectTimeoutInSeconds = 10;
  nzDefaultSecureTimeoutInSeconds = 5;
  nzDefaultTransactionTimeoutInSeconds = 10;
  cURL = cHTTPConnection.cHTTPRequest.cURL;
  
  @ShowDebugOutput
  def __init__(oSelf,
    ozCertificateStore = None, uzMaxNumerOfConnectionsToServer = None,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
  ):
    oSelf.__ozCertificateStore = ozCertificateStore or (czCertificateStore() if czCertificateStore else None);
    oSelf.__uzMaxNumerOfConnectionsToServer = uzMaxNumerOfConnectionsToServer or oSelf.uzDefaultMaxNumerOfConnectionsToServer;
    # Timeouts can be provided through class default, instance defaults, or method call arguments.
    oSelf.__nzConnectTimeoutInSeconds = fxFirstNonNone(nzConnectTimeoutInSeconds, oSelf.nzDefaultConnectTimeoutInSeconds);
    oSelf.__nzSecureTimeoutInSeconds = fxFirstNonNone(nzSecureTimeoutInSeconds, oSelf.nzDefaultSecureTimeoutInSeconds);
    oSelf.__nzTransactionTimeoutInSeconds = fxFirstNonNone(nzTransactionTimeoutInSeconds, oSelf.nzDefaultTransactionTimeoutInSeconds);
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      nzDeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__doConnectionsToServerPool_by_sProtocolHostPort = {};
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    
    oSelf.fAddEvents(
      "connect failed", "new connection",
      "request sent", "response received", "request sent and response received",
      "connection terminated",
      "terminated");
  
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  
  def foGetProxyServerURL(oSelf):
    return None;
  
  @ShowDebugOutput
  def __fCheckForTermination(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated");
      if not oSelf.__bStopping:
        return fShowDebugOutput("Not stopping");
      if len(oSelf.__doConnectionsToServerPool_by_sProtocolHostPort) > 0:
        return fShowDebugOutput("There are open connections to %d servers." % len(oSelf.__doConnectionsToServerPool_by_sProtocolHostPort));
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    fShowDebugOutput("%s terminating." % oSelf.__class__.__name__);
    oSelf.fFireCallbacks("terminated");
  
  @ShowDebugOutput
  def fStop(oSelf):
    if oSelf.bTerminated:
      return fShowDebugOutput("Already terminated");
    if oSelf.__bStopping:
      return fShowDebugOutput("Already stopping");
    fShowDebugOutput("Stopping...");
    # Prevent any new cHTTPConnectionsToServerPool instances from being created.
    oSelf.__bStopping = True;
    # Grab a list of active cHTTPConnectionsToServerPool instances that need to be stopped.
    aoConnectionsToServerPools = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values()
    if aoConnectionsToServerPools:
      fShowDebugOutput("Stopping connections to server pools...");
      # Stop all cHTTPConnectionsToServerPool instances
      for oConnectionsToServerPool in aoConnectionsToServerPools:
        oConnectionsToServerPool.fStop();
    else:
      # This instance has terminated if there were no connections-to-server
      # pools when we set bStopping to True. However, we need to fire events
      # to report this: __fCheckForTermination which will detect and report it.
      oSelf.__fCheckForTermination();
    return;
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    if oSelf.bTerminated:
      return fShowDebugOutput("Already terminated.");
    fShowDebugOutput("Terminating...");
    oSelf.__bStopping = True;
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      # Grab a list of active cHTTPConnectionsToServerPool instances that need to be terminated.
      aoConnectionsToServerPools = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    # Terminate all cHTTPConnectionsToServerPool instances
    if aoConnectionsToServerPools:
      fShowDebugOutput("Terminating %d connections to server pools..." % len(aoConnectionsToServerPools));
      for oConnectionsToServerPool in aoConnectionsToServerPools:
        oConnectionsToServerPool.fTerminate();
    return;
  
  @ShowDebugOutput
  def fWait(oSelf):
    return oSelf.__oTerminatedLock.fWait();
  @ShowDebugOutput
  def fbWait(oSelf, nzTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nzTimeoutInSeconds);
  
  @ShowDebugOutput
  def fozGetResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = False,
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    nzConnectTimeoutInSeconds = fxFirstNonNone(nzConnectTimeoutInSeconds, oSelf.__nzConnectTimeoutInSeconds);
    nzTransactionTimeoutInSeconds = fxFirstNonNone(nzTransactionTimeoutInSeconds, oSelf.__nzConnectTimeoutInSeconds);
    oRequest = oSelf.foGetRequestForURL(oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks);
    oResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest, oURL,
      nzConnectTimeoutInSeconds, nzSecureTimeoutInSeconds, nzTransactionTimeoutInSeconds,
      bCheckHostname,
      uzMaximumNumberOfChunksBeforeDisconnecting
    );
    return oResponse;
  
  @ShowDebugOutput
  def ftoGetRequestAndResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    nzConnectTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = None,
  ):
    oRequest = oSelf.foGetRequestForURL(oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks);
    oResponse = oSelf.fozGetResponseForRequestAndURL(oRequest, oURL, nzConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds, bCheckHostname);
    return (oRequest, oResponse);
  
  @ShowDebugOutput
  def foGetRequestForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
  ):
    oRequest = cHTTPConnection.cHTTPRequest(
      sURL = oURL.sRelative,
      szMethod = szMethod, szVersion = szVersion, ozHeaders = ozHeaders, szBody = szBody, szData = szData, azsBodyChunks = azsBodyChunks,
    );
    if not oRequest.oHeaders.fozGetUniqueHeaderForName("Host"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Host", oURL.sHostnameAndPort);
    if not oRequest.oHeaders.fozGetUniqueHeaderForName("Accept-Encoding"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Accept-Encoding", ", ".join(oRequest.asSupportedCompressionTypes));
    return oRequest;
  
  @ShowDebugOutput
  def fozGetResponseForRequestAndURL(oSelf,
    oRequest, oURL,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = None,
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    nzConnectTimeoutInSeconds = fxFirstNonNone(nzConnectTimeoutInSeconds, oSelf.__nzConnectTimeoutInSeconds);
    nzSecureTimeoutInSeconds = fxFirstNonNone(nzSecureTimeoutInSeconds, oSelf.__nzSecureTimeoutInSeconds);
    nzTransactionTimeoutInSeconds = fxFirstNonNone(nzTransactionTimeoutInSeconds, oSelf.__nzTransactionTimeoutInSeconds);
    oConnectionsToServerPool = oSelf.__foGetConnectionsToServerPoolForURL(oURL, bCheckHostname);
    oResponse = oConnectionsToServerPool.fozSendRequestAndReceiveResponse(
      oRequest,
      nzConnectTimeoutInSeconds = nzConnectTimeoutInSeconds,
      nzSecureTimeoutInSeconds = nzSecureTimeoutInSeconds,
      nzTransactionTimeoutInSeconds = nzTransactionTimeoutInSeconds,
      uzMaximumNumberOfChunksBeforeDisconnecting = uzMaximumNumberOfChunksBeforeDisconnecting,
    );
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert oResponse, \
        "Expected a response but got %s" % repr(oResponse);
    return oResponse;
  
  @ShowDebugOutput
  def __foGetConnectionsToServerPoolForURL(oSelf, oURL, bCheckHostname = None):
    # We will reuse connections to the same server if possible. Servers are identified by host name, port and whether
    # or not the connection is secure. We may want to change this to identification by IP address rather than host name.
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      oConnectionsToServerPool = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.get(oURL.sBase);
      if oConnectionsToServerPool:
        return oConnectionsToServerPool;
      # No connections to the server have been made before: create a new Pool.
      if oURL.bSecure:
        assert oSelf.__ozCertificateStore, \
            "Making secure connections requires a certificate store.";
        ozSSLContext = oSelf.__ozCertificateStore.foGetSSLContextForClientWithHostname(oURL.sHostname);
      else:
        ozSSLContext = None;
      fShowDebugOutput("Creating new cConnectionsToServerPool for %s" % oURL.sBase);
      oConnectionsToServerPool = cHTTPConnectionsToServerPool(
        oServerBaseURL = oURL.oBase,
        uzMaxNumerOfConnectionsToServer = oSelf.__uzMaxNumerOfConnectionsToServer,
        ozSSLContext = ozSSLContext,
        bCheckHostname = bCheckHostname,
      );
      oConnectionsToServerPool.fAddCallback("new connection", oSelf.__fHandleNewConnectionCallbackFromConnectionsToServerPool);
      oConnectionsToServerPool.fAddCallback("connect failed", oSelf.__fHandleConnectFailedCallbackFromConnectionsToServerPool);
      oConnectionsToServerPool.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnectionsToServerPool);
      oConnectionsToServerPool.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnectionsToServerPool);
      oConnectionsToServerPool.fAddCallback("request sent and response received", oSelf.__fHandleRequestSentAndResponseReceivedCallbackFromConnectionsToServerPool);
      oConnectionsToServerPool.fAddCallback("connection terminated", oSelf.__fHandleConnectionTerminatedCallbackFromConnectionsToServerPool);
      oConnectionsToServerPool.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnectionsToServerPool);
      oSelf.__doConnectionsToServerPool_by_sProtocolHostPort[oURL.sBase] = oConnectionsToServerPool;
      return oConnectionsToServerPool;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
  
  def __fHandleConnectFailedCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool, sHostname, uPort, oException):
    oSelf.fFireCallbacks("connect failed", sHostname, uPort, oException);
  
  def __fHandleNewConnectionCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool, oConnection):
    oSelf.fFireCallbacks("new connection", oConnection);
  
  def __fHandleRequestSentCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool, oConnection, oRequest):
    oSelf.fFireCallbacks("request sent", oConnection, oRequest);
  
  def __fHandleResponseReceivedCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool, oConnection, oReponse):
    oSelf.fFireCallbacks("response received", oConnection, oReponse);
  
  def __fHandleRequestSentAndResponseReceivedCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool, oConnection, oRequest, oReponse):
    oSelf.fFireCallbacks("request sent and response received", oConnection, oRequest, oReponse);
  
  def __fHandleConnectionTerminatedCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool, oConnection):
    oSelf.fFireCallbacks("connection terminated", oConnection);
  
  @ShowDebugOutput
  def __fHandleTerminatedCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool):
    assert oSelf.__bStopping, \
        "This is really unexpected!";
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      for sProtocolHostPort in oSelf.__doConnectionsToServerPool_by_sProtocolHostPort:
        if oSelf.__doConnectionsToServerPool_by_sProtocolHostPort[sProtocolHostPort] == oConnectionsToServerPool:
          fShowDebugOutput("Removing cConnectionsToServerPool for %s" % sProtocolHostPort);
          del oSelf.__doConnectionsToServerPool_by_sProtocolHostPort[sProtocolHostPort];
          break;
      else:
        raise AssertionError("A cConnectionsToServerPool instance reported that it terminated, but we were not aware it existed");
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oSelf.__fCheckForTermination();
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    if oSelf.bTerminated:
      return ["terminated"];
    return [s for s in [
      "connected to %d servers" % len(oSelf.__doConnectionsToServerPool_by_sProtocolHostPort),
      "stopping" if oSelf.__bStopping else None,
    ] if s];
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));
