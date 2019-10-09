from .cBufferedSocket import cBufferedSocket;
from .cHTTPServer import cHTTPServer;
from .cHTTPClient import cHTTPClient;
from .cHTTPClientUsingProxyServer import cHTTPClientUsingProxyServer;
from .cHTTPResponse import cHTTPResponse;
from .cURL import cURL;
from .iHTTPMessage import iHTTPMessage;
from mDebugOutput import cWithDebugOutput;
from mMultiThreading import cLock, cThread, cWithCallbacks;

class cHTTPClientProxyServer(cWithCallbacks, cWithDebugOutput):
  nDefaultSecureConnectionTimeoutInSeconds = None;
  nDefaultSecureConnectionIdleTimeoutInSeconds = 20;
  
  def __init__(oSelf, sHostName = None, uPort = None, oServerSSLContext = None, oCertificateStore = None, oChainedProxyURL = None, oInterceptSSLConnectionsCertificateAuthority = None, nTransactionTimeoutInSeconds = None, bCheckHostName = None, nSecureConnectionTimeoutInSeconds = None, nSecureConnectionIdleTimeoutInSeconds = None, uMaxConnectionsToServer = None, bLocal = True):
    oSelf.__oCertificateStore = oCertificateStore;
    oSelf.__oInterceptSSLConnectionsCertificateAuthority = oInterceptSSLConnectionsCertificateAuthority;
    oSelf.__nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds;
    oSelf.__bCheckHostName = bCheckHostName;
    oSelf.__nSecureConnectionTimeoutInSeconds = nSecureConnectionTimeoutInSeconds if nSecureConnectionTimeoutInSeconds is not None else oSelf.nDefaultSecureConnectionTimeoutInSeconds;
    oSelf.__nSecureConnectionIdleTimeoutInSeconds = nSecureConnectionIdleTimeoutInSeconds if nSecureConnectionIdleTimeoutInSeconds is not None else oSelf.nDefaultSecureConnectionIdleTimeoutInSeconds;
    
    oSelf.__oSecureConnectionsLock = cLock("cHTTPClientProxyServer.__oThreadsLock");
    oSelf.__aoSecureConnectionsFromClient = [];
    oSelf.__aoSecureConnectionThreads = [];
    
    oSelf.__bStopping = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = cLock(bLocked = True);
    
    oSelf.fAddEvents(
      "started",
      "new connection from client", "new connection to server",
      "request received from client", "request sent to server",
      "connection piped between client and server",  "connection intercepted between client and server", 
      "response received from server", "response sent to client",
      "request sent to and response received from server",  "request received from and response sent to client", 
      "connection to server terminated", "connection from client terminated", 
      "client terminated", "server terminated",
      "terminated"
    );
    
    oSelf.oHTTPServer = cHTTPServer(sHostName, uPort, oServerSSLContext, bLocal = bLocal);
    oSelf.oHTTPServer.fAddCallback("started",
        lambda oHTTPServer: oSelf.fFireCallbacks("started"));
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
    if oChainedProxyURL:
      oSelf.oHTTPClient = cHTTPClientUsingProxyServer(oChainedProxyURL, oCertificateStore, uMaxConnectionsToServer);
      oSelf.oHTTPClient
    else:
      oSelf.oHTTPClient = cHTTPClient(oCertificateStore, uMaxConnectionsToServer);
    oSelf.oHTTPClient.fAddCallback("new connection",
        lambda oHTTPServer, oConnection: oSelf.fFireCallbacks("new connection to server", oConnection));
    oSelf.oHTTPClient.fAddCallback("request sent",
        lambda oHTTPServer, oConnection, oRequest: oSelf.fFireCallbacks("request sent to server", oConnection, oRequest));
    oSelf.oHTTPClient.fAddCallback("response received",
        lambda oHTTPServer, oConnection, oResponse: oSelf.fFireCallbacks("response received from server", oConnection, oResponse));
    oSelf.oHTTPClient.fAddCallback("request sent and response received",
        lambda oHTTPServer, oConnection, oRequest, oResponse: oSelf.fFireCallbacks("request sent to and response received from server", oConnection, oRequest, oResponse));
    oSelf.oHTTPClient.fAddCallback("connection terminated",
        lambda oHTTPServer, oConnection: oSelf.fFireCallbacks("connection to server terminated", oConnection));
    oSelf.oHTTPClient.fAddCallback("terminated",
        oSelf.__fHandleTerminatedCallbackFromClient);
  
  def __fHandleTerminatedCallbackFromServer(oSelf, oHTTPServer):
    oSelf.fEnterFunctionOutput();
    try:
      assert oSelf.__bStopping, \
          "HTTP server terminated unexpectedly";
      oSelf.fFireCallbacks("server terminated", oHTTPServer);
      oSelf.__fCheckForTermination();
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  def __fHandleTerminatedCallbackFromClient(oSelf, oHTTPClient):
    oSelf.fEnterFunctionOutput();
    try:
      assert oSelf.__bStopping, \
          "HTTP client terminated unexpectedly";
      oSelf.fFireCallbacks("client terminated", oHTTPClient);
      oSelf.__fCheckForTermination();
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fCheckForTermination(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated.");
      if not oSelf.__bStopping:
        return oSelf.fExitFunctionOutput("Not stopping.");
      if not oSelf.oHTTPServer.bTerminated:
        return oSelf.fExitFunctionOutput("Not terminated: server still running.");
      if not oSelf.oHTTPClient.bTerminated:
        return oSelf.fExitFunctionOutput("Not terminated: client still running.");
      oSelf.__oSecureConnectionsLock.fAcquire();
      try:
        uOpenConnections = len(oSelf.__aoSecureConnectionsFromClient);
        uRunningThreads = len(oSelf.__aoSecureConnectionThreads);
        bTerminated = uOpenConnections == 0 and uRunningThreads == 0 and not oSelf.__bTerminated;
        if bTerminated: oSelf.__bTerminated = True;
      finally:
        oSelf.__oSecureConnectionsLock.fRelease();
      if bTerminated:
        oSelf.__bTerminated = True;
        oSelf.__oTerminatedLock.fRelease();
        oSelf.fFireCallbacks("terminated");
        return oSelf.fExitFunctionOutput("Terminated.");
      return oSelf.fExitFunctionOutput("Not terminated; %d open connections." % uOpenConnections);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  # These features are passed to the server part of a proxy
  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;
  @property
  def sAddress(oSelf):
    return oSelf.oHTTPServer.sAddress;
  @property
  def bSecure(oSelf):
    return oSelf.oHTTPServer.bSecure;
  @property
  def sURL(oSelf):
    return oSelf.oHTTPServer.sURL;
  def fStop(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__bStopping = True;
      oSelf.oHTTPServer.fStop();
      oSelf.oHTTPClient.fStop();
      oSelf.__fTerminateSecureConnections(); # We cannot "stop" them as we do not know their state.
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fTerminate(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__bStopping = True;
      oSelf.oHTTPServer.fTerminate();
      oSelf.oHTTPClient.fTerminate();
      oSelf.__fTerminateSecureConnections();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fTerminateSecureConnections(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__oSecureConnectionsLock.fAcquire();
      try:
        aoSecureConnections = oSelf.__aoSecureConnectionsFromClient[:];
      finally:
        oSelf.__oSecureConnectionsLock.fRelease();
      if aoSecureConnections:
        for oSecureConnection in aoSecureConnections:
          oSelf.fStatusOutput("Terminating %s..." % oSecureConnection.fsToString());
          oSecureConnection.fTerminate();
        return oSelf.fExitFunctionOutput("Terminated %d connections" % len(aoSecureConnections));
      else:
        oSelf.__fCheckForTermination();
        return oSelf.fExitFunctionOutput("No connections");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fWait(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.oHTTPServer.fWait();
      oSelf.oHTTPClient.fWait();
      oSelf.__oSecureConnectionsLock.fAcquire();
      try:
        aoSecureConnectionThreads = oSelf.__aoSecureConnectionThreads[:];
      finally:
        oSelf.__oSecureConnectionsLock.fRelease();
      for oSecureConnectionThread in aoSecureConnectionThreads:
        oSelf.fStatusOutput("Waiting for %s..." % oSecureConnectionThread.fsToString());
        oSecureConnectionThread.fWait();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbWait(oSelf, nTimeoutInSeconds = 0):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      nMaxEndWaitTime = time.clock() + nTimeoutInSeconds;
      if not oSelf.oHTTPServer.fbWait(nTimeout):
        return oSelf.fxExitFunctionOutput(False);
      nRemainingTimeoutInSeconds = nMaxEndWaitTime - time.clock();
      if not oSelf.oHTTPClient.fbWait(nRemainingTimeoutInSeconds):
        return oSelf.fxExitFunctionOutput(False);
      nRemainingTimeoutInSeconds = nMaxEndWaitTime - time.clock();
      return oSelf.fxExitFunctionOutput(oSelf.__fbWaitForSecureConnections(nRemainingTimeoutInSeconds));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def __fbWaitForSecureConnections(oSelf, nTimeoutInSeconds = None):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      # We cannot wait for the threads using a timeout, but the threads should terminate almost immediately after
      # the relevant connections from the client do, and we can wait for those with a timeout. So we will wait for
      # the connections and if that succeeds, wait for the threads (which should not take long enough to require
      # timing.
      nMaxEndWaitTime = time.clock() + nTimeoutInSeconds;
      if not oSelf.__oSecureConnectionsLock.fbAcquire(nTimeoutInSeconds):
        return oSelf.fxExitFunctionOutput(False, "Timeout before lock could be acquired");
      try:
        aoSecureConnections = oSelf.__aoSecureConnectionsFromClient[:];
        aoSecureConnectionThreads = oSelf.__aoSecureConnectionThreads[:];
      finally:
        oSelf.__oSecureConnectionsLock.fRelease();
      for oSecureConnection in aoSecureConnections:
        nRemainingTimeoutInSeconds = nMaxEndWaitTime - time.clock();
        if not oSecureConnection.fbWait(nRemainingTimeoutInSeconds):
          return oSelf.fxExitFunctionOutput(False, "Timeout while waiting for connection");
      # Now that the connections are terminated, we should wait for the threads, but this should not
      # take long, so we won't keep track of time.
      for oSecureConnectionThread in aoSecureConnectionThreads:
        oSecureConnectionThread.fWait();
      return oSelf.fxExitFunctionOutput(True);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fStart(oSelf):
    # We strip the cHTTPServer instance from the request handler callback arguments, so we can use the same code
    # in the SSL interception code (i.e. __foRequestHandler):
    oSelf.oHTTPServer.fStart(lambda oHTTPServer, oConnection, oRequest: oSelf.__foRequestHandler(oConnection, oRequest));
  
  def __foRequestHandler(oSelf, oConnection, oRequest, oInterceptedForServerURL = None):
    oSelf.fEnterFunctionOutput(oConnection = oConnection, oRequest = oRequest);
    try:
      ### Sanity checks ##########################################################
      oResponse = oSelf.__foResponseForConnectRequest(oConnection, oRequest);
      if oResponse:
        assert not oInterceptedForServerURL, \
            "A client is not supposed to make a HTTP CONNECT request through a connection where it has previously sent one and which we're intercepting.";
        return oSelf.fxExitFunctionOutput(oResponse, "HTTP CONNECT");
      oResponse = oSelf.__foResponseForInvalidMethodInRequest(oRequest)
      if oResponse: return oSelf.fxExitFunctionOutput(oResponse, "Invalid method");
      if oInterceptedForServerURL:
        # This request was made to a connection we are intercepting after the client send a HTTP CONNECT request.
        # The URL should be relative:
        if oRequest.sURL[:1] == "/":
          oURL = cURL.foFromString(oInterceptedForServerURL.sBase + oRequest.sURL);
        else:
          sReason = "The requested URL was not valid.",
          oResponse = oSelf.__foResponseForInvalidURLInRequest(oRequest, sReason);
      else:
        # This request was made to the proxy; the URL should be absolute:
        try:
          oURL = cURL.foFromString(oRequest.sURL);
        except cURL.cInvalidURLException:
          if oRequest.sURL.split("://")[0] not in ["http", "https"]:
            sReason = "This is a HTTP proxy, not a HTTP server.";
          else:
            sReason = "The requested URL was not valid.",
          oResponse = oSelf.__foResponseForInvalidURLInRequest(oRequest, sReason);
      if oResponse: return oSelf.fxExitFunctionOutput(oResponse, "Invalid URL");
      oResponse = oSelf.__foResponseForInvalidProxyHeaderInRequest(oRequest)
      if oResponse: return oSelf.fxExitFunctionOutput(oResponse, "Invalid proxy header");
      dHeader_sValue_by_sName = {};
      if not oInterceptedForServerURL:
        dHeader_sValue_by_sName["connection"] = "keep-alive";
      for sName in oRequest.fasGetHeaderNames():
        sLowerName = sName.lower();
        if not oInterceptedForServerURL and sLowerName in ["connection", "keep-alive"]:
          pass; # These are not passed on to the server unless we are intercepting the connection.
        elif sLowerName == "accept-encoding":
          # We will not allow the client to request a compression that we cannot decode so we will filter out
          # anything we do not support:
          sAcceptEncoding = ",".join([
            sCompressionType
            for sCompressionType in oRequest.fsGetHeaderValue(sName).split(",")
            if sCompressionType.strip().lower() in oRequest.asSupportedCompressionTypes
          ]);
          # If the client accepts compression types we support let the server know they are accepted, otherwise we
          # won't bother sending the header.
          if sAcceptEncoding:
            dHeader_sValue_by_sName[sName] = sAcceptEncoding;
        else:
          # This header is passed on unmodified:
          dHeader_sValue_by_sName[sName] = oRequest.fsGetHeaderValue(sName).strip();
      try:
        oResponse = oSelf.oHTTPClient.foGetResponseForURL(
          oURL = oURL,
          sMethod = oRequest.sMethod,
          dHeader_sValue_by_sName = dHeader_sValue_by_sName,
          sBody = oRequest.sBody if not oRequest.bChunked else None,
          asBodyChunks = oRequest.asBodyChunks if oRequest.bChunked else None,
          nTransactionTimeoutInSeconds = oSelf.__nTransactionTimeoutInSeconds,
          bCheckHostName = oSelf.__bCheckHostName,
        );
      except oSelf.oHTTPClient.cConnectTimeoutException:
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 502,
          sReasonPhrase = "Bad gateway",
          dHeader_sValue_by_sName = {
            "Connection": "Close",
            "Content-Type": "text/plain",
          },
          sBody = "The server did not respond before the request timed out.",
        );
      except oSelf.oHTTPClient.cConnectToUnknownAddressException:
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 400,
          sReasonPhrase = "Bad request",
          dHeader_sValue_by_sName = {
            "Connection": "Close",
            "Content-Type": "text/plain",
          },
          sBody = "The server cannot be found.",
        );
      except oSelf.oHTTPClient.cInvalidHTTPMessageException:
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 502,
          sReasonPhrase = "Bad gateway",
          dHeader_sValue_by_sName = {
            "Connection": "Close",
            "Content-Type": "text/plain",
          },
          sBody = "The server send an invalid HTTP response.",
        );
        
      # Remote HTTP Strict Transport Security header to allow the user to ignore certificate warnings.
      if oResponse.fbHasHeaderValue("Strict-Transport-Security"):
        oSelf.fStatusOutput("Filtered HSTS header.");
        oResponse.fRemoveHeader("Strict-Transport-Security");
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
    
  def __foResponseForInvalidURLInRequest(oSelf, oRequest, sReason):
    oSelf.fEnterFunctionOutput(oRequest = oRequest, oURL = oURL);
    try:
      # URL is invalid: return error specific to the reason why it is invalid.
      oResponse = cHTTPResponse(
        sHTTPVersion = oRequest.sHTTPVersion,
        uStatusCode = 400,
        sReasonPhrase = "Bad request",
        dHeader_sValue_by_sName = {
          "Connection": "Close",
          "Content-Type": "text/plain",
        },
        sBody = sReason,
      );
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foResponseForInvalidMethodInRequest(oSelf, oRequest):
    oSelf.fEnterFunctionOutput(oRequest = oRequest);
    try:
      if oRequest.sMethod.upper() not in ["CONNECT", "GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH"]:
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 400,
          sReasonPhrase = "Bad request",
          dHeader_sValue_by_sName = {
            "Connection": "Close",
            "Content-Type": "text/plain",
          },
          sBody = "The request method was not valid.",
        );
        return oSelf.fxExitFunctionOutput(oResponse);
      return oSelf.fxExitFunctionOutput(None, "Request has valid method");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foResponseForInvalidProxyHeaderInRequest(oSelf, oRequest):
    oSelf.fEnterFunctionOutput(oRequest = oRequest);
    try:
      if oRequest.fbHasHeaderValue("Proxy-Authenticate"):
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 400,
          sReasonPhrase = "Bad request",
          dHeader_sValue_by_sName = {
            "Connection": "Close",
            "Content-Type": "text/plain",
          },
          sBody = "This proxy does not require authentication.",
        );
        return oSelf.fxExitFunctionOutput(oResponse);
      if oRequest.fbHasHeaderValue("Proxy-Authorization"):
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 400,
          sReasonPhrase = "Bad request",
          dHeader_sValue_by_sName = {
            "Connection": "Close",
            "Content-Type": "text/plain",
          },
          sBody = "This proxy does not require authorization.",
        );
        return oSelf.fxExitFunctionOutput(oResponse);
      return oSelf.fxExitFunctionOutput(None, "Request does not have an invalid proxy header");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foResponseForConnectRequest(oSelf, oConnectionFromClient, oRequest):
    oSelf.fEnterFunctionOutput(oConnectionFromClient = oConnectionFromClient, oRequest = oRequest);
    try:
      if oRequest.sMethod.upper() == "CONNECT":
        # Check the sanity of the request.
        sHostHeader = oRequest.fsGetHeaderValue("Host");
        sLowerRequestURI = oRequest.sURL.lower();
        if not sHostHeader or sHostHeader.strip().lower() != sLowerRequestURI:
          oResponse = cHTTPResponse(
            sHTTPVersion = oRequest.sHTTPVersion,
            uStatusCode = 400,
            sReasonPhrase = "Bad request",
            dHeader_sValue_by_sName = {
              "Connection": "Close",
              "Content-Type": "text/plain",
            },
            sBody = "The requested URL and host header did not match.",
          );
          return oSelf.fxExitFunctionOutput(oResponse, "URL %s and host header %s mismatched" % (repr(oRequest.sURL), repr(sHostHeader)));
        # Parse the request URI to construct a URL for the server:
        try:
          sServerHostName, sServerPort = sLowerRequestURI.split(":");
          uServerPort = long(sServerPort);
        except:
          oResponse = cHTTPResponse(
            sHTTPVersion = oRequest.sHTTPVersion,
            uStatusCode = 400,
            sReasonPhrase = "Bad request",
            dHeader_sValue_by_sName = {
              "Connection": "Close",
              "Content-Type": "text/plain",
            },
            sBody = "The requested URL was not valid.",
          );
          return oSelf.fxExitFunctionOutput(oResponse, "Invalid URL %s" % repr(oRequest.sURL));
        oServerURL = cURL.foFromString("https://%s:%d" % (sServerHostName, uServerPort));
        if oSelf.__oInterceptSSLConnectionsCertificateAuthority:
          # We will be intercepting the requests, so we won't make a connection to the server immediately. We will
          # send a "200 Ok" response and start a thread that will handle the connection, but we will not simply pipe
          # the data in this thread. Instead the thread will negotiate SSL with the client using a wildcard certificate
          # and then wait for requests, forward them to the server, receive the response and forward it to the client.
          fConnectionHandler = oSelf.__fInterceptConnection;
          txConnectionHandlerArguments = (oConnectionFromClient, oServerURL);
        else:
          # If we are not intercepting SSL connections, we will try to connect to the server. If this succeeds we will
          # send a "200 OK" response to the client and start a thread that will pipe data back and forth between the
          # client and server.
          # Ask the cHTTPClient instance for a connection to this server:
          oConnectionToServer = oSelf.oHTTPClient.foGetConnectionAndStartTransaction(
            oURL = oServerURL,
            nConnectTimeoutInSeconds = oSelf.oHTTPClient.nDefaultConnectTimeoutInSeconds,
            nTransactionTimeoutInSeconds = None,
            bCheckHostName = oSelf.__bCheckHostName,
            # Normally the client is going to do the SSL negotiation, but if we are intercepting SSL connections, we will
            bNoSSLNegotiation = True,
          );
          if not oConnectionToServer:
            oResponse = cHTTPResponse(
              sHTTPVersion = oRequest.sHTTPVersion,
              uStatusCode = 502,
              sReasonPhrase = "Bad gateway",
              dHeader_sValue_by_sName = {
                "Connection": "Close",
                "Content-type": "text/plain",
              },
              sBody = "Could not connect to remote server.",
            );
            return oSelf.fxExitFunctionOutput(oResponse, "Could not connect to %s" % oServerURL);
          # Create a thread that will pipe data back and forth between the client and server
          fConnectionHandler = oSelf.__fPipeConnection;
          txConnectionHandlerArguments = (oConnectionFromClient, oConnectionToServer, oServerURL);
        def fStartConnectionHandlerThread(oConnectionFromClient, oResponse):
          # We'll continue to use "oConnectionFromClient.fSendResponse(oResponse)" in the interception thread, which
          # will trigger more "response sent" callbacks. For this reason, we need to remove the callback after the
          # first, or we'll have multiple threads attempting to handle the same connection.
          assert oConnectionFromClient.fbRemoveCallback("response sent", fStartConnectionHandlerThread), \
              "Now breaks my wooden shoe";
          oThread = cThread(fConnectionHandler, *txConnectionHandlerArguments);
          oSelf.__oSecureConnectionsLock.fAcquire();
          try:
            oSelf.__aoSecureConnectionsFromClient.append(oConnectionFromClient);
            oSelf.__aoSecureConnectionThreads.append(oThread);
          finally:
            oSelf.__oSecureConnectionsLock.fRelease();
          oThread.fStart(bVital = False);
        oConnectionFromClient.fAddCallback("response sent", fStartConnectionHandlerThread);
        # Send a reponse to the client.
        oResponse = cHTTPResponse(
          sHTTPVersion = oRequest.sHTTPVersion,
          uStatusCode = 200,
          sReasonPhrase = "Ok",
          dHeader_sValue_by_sName = {
            "Connection": "Keep-Alive",
            "Content-type": "text/plain",
          },
          sBody = "Connected to remote server.",
        );
        oResponse.fSetMetaData("bStopHandlingHTTPMessages", True);
        return oSelf.fxExitFunctionOutput(oResponse);
      return oSelf.fxExitFunctionOutput(None, "Not a CONNECT request");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fInterceptConnection(oSelf, oConnectionFromClient, oServerURL):
    oSelf.fEnterFunctionOutput(oConnectionFromClient = oConnectionFromClient);
    try:
      oThread = cThread.foGetCurrent();
      try:
        # When intercepting a supposedly secure connection, we will wait for the client to make requests through the
        # connection, forward it to the server to get a response using the same code as the normal proxy, and then
        # send the response back to the client.
        oSelf.fStatusOutput("Intercepting secure connection to server %s for client %s." % (oServerURL.sBase, oConnectionFromClient.fsToString()), bVerbose = False);
        oSelf.fStatusOutput("Generating SSL certificate for %s..." % oServerURL.sHostName);
        oSSLContext = oSelf.__oInterceptSSLConnectionsCertificateAuthority.foGenerateSSLContextForServerWithHostName(oServerURL.sHostName);
        oSelf.fStatusOutput("Negotiating secure socket for %s..." % oConnectionFromClient.fsToString());
        if not oConnectionFromClient.fbStartTransaction(oSelf.__nSecureConnectionIdleTimeoutInSeconds, bWait = True):
          return oSelf.fExitFunctionOutput("Cannot start a transaction on the client socket");
        try:
          try:
            oConnectionFromClient.fWrapInSSLContext(oSSLContext);
          except oConnectionFromClient.cTransactionTimeoutException:
            return oSelf.fExitFunctionOutput("Transaction timeout while negotiating secure connection with client %s." % oConnectionFromClient.fsToString());
          except oConnectionFromClient.cConnectionClosedException:
            return oSelf.fExitFunctionOutput("Connection closed while negotiating secure connection with client %s." % oConnectionFromClient.fsToString());
          except oSSLContext.cSSLException as oException:
            return oSelf.fExitFunctionOutput("Could not negotiate a secure connection with the client; is SSL pinning enabled? (error: %s)" % repr(oException));
        finally:
          oConnectionFromClient.fEndTransaction();
        while not oSelf.__bStopping:
          oSelf.fStatusOutput("Reading request from %s..." % oConnectionFromClient.fsToString());
          if not oConnectionFromClient.fbStartTransaction(oSelf.oHTTPServer.nDefaultWaitForRequestTimeoutInSeconds):
            assert not oConnectionFromClient.bOpen, \
                "Cannot start transaction";
            break;
          try:
            oRequest = oConnectionFromClient.foReceiveRequest();
            if not oRequest:
              oSelf.fStatusOutput("Reading request from %s timed out; terminating connection..." % oConnectionFromClient.fsToString());
              oConnectionFromClient.fTerminate();
              break;
            oResponse = oSelf.__foRequestHandler(oConnectionFromClient, oRequest, oInterceptedForServerURL = oServerURL);
            # Send the response to the client
            oSelf.fStatusOutput("Sending response (%s) to %s..." % (oResponse.fsToString(), oConnectionFromClient.fsToString()));
            try:
              oConnectionFromClient.fSendResponse(oResponse);
            except oConnectionFromClient.cTransactionTimeoutException:
              oSelf.fStatusOutput("Transaction timeout while sending response to %s." % oConnectionFromClient.fsToString());
              break;
            except oConnectionFromClient.cConnectionClosedException:
              oSelf.fStatusOutput("Connection closed while sending response to %s." % oConnectionFromClient.fsToString());
              break;
          finally:
            oConnectionFromClient.fEndTransaction();
          oSelf.fFireCallbacks("response sent to client", oRequest, oResponse);
          if oResponse.fxGetMetaData("bStopHandlingHTTPMessages"):
            break;
          # continue "while 1" loop
        oSelf.fStatusOutput("Stopped intercepting secure connection to server %s for client %s." % (oServerURL.sBase, oConnectionFromClient.fsToString()), bVerbose = False);
        oSelf.fExitFunctionOutput();
      finally:
        oConnectionFromClient.fTerminate(); # Just to be sure.
        oSelf.__oSecureConnectionsLock.fAcquire();
        try:
          oSelf.__aoSecureConnectionsFromClient.remove(oConnectionFromClient);
          oSelf.__aoSecureConnectionThreads.remove(oThread);
        finally:
          oSelf.__oSecureConnectionsLock.fRelease();
        oSelf.__fCheckForTermination();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
      
  def __fPipeConnection(oSelf, oConnectionFromClient, oConnectionToServer, oServerURL):
    oSelf.fEnterFunctionOutput(oConnectionFromClient = oConnectionFromClient, oConnectionToServer = oConnectionToServer);
    try:
      oThread = cThread.foGetCurrent();
      try:
        oSelf.fStatusOutput("Piping secure connection to server %s for client %s." % (oServerURL.sBase, oConnectionFromClient.fsToString()), bVerbose = False);
        if not oConnectionFromClient.fbStartTransaction(oSelf.__nSecureConnectionIdleTimeoutInSeconds, bWait = True):
          return oSelf.fExitFunctionOutput("Cannot start a transaction on the client socket");
        try:
          oConnectionFromClient.fPipe(
            oOther = oConnectionToServer,
            nConnectionTimeoutInSeconds = oSelf.__nSecureConnectionTimeoutInSeconds,
            nIdleTimeoutInSeconds = oSelf.__nSecureConnectionIdleTimeoutInSeconds,
          );
        finally:
          oConnectionFromClient.fEndTransaction();
        oSelf.fStatusOutput("Stopped piping secure connection to server %s for client %s." % (oServerURL.sBase, oConnectionFromClient.fsToString()), bVerbose = False);
        oSelf.fExitFunctionOutput();
      finally:
        oConnectionFromClient.fTerminate(); # Just to be sure.
        oConnectionToServer.fTerminate(); # Just to be sure.
        oSelf.__oSecureConnectionsLock.fAcquire();
        try:
          oSelf.__aoSecureConnectionsFromClient.remove(oConnectionFromClient);
          oSelf.__aoSecureConnectionThreads.remove(oThread);
        finally:
          oSelf.__oSecureConnectionsLock.fRelease();
        oSelf.__fCheckForTermination();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsToString(oSelf):
    # We do not hold an exclusive lock, so values can change while we read them. To prevent a double fetch from causing
    # problems (e.g. a value is check to not be None, but then output after it has been changed to None). we will read
    # all values once. This does not protect against race conditions that make the information contradictory (e.g. the
    # transaction lock being read as not locked, but the timeout being read as not None because the socket was locked
    # between the two reads). However, this function is a half-hearted attempt to get some potentially useful debug
    # information and its output is not vital to the functioning of the object, so it'll have to do for now.
    uSecureConnections = len(oSelf.__aoSecureConnectionsFromClient);
    uSecureConnectionThreads = len(oSelf.__aoSecureConnectionThreads);
    bStopping = oSelf.__bStopping;
    bTerminated = oSelf.__bTerminated;
    asAttributes = [s for s in [
      "%s secure connections" % (str(uSecureConnections) if uSecureConnections else "no"),
      "%s threads" % (str(uSecureConnectionThreads) if uSecureConnectionThreads else "no"),
      "stopping" if bStopping else "",
      "terminated" if bTerminated else "",
    ] if s];
    sDetails = "%s => %s%s" % (
      oSelf.oHTTPServer.fsToString(),
      oSelf.oHTTPClient.fsToString(),
      " (%s)" % ", ".join(asAttributes) if asAttributes else "",
    );
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
    