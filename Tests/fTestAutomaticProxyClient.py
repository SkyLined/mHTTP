from mHTTP import cHTTPClientUsingAutomaticProxyServer;
from oConsole import oConsole;
from fTestClient import fTestClient;

def fTestAutomaticProxyClient(
  oCertificateStore,
  nEndWaitTimeoutInSeconds,
  f0LogEvents
):
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClientUsingAutomaticProxyServer instance... ", sPadding = "\xFE");
  oHTTPClient = cHTTPClientUsingAutomaticProxyServer(
    bAllowUnverifiableCertificatesForProxy = True,
    o0zCertificateStore = oCertificateStore,
    n0zConnectTimeoutInSeconds = 1, # Make sure connection attempts time out quickly to trigger a timeout exception.
  );
  if f0LogEvents: f0LogEvents(oHTTPClient, "oHTTPClient");
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Running client tests through automatic proxy server... ", sPadding = "\xFE");
  fTestClient(oHTTPClient, oCertificateStore, nEndWaitTimeoutInSeconds);
  
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping cHTTPClientUsingAutomaticProxyServer instance... ", sPadding = "\xFE");
  oHTTPClient.fStop();
  assert oHTTPClient.fbWait(nEndWaitTimeoutInSeconds), \
      "cHTTPClientUsingAutomaticProxyServer instance did not stop in time";
