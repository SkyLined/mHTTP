from .cCertificateStore import cCertificateStore;
from .cHTTPConnectionsToServerPool import cHTTPConnectionsToServerPool;
from .cHTTPRequest import cHTTPRequest;
from .cHTTPConnection import cHTTPConnection;
from mDebugOutput import cWithDebugOutput;
from mMultiThreading import cLock, cWithCallbacks;

class cHTTPClient(cWithCallbacks, cWithDebugOutput):
  uDefaultMaxConnectionsToServer = 10;
  nDefaultConnectTimeoutInSeconds = 10;
  nDefaultTransactionTimeoutInSeconds = 10;
  
  def __init__(oSelf, oCertificateStore = None, uMaxConnectionsToServer = None):
    oSelf.__oCertificateStore = oCertificateStore or cCertificateStore();
    oSelf.__uMaxConnectionsToServer = uMaxConnectionsToServer or oSelf.uDefaultMaxConnectionsToServer;
    
    oSelf.__oConnectionsLock = cLock("%s.__oConnectionsLock" % oSelf.__class__.__name__);
    oSelf.__doConnectionsToServerPool_by_sProtocolHostPort = {};
    
    oSelf.__bStopping = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);

    oSelf.fAddEvents("new connection", "request sent", "response received", "request sent and response received", "connection terminated", "terminated");

  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;
  
  def __fCheckForTermination(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      if not oSelf.__bStopping:
        return oSelf.fExitFunctionOutput("Not stopping");
      oSelf.__oConnectionsLock.fAcquire();
      try:
        uServers = 0;
        uOpenConnections = 0;
        for oConnectionsToServerPool in oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values():
          uServers += 1;
          uOpenConnections += oConnectionsToServerPool.uConnectionsCount;
        bTerminated = uServers == 0 and not oSelf.__bTerminated;
        if bTerminated: oSelf.__bTerminated = True;
      finally:
        oSelf.__oConnectionsLock.fRelease();
      if bTerminated:
        oSelf.__oTerminatedLock.fRelease();
        oSelf.fFireCallbacks("terminated");
        return oSelf.fExitFunctionOutput("Terminated");
      return oSelf.fExitFunctionOutput("Not terminated; %d open connections to %d servers." % (uOpenConnections, uServers));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fStop(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      if oSelf.__bStopping:
        return oSelf.fExitFunctionOutput("Already stopping");
      # Prevent any new cHTTPConnectionsToServerPool instances from being created.
      oSelf.__bStopping = True;
      oSelf.__oConnectionsLock.fAcquire();
      try:
        # Grab a list of active cHTTPConnectionsToServerPool instances that need to be stopped.
        aoConnectionsToServerPools = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values()
      finally:
        oSelf.__oConnectionsLock.fRelease();
      if aoConnectionsToServerPools:
        oSelf.fStatusOutput("Stopping connections to server pools...");
        # Stop all cHTTPConnectionsToServerPool instances
        for oConnectionsToServerPool in aoConnectionsToServerPools:
          oConnectionsToServerPool.fStop();
      else:
        # If there were no connections-to-server pools after we set bStopping to True, we've stopped. However, we
        # still need to report this, so we call __fCheckForTermination which will detect and report it.
        oSelf.__fCheckForTermination();
      return oSelf.fExitFunctionOutput("Terminated" if oSelf.__bTerminated else "Stopping");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fTerminate(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      # Prevent any new cHTTPConnectionsToServerPool instances from being created.
      oSelf.__bStopping = True;
      oSelf.__oConnectionsLock.fAcquire();
      try:
        # Grab a list of active cHTTPConnectionsToServerPool instances that need to be terminated.
        aoConnectionsToServerPools = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.values();
      finally:
        oSelf.__oConnectionsLock.fRelease();
      # Terminate all cHTTPConnectionsToServerPool instances
      if aoConnectionsToServerPools:
        oSelf.fStatusOutput("Terminating connections to server pools...");
        for oConnectionsToServerPool in aoConnectionsToServerPools:
          oConnectionsToServerPool.fTerminate();
      oSelf.fStatusOutput("Waiting for termination...");
      oSelf.fWait();
      return oSelf.fExitFunctionOutput("Terminated");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fWait(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__oTerminatedLock.fWait();
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbWait(oSelf, nTimeoutInSeconds = 0):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds = nTimeoutInSeconds);
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetResponseForURL(oSelf,
    oURL,
    sMethod = None, dHeader_sValue_by_sName = None, sBody = None, sData = None, asBodyChunks = None,
    nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None,
    bCheckHostName = None,
  ):
    oSelf.fEnterFunctionOutput(oURL = oURL, sMethod = sMethod, dHeader_sValue_by_sName = dHeader_sValue_by_sName, sBody = sBody, sData = sData, asBodyChunks = asBodyChunks, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostName = bCheckHostName);
    try:
      (oRequest, oResponse) = oSelf.foGetRequestAndResponseForURL(oURL, sMethod, dHeader_sValue_by_sName, sBody, sData, asBodyChunks, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName);
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetRequestAndResponseForURL(oSelf,
    oURL,
    sMethod = None, dHeader_sValue_by_sName = None, sBody = None, sData = None, asBodyChunks = None,
    nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None,
    bCheckHostName = None,
  ):
    oSelf.fEnterFunctionOutput(oURL = oURL, sMethod = sMethod, dHeader_sValue_by_sName = dHeader_sValue_by_sName, sBody = sBody, sData = sData, asBodyChunks = asBodyChunks, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostName = bCheckHostName);
    try:
      oRequest = oSelf.foGetRequestForURL(oURL, sMethod, dHeader_sValue_by_sName, sBody, sData, asBodyChunks);
      oResponse = oSelf.foGetResponseForRequestAndURL(oRequest, oURL, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName);
      return oSelf.fxExitFunctionOutput((oRequest, oResponse));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetRequestForURL(oSelf,
    oURL,
    sMethod = None, dHeader_sValue_by_sName = None, sBody = None, sData = None, asBodyChunks = None,
  ):
    oSelf.fEnterFunctionOutput(oURL = oURL, sMethod = sMethod, dHeader_sValue_by_sName = dHeader_sValue_by_sName, sBody = sBody, sData = sData, asBodyChunks = asBodyChunks);
    try:
      oRequest = cHTTPRequest(
        sURL = oURL.sRelative,
        sMethod = sMethod or "GET",
        dHeader_sValue_by_sName = dHeader_sValue_by_sName,
        sBody = sBody,
        sData = sData, 
        asBodyChunks = asBodyChunks,
      );
      if not oRequest.fbHasHeaderValue("Host"):
        oRequest.fSetHeaderValue("Host", oURL.sHostNameAndPort);
      if not oRequest.fbHasHeaderValue("Accept-Encoding"):
        oRequest.fSetHeaderValue("Accept-Encoding", ", ".join(oRequest.asSupportedCompressionTypes));
      return oSelf.fxExitFunctionOutput(oRequest);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetResponseForRequestAndURL(oSelf,
    oRequest, oURL,
    nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None,
    bCheckHostName = None,
  ):
    oSelf.fEnterFunctionOutput(oRequest = oRequest, oURL = oURL, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostName = bCheckHostName);
    try:
      if nConnectTimeoutInSeconds is None:
        nConnectTimeoutInSeconds = oSelf.nDefaultConnectTimeoutInSeconds;
      if nTransactionTimeoutInSeconds is None:
        nTransactionTimeoutInSeconds = oSelf.nDefaultTransactionTimeoutInSeconds;
      oConnectionsToServerPool = oSelf.foGetConnectionsToServerPoolForURL(oURL);
      oResponse = oConnectionsToServerPool.foGetResponseForRequest(oRequest, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName);
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetConnectionsToServerPoolForURL(oSelf, oURL):
    oSelf.fEnterFunctionOutput(oURL = oURL);
    try:
      # We will reuse connections to the same server if possible. Servers are identified by host name, port and whether
      # or not the connection is secure. We may want to change this to identification by IP address rather than host name.
      oSelf.__oConnectionsLock.fAcquire();
      try:
        oConnectionsToServerPool = oSelf.__doConnectionsToServerPool_by_sProtocolHostPort.get(oURL.sBase);
        if oConnectionsToServerPool:
          return oSelf.fxExitFunctionOutput(oConnectionsToServerPool);
        # No connections to the server have been made before: create a new Pool.
        if oURL.bSecure:
          assert oSelf.__oCertificateStore, \
              "Making secure connections requires a certificate store.";
          oSSLContext = oSelf.__oCertificateStore.foGetSSLContextForClientWithHostName(oURL.sHostName);
        else:
          oSSLContext = None;
        oConnectionsToServerPool = cHTTPConnectionsToServerPool(
          oServerBaseURL = oURL.oBase,
          uMaxConnectionsToServer = oSelf.__uMaxConnectionsToServer,
          oSSLContext = oSSLContext,
        );
        oConnectionsToServerPool.fAddCallback("new connection", oSelf.__fHandleNewConnectionCallbackFromConnectionsToServerPool);
        oConnectionsToServerPool.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnectionsToServerPool);
        oConnectionsToServerPool.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnectionsToServerPool);
        oConnectionsToServerPool.fAddCallback("request sent and response received", oSelf.__fHandleRequestSentAndResponseReceivedCallbackFromConnectionsToServerPool);
        oConnectionsToServerPool.fAddCallback("connection terminated", oSelf.__fHandleConnectionTerminatedCallbackFromConnectionsToServerPool);
        oConnectionsToServerPool.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnectionsToServerPool);
        oSelf.__doConnectionsToServerPool_by_sProtocolHostPort[oURL.sBase] = oConnectionsToServerPool;
        return oSelf.fxExitFunctionOutput(oConnectionsToServerPool);
      finally:
        oSelf.__oConnectionsLock.fRelease();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetConnectionAndStartTransaction(oSelf, oURL, nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None, bCheckHostName = None, bNoSSLNegotiation = None):
    oSelf.fEnterFunctionOutput(oURL = oURL);
    try:
      if nConnectTimeoutInSeconds is None:
        nConnectTimeoutInSeconds = oSelf.nDefaultConnectTimeoutInSeconds;
      if nTransactionTimeoutInSeconds is None:
        nTransactionTimeoutInSeconds = oSelf.nDefaultTransactionTimeoutInSeconds;
      oConnectionsToServerPool = oSelf.foGetConnectionsToServerPoolForURL(oURL);
      oConnection = oConnectionsToServerPool.foGetConnectionAndStartTransaction(nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName, bNoSSLNegotiation);
      return oSelf.fxExitFunctionOutput(oConnection);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
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
  
  def __fHandleTerminatedCallbackFromConnectionsToServerPool(oSelf, oConnectionsToServerPool):
    oSelf.fEnterFunctionOutput(oConnectionsToServerPool = oConnectionsToServerPool.fsToString());
    try:
      assert oSelf.__bStopping, \
          "This is really unexpected!";
      oSelf.__oConnectionsLock.fAcquire();
      try:
        for sProtocolHostPort in oSelf.__doConnectionsToServerPool_by_sProtocolHostPort:
          if oSelf.__doConnectionsToServerPool_by_sProtocolHostPort[sProtocolHostPort] == oConnectionsToServerPool:
            del oSelf.__doConnectionsToServerPool_by_sProtocolHostPort[sProtocolHostPort];
            break;
        else:
          raise AssertionError("A cConnectionsToServerPool instance reported that it terminated, but we were not aware it existed");
      finally:
        oSelf.__oConnectionsLock.fRelease();
      oSelf.__fCheckForTermination();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsToString(oSelf):
    asAttributes = [s for s in [
      "%d servers" % len(oSelf.__doConnectionsToServerPool_by_sProtocolHostPort) if not oSelf.__bTerminated else None,
      "terminated" if oSelf.__bTerminated else 
        "stopping" if oSelf.__bStopping else None,
    ] if s];
    sDetails = ", ".join(asAttributes) if asAttributes else "";
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
