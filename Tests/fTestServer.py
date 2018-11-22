from mHTTP import cHTTPClient, cHTTPResponse, cHTTPServer;
from mDebugOutput import fDebugOutput;

def foRequestHandler(oHTTPServer, oConnection, oRequest):
  return cHTTPResponse(sData = "Hello, world!");

def fTestServer(oCertificateStore, oServerURL):
  # Can be use to test cHTTPServer with a http:// or https:// URL.
  fDebugOutput(("**** Creating a cHTTPServer instance at %s " % oServerURL).ljust(160, "*"));
  if oServerURL.bSecure:
    oSSLContext = oCertificateStore.foGetSSLContextForServerWithHostName(oServerURL.sHostName);
  else:
    oSSLContext = None;
  oHTTPServer = cHTTPServer(oServerURL.sHostName, oServerURL.uPort, oSSLContext);
  fDebugOutput(("**** Starting the cHTTPServer instance at %s " % oServerURL).ljust(160, "*"));
  oHTTPServer.fStart(foRequestHandler);
  fDebugOutput("**** Creating a new cHTTPClient instance ".ljust(160, "*"));
  oHTTPClient = cHTTPClient(oCertificateStore);
  fDebugOutput(("**** Making a first test request to %s " % oServerURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oServerURL).fsSerialize()));
  fDebugOutput(("**** Making a second test request to %s " % oServerURL).ljust(160, "*"));
  fDebugOutput(repr(oHTTPClient.foGetResponseForURL(oServerURL).fsSerialize()));
  fDebugOutput(("**** Stopping the cHTTPServer instance at %s " % oServerURL).ljust(160, "*"));
  oHTTPServer.fStop();
  oHTTPServer.fWait();
  oHTTPClient.fStop();
  oHTTPServer.fWait();
