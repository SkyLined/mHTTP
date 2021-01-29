from mHTTP import cHTTPClientSideProxyServer, cHTTPClientUsingProxyServer;
from oConsole import oConsole;
from fTestClient import fTestClient;
try: # SSL support is optional.
  from mSSL import oCertificateAuthority as o0CertificateAuthority;
except:
  o0CertificateAuthority = None; # No SSL support

def fTestProxyClientAndServer(
  oProxyServerURL,
  oCertificateStore,
  oInterceptSSLConnectionsCertificateAuthority,
  nEndWaitTimeoutInSeconds,
  f0LogEvents
):
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClientSideProxyServer instance... ", sPadding = "\xFE");
  oProxyServer = cHTTPClientSideProxyServer(
    szHostname = oProxyServerURL.sHostname,
    uzPort = oProxyServerURL.uPort,
    o0ServerSSLContext = (
      o0CertificateAuthority.foGenerateServersideSSLContextForHostname(oProxyServerURL.sHostname)
    ) if oProxyServerURL.bSecure else None,
    o0zCertificateStore = oCertificateStore,
    o0InterceptSSLConnectionsCertificateAuthority = oInterceptSSLConnectionsCertificateAuthority,
    # Make sure the proxy server times out waiting for the HTTP server
    # before the client times out waiting for the proxy.
    n0zConnectTimeoutInSeconds = 5,
    n0zTransactionTimeoutInSeconds = 6,
  );
  if f0LogEvents: f0LogEvents(oProxyServer, "oProxyServer");
  oConsole.fPrint("  oProxyServer = ", str(oProxyServer));
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClientUsingProxyServer instance... ", sPadding = "\xFE");
  oHTTPClient = cHTTPClientUsingProxyServer(
    oProxyServerURL = oProxyServerURL,
    bAllowUnverifiableCertificatesForProxy = True,
    o0zCertificateStore = oCertificateStore,
    n0zConnectToProxyTimeoutInSeconds = 1, # Make sure connection attempts time out quickly to trigger a timeout exception.
  );
  if f0LogEvents: f0LogEvents(oHTTPClient, "oHTTPClient");
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Running client tests through proxy server... ", sPadding = "\xFE");
  fTestClient(oHTTPClient, oCertificateStore, nEndWaitTimeoutInSeconds);
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping cHTTPClientUsingProxyServer instance... ", sPadding = "\xFE");
  oHTTPClient.fStop();
  assert oHTTPClient.fbWait(nEndWaitTimeoutInSeconds), \
      "cHTTPClientUsingProxyServer instance did not stop in time";
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping cHTTPClientSideProxyServer instance... ", sPadding = "\xFE");
  oProxyServer.fStop();
  assert oProxyServer.fbWait(nEndWaitTimeoutInSeconds), \
      "cHTTPClientSideProxyServer instance did not stop in time";
  