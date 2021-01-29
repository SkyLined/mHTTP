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
from mNotProvided import *;
try: # SSL support is optional.
  from mSSL import cCertificateStore as c0CertificateStore;
except:
  c0CertificateStore = None; # No SSL support

from .iHTTPClient import iHTTPClient;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cHTTPClient(iHTTPClient, cWithCallbacks):
  u0zDefaultMaxNumberOfConnectionsToServer = 10;
  n0zDefaultConnectTimeoutInSeconds = 10;
  n0zDefaultSecureTimeoutInSeconds = 5;
  n0zDefaultTransactionTimeoutInSeconds = 10;
  
  @ShowDebugOutput
  def __init__(oSelf,
    o0zCertificateStore = zNotProvided,
    u0zMaxNumberOfConnectionsToServer = zNotProvided,
    n0zConnectTimeoutInSeconds = zNotProvided,
    n0zSecureTimeoutInSeconds = zNotProvided,
    n0zTransactionTimeoutInSeconds = zNotProvided,
    bAllowUnverifiableCertificates = False,
    bCheckHostname = True,
  ):
    oSelf.__o0CertificateStore = (
      o0zCertificateStore if fbIsProvided(o0zCertificateStore) else
      c0CertificateStore() if c0CertificateStore else
      None
    );
    oSelf.__u0zMaxNumberOfConnectionsToServer = fxGetFirstProvidedValue(u0zMaxNumberOfConnectionsToServer, oSelf.u0zDefaultMaxNumberOfConnectionsToServer);
    # Timeouts can be provided through class default, instance defaults, or method call arguments.
    oSelf.__n0zConnectTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zConnectTimeoutInSeconds, oSelf.n0zDefaultConnectTimeoutInSeconds);
    oSelf.__n0zSecureTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureTimeoutInSeconds, oSelf.n0zDefaultSecureTimeoutInSeconds);
    oSelf.__n0zTransactionTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zTransactionTimeoutInSeconds, oSelf.n0zDefaultTransactionTimeoutInSeconds);
    oSelf.__bAllowUnverifiableCertificates = bAllowUnverifiableCertificates;
    oSelf.__bCheckHostname = bCheckHostname;
    
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__doConnectionsToServerPool_by_sProtocolHostPort = {};
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    
    oSelf.fAddEvents(
      "connect failed", "new connection",
      "request sent", "response received", "request sent and response received",
      "connection terminated",
      "terminated",
    );
  
  @property
  def bStopping(oSelf):
    return oSelf.__bStopping;
  
  @ShowDebugOutput
  def fStop(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated");
      if oSelf.__bStopping:
        return fShowDebugOutput("Already stopping");
      fShowDebugOutput("Stopping...");
      # Prevent any new cHTTPConnectionsToServerPool instances from being created.
      oSelf.__bStopping = True;
      # Grab a list of active cHTTPConnectionsToServerPool instances that need to be stopped.
      aoConnectionsToServerPools = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values()
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if len(aoConnectionsToServerPools) == 0:
      # We stopped when there were no connections: we are terminated.
      fShowDebugOutput("Terminated.");
      oSelf.__oTerminatedLock.fRelease();
      oSelf.fFireEvent("terminated");
    else:
      fShowDebugOutput("Stopping connections to server pools...");
      # Stop all cHTTPConnectionsToServerPool instances
      for oConnectionsToServerPool in aoConnectionsToServerPools:
        oConnectionsToServerPool.fStop();
  
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated.");
      fShowDebugOutput("Terminating...");
      oSelf.__bStopping = True;
      # Grab a list of active cHTTPConnectionsToServerPool instances that need to be terminated.
      aoConnectionsToServerPools = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    # Terminate all cHTTPConnectionsToServerPool instances
    if len(aoConnectionsToServerPools) == 0:
      fShowDebugOutput("Terminated.");
      oSelf.__oTerminatedLock.fRelease();
      oSelf.fFireEvent("terminated");
    else:
      fShowDebugOutput("Terminating %d connections to server pools..." % len(aoConnectionsToServerPools));
      for oConnectionsToServerPool in aoConnectionsToServerPools:
        oConnectionsToServerPool.fTerminate();
  
  @ShowDebugOutput
  def fWait(oSelf):
    return oSelf.__oTerminatedLock.fWait();
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  def fo0GetProxyServerURLForURL(oSelf, oURL):
    return None;
  
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
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    oConnectionsToServerPool = oSelf.__foGetConnectionsToServerPoolForURL(oURL);
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    o0Response = oConnectionsToServerPool.fo0SendRequestAndReceiveResponse(
      oRequest,
      n0zConnectTimeoutInSeconds = oSelf.__n0zConnectTimeoutInSeconds,
      n0zSecureTimeoutInSeconds = oSelf.__n0zSecureTimeoutInSeconds,
      n0zTransactionTimeoutInSeconds = oSelf.__n0zTransactionTimeoutInSeconds,
      u0zMaxStatusLineSize = u0zMaxStatusLineSize,
      u0zMaxHeaderNameSize = u0zMaxHeaderNameSize,
      u0zMaxHeaderValueSize = u0zMaxHeaderValueSize,
      u0zMaxNumberOfHeaders = u0zMaxNumberOfHeaders,
      u0zMaxBodySize = u0zMaxBodySize,
      u0zMaxChunkSize = u0zMaxChunkSize,
      u0zMaxNumberOfChunks = u0zMaxNumberOfChunks,
      u0MaxNumberOfChunksBeforeDisconnecting = u0MaxNumberOfChunksBeforeDisconnecting,
    );
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert o0Response, \
        "Expected a response but got %s" % repr(o0Response);
    return o0Response;
  
  @ShowDebugOutput
  def __foGetConnectionsToServerPoolForURL(oSelf, oURL):
    # We will reuse connections to the same server if possible. Servers are identified by host name, port and whether
    # or not the connection is secure. We may want to change this to identification by IP address rather than host name.
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      oConnectionsToServerPool = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.get(oURL.sBase);
      if oConnectionsToServerPool:
        return oConnectionsToServerPool;
      # No connections to the server have been made before: create a new Pool.
      if oURL.bSecure:
        assert oSelf.__o0CertificateStore, \
            "Making secure connections requires a certificate store.";
        if oSelf.__bAllowUnverifiableCertificates:
          o0SSLContext = oSelf.__o0CertificateStore.foGetClientsideSSLContextWithoutVerification();
        else:
          o0SSLContext = oSelf.__o0CertificateStore.foGetClientsideSSLContextForHostname(
            oURL.sHostname,
            bCheckHostname = oSelf.__bCheckHostname
          );
      else:
        o0SSLContext = None;
      fShowDebugOutput("Creating new cConnectionsToServerPool for %s" % oURL.sBase);
      oConnectionsToServerPool = cHTTPConnectionsToServerPool(
        oServerBaseURL = oURL.oBase,
        u0zMaxNumberOfConnectionsToServer = oSelf.__u0zMaxNumberOfConnectionsToServer,
        o0SSLContext = o0SSLContext,
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
      # Return if we are not stopping or if there are other connections open:
      if not oSelf.__bStopping:
        return;
      if len(oSelf.__doConnectionsToServerPool_by_sProtocolHostPort) > 0:
        return;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    # We are stopping and the last connection just terminated: we are terminated.
    fShowDebugOutput("Terminated.");
    oSelf.__oTerminatedLock.fRelease();
    oSelf.fFireCallbacks("terminated");
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    if oSelf.bTerminated:
      return ["terminated"];
    return [s for s in [
      "connected to %d servers" % len(oSelf.__doConnectionsToServerPool_by_sProtocolHostPort),
      "stopping" if oSelf.__bStopping else None,
    ] if s];
