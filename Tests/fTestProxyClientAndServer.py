from mHTTP import cHTTPClientSideProxyServer, cHTTPClientUsingProxyServer;
from oConsole import oConsole;
from fTestClient import fTestClient;
try: # SSL support is optional.
  from mSSL import oCertificateAuthority as ozCertificateAuthority;
except:
  ozCertificateAuthority = None; # No SSL support

def fTestProxyClientAndServer(
  oProxyServerURL,
  oCertificateStore,
  oInterceptSSLConnectionsCertificateAuthority,
  nEndWaitTimeoutInSeconds,
  fzLogEvents
):
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClientSideProxyServer instance... ", sPadding = "\xFE");
  oProxyServer = cHTTPClientSideProxyServer(
    szHostname = oProxyServerURL.sHostname,
    uzPort = oProxyServerURL.uPort,
    ozServerSSLContext = (
      ozCertificateAuthority.foGenerateServersideSSLContextForHostname(oProxyServerURL.sHostname)
    ) if oProxyServerURL.bSecure else None,
    ozCertificateStore = oCertificateStore,
    ozInterceptSSLConnectionsCertificateAuthority = oInterceptSSLConnectionsCertificateAuthority,
    # Make sure the proxy server times out waiting for the HTTP server
    # before the client times out waiting for the proxy.
    nzConnectTimeoutInSeconds = 5,
    nzTransactionTimeoutInSeconds = 6,
  );
  if fzLogEvents: fzLogEvents(oProxyServer, "oProxyServer");
  oConsole.fPrint("  oProxyServer = ", str(oProxyServer));
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClientUsingProxyServer instance... ", sPadding = "\xFE");
  oHTTPClient = cHTTPClientUsingProxyServer(
    oProxyServerURL = oProxyServerURL,
    bAllowUnverifiableCertificatesForProxy = True,
    ozCertificateStore = oCertificateStore
  );
  if fzLogEvents: fzLogEvents(oHTTPClient, "oHTTPClient");
  
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
  