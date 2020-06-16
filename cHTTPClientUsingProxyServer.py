import time;

from .cException import cException;
from .cHTTPClient import cHTTPClient;

from mDebugOutput import ShowDebugOutput, fShowDebugOutput;
from mMultiThreading import cLock, cWithCallbacks;
from mSSL import cCertificateStore;
from mHTTPConnections import cHTTPConnection;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

def fxFirstNonNone(*txArguments):
  for xArgument in txArguments:
    if xArgument is not None:
      return xArgument;
  return None;

class cHTTPClientUsingProxyServer(cWithCallbacks):
  uzDefaultMaxNumberOfConnectionsToServer = 10;
  nzDefaultConnectTimeoutInSeconds = 10;
  nzDefaultSecureTimeoutInSeconds = 5;
  nzDefaultTransactionTimeoutInSeconds = 10;
  
  class cHTTPProxyConnectFailedException(cException):
    pass; # The proxy server did not respond to our CONNECT request with a 200 OK.

  @ShowDebugOutput
  def __init__(oSelf,
    oProxyServerURL, ozCertificateStore = None, uzMaxNumerOfConnectionsToServer = None,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None
  ):
    oSelf.__oProxyServerURL = oProxyServerURL;
    oSelf.__oCertificateStore = ozCertificateStore or cCertificateStore();
    oSelf.__uzMaxNumerOfConnectionsToServer = uzMaxNumerOfConnectionsToServer or oSelf.uzDefaultMaxNumberOfConnectionsToServer;
    # If these arguments are provided they overwrite the static default only for this instance.
    oSelf.__nzConnectTimeoutInSeconds = fxFirstNonNone(nzConnectTimeoutInSeconds, oSelf.nzDefaultConnectTimeoutInSeconds);
    oSelf.__nzSecureTimeoutInSeconds = fxFirstNonNone(nzSecureTimeoutInSeconds, oSelf.nzDefaultSecureTimeoutInSeconds);
    oSelf.__nzTransactionTimeoutInSeconds = fxFirstNonNone(nzTransactionTimeoutInSeconds, oSelf.nzDefaultTransactionTimeoutInSeconds);

    oSelf.__oProxyServerSSLContext = oSelf.__oCertificateStore.foGetSSLContextForClientWithHostname(oProxyServerURL.sHostname) \
        if oProxyServerURL.bSecure else None;
    
    oSelf.__oWaitingForConnectionToBecomeAvailableLock = cLock(
      "%s.__oWaitingForConnectionToBecomeAvailableLock" % oSelf.__class__.__name__,
    );
    
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      nzDeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__aoNonSecureConnections = [];
    oSelf.__doSecureConnectionToServer_by_sProtocolHostPort = {};
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );
    
    oSelf.fAddEvents("new connection", "request sent", "response received", "request sent and response received", "secure connection established", "connection terminated", "terminated");
  
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  
  def foGetProxyServerURL(oSelf):
    return oSelf.__oProxyServerURL.foClone();
  
  def __faoGetAllConnections(oSelf):
    return oSelf.__aoNonSecureConnections + oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.values();

  def __fuCountAllConnections(oSelf):
    return len(oSelf.__aoNonSecureConnections) + len(oSelf.__doSecureConnectionToServer_by_sProtocolHostPort);
  
  @ShowDebugOutput
  def fStop(oSelf):
    if oSelf.bTerminated:
      return fShowDebugOutput("Already terminated.");
    if oSelf.__bStopping:
      return fShowDebugOutput("Already stopping.");
    fShowDebugOutput("Stopping...");
    oSelf.__bStopping = True;
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      aoConnections = oSelf.__faoGetAllConnections();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    fShowDebugOutput("Stopping connections to proxy server...");
    for oConnection in aoConnections:
      oConnection.fStop();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    # We'll run through all the steps no matter what.
    if oSelf.bTerminated:
      fShowDebugOutput("Already terminated.");
      return True;
    oSelf.__bStopping = True;
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      aoConnections = oSelf.__faoGetAllConnections();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    for oConnection in aoConnections:
      fShowDebugOutput("Terminating connection to proxy server %s..." % oConnection);
      oConnection.fTerminate();
  
  @ShowDebugOutput
  def fWait(oSelf):
    return oSelf.__oTerminatedLock.fWait();
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  @ShowDebugOutput
  def fozGetResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = False,
  ):
    oRequest = oSelf.foGetRequestForURL(oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks);
    ozResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest, oURL,
      nzConnectTimeoutInSeconds, nzSecureTimeoutInSeconds, nzTransactionTimeoutInSeconds,
      bCheckHostname
    );
    return ozResponse;
  
  @ShowDebugOutput
  def ftozGetRequestAndResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = None,
  ):
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return (None, None);
    oRequest = oSelf.foGetRequestForURL(oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks);
    ozResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest,
      oURL,
      nzConnectTimeoutInSeconds, nzSecureTimeoutInSeconds, nzTransactionTimeoutInSeconds,
      bCheckHostname = bCheckHostname
    );
    return (oRequest, ozResponse);
  
  @ShowDebugOutput
  def foGetRequestForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
  ):
    if ozHeaders is not None:
      for sName in ["Proxy-Authenticate", "Proxy-Authorization", "Proxy-Connection"]:
        ozHeader = oHeaders.fozGetUniqueHeaderForName(sName);
        assert ozHeader is None, \
            "%s header is not implemented!" % repr(ozHeader.sName);
    oRequest = cHTTPConnection.cHTTPRequest(
      # Secure requests are made directly from the server after a CONNECT request, so the URL must be relative.
      # Non-secure requests are made to the proxy, so the URL must be absolute.
      sURL = oURL.sRelative if oURL.bSecure else oURL.sAbsolute,
      szMethod = szMethod,
      szVersion = szVersion,
      ozHeaders = ozHeaders,
      szBody = szBody,
      szData = szData,
      azsBodyChunks = azsBodyChunks,
    );
    if not oRequest.oHeaders.fozGetUniqueHeaderForName("Host"):
      oRequest.oHeaders.foAddHeaderForNameAndValue("Host", oURL.sHostnameAndPort);
    return oRequest;
  
  @ShowDebugOutput
  def fozGetResponseForRequestAndURL(oSelf,
    oRequest, oURL,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = False,
  ):
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    nzConnectTimeoutInSeconds = fxFirstNonNone(nzConnectTimeoutInSeconds, oSelf.__nzConnectTimeoutInSeconds);
    nzSecureTimeoutInSeconds = fxFirstNonNone(nzSecureTimeoutInSeconds, oSelf.__nzSecureTimeoutInSeconds);
    nzTransactionTimeoutInSeconds = fxFirstNonNone(nzTransactionTimeoutInSeconds, oSelf.__nzTransactionTimeoutInSeconds);
    oConnection = oSelf.__fozGetConnectionAndStartTransaction(
      oURL,
      nzConnectTimeoutInSeconds, nzSecureTimeoutInSeconds, nzTransactionTimeoutInSeconds,
      bCheckHostname = bCheckHostname
    );# oConnection can be None if we are stopping!
    if oSelf.__bStopping:
      return None;
    assert oConnection, \
        "Expected a connection but got %s" % repr(oConnection);
    oResponse = oConnection.fozSendRequestAndReceiveResponse(oRequest, bStartTransaction = False);
    if oResponse:
      oSelf.fFireCallbacks("request sent and response received", oConnection, oRequest, oResponse);
    return oResponse;
  
  @ShowDebugOutput
  def __fozGetConnectionAndStartTransaction(oSelf,
    oURL,
    nzConnectTimeoutInSeconds = None, nzSecureTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bCheckHostname = False,
    bNoSSLNegotiation = False,
  ):
    if not oURL.bSecure:
      assert not bCheckHostname, \
          "Cannot check hostname on non-secure connections";
      oConnection = oSelf.__fozGetNonSecureConnectionToProxyAndStartTransaction(
        nzConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds,
      ); # oConnection can be None if we are stopping!
    else:
      oConnection = oSelf.__fozGetSecureConnectionToServerAndStartTransaction(
        oURL.oBase,
        nzConnectTimeoutInSeconds, nzSecureTimeoutInSeconds, nzTransactionTimeoutInSeconds,
        bNoSSLNegotiation,
      );# oConnection can be None if we are stopping!
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert oConnection, \
        "Expected a connection but got %s" % repr(oConnection);
    if bCheckHostname and oURL.bSecure:
      try:
        oConnection.fCheckHostname();
      except Exception as oException:
        oConnection.fDisconnect();
        oConnection = None;
        raise;
    return oConnection;
  
  @ShowDebugOutput
  def __fozReuseConnectionToProxyAndStartTransaction(oSelf, nzTransactionTimeoutInSeconds):
    oSelf.__oPropertyAccessTransactionLock.fbAcquire();
    try:
      # Try to find the non-secure connection that is available:
      for oConnection in oSelf.__aoNonSecureConnections:
        if oConnection.fbStartTransaction(nzTransactionTimeoutInSeconds):
          # This connection can be reused.
          fShowDebugOutput("Reusing existing connection to proxy: %s" % repr(oConnection));
          return oConnection;
      return None;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
  
  @ShowDebugOutput
  def __fbTerminateAnIdleSecureConnection(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fbAcquire();
    try:
      # Try to find the secure connection that is idle:
      for ozIdleSecureConnection in oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.values():
        if ozIdleSecureConnection.fbStartTransaction(0):
          # This connection is idle so it can be disconnected.
          break;
      else:
        return False;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    ozIdleSecureConnection.fDisconnect();
    return True;
  
  @ShowDebugOutput
  def __fozGetNonSecureConnectionToProxyAndStartTransaction(oSelf,
    nzConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds
  ):
    # Try to reuse a non-secure connection if possible:
    oConnection = oSelf.__fozReuseConnectionToProxyAndStartTransaction(nzTransactionTimeoutInSeconds);
    if oConnection:
      fShowDebugOutput("Existing connectiong to proxy reused: %s." % repr(oConnection));
      return oConnection;
    # Try to create a new connection if possible:
    if (
      oSelf.__uzMaxNumerOfConnectionsToServer is not None
      or oSelf.__fuCountAllConnections() < oSelf.__uzMaxNumerOfConnectionsToServer
    ):
      oConnection = oSelf.__fozCreateNewNonSecureConnectionToProxyAndStartTransaction(
        nzConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds
      ); # oConnection can be None if we are stopping!
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert oConnection, \
          "Expected a connection but got %s" % oConnection;
      fShowDebugOutput("New connectiong to proxy created: %s." % repr(oConnection));
      return oConnection;
    # Wait until we can start a transaction on any of the existing connections,
    # i.e. the conenction is idle:
    fShowDebugOutput("Maximum number of connections to proxy reached; waiting for a connection to become idle...");
    nzConnectEndTime = time.time() + nzConnectTimeoutInSeconds if nzConnectTimeoutInSeconds is not None else None;
    # Since we want multiple thread to wait in turn, use a lock to allow only one
    # thread to enter the next block of code at a time.
    if not oSelf.__oWaitingForConnectionToBecomeAvailableLock.fbAcquire(nzConnectTimeoutInSeconds):
      # Another thread was waiting first and we timed out before a connection became available.
      raise cHTTPConnection.cMaxConnectionsReachedException(
        "Maximum number of active connections reached and all existing connections are busy.",
      );
    try:
      # Wait until transactions can be started on one or more of the existing connections:
      aoConnectionsWithStartedTransactions = cHTTPConnection.faoWaitUntilTransactionsCanBeStartedAndStartTransactions(
        oSelf.__faoGetAllConnections(),
        nzConnectTimeoutInSeconds,
      );
      if not aoConnectionsWithStartedTransactions:
        # We timed out before a connection became available.
        raise cHTTPConnection.cMaxConnectionsReachedException(
          "Maximum number of active connections reached and all existing connections are busy.",
        );
      # If one of the available connections is a non-secure connection, reuse it:
      for oConnection in aoConnectionsWithStartedTransactions:
        if oConnection in oSelf.__aoNonSecureConnections:
          # End the transactions that we started on all other connections.
          for oOtherConnection in aoConnectionsWithStartedTransactions:
            if oOtherConnection != oConnection:
              oOtherConnection.fEndTransaction();
          # return the connection that can be reused.
          return oConnection;
      # There are only secure connections; terminate the first one and end the transaction on the others.
      for oSecureConnection in aoAvailableConnectionsWithStartedTransactions:
        if oSecureConnection == aoAvailableConnectionsWithStartedTransactions[0]:
          oSecureConnection.fDisconnect();
        else:
          oSecureConnection.fEndTransaction();
      # Create a new connection
      nzRemainingConnectTimeoutInSeconds = nzMaxEndConnectTime - time.time() if nzMaxEndConnectTime is not None else None;
      oConnection = oSelf.__fozCreateNewNonSecureConnectionToProxyAndStartTransaction(
        nzRemainingConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds
      ); # oConnection can be None if we are stopping!
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert oConnection, \
          "Expected a connection but got %s" % oConnection;
      fShowDebugOutput("New connectiong to proxy created: %s." % repr(oConnection));
      return oConnection;
    finally:
      oSelf.__oWaitingForConnectionToBecomeAvailableLock.fRelease(nzConnectTimeoutInSeconds);
  
  @ShowDebugOutput
  def __fozCreateNewNonSecureConnectionToProxyAndStartTransaction(oSelf,
    nzConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds
  ):
    # Create a new socket and return that.
    fShowDebugOutput("Connecting to %s..." % oSelf.__oProxyServerURL);
    oConnection = cHTTPConnection.foConnectTo(
      sHostname = oSelf.__oProxyServerURL.sHostname,
      uPort = oSelf.__oProxyServerURL.uPort,
      nzConnectTimeoutInSeconds = nzConnectTimeoutInSeconds,
    );
    assert oConnection, \
        "Expected connection but got %s" % oConnection;
    oConnection.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnection);
    oConnection.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnection);
    oConnection.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
    assert oConnection.fbStartTransaction(nzTransactionTimeoutInSeconds), \
        "Cannot start a transaction on a new connection (%s)" % repr(oConnection);
    oSelf.__aoNonSecureConnections.append(oConnection);
    oSelf.fFireCallbacks("new connection", oConnection);
    return oConnection;
  
  @ShowDebugOutput
  def __fozGetSecureConnectionToServerAndStartTransaction(oSelf,
    oServerBaseURL,
    nzConnectTimeoutInSeconds, nzSecureTimeoutInSeconds, nzTransactionTimeoutInSeconds,
    bNoSSLNegotiation
  ):
    nzMaxEndConnectTime = time.time() + nzConnectTimeoutInSeconds if nzConnectTimeoutInSeconds is not None else None;
    if not bNoSSLNegotiation:
      # See if we already have a secure connection to the server that is not in use and reuse that if we do:
      ozSecureConnection = oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.get(oServerBaseURL.sBase);
      if ozSecureConnection:
        assert ozSecureConnection.fbStartTransaction(nzTransactionTimeoutInSeconds), \
            "Cannot start a transaction on an existing secure connection to the server (%s)" % repr(ozSecureConnection);
        fShowDebugOutput("Reusing existing connection");
        return ozSecureConnection;
    nzRemainingConnectTimeoutInSeconds = nzMaxEndConnectTime - time.time() if nzMaxEndConnectTime is not None else None;
    oConnectionToProxy = oSelf.__fozGetNonSecureConnectionToProxyAndStartTransaction(
      nzRemainingConnectTimeoutInSeconds, nzTransactionTimeoutInSeconds
    ); # oConnectionToProxy can be None if we are stopping
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert oConnectionToProxy, \
        "Expected a connection but got %s" % oConnectionToProxy;
    # We have a non-secure connection to the the proxy and we need to make it a secure connection to a server by
    # sending a CONNECT request to the proxy first and then wrap the socket in SSL.
    oConnectRequest = cHTTPConnection.cHTTPRequest(
      sURL = oServerBaseURL,
      szMethod = "CONNECT",
      ozHeaders = cHTTPConnection.cHTTPRequest.cHTTPHeaders.foFromDict({
        "Host": oServerBaseURL.sAddress,
        "Connection": "Keep-Alive",
      }),
    );
    oConnectResponse = oConnectionToProxy.fozSendRequestAndReceiveResponse(oConnectRequest, bStartTransaction = False);
    # oConnectResponse can be None if we are stopping.
    if oSelf.__bStopping:
      return None;
    assert oConnectResponse, \
        "Expected a CONNECT response but got %s" % oConnectResponse;
    if oConnectResponse.uStatusCode != 200:
      # I am not entirely sure if we can trust the connection after this, so let's close it to prevent issues:
      assert oConnectionToProxy.fbStartTransaction(), \
          "Cannot start a transaction!?";
      oConnectionToProxy.fDisconnect();
      raise oSelf.cHTTPProxyConnectFailedException(
        "The proxy did not accept our CONNECT request.",
        {"oConnectRequest": oConnectRequest, "oConnectResponse": oConnectResponse},
      );
    if bNoSSLNegotiation:
      fShowDebugOutput("No SSL negotiation initiated!");
    else:
      fShowDebugOutput("Starting SSL negotiation...");
      # Wrap the connection in SSL.
      oSSLContext = oSelf.__oCertificateStore.foGetSSLContextForClientWithHostname(oServerBaseURL.sHostname);
      oConnectionToProxy.fSecure(oSSLContext, bCheckHostname = True, nzTimeoutInSeconds = nzSecureTimeoutInSeconds);
    # Remember that we now have this secure connection to the server
    oSelf.__aoNonSecureConnections.remove(oConnectionToProxy);
    oSelf.__doSecureConnectionToServer_by_sProtocolHostPort[oServerBaseURL.sBase] = oConnectionToProxy;
    oSelf.fFireCallbacks("secure connection established", oConnectionToProxy, oServerBaseURL.sHostname);
    # and start using it...
    assert oConnectionToProxy.fbStartTransaction(nzTransactionTimeoutInSeconds), \
        "Cannot start a connection on a newly created connection?";
    return oConnectionToProxy;
  
  def __fHandleRequestSentCallbackFromConnection(oSelf, oConnection, oRequest):
    oSelf.fFireCallbacks("request sent", oConnection, oRequest);
  
  def __fHandleResponseReceivedCallbackFromConnection(oSelf, oConnection, oReponse):
    oSelf.fFireCallbacks("response received", oConnection, oReponse);
  
  def __fHandleTerminatedCallbackFromConnection(oSelf, oConnection):
    oSelf.fFireCallbacks("connection terminated", oConnection);
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oConnection in oSelf.__aoNonSecureConnections:
        oSelf.__aoNonSecureConnections.remove(oConnection);
      else:
        for sProtocolHostPort in oSelf.__doSecureConnectionToServer_by_sProtocolHostPort:
          if oSelf.__doSecureConnectionToServer_by_sProtocolHostPort[sProtocolHostPort] == oConnection:
            del oSelf.__doSecureConnectionToServer_by_sProtocolHostPort[sProtocolHostPort];
            break;
        else:
          raise AssertionError("A secure connection was terminated that we did not know exists (unknown: %s, known: %s)" % \
              (oConnection, ", ".join([
                str(oKnownConnection) for oKnownConnection in oSelf.__doSecureConnectionToServer_by_sProtocolHostPort.items()
              ])));
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oSelf.__fCheckTerminated();
  
  def __fCheckTerminated(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if not oSelf.__bStopping:
        return;
      if oSelf.__aoNonSecureConnections:
        return;
      if oSelf.__doSecureConnectionToServer_by_sProtocolHostPort:
        return;
      if oSelf.bTerminated:
        return;
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oSelf.fFireCallbacks("terminated");
