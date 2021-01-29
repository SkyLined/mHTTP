from mHTTP import cHTTPClient, cHTTPServer;
from oConsole import oConsole;

def ftxRequestHandler(
  oHTTPServer,
  oConnection,
  oRequest,
):
  return (
    oConnection.foCreateResponse(s0Data = "Hello, world!"),
    True
  );

def fTestServer(
  cHTTPServer,
  cHTTPClient,
  oCertificateStore,
  oServerURL,
  nEndWaitTimeoutInSeconds,
  f0LogEvents,
):
  # Can be use to test cHTTPServer with a http:// or https:// URL.
  if oServerURL.bSecure:
    oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cSSLContext instance for %s... " % oServerURL.sHostname, sPadding = "\xFE");
    oSSLContext = oCertificateStore.foGetServersideSSLContextForHostname(oServerURL.sHostname);
    oConsole.fOutput(0x0F0F, repr(oSSLContext._cSSLContext__oPythonSSLContext.get_ca_certs()));
    oConsole.fPrint("* oSSLContext for ", oServerURL.sHostname, ": ", str(oSSLContext));
  else:
    oSSLContext = None;
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPServer instance at %s... " % oServerURL, sPadding = "\xFE");
  oHTTPServer = cHTTPServer(ftxRequestHandler, oServerURL.sHostname, oServerURL.uPort, oSSLContext);
  if f0LogEvents: f0LogEvents(oHTTPServer, "oHTTPServer");
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a new cHTTPClient instance... ", sPadding = "\xFE");
  oHTTPClient = cHTTPClient(oCertificateStore);
  if f0LogEvents: f0LogEvents(oHTTPClient, "oHTTPClient");
  oConsole.fPrint("\xFE\xFE\xFE\xFE Making a first test request to %s... " % oServerURL, sPadding = "\xFE");
  o0Response = oHTTPClient.fo0GetResponseForURL(oServerURL);
  assert o0Response, \
      "No response!?";
  oConsole.fPrint(repr(o0Response.fsSerialize()));
  oConsole.fPrint("\xFE\xFE\xFE\xFE Making a second test request to %s... " % oServerURL, sPadding = "\xFE");
  o0Response = oHTTPClient.fo0GetResponseForURL(oServerURL);
  assert o0Response, \
      "No response!?";
  oConsole.fPrint(repr(o0Response.fsSerialize()));
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping the cHTTPServer instance at %s... " % oServerURL, sPadding = "\xFE");
  oHTTPServer.fStop();
  assert oHTTPServer.fbWait(nEndWaitTimeoutInSeconds), \
      "cHTTPServer instance did not stop in time";
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping the cHTTPClient instance... ", sPadding = "\xFE");
  oHTTPClient.fStop();
  assert oHTTPClient.fbWait(nEndWaitTimeoutInSeconds), \
      "oHTTPClient instance did not stop in time";
