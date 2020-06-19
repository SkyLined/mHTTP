import socket, threading;
from mHTTP import *;
from mHTTP.mHTTPExceptions import *;
from mHTTPConnections import cHTTPConnection;
from mMultiThreading import cThread;
from oConsole import oConsole;

uServerPort = 28080;
def foGetServerURL(sNote):
  global uServerPort;
  uServerPort += 1;
  return cURL.foFromString("http://localhost:%d/%s" % (uServerPort, sNote));

oTestURL = cURL.foFromString("http://example.com");
oSecureTestURL = cURL.foFromString("https://example.com");
oUnknownHostnameURL = cURL.foFromString("http://does.not.exist.example.com/unknown-hostname");
oInvalidAddressURL = cURL.foFromString("http://0.0.0.0/invalid-address");
oConnectionRefusedURL = foGetServerURL("refuse-connection");
oConnectionTimeoutURL = cURL.foFromString("http://example.com:1"); # Not sure how to do this locally :(
oConnectionDisconnectedURL = foGetServerURL("disconnect");
oConnectionShutdownURL = foGetServerURL("shutdown");
oResponseTimeoutURL = foGetServerURL("timeout");
oOutOfBandDataURL = foGetServerURL("send-out-of-band-data");
oInvalidHTTPMessageURL = foGetServerURL("send-invalid-response");

def fTestClient(
  oHTTPClient,
  oCertificateStore,
  nEndWaitTimeoutInSeconds,
):
  oServersShouldBeRunningLock = threading.Lock();
  oServersShouldBeRunningLock.acquire(); # Released once servers should stop runnning.
  oConsole.fPrint("\xFE\xFE\xFE\xFE Making a first test request to %s " % oTestURL, sPadding = "\xFE");
  (oRequest, oResponse) = oHTTPClient.ftozGetRequestAndResponseForURL(oTestURL);
  assert oResponse, \
      "No response!?";
  oConsole.fPrint("  oRequest = %s" % oRequest.fsSerialize());
  oConsole.fPrint("  oResponse = %s" % oResponse.fsSerialize());
  oConsole.fPrint("\xFE\xFE\xFE\xFE Making a second test request to %s " % oTestURL, sPadding = "\xFE");
  (oRequest, oResponse) = oHTTPClient.ftozGetRequestAndResponseForURL(oTestURL);
  assert oResponse, \
      "No response!?";
  oConsole.fPrint("  oRequest = %s" % oRequest);
  oConsole.fPrint("  oResponse = %s" % oResponse);
  if oHTTPClient.__class__.__name__ == "cHTTPClient": 
    # cHTTPClient specific checks
    asConnectionPoolsProtocolHostPort = set(oHTTPClient._cHTTPClient__doConnectionsToServerPool_by_sProtocolHostPort.keys());
    assert asConnectionPoolsProtocolHostPort == set((oTestURL.sBase,)), \
        "Expected a oHTTPClient instance to have one cConnectionsToServerPool instance for %s, but found %s" % \
        (oTestURL.sBase, repr(asConnectionPoolsProtocolHostPort));
    oConnectionsToServerPool = oHTTPClient._cHTTPClient__doConnectionsToServerPool_by_sProtocolHostPort.get(oTestURL.sBase);
    assert oConnectionsToServerPool, \
        "Expected a cConnectionsToServerPool instance for %s, but found none" % oTestURL;
    aoConnections = oConnectionsToServerPool._cHTTPConnectionsToServerPool__aoConnections;
    assert len(aoConnections) == 1, \
        "Expected a cConnectionsToServerPool instance with one connection for %s, but found %d connections" % \
        (oTestURL, len(aoConnections));
  if oHTTPClient.__class__.__name__ == "cHTTPClientUsingProxyServer": 
    # cHTTPClientUsingProxyServer specific checks
    aoConnectionsToProxyNotConnectedToAServer = oHTTPClient._cHTTPClientUsingProxyServer__aoConnectionsToProxyNotConnectedToAServer;
    assert len(aoConnectionsToProxyNotConnectedToAServer) == 1, \
        "Expected one connection to the proxy, but found %d connections" % len(aoConnectionsToProxyNotConnectedToAServer);
    doSecureConnectionToServerThroughProxy_by_sProtocolHostPort = oHTTPClient._cHTTPClientUsingProxyServer__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort;
    asSecureConnectionTargets = doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.keys();
    assert len(asSecureConnectionTargets) == 0, \
        "Expected no secure connections, but found %s" % repr(asSecureConnectionTargets);
  
  # Wrapping SSL secured sockets in SSL is not currently supported, so the client cannot secure a connection
  # to a server over a secure connection to a proxy.
  if oHTTPClient.__class__.__name__ != "cHTTPClientUsingProxyServer" or not oHTTPClient.foGetProxyServerURL().bSecure: 
    oConsole.fPrint("\xFE\xFE\xFE\xFE Making a first test request to %s " % oSecureTestURL, sPadding = "\xFE");
    (oRequest, oResponse) = oHTTPClient.ftozGetRequestAndResponseForURL(oSecureTestURL);
    assert oResponse, \
        "No response!?";
    oConsole.fPrint("  oRequest = %s" % oRequest);
    oConsole.fPrint("  oResponse = %s" % oResponse);
    oConsole.fPrint("\xFE\xFE\xFE\xFE Making a second test request to %s " % oSecureTestURL, sPadding = "\xFE");
    (oRequest, oResponse) = oHTTPClient.ftozGetRequestAndResponseForURL(oSecureTestURL);
    assert oResponse, \
        "No response!?";
    oConsole.fPrint("  oRequest = %s" % oRequest);
    oConsole.fPrint("  oResponse = %s" % oResponse);
    if oHTTPClient.__class__.__name__ == "cHTTPClient": 
      # cHTTPClient specific checks
      asConnectionPoolsProtocolHostPort = set(oHTTPClient._cHTTPClient__doConnectionsToServerPool_by_sProtocolHostPort.keys());
      assert asConnectionPoolsProtocolHostPort == set((oTestURL.sBase, oSecureTestURL.sBase)), \
          "Expected a oHTTPClient instance to have a cConnectionsToServerPool instance for %s and %s, but found %s" % \
          (oTestURL.sBase, oSecureTestURL.sBase, repr(asConnectionPoolsProtocolHostPort));
      
      oConnectionsToServerPool = oHTTPClient._cHTTPClient__doConnectionsToServerPool_by_sProtocolHostPort.get(oSecureTestURL.sBase);
      assert oConnectionsToServerPool, \
          "Expected a cConnectionsToServerPool instance for %s, but found none" % oSecureTestURL;
      aoConnections = oConnectionsToServerPool._cHTTPConnectionsToServerPool__aoConnections;
      assert len(aoConnections) == 1, \
          "Expected a cConnectionsToServerPool instance with one connection for %s, but found %d connections" % \
          (oSecureTestURL, len(aoConnections));
    if oHTTPClient.__class__.__name__ == "cHTTPClientUsingProxyServer": 
      # cHTTPClientUsingProxyServer specific checks
      aoConnectionsToProxyNotConnectedToAServer = oHTTPClient._cHTTPClientUsingProxyServer__aoConnectionsToProxyNotConnectedToAServer;
      doSecureConnectionToServerThroughProxy_by_sProtocolHostPort = oHTTPClient._cHTTPClientUsingProxyServer__doSecureConnectionToServerThroughProxy_by_sProtocolHostPort;
      asSecureConnectionTargets = doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.keys();
      bFoundUnexpectedNonSecureConnections = len(aoConnectionsToProxyNotConnectedToAServer) != 0;
      bFoundUnexpectedSecureConnections = set(asSecureConnectionTargets) != set((oSecureTestURL.sBase,));
      if bFoundUnexpectedNonSecureConnections or bFoundUnexpectedSecureConnections:
        if bFoundUnexpectedNonSecureConnections:
          print "The HTTP client has unexpected non-secure connections!";
        if bFoundUnexpectedSecureConnections:
          print "The HTTP client has unexpected secure connections!";
        print "Non-secure connections:";
        for oNonSecureConnection in aoConnectionsToProxyNotConnectedToAServer:
          print "* %s" % repr(oNonSecureConnection);
        print "Secure connections:";
        for (sProtocolHostPort, oSecureConnection) in doSecureConnectionToServerThroughProxy_by_sProtocolHostPort.items():
          print "* %S => %s" % (sProtocolHostPort, repr(oSecureConnection));
        raise AssertionError();
  
  # Create a server on a socket but do not listen so connections are refused.
  oConnectionRefusedServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oConnectionRefusedServerSocket.bind((oConnectionRefusedURL.sHostname, oConnectionRefusedURL.uPort));

  # Create a server on a socket that sends out-of-band data.
  oOutOfBandDataServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oOutOfBandDataServerSocket.bind((oOutOfBandDataURL.sHostname, oOutOfBandDataURL.uPort));
  oOutOfBandDataServerSocket.listen(1);
  oResponse = cHTTPConnection.foCreateResponse(szData = "Hello, world!");
  sResponseWithOutOfBandData = oResponse.fsSerialize() + oResponse.fsSerialize();
  def fOutOfBandDataServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oOutOfBandDataServerSocket.accept();
    oConsole.fPrint("Out-of-band data server receiving request...");
    oClientSocket.recv(0x1000);
    oConsole.fPrint("Out-of-band data server sending valid response with out-of-band data...");
    oClientSocket.send(oResponse.fsSerialize() + "X");
    oConsole.fPrint("Out-of-band data server thread terminated.");
    oClientSocket.close();
  
  oOutOfBandDataServerThread = cThread(fOutOfBandDataServerThread);
  oOutOfBandDataServerThread.fStart(bVital = False);
  
  # Create a server on a socket that immediately closes the connection.
  oConnectionDisconnectedServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oConnectionDisconnectedServerSocket.bind((oConnectionDisconnectedURL.sHostname, oConnectionDisconnectedURL.uPort));
  oConnectionDisconnectedServerSocket.listen(1);
  def fConnectionDisconnectedServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oConnectionDisconnectedServerSocket.accept();
    oConsole.fPrint("Disconnect server is disconnecting the connection...");
    oClientSocket.close();
    oConsole.fPrint("Disconnect server thread terminated.");
    
  oConnectionDisconnectedServerThread = cThread(fConnectionDisconnectedServerThread);
  oConnectionDisconnectedServerThread.fStart(bVital = False);
  
  # Create a server on a socket that immediately shuts down the connection.
  oConnectionShutdownServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oConnectionShutdownServerSocket.bind((oConnectionShutdownURL.sHostname, oConnectionShutdownURL.uPort));
  oConnectionShutdownServerSocket.listen(1);
  def fConnectionShutdownServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oConnectionShutdownServerSocket.accept();
    oConsole.fPrint("Shutdown server is shutting down the connection for writing...");
    oClientSocket.shutdown(socket.SHUT_WR);
    oConsole.fPrint("Shutdown server is sleeping to keep the connection open....");
    oServersShouldBeRunningLock.acquire();
    oServersShouldBeRunningLock.release();
    oConsole.fPrint("Shutdown server thread terminated.");
    
  oConnectionShutdownServerThread = cThread(fConnectionShutdownServerThread);
  oConnectionShutdownServerThread.fStart(bVital = False);

  # Create a server on a socket that does not send a response.
  oResponseTimeoutServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oResponseTimeoutServerSocket.bind((oResponseTimeoutURL.sHostname, oResponseTimeoutURL.uPort));
  oResponseTimeoutServerSocket.listen(1);
  def fResponseTimeoutServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oResponseTimeoutServerSocket.accept();
    oConsole.fPrint("Response timeout server receiving request...");
    oClientSocket.recv(0x1000);
    oConsole.fPrint("Response timeout server is sleeping to avoid sending a response...");
    oServersShouldBeRunningLock.acquire();
    oServersShouldBeRunningLock.release();
    oConsole.fPrint("Response timeout thread terminated.");
    
  oResponseTimeoutServerThread = cThread(fResponseTimeoutServerThread);
  oResponseTimeoutServerThread.fStart(bVital = False);

  # Create a server on a socket that sends an invalid response.
  oInvalidHTTPMessageServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oInvalidHTTPMessageServerSocket.bind((oInvalidHTTPMessageURL.sHostname, oInvalidHTTPMessageURL.uPort));
  oInvalidHTTPMessageServerSocket.listen(1);
  sInvalidResponse = "Hello, world!\r\n";
  def fInvalidHTTPMessageServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oInvalidHTTPMessageServerSocket.accept();
    oConsole.fPrint("Invalid HTTP Message server received request; sending invalid response...");
    oClientSocket.recv(0x1000); # This should cover the request, which we discard.
    oClientSocket.send(sInvalidResponse);
    oConsole.fPrint("Invalid HTTP Message server thread terminated.");
  
  oInvalidHTTPMessageServerThread = cThread(fInvalidHTTPMessageServerThread);
  oInvalidHTTPMessageServerThread.fStart(bVital = False);
  
  for (oURL, cException, uStatusCode, uNumberOfRequests) in (
    (oUnknownHostnameURL,         cUnknownHostnameException,    400, 1),
    (oInvalidAddressURL,          cInvalidAddressException,     400, 1),
    (oConnectionRefusedURL,       cConnectionRefusedException,  502, 1),
    (oConnectionTimeoutURL,       cTimeoutException,            504, 1),
    (oConnectionDisconnectedURL,  cDisconnectedException,       502, 1),
    (oConnectionShutdownURL,      cShutdownException,           502, 1),
    (oResponseTimeoutURL,         cTimeoutException,            504, 1),
    (oOutOfBandDataURL,           cOutOfBandDataException,      502, 2),
    (oInvalidHTTPMessageURL,      cInvalidMessageException,     502, 1),
  ):
    oConsole.fPrint("\xFE\xFE\xFE\xFE Making a test request to %s " % oURL, sPadding = "\xFE");
    if oHTTPClient.__class__.__name__ == "cHTTPClient":
      oConsole.fStatus("  * Expecting %s exception..." % cException.__name__);
      uStatusCode = None;
    if oHTTPClient.__class__.__name__ == "cHTTPClientUsingProxyServer":
      if uStatusCode:
        oConsole.fStatus("  * Expecting a HTTP %03d reponse..." % uStatusCode);
        cException = None;
    for uConnectionNumber in xrange(1, uNumberOfRequests + 1):
      if uConnectionNumber < uNumberOfRequests:
        # We do not yet expect an exception, so we won't handle one.
        oResponse = oHTTPClient.fozGetResponseForURL(oURL);
        assert oResponse, \
            "No response!?";
        oConsole.fPrint("  oResponse = %s" % oResponse);
      else:
        try:
          # Use a short connect timeout to speed things up: all connections should be created in about 1 second except the
          # one that purposefully times out and this way we do not have to wait for that to happen very long.
          oResponse = oHTTPClient.fozGetResponseForURL(oURL);
          assert oResponse, \
              "No response!?";
          assert uStatusCode in (None, oResponse.uStatusCode), \
              "Expected a HTTP %03d response, got %s" % (uStatusCode, oResponse.fsGetStatusLine());
          oConsole.fPrint("  oResponse = %s" % oResponse);
        except Exception as oException:
          if cException and isinstance(oException, cException):
            oConsole.fPrint("  + Threw %s." % repr(oException));
          else:
            oConsole.fPrint("  - Threw %s." % repr(oException));
            if cException:
              oConsole.fPrint("    Expected %s." % cException.__name__);
            else:
              oConsole.fPrint("    No exception expected.");
            raise;
        else:
          if cException:
            oConsole.fPrint("  - No exception thrown.");
            raise AssertionError("No exception");
  
  # Allow server threads to stop.
  oServersShouldBeRunningLock.release();
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping HTTP Client ", sPadding = "\xFE");
  oHTTPClient.fStop();
  assert oHTTPClient.fbWait(nEndWaitTimeoutInSeconds), \
    "HTTP Client did not stop in time";
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping connection refused server ", sPadding = "\xFE");
  oConnectionRefusedServerSocket.close(); # Has no thread.

  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping out-of-band data server ", sPadding = "\xFE");
  oOutOfBandDataServerSocket.close();
  assert oOutOfBandDataServerThread.fbWait(nEndWaitTimeoutInSeconds), \
      "Out-of-band data server thread (%d/0x%X) did not stop in time." % \
      (oOutOfBandDataServerThread.uId, oOutOfBandDataServerThread.uId);
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping connection closed server ", sPadding = "\xFE");
  oConnectionDisconnectedServerSocket.close();
  assert oConnectionDisconnectedServerThread.fbWait(nEndWaitTimeoutInSeconds), \
      "Connection closed server thread (%d/0x%X) did not stop in time." % \
      (oConnectionDisconnectedServerThread.uId, oConnectionDisconnectedServerThread.uId);
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping connection shutdown server ", sPadding = "\xFE");
  oConnectionShutdownServerSocket.close();
  assert oConnectionShutdownServerThread.fbWait(nEndWaitTimeoutInSeconds), \
      "Connection shutdown server thread (%d/0x%X) did not stop in time." % \
      (oConnectionShutdownServerThread.uId, oConnectionShutdownServerThread.uId);
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping response timeout server ", sPadding = "\xFE");
  oResponseTimeoutServerSocket.close();
  assert oResponseTimeoutServerThread.fbWait(nEndWaitTimeoutInSeconds), \
      "Connection shutdown server thread (%d/0x%X) did not stop in time." % \
      (oResponseTimeoutServerThread.uId, oResponseTimeoutServerThread.uId);
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping invalid http message server ", sPadding = "\xFE");
  oInvalidHTTPMessageServerSocket.close();
  assert oInvalidHTTPMessageServerThread.fbWait(nEndWaitTimeoutInSeconds), \
      "Invalid http message server thread (%d/0x%X) did not stop in time." % \
      (oInvalidHTTPMessageServerThread.uId, oInvalidHTTPMessageServerThread.uId);
  
