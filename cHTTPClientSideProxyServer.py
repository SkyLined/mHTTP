import re, time;

try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mHTTPConnections import cHTTPConnection, cHTTPResponse, cHTTPHeaders, mExceptions, cURL;
from mMultiThreading import cLock, cThread, cWithCallbacks;
from mTCPIPConnections import cTransactionalBufferedTCPIPConnection;

from .cHTTPServer import cHTTPServer;
from .cHTTPClient import cHTTPClient;
from .cHTTPClientUsingProxyServer import cHTTPClientUsingProxyServer;
from .mNotProvided import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

def foGetErrorResponse(sVersion, uStatusCode, sBody):
  return cHTTPResponse(
    szVersion = sVersion,
    uzStatusCode = uStatusCode,
    o0zHeaders = cHTTPHeaders.foFromDict({
      "Connection": "Close",
      "Content-Type": "text/plain",
    }),
    s0Body = sBody,
    bAutomaticallyAddContentLengthHeader = True,
  );

def foGetResponseForException(oException, sHTTPVersion):
  if isinstance(oException, (mExceptions.cDNSUnknownHostnameException, mExceptions.cTCPIPInvalidAddressException)):
    return foGetErrorResponse(sHTTPVersion, 400, "The server cannot be found.");
  if isinstance(oException, mExceptions.cTCPIPConnectTimeoutException):
    return foGetErrorResponse(sHTTPVersion, 504, "Connecting to the server timed out.");
  if isinstance(oException, mExceptions.cTCPIPDataTimeoutException):
    return foGetErrorResponse(sHTTPVersion, 504, "The server did not respond before the request timed out.");
  if isinstance(oException, mExceptions.cHTTPOutOfBandDataException):
    return foGetErrorResponse(sHTTPVersion, 502, "The server send out-of-band data.");
  if isinstance(oException, mExceptions.cTCPIPConnectionRefusedException):
    return foGetErrorResponse(sHTTPVersion, 502, "The server did not accept our connection.");
  if isinstance(oException, (mExceptions.cTCPIPConnectionShutdownException, mExceptions.cTCPIPConnectionDisconnectedException)):
    return foGetErrorResponse(sHTTPVersion, 502, "The server disconnected before sending a response.");
  if isinstance(oException, mExceptions.cHTTPInvalidMessageException):
    return foGetErrorResponse(sHTTPVersion, 502, "The server send an invalid HTTP response.");
  if mExceptions.cSSLException and isinstance(oException, mExceptions.cSSLSecureTimeoutException):
    return foGetErrorResponse(sHTTPVersion, 504, "The connection to the server could not be secured before the request timed out.");
  if mExceptions.cSSLException and isinstance(oException, (mExceptions.cSSLSecureHandshakeException, mExceptions.cSSLIncorrectHostnameException)):
    return foGetErrorResponse(sHTTPVersion, 504, "The connection to the server could not be secured.");
  raise;

class cHTTPClientSideProxyServer(cWithCallbacks):
  u0DefaultMaxNumberOfConnectionsToChainedProxy = 10;
  n0DefaultSecureConnectionToChainedProxyTimeoutInSeconds = 5;
  
  n0DefaultSecureTimeoutInSeconds = zNotProvided; # Let mHTTPConnection pick a default.
  n0DefaultTransactionTimeoutInSeconds = 10;
  n0DefaultSecureConnectionPipeTotalDurationTimeoutInSeconds = None;
  n0DefaultSecureConnectionPipeIdleTimeoutInSeconds = 20;
  n0DefaultConnectionTerminateTimeoutInSeconds = 10;
  
  @ShowDebugOutput
  def __init__(oSelf,
    szHostname = zNotProvided, uzPort = zNotProvided,
    o0ServerSSLContext = None,
    o0zCertificateStore = zNotProvided,
    o0ChainedProxyURL = None,
    o0ChainedProxyHTTPClient = None,
    bAllowUnverifiableCertificatesForChainedProxy = False,
    bCheckChainedProxyHostname = True,
    u0zMaxNumberOfConnectionsToChainedProxy = zNotProvided,
    # Connections to proxy use nzConnectTimeoutInSeconds
    n0zSecureConnectionToChainedProxyTimeoutInSeconds = zNotProvided,
    # Connections to proxy use nzTransactionTimeoutInSeconds
    o0InterceptSSLConnectionsCertificateAuthority = None,
    n0zConnectTimeoutInSeconds = zNotProvided,
    n0zSecureTimeoutInSeconds = zNotProvided,
    n0zTransactionTimeoutInSeconds = zNotProvided,
    bAllowUnverifiableCertificates = False,
    bCheckHostname = True,
    n0zSecureConnectionPipeTotalDurationTimeoutInSeconds = zNotProvided,
    n0zSecureConnectionPipeIdleTimeoutInSeconds = zNotProvided,
    u0zMaxNumberOfConnectionsToServer = zNotProvided,
  ):
    oSelf.__o0InterceptSSLConnectionsCertificateAuthority = o0InterceptSSLConnectionsCertificateAuthority;
    oSelf.__n0zConnectTimeoutInSeconds = n0zConnectTimeoutInSeconds;
    oSelf.__n0zSecureTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureTimeoutInSeconds, oSelf.n0DefaultSecureTimeoutInSeconds);
    oSelf.__n0zTransactionTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zTransactionTimeoutInSeconds, oSelf.n0DefaultTransactionTimeoutInSeconds);
    oSelf.__bAllowUnverifiableCertificates = bAllowUnverifiableCertificates;
    oSelf.__bCheckHostname = bCheckHostname;
    oSelf.__n0SecureConnectionPipeTotalDurationTimeoutInSeconds = fxGetFirstProvidedValue( \
        n0zSecureConnectionPipeTotalDurationTimeoutInSeconds, oSelf.n0DefaultSecureConnectionPipeTotalDurationTimeoutInSeconds);
    oSelf.__n0SecureConnectionPipeIdleTimeoutInSeconds = fxGetFirstProvidedValue( \
        n0zSecureConnectionPipeIdleTimeoutInSeconds, oSelf.n0DefaultSecureConnectionPipeIdleTimeoutInSeconds);
    
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__aoSecureConnectionsFromClient = [];
    oSelf.__aoSecureConnectionThreads = [];
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );
    
    oSelf.fAddEvents(
      "new connection from client",
      "connect to server failed", "new connection to server",
      "request received from client", "request sent to server",
      "connection piped between client and server",  "connection intercepted between client and server", 
      "response received from server", "response sent to client",
      "request sent to and response received from server",  "request received from and response sent to client", 
      "connection to server terminated", "connection from client terminated", 
      "client terminated", "server terminated",
      "terminated"
    );
    
    # Create client
    if o0ChainedProxyHTTPClient:
      assert not o0ChainedProxyURL, \
          "Cannot provide both a chained proxy URL (%s) and HTTP client (%s)" % \
          (o0ChainedProxyURL, o0ChainedProxyHTTPClient);
      # Ideally, we want to check the caller did not provide any unapplicable arguments here, but that's a lot of
      # work, so I've pushed this out until it makes sense to add these checks
      oSelf.oHTTPClient = o0ChainedProxyHTTPClient;
      oSelf.__bUsingChainedProxy = True;
    elif o0ChainedProxyURL:
      # Ideally, we want to check the caller did not provide any unapplicable arguments here, but that's a lot of
      # work, so I've pushed this out until it makes sense to add these checks
      oSelf.oHTTPClient = cHTTPClientUsingProxyServer(
        oProxyServerURL = o0ChainedProxyURL,
        bAllowUnverifiableCertificatesForProxy = bAllowUnverifiableCertificatesForChainedProxy,
        bCheckProxyHostname = bCheckChainedProxyHostname,
        o0zCertificateStore = o0zCertificateStore,
        u0zMaxNumberOfConnectionsToProxy = fxGetFirstProvidedValue( \
            u0zMaxNumberOfConnectionsToChainedProxy, oSelf.u0DefaultMaxNumberOfConnectionsToChainedProxy),
        n0zConnectToProxyTimeoutInSeconds = n0zConnectTimeoutInSeconds,
        n0zSecureConnectionToProxyTimeoutInSeconds = fxGetFirstProvidedValue( \
            n0zSecureConnectionToChainedProxyTimeoutInSeconds, oSelf.n0DefaultSecureConnectionToChainedProxyTimeoutInSeconds),
        n0zSecureConnectionToServerTimeoutInSeconds = oSelf.__n0zSecureTimeoutInSeconds,
        n0zTransactionTimeoutInSeconds = oSelf.__n0zTransactionTimeoutInSeconds,
        bAllowUnverifiableCertificates = bAllowUnverifiableCertificates,
        bCheckHostname = bCheckHostname,
      );
      oSelf.__bUsingChainedProxy = True;
    else:
      # Ideally, we want to check the caller did not provide any unapplicable arguments here, but that's a lot of
      # work, so I've pushed this out until it makes sense to add these checks
      oSelf.oHTTPClient = cHTTPClient(
        o0zCertificateStore = o0zCertificateStore,
        u0zMaxNumberOfConnectionsToServer = u0zMaxNumberOfConnectionsToServer,
        n0zConnectTimeoutInSeconds = n0zConnectTimeoutInSeconds,
        n0zSecureTimeoutInSeconds = oSelf.__n0zSecureTimeoutInSeconds,
        n0zTransactionTimeoutInSeconds = oSelf.__n0zTransactionTimeoutInSeconds,
        bAllowUnverifiableCertificates = bAllowUnverifiableCertificates,
        bCheckHostname = bCheckHostname,
      );
      oSelf.__bUsingChainedProxy = False;
    # Create server
    oSelf.oHTTPServer = cHTTPServer(
      ftxRequestHandler = oSelf.__ftxRequestHandler,
      szHostname = szHostname,
      uzPort = uzPort,
      o0SSLContext = o0ServerSSLContext,
    );
    
    # Forward events from client
    oSelf.oHTTPClient.fAddCallback("connect failed", lambda oHTTPServer, sHostname, uPort, oException:
        oSelf.fFireCallbacks("connect to server failed", sHostname, uPort, oException));
    oSelf.oHTTPClient.fAddCallback("new connection", lambda oHTTPServer, oConnection:
        oSelf.fFireCallbacks("new connection to server", oConnection));
    oSelf.oHTTPClient.fAddCallback("request sent", lambda oHTTPServer, oConnection, oRequest:
        oSelf.fFireCallbacks("request sent to server", oConnection, oRequest));
    oSelf.oHTTPClient.fAddCallback("response received", lambda oHTTPServer, oConnection, oResponse:
        oSelf.fFireCallbacks("response received from server", oConnection, oResponse));
    oSelf.oHTTPClient.fAddCallback("request sent and response received", lambda oHTTPServer, oConnection, oRequest, oResponse:
        oSelf.fFireCallbacks("request sent to and response received from server", oConnection, oRequest, oResponse));
    oSelf.oHTTPClient.fAddCallback("connection terminated", lambda oHTTPServer, oConnection:
        oSelf.fFireCallbacks("connection to server terminated", oConnection));
    oSelf.oHTTPClient.fAddCallback("terminated",
        oSelf.__fHandleTerminatedCallbackFromClient);
    
    # Forward events from server
    oSelf.oHTTPServer.fAddCallback("new connection",
        lambda oHTTPServer, oConnection: oSelf.fFireCallbacks("new connection from client", oConnection));
    oSelf.oHTTPServer.fAddCallback("request received",
        lambda oHTTPServer, oConnection, oRequest: oSelf.fFireCallbacks("request received from client", oConnection, oRequest));
    oSelf.oHTTPServer.fAddCallback("response sent",
        lambda oHTTPServer, oConnection, oResponse: oSelf.fFireCallbacks("response sent to client", oConnection, oResponse));
    oSelf.oHTTPServer.fAddCallback("request received and response sent",
        lambda oHTTPServer, oConnection, oRequest, oResponse: oSelf.fFireCallbacks("request received from and response sent to client", oConnection, oRequest, oResponse));
    oSelf.oHTTPServer.fAddCallback("connection terminated",
        lambda oHTTPServer, oConnection: oSelf.fFireCallbacks("connection from client terminated", oConnection));
    oSelf.oHTTPServer.fAddCallback("terminated",
        oSelf.__fHandleTerminatedCallbackFromServer);
  
  @ShowDebugOutput
  def __fHandleTerminatedCallbackFromServer(oSelf, oHTTPServer):
    assert oSelf.__bStopping, \
        "HTTP server terminated unexpectedly";
    oSelf.fFireCallbacks("server terminated", oHTTPServer);
    oSelf.__fCheckForTermination();
  
  @ShowDebugOutput
  def __fHandleTerminatedCallbackFromClient(oSelf, oHTTPClient):
    assert oSelf.__bStopping, \
        "HTTP client terminated unexpectedly";
    oSelf.fFireCallbacks("client terminated", oHTTPClient);
    oSelf.__fCheckForTermination();
  
  @ShowDebugOutput
  def __fCheckForTermination(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated.");
      if not oSelf.oHTTPServer.bTerminated:
        return fShowDebugOutput("Not terminated: server still running.");
      if not oSelf.oHTTPClient.bTerminated:
        return fShowDebugOutput("Not terminated: client still running.");
      if oSelf.__aoSecureConnectionsFromClient:
        return fShowDebugOutput("Not terminated: %d open connections." % len(oSelf.__aoSecureConnectionsFromClient));
      if oSelf.__aoSecureConnectionThreads:
        return fShowDebugOutput("Not terminated: %d running thread." % len(oSelf.__aoSecureConnectionThreads));
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    fShowDebugOutput("%s terminating." % oSelf.__class__.__name__);
    oSelf.fFireCallbacks("terminated");
  
  # These features are passed to the server part of a proxy
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  @property
  def sAddress(oSelf):
    return oSelf.oHTTPServer.sAddress;
  @property
  def bSecure(oSelf):
    return oSelf.oHTTPServer.bSecure;
  @property
  def sURL(oSelf):
    return oSelf.oHTTPServer.sURL;
  
  @ShowDebugOutput
  def fStop(oSelf):
    oSelf.__bStopping = True;
    fShowDebugOutput("Stopping HTTP server...");
    oSelf.oHTTPServer.fStop();
    fShowDebugOutput("Stopping HTTP client...");
    oSelf.oHTTPClient.fStop();
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      aoSecureConnections = oSelf.__aoSecureConnectionsFromClient[:];
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    for oSecureConnection in aoSecureConnections:
      fShowDebugOutput("Stopping secure connection %s..." % oSecureConnection);
      oSecureConnection.fStop();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    if oSelf.bTerminated:
      fShowDebugOutput("Already terminated.");
      return True;
    # Prevent any new connections from being accepted.
    oSelf.__bStopping = True;
    fShowDebugOutput("Terminating HTTP server...");
    oSelf.oHTTPServer.fTerminate();
    fShowDebugOutput("Terminating HTTP client...");
    oSelf.oHTTPClient.fTerminate();
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      aoSecureConnections = oSelf.__aoSecureConnectionsFromClient[:];
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    for oSecureConnection in aoSecureConnections:
      fShowDebugOutput("Terminating secure connection %s..." % oSecureConnection);
      oSecureConnection.fTerminate();
  
  @ShowDebugOutput
  def fWait(oSelf):
    # We could just wait for the termined lock, but while debugging, we may want
    # to know exactly what it is we're waiting for:
    if oSelf.__oTerminatedLock.bLocked:
      fShowDebugOutput("Waiting for HTTP server...");
      oSelf.oHTTPServer.fWait();
      fShowDebugOutput("Waiting for HTTP client...");
      oSelf.oHTTPClient.fWait();
      oSelf.__oPropertyAccessTransactionLock.fAcquire();
      try:
        aoSecureConnectionThreads = oSelf.__aoSecureConnectionThreads[:];
      finally:
        oSelf.__oPropertyAccessTransactionLock.fRelease();
      for oSecureConnectionThread in aoSecureConnectionThreads:
        fShowDebugOutput("Waiting for secure connection thread %s..." % oSecureConnectionThread);
        oSecureConnectionThread.fWait();
  
  @ShowDebugOutput
  def fbWait(oSelf, nTimeoutInSeconds):
    # We could just wait for the termined lock, but while debugging, we may want
    # to know exactly what it is we're waiting for:
    if oSelf.__oTerminatedLock.bLocked:
      nEndTime = time.clock() + nTimeoutInSeconds;
      fShowDebugOutput("Waiting for HTTP server...");
      if not oSelf.oHTTPServer.fbWait(nTimeoutInSeconds):
        fShowDebugOutput("Timeout.");
        return False;
      
      fShowDebugOutput("Waiting for HTTP client...");
      nRemainingTimeoutInSeconds = nEndTime - time.clock();
      if not oSelf.oHTTPClient.fbWait(nRemainingTimeoutInSeconds):
        fShowDebugOutput("Timeout.");
        return False;
      
      oSelf.__oPropertyAccessTransactionLock.fAcquire();
      try:
        aoSecureConnectionThreads = oSelf.__aoSecureConnectionThreads[:];
      finally:
        oSelf.__oPropertyAccessTransactionLock.fRelease();
      for oSecureConnectionThread in aoSecureConnectionThreads:
        fShowDebugOutput("Waiting for secure connection thread %s..." % oSecureConnectionThread);
        nRemainingTimeoutInSeconds = nEndTime - time.clock();
        if not oSecureConnectionThread.fbWait(nRemainingTimeoutInSeconds):
          fShowDebugOutput("Timeout.");
          return False;
    return True;
  
  @ShowDebugOutput
  def __ftxRequestHandler(oSelf, oHTTPServer, oConnection, oRequest, o0SecureConnectionInterceptedForServerURL = None):
    ### Sanity checks ##########################################################
    oResponse = oSelf.__foResponseForConnectRequest(oConnection, oRequest);
    if oResponse:
      if oResponse.uStatusCode == 200:
        fShowDebugOutput("HTTP CONNECT request handled; started forwarding data.");
        return (oResponse, False);
      fShowDebugOutput("HTTP CONNECT request failed.");
      return (oResponse, True);
    elif oRequest.sMethod.upper() not in ["CONNECT", "GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH"]:
      fShowDebugOutput("HTTP request method (%s) is not valid." % repr(oRequest.sMethod));
      oResponse = foGetErrorResponse(oRequest.sVersion, 400, "The request method was not valid.");
      return (oResponse, True);
    elif o0SecureConnectionInterceptedForServerURL is not None:
      # This request was made to a connection we are intercepting after the client send a HTTP CONNECT request.
      # The URL should be relative:
      if oRequest.sURL[:1] != "/":
        fShowDebugOutput("HTTP request URL (%s) does not start with '/'." % repr(oRequest.sURL));
        oResponse = foGetErrorResponse(oRequest.sVersion, 400, "The requested URL was not valid.");
        return (oResponse, True);
      oURL = cURL.foFromString(o0SecureConnectionInterceptedForServerURL.sBase + oRequest.sURL);
    else:
      # This request was made to the proxy; the URL should be absolute:
      try:
        oURL = cURL.foFromString(oRequest.sURL);
      except mExceptions.cInvalidURLException:
        if oRequest.sURL.split("://")[0] not in ["http", "https"]:
          fShowDebugOutput("HTTP request URL (%s) suggest request was meant for a server, not a proxy." % repr(oRequest.sURL));
          sReason = "This is a HTTP proxy, not a HTTP server.";
        else:
          fShowDebugOutput("HTTP request URL (%s) is not valid." % repr(oRequest.sURL));
          sReason = "The requested URL was not valid.",
        oResponse = foGetErrorResponse(oRequest.sVersion, 400, sReason);
        return (oResponse, True);
    oResponse = oSelf.__foResponseForInvalidProxyHeaderInRequest(oRequest)
    if oResponse:
      fShowDebugOutput("Invalid proxy header.");
      return (oResponse, True);
    oHeaders = oRequest.oHeaders.foClone();
    # This client does not decide how we handle our connection to the server, so we will overwrite any "Connection"
    # header copied from the request to the proxy with the value we want for the request to the server:
    oHeaders.fbReplaceHeadersForName("Connection", "Keep-Alive");
    # We will not allow the client to request a compression that we cannot decode so we will remove any
    # "Accept-Encoding" value copied from the request to the proxy that we cannot decode:
    for oAcceptEncodingHeader in oHeaders.faoGetHeadersForName("Accept-Encoding"):
      sFilteredValue = ",".join([
        sCompressionType
        for sCompressionType in oAcceptEncodingHeader.sValue.split(",")
        if sCompressionType.strip().lower() in oRequest.asSupportedCompressionTypes
      ]);
      if sFilteredValue.strip():
        oAcceptEncodingHeader.sValue = sFilteredValue;
      else:
        oHeaders.fbRemoveHeader(oAcceptEncodingHeader);
    # When we are intercepting HTTPS traffice, HTTP Strict Transport Security (HSTS) headers must be stripped to allow
    # the user to ignore certificate warnings.
    if oSelf.__o0InterceptSSLConnectionsCertificateAuthority and oHeaders.fbRemoveHeadersForName("Strict-Transport-Security"):
      fShowDebugOutput("Filtered HSTS header.");
    try:
      oResponse = oSelf.oHTTPClient.fo0GetResponseForURL(
        oURL = oURL,
        szMethod = oRequest.sMethod,
        o0zHeaders = oHeaders,
        s0Body = oRequest.sBody, # oRequest.sBody is the raw data, so this also handles Chunked requests.
      );
    except Exception as oException:
      oResponse = foGetResponseForException(oException, oRequest.sVersion);
    else:
      if oSelf.__bStopping:
        fShowDebugOutput("Stopping.");
        return None;
      assert oResponse, \
          "Expected a response but got %s" % repr(oResponse);
    return (oResponse, True);
  
  @ShowDebugOutput
  def __foResponseForInvalidProxyHeaderInRequest(oSelf, oRequest):
    if oRequest.oHeaders.fo0GetUniqueHeaderForName("Proxy-Authenticate"):
      oResponse = foGetErrorResponse(oRequest.sVersion, 400, "This proxy does not require authentication.");
      return oResponse;
    if oRequest.oHeaders.fo0GetUniqueHeaderForName("Proxy-Authorization"):
      oResponse = foGetErrorResponse(oRequest.sVersion, 400, "This proxy does not require authorization.");
      return oResponse;
    fShowDebugOutput("Request does not have an invalid proxy header");
    return None;

  @ShowDebugOutput
  def __foResponseForConnectRequest(oSelf, oConnectionFromClient, oRequest):
    if oRequest.sMethod.upper() != "CONNECT":
      return None;
    
    # Check the sanity of the request.
    aoHostHeaders = oRequest.oHeaders.faoGetHeadersForName("Host");
    if len(aoHostHeaders) == 0:
      fShowDebugOutput("The request has no host header");
      return foGetErrorResponse(oRequest.sVersion, 400, "The request has no host header.");
    
    sLowerHostHeader = aoHostHeaders[0].sLowerValue;
    for oAdditionalHeader in aoHostHeaders[1:]:
      if oAdditionalHeader.sLowerValue != sLowerHostHeader:
        fShowDebugOutput("The request has multiple contradicting host headers");
        return foGetErrorResponse(oRequest.sVersion, 400, "The request has multiple contradicting host headers.");
    try:
      oServerURL = cURL.foFromString(oRequest.sURL);
    except mExceptions.cInvalidURLException:
      if oRequest.sURL.split("://")[0] not in ["http", "https"]:
        fShowDebugOutput("HTTP request URL (%s) suggest request was meant for a server, not a proxy." % repr(oRequest.sURL));
        sReason = "This is a HTTP proxy, not a HTTP server.";
      else:
        fShowDebugOutput("HTTP request URL (%s) is not valid." % repr(oRequest.sURL));
        sReason = "The requested URL was not valid.",
      return foGetErrorResponse(oRequest.sVersion, 400, sReason);
    
    sLowerHostHeaderHostname, s0HostHeaderPort = (sLowerHostHeader.lower().split(":", 1) + [None])[:2];
    if sLowerHostHeaderHostname != oServerURL.sHostname.lower() or s0HostHeaderPort not in (None, str(oServerURL.uPort)):
      fShowDebugOutput("HTTP request URL (%s) does not match the Host header (%s)." % (repr(oRequest.sURL), repr(aoHostHeaders[0])));
      return foGetErrorResponse(oRequest.sVersion, 400, "The requested URL did not match the 'Host' header.");
    
    if oSelf.__o0InterceptSSLConnectionsCertificateAuthority:
      # We will be intercepting the requests, so we won't make a connection to the server immediately. We will
      # send a "200 Ok" response and start a thread that will handle the connection, but we will not simply pipe
      # the data in this thread. Instead the thread will negotiate SSL with the client using a wildcard certificate
      # and then wait for requests, forward them to the server, receive the response and forward it to the client.
      fConnectionHandler = oSelf.__fInterceptAndPipeConnection;
      txConnectionHandlerArguments = (oConnectionFromClient, oServerURL);
    else:
      # If we are not intercepting SSL connections, we will try to connect to the server. If this succeeds we will
      # send a "200 OK" response to the client and start a thread that will pipe data back and forth between the
      # client and server. We will ask out HTTP client to set up the connection, because the client may be using
      # a proxy, so we cannot connect directly.
      try:
        oConnectionToServer = oSelf.__oHTTPClient.fo0GetConnectionToServer(oServerURL);
      except Exception as oException:
        return foGetResponseForException(oException, oRequest.sVersion);
      oSelf.fFireCallbacks("new connection to server", oConnectionToServer);
      oConnectionToServer.fAddCallback("terminated",
        lambda oConnectionToServer: oSelf.fFireCallbacks("connection to server terminated", oConnectionToServer)
      );
      # Create a thread that will pipe data back and forth between the client and server
      fConnectionHandler = oSelf.__fPipeConnection;
      txConnectionHandlerArguments = (oConnectionFromClient, oConnectionToServer, oServerURL);
    def fStartConnectionHandlerThread(oConnectionFromClient, oResponse):
      oThread = cThread(fConnectionHandler, *txConnectionHandlerArguments);
      oSelf.__oPropertyAccessTransactionLock.fAcquire();
      try:
        oSelf.__aoSecureConnectionsFromClient.append(oConnectionFromClient);
        oSelf.__aoSecureConnectionThreads.append(oThread);
      finally:
        oSelf.__oPropertyAccessTransactionLock.fRelease();
      oThread.fStart(bVital = False);
    # After our response is sent to the client, we start handling the connection, i.e. piping (intercepted) data
    # between them.
    oConnectionFromClient.fAddCallback("response sent", fStartConnectionHandlerThread, bFireOnce = True);
    # Send a reponse to the client.
    oResponse = cHTTPResponse(
      szVersion = oRequest.sVersion,
      uzStatusCode = 200,
      szReasonPhrase = "Ok",
      o0zHeaders = cHTTPHeaders.foFromDict({
        "Connection": "Keep-Alive",
        "Content-type": "text/plain",
      }),
      s0Body = "Connected to remote server.",
      bAutomaticallyAddContentLengthHeader = True,
    );
    return oResponse;
  
  @ShowDebugOutput
  def __fInterceptAndPipeConnection(oSelf, oConnectionFromClient, oServerURL):
    n0TotalDurationEndTime = (
      time.clock() + oSelf.__n0zSecureConnectionPipeTotalDurationTimeoutInSeconds
      if fbProvided(oSelf.__n0zSecureConnectionPipeTotalDurationTimeoutInSeconds)
      else None
    );
    # When intercepting a supposedly secure connection, we will wait for the client to make requests through the
    # connection, forward it to the server to get a response using the same code as the normal proxy, and then
    # send the response back to the client.
    fShowDebugOutput("Intercepting secure connection for client %s to server %s." % (oConnectionFromClient, oServerURL.sBase));
    fShowDebugOutput("Generating SSL certificate for %s..." % oServerURL.sHostname);
    oSSLContext = oSelf.__o0InterceptSSLConnectionsCertificateAuthority.foGenerateserverSideSSLContextForHostname(
      oServerURL.sHostname
    );
    bEndTransaction = False;
    try:
      fShowDebugOutput("Negotiating security for %s..." % oConnectionFromClient);
      sWhile = "Negotiating security for %s" % oConnectionFromClient;
      oConnectionFromClient.fSecure(
        oSSLContext,
        bCheckHostname = oSelf.__bCheckHostname,
        n0zTimeoutInSeconds = oSelf.__n0zSecureConnectionPipeTotalDurationTimeoutInSeconds,
      );
      while not oSelf.__bStopping and oConnectionFromClient.bConnected:
        if n0TotalDurationEndTime is not None:
          n0TotalDurationRemainingTimeoutInSeconds = max(0, n0TotalDurationEndTime - time.clock());
          if n0TotalDurationRemainingTimeoutInSeconds == 0:
            fShowDebugOutput("Max secure connection piping time reached; disconnecting..." % oConnectionFromClient);
            break;
        else:
          n0TotalDurationRemainingTimeoutInSeconds = None;
        fShowDebugOutput("Reading request from %s..." % oConnectionFromClient);
        sWhile = "reading request from %s" % oConnectionFromClient;
        anProvidedTimeoutsInSeconds = [
            n0TimeoutInSeconds
            for n0TimeoutInSeconds in (n0TotalDurationRemainingTimeoutInSeconds, oSelf.__n0SecureConnectionPipeIdleTimeoutInSeconds)
            if n0TimeoutInSeconds is not None
        ];
        oRequest = oConnectionFromClient.foReceiveRequest(
          n0TransactionTimeoutInSeconds = min(anProvidedTimeoutsInSeconds) if len(anProvidedTimeoutsInSeconds) > 0 else None,
        );
        bEndTransaction = True;
        if oSelf.__bStopping:
          fShowDebugOutput("Stopping...");
          break;
        assert oRequest, \
            "No request!?";
        sWhile = None;
        (oResponse, bContinueHandlingRequests) = oSelf.__ftxRequestHandler(
          oHTTPServer = None, # Intercepted requests were not received by our HTTP server.
          oConnection = oConnectionFromClient,
          oRequest = oRequest,
          o0SecureConnectionInterceptedForServerURL = oServerURL
        );
        if oSelf.__bStopping:
          fShowDebugOutput("Stopping...");
          break;
        assert oResponse, \
            "No response!?";
        sWhile = "sending response to %s" % oConnectionFromClient;
        # Send the response to the client
        fShowDebugOutput("Sending response (%s) to %s..." % (oResponse, oConnectionFromClient));
        oConnectionFromClient.fSendResponse(oResponse);
        bEndTransaction = False;
        oSelf.fFireCallbacks("response sent to client", oRequest, oResponse);
        if not bContinueHandlingRequests:
          break;
    except Exception as oException:
      if sWhile is None: raise; # Exception thrown during __ftxRequestHandler call!?
      if mExceptions.cSSLException and isinstance(oException, mExceptions.cSSLException):
        fShowDebugOutput("Secure connection exception while %s: %s." % (sWhile, oException));
      elif isinstance(oException, mExceptions.cTCPIPConnectionShutdownException):
        fShowDebugOutput("Shutdown while %s." % sWhile);
      elif isinstance(oException, mExceptions.cTCPIPConnectionDisconnectedException):
        fShowDebugOutput("Disconnected while %s." % sWhile);
      else:
        raise;
    finally:
      if bEndTransaction: oConnectionFromClient.fEndTransaction();
      fShowDebugOutput("Stopped intercepting secure connection for client %s to server %s." % (oConnectionFromClient, oServerURL.sBase));
      if oConnectionFromClient.bConnected:
        try:
          assert oConnectionFromClient.fbStartTransaction(), \
              "Cannot start a transaction on the connection from the client (%s)" % repr(oConnectionFromClient);
          try:
            oConnectionFromClient.fDisconnect();
          finally:
            oConnectionFromClient.fEndTransaction();
        except mExceptions.cTCPIPConnectionDisconnectedException as oException:
          pass;
      oSelf.__oPropertyAccessTransactionLock.fAcquire();
      try:
        oSelf.__aoSecureConnectionsFromClient.remove(oConnectionFromClient);
        oSelf.__aoSecureConnectionThreads.remove(cThread.foGetCurrent());
      finally:
        oSelf.__oPropertyAccessTransactionLock.fRelease();
      oSelf.__fCheckForTermination();
  
  @ShowDebugOutput
  def __fPipeConnection(oSelf, oConnectionFromClient, oConnectionToServer, oServerURL):
    n0TotalDurationEndTime = (
      time.clock() + oSelf.__n0SecureConnectionPipeTotalDurationTimeoutInSeconds \
      if oSelf.__n0SecureConnectionPipeTotalDurationTimeoutInSeconds is not None
      else None
    );
    fShowDebugOutput("Piping secure connection for client %s to server %s ." % (oConnectionFromClient, oServerURL.sBase));
    bEndTransactions = False;
    try:
      while not oSelf.__bStopping and oConnectionToServer.bConnected and oConnectionFromClient.bConnected:
        sWhile = None;
        if n0TotalDurationEndTime is not None:
          n0TotalDurationRemainingTimeoutInSeconds = max(0, n0TotalDurationEndTime - time.clock());
          if n0TotalDurationRemainingTimeoutInSeconds == 0:
            fShowDebugOutput("Max secure connection piping time reached; disconnecting..." % oConnectionFromClient);
            break;
        else:
          n0TotalDurationRemainingTimeoutInSeconds = None;
        fShowDebugOutput("%s %s=waiting for data=%s %s." % (
          oConnectionFromClient,
          "<" if (oConnectionFromClient.bShouldAllowWriting and oConnectionToServer.bShouldAllowReading) else "",
          ">" if (oConnectionToServer.bShouldAllowWriting and oConnectionFromClient.bShouldAllowReading) else "",
          oConnectionToServer,
        ));
        sWhile = "waiting for readable bytes from client or server";
        anProvidedTimeoutsInSeconds = [
          n0TimeoutInSeconds
          for n0TimeoutInSeconds in (n0TotalDurationRemainingTimeoutInSeconds, oSelf.__n0SecureConnectionPipeIdleTimeoutInSeconds)
          if n0TimeoutInSeconds is not None
        ];
        aoConnectionsWithDataToPipe = oConnectionFromClient.__class__.faoWaitUntilBytesAreAvailableForReadingAndStartTransactions(
          [oConnection for oConnection in [oConnectionFromClient, oConnectionToServer] if oConnection.bShouldAllowReading], 
          n0WaitTimeoutInSeconds = min(anProvidedTimeoutsInSeconds) if len(anProvidedTimeoutsInSeconds) > 0 else None,
        );
        sWhile = None;
        # We need to start transactions on both connections, not just the ones with readable data.
        # We also need to set a transaction timeout.
        # End the current transactions so we can start new ones.
        for oConnection in aoConnectionsWithDataToPipe:
          oConnection.fEndTransaction();
        if len(aoConnectionsWithDataToPipe) == 0:
          break;
        if n0TotalDurationEndTime is not None:
          n0TotalDurationRemainingTimeoutInSeconds = max(0, n0TotalDurationEndTime - time.clock());
          if n0TotalDurationRemainingTimeoutInSeconds == 0:
            fShowDebugOutput("Max secure connection piping time reached; disconnecting..." % oConnectionFromClient);
            break;
        else:
          n0TotalDurationRemainingTimeoutInSeconds = None;
        assert oConnectionFromClient.fbStartTransaction(n0TimeoutInSeconds = n0TotalDurationRemainingTimeoutInSeconds), \
            "Cannot start transaction!?";
        assert oConnectionToServer.fbStartTransaction(n0TimeoutInSeconds = n0TotalDurationRemainingTimeoutInSeconds), \
            "Cannot start transaction!?";
        bEndTransactions = True;
        for oFromConnection in aoConnectionsWithDataToPipe:
          sWhile = "reading bytes from %s" % ("client" if oFromConnection is oConnectionFromClient else "server");
          sBytes = oFromConnection.fsReadAvailableBytes();
          fShowDebugOutput("%s %s=%d bytes=%s %s." % (
            oConnectionFromClient,
            "<" if oFromConnection is oConnectionToServer else "",
            len(sBytes),
            ">" if oFromConnection is oConnectionFromClient else "",
            oConnectionToServer,
          ));
          oToConnection = oConnectionFromClient if oFromConnection is oConnectionToServer else oConnectionToServer;
          sWhile = "writing bytes to %s" % ("client" if oToConnection is oConnectionFromClient else "server");
          oToConnection.fWriteBytes(sBytes);
          sWhile = None;
        oConnectionFromClient.fEndTransaction();
        oConnectionToServer.fEndTransaction();
        bEndTransactions = False;
    except mExceptions.cTCPIPDataTimeoutException:
      if sWhile is None: raise; # Exception thrown during __ftxRequestHandler call!?
      fShowDebugOutput("Transaction timeout while %s." % sWhile);
    except mExceptions.cTCPIPConnectionShutdownException:
      if sWhile is None: raise; # Exception thrown during __ftxRequestHandler call!?
      fShowDebugOutput("Shutdown while %s." % sWhile);
    except mExceptions.cTCPIPConnectionDisconnectedException:
      if sWhile is None: raise; # Exception thrown during __ftxRequestHandler call!?
      fShowDebugOutput("Disconnected while %s." % sWhile);
    finally:
      fShowDebugOutput("Stopped piping secure connection for client %s to server %s." % (oConnectionFromClient, oServerURL.sBase));
      if oConnectionFromClient.bConnected:
        try:
          assert bEndTransactions or oConnectionFromClient.fbStartTransaction(), \
              "Cannot start a transaction on the connection from the client (%s)" % repr(oConnectionFromClient);
          try:
            oConnectionFromClient.fDisconnect();
          finally:
            oConnectionFromClient.fEndTransaction();
        except mExceptions.cTCPIPConnectionDisconnectedException as oException:
          pass;
      elif bEndTransactions:
        oConnectionFromClient.fEndTransaction();
      if oConnectionToServer.bConnected:
        try:
          assert bEndTransactions or oConnectionToServer.fbStartTransaction(), \
              "Cannot start a transaction on the connection from the client (%s)" % repr(oConnectionFromClient);
          try:
            oConnectionToServer.fDisconnect();
          finally:
            oConnectionToServer.fEndTransaction();
        except mExceptions.cTCPIPConnectionDisconnectedException as oException:
          pass;
      elif bEndTransactions:
        oConnectionToServer.fEndTransaction();
      oSelf.__oPropertyAccessTransactionLock.fAcquire();
      try:
        oSelf.__aoSecureConnectionsFromClient.remove(oConnectionFromClient);
        oSelf.__aoSecureConnectionThreads.remove(cThread.foGetCurrent());
      finally:
        oSelf.__oPropertyAccessTransactionLock.fRelease();
      oSelf.__fCheckForTermination();
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    if oSelf.bTerminated:
      return ["terminated"];
    uSecureConnections = len(oSelf.__aoSecureConnectionsFromClient);
    uSecureConnectionThreads = len(oSelf.__aoSecureConnectionThreads);
    return [s for s in [
      "%s => %s" % (oSelf.oHTTPServer, oSelf.oHTTPClient),
      "%s secure connections" % (uSecureConnections or "no"),
      "%s threads" % (uSecureConnectionThreads or "no"),
      "terminated" if oSelf.bTerminated else \
          "stopping" if oSelf.__bStopping else None,
    ] if s];
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));
