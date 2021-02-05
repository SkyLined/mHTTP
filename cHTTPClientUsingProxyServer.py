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
from mNotProvided import *;
try: # SSL support is optional.
  from mSSL import cCertificateStore as c0CertificateStore;
except:
  c0CertificateStore = None; # No SSL support

from .iHTTPClient import iHTTPClient;
from .mExceptions import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cHTTPClientUsingProxyServer(iHTTPClient, cWithCallbacks):
  # Some sane limitation on the number of connections to the proxy makes sense, to reduce the risk of a bug in the
  # code causing an excessive number of connections to be made:
  u0DefaultMaxNumberOfConnectionsToProxy = 10;
  # The following defaults can be used to override the defaults from the mHTTPConnections classes.
  # If they are set to `zNotProvided`, the defaults from the mHTTPConnections classes will be used.
  n0zDefaultConnectToProxyTimeoutInSeconds = zNotProvided;
  n0zDefaultSecureConnectionToProxyTimeoutInSeconds = zNotProvided;
  n0zDefaultSecureConnectionToServerTimeoutInSeconds = zNotProvided;
  # There is no default transaction timeout in the mHTTPConnections classes, so this cannot be zNotProvided.
  n0DefaultTransactionTimeoutInSeconds = 10;
  
  @ShowDebugOutput
  def __init__(oSelf,
    oProxyServerURL,
    bAllowUnverifiableCertificatesForProxy = False, bCheckProxyHostname = True,
    o0zCertificateStore = zNotProvided,
    u0zMaxNumberOfConnectionsToProxy = zNotProvided,
    n0zConnectToProxyTimeoutInSeconds = zNotProvided,
    n0zSecureConnectionToProxyTimeoutInSeconds = zNotProvided,
    n0zSecureConnectionToServerTimeoutInSeconds = zNotProvided,
    n0zTransactionTimeoutInSeconds = zNotProvided,
    bAllowUnverifiableCertificates = False,
    bCheckHostname = True,
  ):
    oSelf.oProxyServerURL = oProxyServerURL;
    oSelf.__bAllowUnverifiableCertificatesForProxy = bAllowUnverifiableCertificatesForProxy;
    oSelf.__bCheckProxyHostname = bCheckProxyHostname;
    
    oSelf.__o0CertificateStore = (
      o0zCertificateStore if fbIsProvided(o0zCertificateStore) else
      c0CertificateStore() if c0CertificateStore is not None else
      None
    );
    assert not oProxyServerURL.bSecure or oSelf.__o0CertificateStore, \
        "Cannot use a secure proxy without the mSSL module!";
    oSelf.__u0MaxNumberOfConnectionsToProxy = fxGetFirstProvidedValue(u0zMaxNumberOfConnectionsToProxy, oSelf.u0DefaultMaxNumberOfConnectionsToProxy);
    # Timeouts for this instance default to the timeouts specified for the class.
    oSelf.__n0zConnectToProxyTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zConnectToProxyTimeoutInSeconds, oSelf.n0zDefaultConnectToProxyTimeoutInSeconds);
    oSelf.__n0zSecureConnectionToProxyTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureConnectionToProxyTimeoutInSeconds, oSelf.n0zDefaultSecureConnectionToProxyTimeoutInSeconds);
    oSelf.__n0zSecureConnectionToServerTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureConnectionToServerTimeoutInSeconds, oSelf.n0zDefaultSecureConnectionToServerTimeoutInSeconds);
    oSelf.__n0TransactionTimeoutInSeconds = fxGetFirstProvidedValue(n0zTransactionTimeoutInSeconds, oSelf.n0DefaultTransactionTimeoutInSeconds);
    oSelf.__bAllowUnverifiableCertificates = bAllowUnverifiableCertificates;
    oSelf.__bCheckHostname = bCheckHostname;
    
    if not oProxyServerURL.bSecure:
      oSelf.__o0ProxySSLContext = None;
    else:
      assert oSelf.__o0CertificateStore, \
          "A secure proxy cannot be used if no certificate store is available!";
      if bAllowUnverifiableCertificatesForProxy:
        oSelf.__o0ProxySSLContext = oSelf.__o0CertificateStore.foGetClientsideSSLContextWithoutVerification();
      else:
        oSelf.__o0ProxySSLContext = oSelf.__o0CertificateStore.foGetClientsideSSLContextForHostname(
          oProxyServerURL.sHostname,
          oSelf.__bCheckProxyHostname,
        );
    
    oSelf.__oWaitingForConnectionToBecomeAvailableLock = cLock(
      "%s.__oWaitingForConnectionToBecomeAvailableLock" % oSelf.__class__.__name__,
    );
    
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__aoConnectionsToProxyNotConnectedToAServer = [];
    oSelf.__doConnectionToProxyUsedForSecureConnectionToServer_by_sProtocolHostPort = {};
    oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort = {};
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );
    
    oSelf.fAddEvents(
      "connect failed", "new connection", # connect failed currently does not fire: assertions are triggered instead.
      "request sent", "response received", "request sent and response received",
      "secure connection established",
      "connection terminated",
      "terminated",
    );
  
  def __faoGetAllConnections(oSelf):
    return oSelf.__aoConnectionsToProxyNotConnectedToAServer + oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.values();

  def __fuCountAllConnections(oSelf):
    return len(oSelf.__aoConnectionsToProxyNotConnectedToAServer) + len(oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort);
  
  @property
  def bStopping(oSelf):
    return oSelf.__bStopping;
  
  @ShowDebugOutput
  def fStop(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated.");
      if oSelf.__bStopping:
        return fShowDebugOutput("Already stopping.");
      fShowDebugOutput("Stopping...");
      oSelf.__bStopping = True;
      aoConnections = oSelf.__faoGetAllConnections();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    fShowDebugOutput("Stopping connections to proxy server...");
    if len(aoConnections) == 0:
      # We stopped when there were no connections: we are terminated.
      fShowDebugOutput("Terminated.");
      oSelf.__oTerminatedLock.fRelease();
      oSelf.fFireEvent("terminated");
    else:
      for oConnection in aoConnections:
        oConnection.fStop();
  
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      # We'll run through all the steps no matter what.
      if oSelf.bTerminated:
        fShowDebugOutput("Already terminated.");
        return True;
      oSelf.__bStopping = True;
      aoConnections = oSelf.__faoGetAllConnections();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if len(aoConnections) == 0:
      # We terminated when there were no connections: we are terminated.
      fShowDebugOutput("Terminated.");
      oSelf.__oTerminatedLock.fRelease();
      oSelf.fFireEvent("terminated");
    else:
      for oConnection in aoConnections:
        fShowDebugOutput("Terminating connection to proxy server %s..." % oConnection);
        oConnection.fTerminate();
  
  @ShowDebugOutput
  def fWait(oSelf):
    return oSelf.__oTerminatedLock.fWait();
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds);
  
  def fo0GetProxyServerURLForURL(oSelf, oURL):
    return oSelf.oProxyServerURL.foClone();
  
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
    if not oURL.bSecure:
      o0Connection = oSelf.__fo0GetUnusedConnectionToProxyAndStartTransaction();
    else:
      o0Connection = oSelf.__fo0GetUnusedSecureConnectionToServerThroughProxyAndStartTransaction(
        oURL.oBase,
      );
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert o0Connection, \
        "Expected a connection but got %s" % repr(o0Connection);
    o0Response = o0Connection.fo0SendRequestAndReceiveResponse(
      oRequest,
      bStartTransaction = False,
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
    oSelf.fFireCallbacks("request sent and response received", o0Connection, oRequest, o0Response);
    return o0Response;
  
  @ShowDebugOutput
  def __fo0ReuseUnusedConnectionToProxyAndStartTransaction(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fbAcquire();
    try:
      # Try to find the non-secure connection that is available:
      for oConnection in oSelf.__aoConnectionsToProxyNotConnectedToAServer:
        if oConnection.fbStartTransaction(oSelf.__n0TransactionTimeoutInSeconds):
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
      for oIdleSecureConnection in oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.values():
        if oIdleSecureConnection.fbStartTransaction(0):
          break;
      else:
        return False;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oIdleSecureConnection.fDisconnect();
    return True;
  
  @ShowDebugOutput
  def __fo0GetUnusedConnectionToProxyAndStartTransaction(oSelf):
    # Try to reuse a non-secure connection if possible:
    o0Connection = oSelf.__fo0ReuseUnusedConnectionToProxyAndStartTransaction();
    if o0Connection:
      fShowDebugOutput("Existing connectiong to proxy reused: %s." % repr(o0Connection));
      return o0Connection;
    # Try to create a new connection if possible:
    if (
      oSelf.__u0MaxNumberOfConnectionsToProxy is None
      or oSelf.__fuCountAllConnections() < oSelf.__u0MaxNumberOfConnectionsToProxy
    ):
      o0Connection = oSelf.__fo0CreateNewConnectionToProxyAndStartTransaction(
        n0zConnectTimeoutInSeconds = oSelf.__n0zConnectToProxyTimeoutInSeconds,
      );
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert o0Connection, \
          "Expected a connection but got %s" % o0Connection;
      fShowDebugOutput("New connectiong to proxy created: %s." % repr(o0Connection));
      return o0Connection;
    # Wait until we can start a transaction on any of the existing connections,
    # i.e. the conenction is idle:
    fShowDebugOutput("Maximum number of connections to proxy reached; waiting for a connection to become idle...");
    n0zConnectEndTime = (
      zNotProvided if not fbIsProvided(oSelf.__n0zConnectToProxyTimeoutInSeconds) else
      None if oSelf.__n0zConnectToProxyTimeoutInSeconds is None else
      time.clock() + oSelf.__n0zConnectToProxyTimeoutInSeconds
    );
    # Since we want multiple thread to wait in turn, use a lock to allow only one
    # thread to enter the next block of code at a time.
    if not oSelf.__oWaitingForConnectionToBecomeAvailableLock.fbAcquire(oSelf.__nzConnectToProxyTimeoutInSeconds):
      # Another thread was waiting first and we timed out before a connection became available.
      raise cMaxConnectionsReachedException(
        "Maximum number of active connections reached and all existing connections are busy.",
      );
    try:
      # Wait until transactions can be started on one or more of the existing connections:
      aoConnectionsWithStartedTransactions = cHTTPConnection.faoWaitUntilTransactionsCanBeStartedAndStartTransactions(
        aoConnections = oSelf.__faoGetAllConnections(),
        n0zTimeoutInSeconds = (
          zNotProvided if fbIsProvided(n0zConnectEndTime) else
          None if n0zConnectEndTime is None else 
          n0zConnectEndTime - time.clock()
        ),
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
      o0Connection = oSelf.__fo0CreateNewConnectionToProxyAndStartTransaction(
        n0zConnectTimeoutInSeconds = (
          zNotProvided if fbIsProvided(n0zConnectEndTime) else
          None if n0zConnectEndTime is None else 
          n0zConnectEndTime - time.clock()
        ),
      );
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert o0Connection, \
          "Expected a connection but got %s" % o0Connection;
      fShowDebugOutput("New connectiong to proxy created: %s." % repr(o0Connection));
      return oConnection;
    finally:
      oSelf.__oWaitingForConnectionToBecomeAvailableLock.fRelease();
  
  @ShowDebugOutput
  def __fo0CreateNewConnectionToProxyAndStartTransaction(oSelf,
    # The connect timeout can be less than oSelf.__n0zConnectTimeoutInSeconds 
    # because we may have already have to wait for another connection to be
    # closed if we had reached the maximum number of connections.
    n0zConnectTimeoutInSeconds, 
  ):
    # Create a new socket and return that.
    fShowDebugOutput("Connecting to %s..." % oSelf.oProxyServerURL);
    oConnection = cHTTPConnection.foConnectTo(
      sHostname = oSelf.oProxyServerURL.sHostname,
      uPort = oSelf.oProxyServerURL.uPort,
      n0zConnectTimeoutInSeconds = n0zConnectTimeoutInSeconds,
      o0SSLContext = oSelf.__o0ProxySSLContext,
      n0zSecureTimeoutInSeconds = oSelf.__n0zSecureConnectionToProxyTimeoutInSeconds,
    );
    assert oConnection, \
        "Expected connection but got %s" % oConnection;
    oConnection.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnection);
    oConnection.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnection);
    oConnection.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
    assert oConnection.fbStartTransaction(oSelf.__n0TransactionTimeoutInSeconds), \
        "Cannot start a transaction on a new connection (%s)" % repr(oConnection);
    oSelf.__aoConnectionsToProxyNotConnectedToAServer.append(oConnection);
    oSelf.fFireCallbacks("new connection", oConnection);
    return oConnection;
  
  @ShowDebugOutput
  def fo0GetConnectionToServerThroughProxyAndStartTransaction(oSelf, oServerBaseURL):
    o0ConnectionToProxy = oSelf.__fo0GetUnusedConnectionToProxyAndStartTransaction();
    if oSelf.__bStopping:
      if o0ConnectionToProxy:
        o0ConnectionToProxy.fEndTransaction();
      fShowDebugOutput("Stopping.");
      return None;
    assert o0ConnectionToProxy, \
        "Expected a connection but got %s" % o0ConnectionToProxy;
    # We have a connection to the the proxy and we need to ask it pipe the connection to a server by
    # sending a CONNECT request:
    oConnectionToProxy = o0ConnectionToProxy;
    oConnectRequest = cHTTPRequest(
      sURL = oServerBaseURL.sAddress,
      szMethod = "CONNECT",
      o0Headers = cHTTPHeaders.foFromDict({
        "Host": oServerBaseURL.sAddress,
        "Connection": "Keep-Alive",
      }),
    );
    o0ConnectResponse = oConnectionToProxy.fo0SendRequestAndReceiveResponse(oConnectRequest, bStartTransaction = False, bEndTransaction = False);
    # oConnectResponse can be None if we are stopping.
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    assert o0ConnectResponse, \
        "Expected a CONNECT response but got %s" % o0ConnectResponse;
    oConnectResponse = o0ConnectResponse;
    if oConnectResponse.uStatusCode != 200:
      # I am not entirely sure if we can trust the connection after this, so let's close it to prevent issues:
      oConnectionToProxy.fDisconnect();
      raise cHTTPProxyConnectFailedException(
        "The proxy did not accept our CONNECT request.",
        {"oConnectRequest": oConnectRequest, "oConnectResponse": oConnectResponse},
      );
    oConnectionToServerThroughProxy = oConnectionToProxy
    # We've used some time to setup the connection; reset the transaction timeout
    oConnectionToServerThroughProxy.fRestartTransaction(oSelf.__n0TransactionTimeoutInSeconds);
    return oConnectionToServerThroughProxy;
  
  @ShowDebugOutput
  def __fo0GetUnusedSecureConnectionToServerThroughProxyAndStartTransaction(oSelf, oServerBaseURL):
    # See if we already have a secure connection to the server that is not in use and reuse that if we do:
    o0SecureConnection = oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.get(oServerBaseURL.sBase);
    if o0SecureConnection:
      assert o0SecureConnection.fbStartTransaction(oSelf.__n0TransactionTimeoutInSeconds), \
          "Cannot start a transaction on an existing secure connection to the server (%s)" % repr(o0SecureConnection);
      fShowDebugOutput("Reusing existing connection");
      return o0SecureConnection;
    oConnectionToServerThroughProxy = oSelf.fo0GetConnectionToServerThroughProxyAndStartTransaction(oServerBaseURL);
    fShowDebugOutput("Starting SSL negotiation...");
    # Wrap the connection in SSL.
    assert oSelf.__o0CertificateStore, \
        "Cannot make secure requests without a certificate store";
    if oSelf.__bAllowUnverifiableCertificates:
      oSSLContext = oSelf.__o0CertificateStore.foGetClientsideSSLContextWithoutVerification();
    else:
      oSSLContext = oSelf.__o0CertificateStore.foGetClientsideSSLContextForHostname(
        oServerBaseURL.sHostname,
        oSelf.__bCheckHostname
      );
    oConnectionToServerThroughProxy.fSecure(
      oSSLContext = oSSLContext,
      n0zTimeoutInSeconds = oSelf.__n0zSecureConnectionToServerTimeoutInSeconds
    );
    # Remember that we now have this secure connection to the server
    oSelf.__aoConnectionsToProxyNotConnectedToAServer.remove(oConnectionToServerThroughProxy);
    oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort[oServerBaseURL.sBase] = oConnectionToServerThroughProxy;
    oSelf.fFireCallbacks("secure connection established", oConnectionToServerThroughProxy, oServerBaseURL.sHostname);
    # and start using it...
    assert oConnectionToServerThroughProxy.fRestartTransaction(oSelf.__n0TransactionTimeoutInSeconds), \
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
      # Return if we are not stopping or if there are other connections open:
      if not oSelf.__bStopping:
        return;
      if oSelf.__aoConnectionsToProxyNotConnectedToAServer:
        return;
      if oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort:
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
      "%d connections to proxy server" % len(oSelf.__aoConnectionsToProxyNotConnectedToAServer),
      "%d secure connections to server through proxy" % len(oSelf.__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort),
      "stopping" if oSelf.__bStopping else None,
    ] if s];
