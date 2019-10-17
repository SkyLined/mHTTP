import socket, time;
from mDebugOutput import fDebugOutput;
import mHTTP;
from mMultiThreading import cThread;

def fTestClient(oCertificateStore, oTestURL, oSecureTestURL, oUnknownAddressURL, oInvalidAddressURL, oConnectionRefusedURL, oConnectionTimeoutURL, oConnectionClosedURL, oOutOfBandDataURL, oInvalidHTTPMessageURL):
  fDebugOutput("**** Creating a mHTTP.cHTTPClient instance ".ljust(160, "*"));
  oHTTPClient = mHTTP.cHTTPClient(oCertificateStore);
  fDebugOutput(("**** Making a first test request to %s " % oTestURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oTestURL).sData));
  fDebugOutput(("**** Making a second test request to %s " % oTestURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oTestURL).sData));
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
  
  fDebugOutput(("**** Making a first test request to %s " % oSecureTestURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oSecureTestURL).sData));
  fDebugOutput(("**** Making a second test request to %s " % oSecureTestURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oSecureTestURL).sData));
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
  
  # Create a server on a socket but do not listen so connections are refused.
  oConnectionRefusedServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oConnectionRefusedServerSocket.bind((oConnectionRefusedURL.sHostName, oConnectionRefusedURL.uPort));
  
  # Create a server on a socket that sends out-of-band data.
  oOutOfBandDataServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oOutOfBandDataServerSocket.bind((oOutOfBandDataURL.sHostName, oOutOfBandDataURL.uPort));
  oOutOfBandDataServerSocket.listen(1);
  oResponse = mHTTP.cHTTPResponse(sData = "Hello, world!");
  sResponseWithOutOfBandData = oResponse.fsSerialize() + oResponse.fsSerialize();
  def fOutOfBandDataServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oOutOfBandDataServerSocket.accept();
    oClientSocket.send(sResponseWithOutOfBandData);
    while 1:
      try:
        oClientSocket.recv(0x1000);
      except Exception:
        break;
  
  oOutOfBandDataServerThread = cThread(fOutOfBandDataServerThread);
  oOutOfBandDataServerThread.fStart(bVital = False);
  
  # Create a server on a socket that immediately closes the connection.
  oConnectionClosedServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oConnectionClosedServerSocket.bind((oConnectionClosedURL.sHostName, oConnectionClosedURL.uPort));
  oConnectionClosedServerSocket.listen(1);
  def fConnectionClosedServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oConnectionClosedServerSocket.accept();
    oClientSocket.close();
    
  oConnectionClosedServerThread = cThread(fConnectionClosedServerThread);
  oConnectionClosedServerThread.fStart(bVital = False);

  # Create a server on a socket that sends an invalid response.
  oInvalidHTTPMessageServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
  oInvalidHTTPMessageServerSocket.bind((oInvalidHTTPMessageURL.sHostName, oInvalidHTTPMessageURL.uPort));
  oInvalidHTTPMessageServerSocket.listen(1);
  sInvalidResponse = "Hello, world!\r\n";
  def fInvalidHTTPMessageServerThread():
    (oClientSocket, (sClientIP, uClientPort)) = oInvalidHTTPMessageServerSocket.accept();
    oClientSocket.recv(0x1000); # This should cover the request, which we discard.
    oClientSocket.send(sInvalidResponse);
  
  oInvalidHTTPMessageServerThread = cThread(fInvalidHTTPMessageServerThread);
  oInvalidHTTPMessageServerThread.fStart(bVital = False);
  
  for (oURL, cException) in (
    (oUnknownAddressURL, mHTTP.cConnectToUnknownAddressException),
    (oInvalidAddressURL, mHTTP.cConnectToInvalidAddressException),
    (oConnectionRefusedURL, mHTTP.cConnectionRefusedException),
    (oConnectionTimeoutURL, mHTTP.cConnectTimeoutException),
    (oConnectionClosedURL, mHTTP.cConnectionClosedException),
    (oOutOfBandDataURL, mHTTP.cOutOfBandDataException),
    (oInvalidHTTPMessageURL, mHTTP.cInvalidHTTPMessageException),
  ):
    fDebugOutput(("**** Making a test request to %s " % oURL).ljust(160, "*"));
    fDebugOutput("  * Expecting %s exception." % cException.__name__);
    try:
      # Use a short connect timeout to speed things up: all connections should be created in about 1 second except the
      # one that purposefully times out and this way we do not have to wait for that to happen very long.
      fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oURL, nConnectTimeoutInSeconds = 4).sData));
    except cException as oException:
      fDebugOutput("  + Threw %s." % repr(oException));
    else:
      raise AssertionError("No exception");
  
  fDebugOutput("**** Stopping mHTTP.cHTTPClient instance ".ljust(160, "*"));
  oHTTPClient.fStop();
  oHTTPClient.fWait();
  
  fDebugOutput("**** Stopping connection refused server ".ljust(160, "*"));
  oConnectionRefusedServerSocket.close(); # Has no thread.
  
  fDebugOutput("**** Stopping out-of-band data server ".ljust(160, "*"));
  oOutOfBandDataServerSocket.close();
  oOutOfBandDataServerThread.fWait();
  
  fDebugOutput("**** Stopping connection closed server ".ljust(160, "*"));
  oConnectionClosedServerSocket.close();
  oConnectionClosedServerThread.fWait();
  
  fDebugOutput("**** Stopping invalid http message server ".ljust(160, "*"));
  oInvalidHTTPMessageServerSocket.close();
  oInvalidHTTPMessageServerThread.fWait();
  
