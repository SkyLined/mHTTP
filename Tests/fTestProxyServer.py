from mHTTP import cHTTPClientProxyServer, cHTTPClientUsingProxyServer;
from mDebugOutput import fDebugOutput;

def fTestProxyServer(oProxyServerURL, oCertificateStore, oExampleURL, oSecureExampleURL, oInterceptSSLConnectionsCertificateAuthority = None):
  fDebugOutput("**** Creating and starting a cHTTPClientProxyServer instance ".ljust(160, "*"));
  oProxyServer = cHTTPClientProxyServer(
    sHostName = oProxyServerURL.sHostName,
    uPort = oProxyServerURL.uPort,
    oCertificateStore = oCertificateStore,
    oInterceptSSLConnectionsCertificateAuthority = oInterceptSSLConnectionsCertificateAuthority,
  );
  oProxyServer.fStart();
  fDebugOutput("**** Creating a cHTTPClientUsingProxyServer instance ".ljust(160, "*"));
  oHTTPClient = cHTTPClientUsingProxyServer(oProxyServerURL, oCertificateStore);
  fDebugOutput(("**** Making a first test request to %s " % oExampleURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oExampleURL).fsSerialize()));
  fDebugOutput(("**** Making a second test request to %s " % oExampleURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oExampleURL).fsSerialize()));
  aoNonSecureConnections = oHTTPClient._cHTTPClientUsingProxyServer__aoNonSecureConnections;
  assert len(aoNonSecureConnections) == 1, \
      "Expected one connection to the proxy, but found %d connections" % (oExampleURL, len(aoConnections));
  doSecureConnectionToServer_by_sProtocolHostPort = oHTTPClient._cHTTPClientUsingProxyServer__doSecureConnectionToServer_by_sProtocolHostPort;
  asSecureConnectionTargets = doSecureConnectionToServer_by_sProtocolHostPort.keys();
  assert len(asSecureConnectionTargets) == 0, \
      "Expected no secure connections, but found %s" % repr(asSecureConnectionTargets);
  
  fDebugOutput(("**** Making a first test request to %s " % oSecureExampleURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oSecureExampleURL).fsSerialize()));
  fDebugOutput(("**** Making a second test request to %s " % oSecureExampleURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oSecureExampleURL).fsSerialize()));
  aoNonSecureConnections = oHTTPClient._cHTTPClientUsingProxyServer__aoNonSecureConnections;
  assert len(aoNonSecureConnections) == 0, \
      "Expected no non-secure connections to the proxy, but found %d connections" % len(aoNonSecureConnections);
  doSecureConnectionToServer_by_sProtocolHostPort = oHTTPClient._cHTTPClientUsingProxyServer__doSecureConnectionToServer_by_sProtocolHostPort;
  asSecureConnectionTargets = doSecureConnectionToServer_by_sProtocolHostPort.keys();
  assert set(asSecureConnectionTargets) == set((oSecureExampleURL.sBase,)), \
      "Expected one secure connection to %s, but found %s" % (oSecureExampleURL.sBase, repr(asSecureConnectionTargets));
  fDebugOutput("**** Stopping cHTTPClientUsingProxyServer instance ".ljust(160, "*"));
  oHTTPClient.fStop();
  oHTTPClient.fWait();
  fDebugOutput("**** Stopping cHTTPClientProxyServer instance ".ljust(160, "*"));
  oProxyServer.fStop();
  oProxyServer.fWait();
