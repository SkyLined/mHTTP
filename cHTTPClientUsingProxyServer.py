import time;
from .cCertificateStore import cCertificateStore;
from .cHTTPClient import cHTTPClient;
from .cHTTPConnection import cHTTPConnection;
from .cHTTPHeaders import cHTTPHeaders;
from .cHTTPRequest import cHTTPRequest;
from .iHTTPMessage import iHTTPMessage;
from mDebugOutput import cWithDebugOutput;
from mMultiThreading import cLock, cWithCallbacks;

class cHTTPClientUsingProxyServer(cWithCallbacks, cWithDebugOutput):
  uDefaultMaxConnectionsToServer = 10;
  nDefaultConnectTimeoutInSeconds = 10;
  nDefaultTransactionTimeoutInSeconds = 10;
  
  def __init__(oSelf, oProxyServerURL, oCertificateStore = None, uMaxConnectionsToServer = None):
    oSelf.__oProxyServerURL = oProxyServerURL;
    oSelf.__oCertificateStore = oCertificateStore or cCertificateStore();
    oSelf.__uMaxConnectionsToServer = uMaxConnectionsToServer or oSelf.uDefaultMaxConnectionsToServer;

    oSelf.__oProxyServerSSLContext = oCertificateStore.foGetSSLContextForClientWithHostName(oProxyServerURL.sHostName) if oProxyServerURL.bSecure else None;
    
    oSelf.__oConnectionsAvailableLock = cLock("%s.__oConnectionsAvailableLock" % oSelf.__class__.__name__, uSize = oSelf.__uMaxConnectionsToServer);
    oSelf.__oConnectionsLock = cLock("%s.__oConnectionsLock" % oSelf.__class__.__name__);
    oSelf.__aoNonSecureConnections = [];
    oSelf.__doSecureConnectionToServer_by_sProtocolHostPort = {};
    
    oSelf.__bStopping = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    
    oSelf.fAddEvents("new connection", "request sent", "response received", "request sent and response received", "secure connection established", "connection terminated", "terminated");
  
  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;
  
  def foGetProxyServerURL(oSelf):
    return oSelf.__oProxyServerURL.foClone();
  
  def __faoGetAllConnections(oSelf):
    return oSelf.__aoNonSecureConnections + oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.values();
  
  def fStop(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      if oSelf.__bStopping:
        return oSelf.fExitFunctionOutput("Already stopping");
      oSelf.__bStopping = True;
      oSelf.__oConnectionsLock.fAcquire();
      try:
        aoConnections = oSelf.__faoGetAllConnections();
      finally:
        oSelf.__oConnectionsLock.fRelease();
      oSelf.fStatusOutput("Stopping connections to proxy server...");
      for oConnection in aoConnections:
        oConnection.fStop();
      return oSelf.fExitFunctionOutput("Stopping");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fTerminate(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      oSelf.__bStopping = True;
      oSelf.__oConnectionsLock.fAcquire();
      try:
        aoConnections = oSelf.__faoGetAllConnections();
      finally:
        oSelf.__oConnectionsLock.fRelease();
      oSelf.fStatusOutput("Terminating connections to proxy server...");
      for oConnection in aoConnections:
        oConnection.fTerminate();
      oSelf.fStatusOutput("Waiting for termination...");
      oSelf.fWait();
      return oSelf.fExitFunctionOutput("Terminated");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fWait(oSelf, nTimeoutInSeconds = 0):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds = nTimeoutInSeconds);
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetResponseForURL(oSelf,
    oURL,
    sMethod = None, oHTTPHeaders = None, sBody = None, sData = None, asBodyChunks = None,
    nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None,
    bCheckHostName = None,
  ):
    oSelf.fEnterFunctionOutput(oURL = oURL, sMethod = sMethod, oHTTPHeaders = oHTTPHeaders, sBody = sBody, sData = sData, asBodyChunks = asBodyChunks, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostName = bCheckHostName);
    try:
      (oRequest, oResponse) = oSelf.foGetRequestAndResponseForURL(oURL, sMethod, oHTTPHeaders, sBody, sData, asBodyChunks, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName);
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetRequestAndResponseForURL(oSelf,
    oURL,
    sMethod = None, oHTTPHeaders = None, sBody = None, sData = None, asBodyChunks = None,
    nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None,
    bCheckHostName = None,
  ):
    oSelf.fEnterFunctionOutput(oURL = oURL, sMethod = sMethod, oHTTPHeaders = oHTTPHeaders, sBody = sBody, sData = sData, asBodyChunks = asBodyChunks, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostName = bCheckHostName);
    try:
      oRequest = oSelf.foGetRequestForURL(oURL, sMethod, oHTTPHeaders, sBody, sData, asBodyChunks);
      oResponse = oSelf.foGetResponseForRequestAndURL(oRequest, oURL, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName);
      return oSelf.fxExitFunctionOutput((oRequest, oResponse));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetRequestForURL(oSelf,
    oURL,
    sMethod = None, oHTTPHeaders = None, sBody = None, sData = None, asBodyChunks = None,
  ):
    oSelf.fEnterFunctionOutput(oURL = oURL, sMethod = sMethod, oHTTPHeaders = oHTTPHeaders, sBody = sBody, sData = sData, asBodyChunks = asBodyChunks);
    try:
      if oHTTPHeaders is not None:
        for sName in ["Proxy-Authenticate", "Proxy-Authorization", "Proxy-Connection"]:
          sExistingName = oHTTPHeaders.fsGetNameCasing(sName);
          assert sExistingName is None, \
              "%s header is not implemented!" % repr(sExistingName);
      oRequest = cHTTPRequest(
        # Secure requests are made directly from the server after a CONNECT request, so the URL must be relative.
        # Non-secure requests are made to the proxy, so the URL must be absolute.
        sURL = oURL.sRelative if oURL.bSecure else oURL.sAbsolute,
        sMethod = sMethod or "GET",
        oHTTPHeaders = oHTTPHeaders,
        sBody = sBody,
        sData = sData,
        asBodyChunks = asBodyChunks,
      );
      if not oRequest.oHTTPHeaders.fbHasValue("Host"):
        oRequest.oHTTPHeaders.fbSet("Host", oURL.sHostNameAndPort);
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
      oConnection = oSelf.foGetConnectionAndStartTransaction(oURL, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostName);
      if oConnection is None:
        return oSelf.fxExitFunctionOutput(None, "No connections available; request not sent");
      oResponse = oConnection.foGetResponseForRequest(oRequest);
      oConnection.fEndTransaction();
      oSelf.__oConnectionsAvailableLock.fRelease();
      if oResponse:
        oSelf.fFireCallbacks("request sent and response received", oConnection, oRequest, oResponse);
        return oSelf.fxExitFunctionOutput(oResponse);
      return oSelf.fxExitFunctionOutput(None, "Transaction timeout or connection closed before request was sent.");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetConnectionAndStartTransaction(oSelf, oURL, nConnectTimeoutInSeconds = None, nTransactionTimeoutInSeconds = None, bCheckHostName = None, bNoSSLNegotiation = None):
    oSelf.fEnterFunctionOutput(oURL = oURL, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostName = bCheckHostName, bNoSSLNegotiation = bNoSSLNegotiation);
    try:
      if oSelf.__bStopping:
        return oSelf.fxExitFunctionOutput(None, "Stopping");
      if nConnectTimeoutInSeconds is None:
        nConnectTimeoutInSeconds = oSelf.nDefaultConnectTimeoutInSeconds;
      if nTransactionTimeoutInSeconds is None:
        nTransactionTimeoutInSeconds = oSelf.nDefaultTransactionTimeoutInSeconds;
      # We may have to wait for a connection to become available, or to be able to create a new connection. In the
      # last case, we need to know by what time we need to be connected, so we can calculate how much time we have
      # left to create a connection after waiting.
      nMaxEndConnectTime = time.clock() + nConnectTimeoutInSeconds;
      # Wait for a connection to become available or for additional connections to be possible.
      if not oSelf.__oConnectionsAvailableLock.fbAcquire(nTimeoutInSeconds = nConnectTimeoutInSeconds):
        # timeout waiting for a connection to become available or new connections to be possible.
        return oSelf.fxExitFunctionOutput(None, "Connect timeout");
      # Calculate how much time there is left to create a connection in case we have to do so.
      nRemainingConnectTimeoutInSeconds = nMaxEndConnectTime - time.clock();
      if not oURL.bSecure:
        assert not bCheckHostName, \
            "Cannot check hostname on non-secure connections";
        oConnection = oSelf.__foGetNonSecureConnectionAndStartTransaction(nRemainingConnectTimeoutInSeconds, nTransactionTimeoutInSeconds);
      else:
        oConnection = oSelf.__foGetSecureConnectionToServerAndStartTransaction(oURL.oBase, nRemainingConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bNoSSLNegotiation);
        if oConnection and bCheckHostName:
          try:
            oConnection.fCheckHostName();
          except oException:
            oConnection.fClose();
            oSelf.__oConnectionsAvailableLock.fRelease();
            raise;
      if not oConnection:
        oSelf.__oConnectionsAvailableLock.fRelease(); # We are not going to use a connection.
      return oSelf.fxExitFunctionOutput(oConnection);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def __foGetNonSecureConnectionAndStartTransaction(oSelf, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds):
    oSelf.fEnterFunctionOutput(nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds);
    try:
      nMaxEndConnectTime = time.clock() + nConnectTimeoutInSeconds;
      while time.clock() < nMaxEndConnectTime:
        # Try to find the connection that is available, or create a new connection if possible.
        oSelf.__oConnectionsLock.fbAcquire();
        try:
          for oConnection in oSelf.__aoNonSecureConnections:
            if oConnection.fbStartTransaction(nTransactionTimeoutInSeconds):
              # This connection can be reused.
              return oSelf.fxExitFunctionOutput(oConnection, "Reuse");
          # No existing connection is available, see if we can create a new one:
          if len(oSelf.__faoGetAllConnections()) < oSelf.__uMaxConnectionsToServer:
            nRemainingConnectTimeoutInSeconds = nMaxEndConnectTime - time.clock();
            oConnection = oSelf.__foCreateNewConnectionToProxyAndStartTransaction(nRemainingConnectTimeoutInSeconds, nTransactionTimeoutInSeconds);
            if not oConnection:
              return oSelf.fxExitFunctionOutput(None, "None (timeout creating a new connection).");
            return oSelf.fxExitFunctionOutput(oConnection, "New");
          # We cannot use an existing non-secure connection or create more connections, but we should be able to
          # terminate a secure connection that is not currently in use:
          for oSecureConnection in oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.values():
            if oSecureConnection.fbStartTransaction(nTransactionTimeoutInSeconds):
              break;
          else:
            return oSelf.fxExitFunctionOutput(None, "None (all connections are in use).");
        finally:
          oSelf.__oConnectionsLock.fRelease();
        # We reach this code after finding an unused secure connection and starting a transaction on it.
        # We'll close it and wait for it to terminate before trying again.
        oSecureConnection.fClose();
        oSecureConnection.fWait();
      # We've had to close connections in order to make a new one but other threads apparently created new connections
      # before we did and we were not able to create a new connection before the timeout passed.
      return oSelf.fxExitFunctionOutput(None, "None (timeout trying to create a new connection).");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foCreateNewConnectionToProxyAndStartTransaction(oSelf, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds):
    oSelf.fEnterFunctionOutput(nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds);
    try:
      # Create a new socket and return that.
      oSelf.fStatusOutput("Connecting to %s..." % oSelf.__oProxyServerURL);
      oConnection = cHTTPConnection.foConnectTo(
        sHostName = oSelf.__oProxyServerURL.sHostName,
        uPort = oSelf.__oProxyServerURL.uPort,
        oSSLContext = oSelf.__oProxyServerSSLContext,
        nConnectTimeoutInSeconds = nConnectTimeoutInSeconds,
      );
      if not oConnection:
        return oSelf.fxExitFunctionOutput(None, "Connection closed while negotiating secure connection");
      oConnection.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnection);
      oConnection.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnection);
      oConnection.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
      oSelf.__aoNonSecureConnections.append(oConnection);
      oSelf.fFireCallbacks("new connection", oConnection);
      assert oConnection.fbStartTransaction(nTransactionTimeoutInSeconds), \
          "wut!?";
      return oSelf.fxExitFunctionOutput(oConnection);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foGetSecureConnectionToServerAndStartTransaction(oSelf, oServerBaseURL, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bNoSSLNegotiation):
    oSelf.fEnterFunctionOutput(oServerBaseURL = oServerBaseURL, nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bNoSSLNegotiation = bNoSSLNegotiation);
    try:
      nMaxEndConnectTime = time.clock() + nConnectTimeoutInSeconds;
      if not bNoSSLNegotiation:
        # See if we already have a secure connection to the server and reuse that if we do:
        oSecureConnection = oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.get(oServerBaseURL.sBase);
        if oSecureConnection:
          if oSecureConnection.fbStartTransaction(nTransactionTimeoutInSeconds, bWait = True):
            return oSelf.fxExitFunctionOutput(oSecureConnection);
          else:
            return oSelf.fxExitFunctionOutput(None, "Transaction timeout while waiting for secure connection");
      # See if we have an unused non-secure connection to the proxy and use that to create a secure connection to the server:
      for oConnectionToProxy in oSelf.__aoNonSecureConnections:
        if oConnectionToProxy.fbStartTransaction(nTransactionTimeoutInSeconds):
          oSelf.__aoNonSecureConnections.remove(oConnectionToProxy);
          break;
      else:
        # See if we can create a new connection:
        if len(oSelf.__faoGetAllConnections()) < oSelf.__uMaxConnectionsToServer:
          nRemainingConnectTimeoutInSeconds = nMaxEndConnectTime - time.clock();
          oConnectionToProxy = oSelf.__foCreateNewConnectionToProxyAndStartTransaction(nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds);
        else:
          # We do not have and cannot create a secure connection to the server; return.
          return oSelf.fxExitFunctionOutput(None, "Connection to the server cannot be created");
      # We have a non-secure connection to the the proxy and we need to make it a secure connection to a server by
      # sending a CONNECT request to the proxy first and then wrap the socket in SSL.
      oConnectRequest = cHTTPRequest(
        sURL = oServerBaseURL.sAddress,
        sMethod = "CONNECT",
        oHTTPHeaders = cHTTPHeaders({
          "Host": oServerBaseURL.sAddress,
          "Connection": "Keep-Alive",
        }),
      );
      try:
        oConnectResponse = oConnectionToProxy.foGetResponseForRequest(oConnectRequest);
      except cHTTPConnection.cOutOfBandDataException:
        return oSelf.fxExitFunctionOutput(None, "The proxy sent out-of-band data before a CONNECT request could be sent.");
      except cHTTPConnection.cTransactionTimeoutException:
        return oSelf.fxExitFunctionOutput(None, "Timeout while sending a CONNECT request or waiting for a response from the proxy.");
      except cHTTPConnection.cConnectionClosedException:
        return oSelf.fxExitFunctionOutput(None, "The connection to the proxy was closed while sending a CONNECT request or waiting for a response from the proxy.");
      except iHTTPMessage.cInvalidHTTPMessageException:
        return oSelf.fxExitFunctionOutput(None, "The proxy sent an invalid response to a CONNECT request.");
      if oConnectResponse is None:
        return oSelf.fxExitFunctionOutput(None, "The connection to the proxy was closed before a CONNECT request could be sent.");
      if oConnectResponse.uStatusCode != 200:
        oConnectionToProxy.fClose();
        return oSelf.fxExitFunctionOutput(None, "The proxy did not accept our CONNECT request.");
      if not bNoSSLNegotiation:
        # Wrap the connection in SSL.
        oSSLContext = oSelf.__oCertificateStore.foGetSSLContextForClientWithHostName(oServerBaseURL.sHostName);
        try:
          oConnectionToProxy.fWrapInSSLContext(oSSLContext);
        except cHTTPConnection.cTransactionTimeoutException:
          return oSelf.fxExitFunctionOutput(None, "Transaction timeout while negotiating secure connection with proxy %s." % oConnectionToProxy.fsToString());
        except cHTTPConnection.cConnectionClosedException:
          return oSelf.fxExitFunctionOutput(None, "Connection closed while negotiating secure connection with proxy %s." % oConnectionToProxy.fsToString());
        except oSSLContext.cSSLException as oException:
          return oSelf.fxExitFunctionOutput(None, "Could not negotiate a secure connection with the client; is SSL pinning enabled? (error: %s)" % repr(oException));
      # Remember that we now have this secure connection to the server
      oSelf.__doSecureConnectionToServer_by_sProtocolHostPort[oServerBaseURL.sBase] = oConnectionToProxy;
      oSelf.fFireCallbacks("secure connection established", oConnectionToProxy, oServerBaseURL.sHostName);
      # and start using it...
      return oSelf.fxExitFunctionOutput(oConnectionToProxy);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fHandleRequestSentCallbackFromConnection(oSelf, oConnection, oRequest):
    oSelf.fFireCallbacks("request sent", oConnection, oRequest);
  
  def __fHandleResponseReceivedCallbackFromConnection(oSelf, oConnection, oReponse):
    oSelf.fFireCallbacks("response received", oConnection, oReponse);
  
  def __fHandleTerminatedCallbackFromConnection(oSelf, oConnection):
    oSelf.__oConnectionsLock.fAcquire();
    try:
      if oConnection in oSelf.__aoNonSecureConnections:
        oSelf.__aoNonSecureConnections.remove(oConnection);
      else:
        for sProtocolHostPort in oSelf.__doSecureConnectionToServer_by_sProtocolHostPort:
          if oSelf.__doSecureConnectionToServer_by_sProtocolHostPort[sProtocolHostPort] == oConnection:
            del oSelf.__doSecureConnectionToServer_by_sProtocolHostPort[sProtocolHostPort];
            break;
        else:
          raise AssertionError("A connection was terminated that we did not know exists");
      bTerminated = oSelf.__bStopping and len(oSelf.__faoGetAllConnections()) == 0 and not oSelf.__bTerminated;
    finally:
      oSelf.__oConnectionsLock.fRelease();
    oSelf.fFireCallbacks("connection terminated", oConnection);
    if bTerminated:
      oSelf.__bTerminated = True;
      oSelf.__oTerminatedLock.fRelease();
      oSelf.fFireCallbacks("terminated");
