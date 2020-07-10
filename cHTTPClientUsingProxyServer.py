import time;

try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mMultiThreading import cLock, cWithCallbacks;
from mHTTPConnections import cHTTPConnection, cHTTPRequest, cHTTPHeaders;
try: # SSL support is optional.
  from mSSL import cCertificateStore as czCertificateStore;
except:
  czCertificateStore = None; # No SSL support

from .mExceptions import *;

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
  uzDefaultMaxNumberOfConnectionsToProxy = 10;
  nzDefaultConnectToProxyTimeoutInSeconds = 10;
  nzDefaultSecureConnectionToProxyTimeoutInSeconds = 5;
  nzDefaultSecureConnectionToServerTimeoutInSeconds = 5;
  nzDefaultTransactionTimeoutInSeconds = 10;
  
  @ShowDebugOutput
  def __init__(oSelf,
    oProxyServerURL,
    bAllowUnverifiableCertificatesForProxy = False, bCheckProxyHostname = True,
    ozCertificateStore = None, uzMaxNumerOfConnectionsToProxy = None,
    nzConnectToProxyTimeoutInSeconds = None, nzSecureConnectionToProxyTimeoutInSeconds = None,
    nzSecureConnectionToServerTimeoutInSeconds = None, nzTransactionTimeoutInSeconds = None,
    bAllowUnverifiableCertificates = False, bCheckHostname = True,
  ):
    oSelf.__oProxyServerURL = oProxyServerURL;
    oSelf.__bAllowUnverifiableCertificatesForProxy = bAllowUnverifiableCertificatesForProxy;
    oSelf.__bCheckProxyHostname = bCheckProxyHostname;
    
    oSelf.__ozCertificateStore = (
      ozCertificateStore if ozCertificateStore else
      czCertificateStore() if czCertificateStore else
      None
    );
    assert not oProxyServerURL.bSecure or oSelf.__ozCertificateStore, \
        "Cannot use a secure proxy without the mSSL module!";
    oSelf.__uzMaxNumerOfConnectionsToProxy = uzMaxNumerOfConnectionsToProxy or oSelf.uzDefaultMaxNumberOfConnectionsToProxy;
    # Timeouts for this instance default to the timeouts specified for the class.
    oSelf.__nzConnectToProxyTimeoutInSeconds = fxFirstNonNone(nzConnectToProxyTimeoutInSeconds, oSelf.nzDefaultConnectToProxyTimeoutInSeconds);
    oSelf.__nzSecureConnectionToProxyTimeoutInSeconds = fxFirstNonNone(nzSecureConnectionToProxyTimeoutInSeconds, oSelf.nzDefaultSecureConnectionToProxyTimeoutInSeconds);
    oSelf.__nzSecureConnectionToServerTimeoutInSeconds = fxFirstNonNone(nzSecureConnectionToServerTimeoutInSeconds, oSelf.nzDefaultSecureConnectionToServerTimeoutInSeconds);
    oSelf.__nzTransactionTimeoutInSeconds = fxFirstNonNone(nzTransactionTimeoutInSeconds, oSelf.nzDefaultTransactionTimeoutInSeconds);
    oSelf.__bAllowUnverifiableCertificates = bAllowUnverifiableCertificates;
    oSelf.__bCheckHostname = bCheckHostname;

    oSelf.__ozProxySSLContext = (
      oSelf.__ozCertificateStore.foGetClientsideSSLContextWithoutVerification() \
      if bAllowUnverifiableCertificatesForProxy else 
      oSelf.__ozCertificateStore.foGetClientsideSSLContextForHostname(
        oProxyServerURL.sHostname,
        oSelf.__bCheckProxyHostname,
      )
    ) if oProxyServerURL.bSecure else None;
    
    oSelf.__oWaitingForConnectionToBecomeAvailableLock = cLock(
      "%s.__oWaitingForConnectionToBecomeAvailableLock" % oSelf.__class__.__name__,
    );
    
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      nzDeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__aoConnectionsToProxyNotConnectedToAServer = [];
    oSelf.__doConnectionToProxyUsedForSecureConnectionToServer_by_sProtocolHostPort = {};
    oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort = {};
    
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
    return oSelf.__aoConnectionsToProxyNotConnectedToAServer + oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.values();

  def __fuCountAllConnections(oSelf):
    return len(oSelf.__aoConnectionsToProxyNotConnectedToAServer) + len(oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort);
  
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
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    oRequest = oSelf.foGetRequestForURL(
      oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks,
    );
    ozResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest, oURL, uzMaximumNumberOfChunksBeforeDisconnecting,
    );
    return ozResponse;
  
  @ShowDebugOutput
  def ftozGetRequestAndResponseForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return (None, None);
    oRequest = oSelf.foGetRequestForURL(
      oURL, szMethod, szVersion, ozHeaders, szBody, szData, azsBodyChunks
    );
    ozResponse = oSelf.fozGetResponseForRequestAndURL(
      oRequest, oURL, uzMaximumNumberOfChunksBeforeDisconnecting
    );
    return (oRequest, ozResponse);
  
  @ShowDebugOutput
  def foGetRequestForURL(oSelf,
    oURL,
    szMethod = None, szVersion = None, ozHeaders = None, szBody = None, szData = None, azsBodyChunks = None,
    ozAdditionalHeaders = None, bAutomaticallyAddContentLengthHeader = False
  ):
    if ozHeaders is not None:
      for sName in ["Proxy-Authenticate", "Proxy-Authorization", "Proxy-Connection"]:
        ozHeader = oHeaders.fozGetUniqueHeaderForName(sName);
        assert ozHeader is None, \
            "%s header is not implemented!" % repr(ozHeader.sName);
    oRequest = cHTTPRequest(
      # Secure requests are made directly from the server after a CONNECT request, so the URL must be relative.
      # Non-secure requests are made to the proxy, so the URL must be absolute.
      sURL = oURL.sRelative if oURL.bSecure else oURL.sAbsolute,
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
    uzMaximumNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    if not oURL.bSecure:
      ozConnection = oSelf.__fozGetUnusedConnectionToProxyAndStartTransaction();
    else:
      ozConnection = oSelf.__fozGetUnusedSecureConnectionToServerThroughProxyAndStartTransaction(
        oURL.oBase,
      );
    if oSelf.__bStopping:
      return None;
    assert ozConnection, \
        "Expected a connection but got %s" % repr(ozConnection);
    oResponse = ozConnection.fozSendRequestAndReceiveResponse(
      oRequest,
      bStartTransaction = False,
      uzMaximumNumberOfChunksBeforeDisconnecting = uzMaximumNumberOfChunksBeforeDisconnecting,
    );
    if oResponse:
      oSelf.fFireCallbacks("request sent and response received", ozConnection, oRequest, oResponse);
    return oResponse;
  
  @ShowDebugOutput
  def __fozReuseUnusedConnectionToProxyAndStartTransaction(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fbAcquire();
    try:
      # Try to find the non-secure connection that is available:
      for oConnection in oSelf.__aoConnectionsToProxyNotConnectedToAServer:
        if oConnection.fbStartTransaction(oSelf.__nzTransactionTimeoutInSeconds):
          # This connection can be reused.
          fShowDebugOutput("Reusing existing connection to proxy: %s" % repr(oConnection));
          return oConnection;
      return None;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
  
  @ShowDebugOutput
  def __fbTerminateAnIdleSecureConnectionToServerThroughProxy(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fbAcquire();
    try:
      # Try to find the secure connection that is idle:
      for ozIdleSecureConnection in oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.values():
        if ozIdleSecureConnection.fbStartTransaction(0):
          break;
      else:
        return False;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    ozIdleSecureConnection.fDisconnect();
    return True;
  
  @ShowDebugOutput
  def __fozGetUnusedConnectionToProxyAndStartTransaction(oSelf):
    # Try to reuse a non-secure connection if possible:
    ozConnection = oSelf.__fozReuseUnusedConnectionToProxyAndStartTransaction();
    if ozConnection:
      fShowDebugOutput("Existing connectiong to proxy reused: %s." % repr(ozConnection));
      return ozConnection;
    # Try to create a new connection if possible:
    if (
      oSelf.__uzMaxNumerOfConnectionsToProxy is not None
      or oSelf.__fuCountAllConnections() < oSelf.__uzMaxNumerOfConnectionsToProxy
    ):
      ozConnection = oSelf.__fozCreateNewConnectionToProxyAndStartTransaction(
        nzConnectTimeoutInSeconds = oSelf.__nzConnectToProxyTimeoutInSeconds,
      );
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert ozConnection, \
          "Expected a connection but got %s" % ozConnection;
      fShowDebugOutput("New connectiong to proxy created: %s." % repr(ozConnection));
      return ozConnection;
    # Wait until we can start a transaction on any of the existing connections,
    # i.e. the conenction is idle:
    fShowDebugOutput("Maximum number of connections to proxy reached; waiting for a connection to become idle...");
    nzConnectEndTime = time.clock() + oSelf.__nzConnectToProxyTimeoutInSeconds if oSelf.__nzConnectToProxyTimeoutInSeconds is not None else None;
    # Since we want multiple thread to wait in turn, use a lock to allow only one
    # thread to enter the next block of code at a time.
    if not oSelf.__oWaitingForConnectionToBecomeAvailableLock.fbAcquire(oSelf.__nzConnectToProxyTimeoutInSeconds):
      # Another thread was waiting first and we timed out before a connection became available.
      raise cMaxConnectionsReachedException(
        "Maximum number of active connections reached and all existing connections are busy.",
      );
    try:
      # Wait until transactions can be started on one or more of the existing connections:
      nzRemainingConnectToProxyTimeoutInSeconds = nzConnectEndTime - time.clock() if nzConnectEndTime is not None else None;
      aoConnectionsWithStartedTransactions = cHTTPConnection.faoWaitUntilTransactionsCanBeStartedAndStartTransactions(
        aoConnections = oSelf.__faoGetAllConnections(),
        nzTimeoutInSeconds = nzRemaingingConnectToProxyTimeoutInSeconds,
      );
      if not aoConnectionsWithStartedTransactions:
        # We timed out before a connection became available.
        raise cMaxConnectionsReachedException(
          "Maximum number of active connections reached and all existing connections are busy.",
        );
      # If one of the available connections is a non-secure connection, reuse it:
      for oConnection in aoConnectionsWithStartedTransactions:
        if oConnection in oSelf.__aoConnectionsToProxyNotConnectedToAServer:
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
      nzRemainingConnectToProxyTimeoutInSeconds = nzConnectEndTime - time.clock() if nzConnectEndTime is not None else None;
      ozConnection = oSelf.__fozCreateNewConnectionToProxyAndStartTransaction(
        nzConnectTimeoutInSeconds = nzRemainingConnectToProxyTimeoutInSeconds,
      );
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert ozConnection, \
          "Expected a connection but got %s" % ozConnection;
      fShowDebugOutput("New connectiong to proxy created: %s." % repr(ozConnection));
      return oConnection;
    finally:
      oSelf.__oWaitingForConnectionToBecomeAvailableLock.fRelease();
  
  @ShowDebugOutput
  def __fozCreateNewConnectionToProxyAndStartTransaction(oSelf,
    # The connect timeout can be less than oSelf.__nzConnectTimeoutInSeconds 
    # because we may have already have to wait for another connection to be
    # closed if we had reached the maximum number of connections.
    nzConnectTimeoutInSeconds, 
  ):
    # Create a new socket and return that.
    fShowDebugOutput("Connecting to %s..." % oSelf.__oProxyServerURL);
    oConnection = cHTTPConnection.foConnectTo(
      sHostname = oSelf.__oProxyServerURL.sHostname,
      uPort = oSelf.__oProxyServerURL.uPort,
      nzConnectTimeoutInSeconds = nzConnectTimeoutInSeconds,
      ozSSLContext = oSelf.__ozProxySSLContext,
      nzSecureTimeoutInSeconds = oSelf.__nzSecureConnectionToProxyTimeoutInSeconds,
    );
    assert oConnection, \
        "Expected connection but got %s" % oConnection;
    oConnection.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnection);
    oConnection.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnection);
    oConnection.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
    assert oConnection.fbStartTransaction(oSelf.__nzTransactionTimeoutInSeconds), \
        "Cannot start a transaction on a new connection (%s)" % repr(oConnection);
    oSelf.__aoConnectionsToProxyNotConnectedToAServer.append(oConnection);
    oSelf.fFireCallbacks("new connection", oConnection);
    return oConnection;
  
  @ShowDebugOutput
  def __fozGetUnusedSecureConnectionToServerThroughProxyAndStartTransaction(oSelf, oServerBaseURL):
    # See if we already have a secure connection to the server that is not in use and reuse that if we do:
    ozSecureConnection = oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.get(oServerBaseURL.sBase);
    if ozSecureConnection:
      assert ozSecureConnection.fbStartTransaction(oSelf.__nzTransactionTimeoutInSeconds), \
          "Cannot start a transaction on an existing secure connection to the server (%s)" % repr(ozSecureConnection);
      fShowDebugOutput("Reusing existing connection");
      return ozSecureConnection;
    ozConnectionToProxy = oSelf.__fozGetUnusedConnectionToProxyAndStartTransaction();
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert ozConnectionToProxy, \
        "Expected a connection but got %s" % ozConnectionToProxy;
    # We have a non-secure connection to the the proxy and we need to make it a secure connection to a server by
    # sending a CONNECT request to the proxy first and then wrap the socket in SSL.
    oConnectRequest = cHTTPRequest(
      sURL = oServerBaseURL,
      szMethod = "CONNECT",
      ozHeaders = cHTTPHeaders.foFromDict({
        "Host": oServerBaseURL.sAddress,
        "Connection": "Keep-Alive",
      }),
    );
    ozConnectResponse = ozConnectionToProxy.fozSendRequestAndReceiveResponse(oConnectRequest, bStartTransaction = False);
    # oConnectResponse can be None if we are stopping.
    if oSelf.__bStopping:
      return None;
    assert ozConnectResponse, \
        "Expected a CONNECT response but got %s" % ozConnectResponse;
    if ozConnectResponse.uStatusCode != 200:
      # I am not entirely sure if we can trust the connection after this, so let's close it to prevent issues:
      assert ozConnectionToProxy.fbStartTransaction(), \
          "Cannot start a transaction!?";
      ozConnectionToProxy.fDisconnect();
      raise cHTTPProxyConnectFailedException(
        "The proxy did not accept our CONNECT request.",
        {"oConnectRequest": oConnectRequest, "oConnectResponse": ozConnectResponse},
      );
    oConnectionToServerThroughProxy = ozConnectionToProxy; # More reasonable name at this point.
    fShowDebugOutput("Starting SSL negotiation...");
    # Wrap the connection in SSL.
    oSSLContext = (
      oSelf.__ozCertificateStore.foGetClientsideSSLContextWithoutVerification()
      if oSelf.__bAllowUnverifiableCertificates else
      oSelf.__ozCertificateStore.foGetClientsideSSLContextForHostname(
        oServerBaseURL.sHostname,
        oSelf.__bCheckHostname
      )
    );
    oConnectionToServerThroughProxy.fSecure(
      oSSLContext = oSSLContext,
      nzTimeoutInSeconds = oSelf.__nzSecureConnectionToServerTimeoutInSeconds
    );
    # Remember that we now have this secure connection to the server
    oSelf.__aoConnectionsToProxyNotConnectedToAServer.remove(ozConnectionToProxy);
    oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort[oServerBaseURL.sBase] = oConnectionToServerThroughProxy;
    oSelf.fFireCallbacks("secure connection established", oConnectionToServerThroughProxy, oServerBaseURL.sHostname);
    # and start using it...
    assert oConnectionToServerThroughProxy.fbStartTransaction(oSelf.__nzTransactionTimeoutInSeconds), \
        "Cannot start a connection on a newly created connection?";
    return oConnectionToServerThroughProxy;
  
  def __fHandleRequestSentCallbackFromConnection(oSelf, oConnection, oRequest):
    oSelf.fFireCallbacks("request sent", oConnection, oRequest);
  
  def __fHandleResponseReceivedCallbackFromConnection(oSelf, oConnection, oReponse):
    oSelf.fFireCallbacks("response received", oConnection, oReponse);
  
  def __fHandleTerminatedCallbackFromConnection(oSelf, oConnection):
    oSelf.fFireCallbacks("connection terminated", oConnection);
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oConnection in oSelf.__aoConnectionsToProxyNotConnectedToAServer:
        oSelf.__aoConnectionsToProxyNotConnectedToAServer.remove(oConnection);
      else:
        for sProtocolHostPort in oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort:
          if oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort[sProtocolHostPort] == oConnection:
            del oSelf.__doConnectionToProxyUsedForSecureConnectionToServer_by_sProtocolHostPort[sProtocolHostPort];
            del oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort[sProtocolHostPort];
            break;
        else:
          raise AssertionError("A secure connection was terminated that we did not know exists (unknown: %s, known: %s)" % \
              (oConnection, ", ".join([
                str(oKnownConnection) for oKnownConnection in oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.items()
              ])));
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oSelf.__fCheckTerminated();
  
  def __fCheckTerminated(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if not oSelf.__bStopping:
        return;
      if oSelf.__aoConnectionsToProxyNotConnectedToAServer:
        return;
      if oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort:
        return;
      if oSelf.bTerminated:
        return;
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oSelf.fFireCallbacks("terminated");
