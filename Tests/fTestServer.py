from mHTTP import cHTTPClient, cHTTPServer;
from oConsole import oConsole;

def ftxRequestHandler(
  oHTTPServer,
  oConnection,
  oRequest,
):
  return (
    oConnection.foCreateResponse(szData = "Hello, world!"),
    True
  );

def fTestServer(
  cHTTPServer,
  cHTTPClient,
  oCertificateStore,
  oServerURL,
  nEndWaitTimeoutInSeconds,
  fzLogEvents,
):
  # Can be use to test cHTTPServer with a http:// or https:// URL.
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPServer instance at %s... " % oServerURL, sPadding = "\xFE");
  if oServerURL.bSecure:
    oSSLContext = oCertificateStore.foGetSSLContextForServerWithHostname(oServerURL.sHostname);
  else:
    oSSLContext = None;
  oHTTPServer = cHTTPServer(ftxRequestHandler, oServerURL.sHostname, oServerURL.uPort, oSSLContext);
  if fzLogEvents: fzLogEvents(oHTTPServer, "oHTTPServer");
  oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a new cHTTPClient instance... ", sPadding = "\xFE");
  oHTTPClient = cHTTPClient(oCertificateStore);
  if fzLogEvents: fzLogEvents(oHTTPClient, "oHTTPClient");
  oConsole.fPrint("\xFE\xFE\xFE\xFE Making a first test request to %s... " % oServerURL, sPadding = "\xFE");
  ozResponse = oHTTPClient.fozGetResponseForURL(oServerURL);
  assert ozResponse, \
      "No response!?";
  oConsole.fPrint(repr(ozResponse.fsSerialize()));
  oConsole.fPrint("\xFE\xFE\xFE\xFE Making a second test request to %s... " % oServerURL, sPadding = "\xFE");
  ozResponse = oHTTPClient.fozGetResponseForURL(oServerURL);
  assert ozResponse, \
      "No response!?";
  oConsole.fPrint(repr(ozResponse.fsSerialize()));
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping the cHTTPServer instance at %s... " % oServerURL, sPadding = "\xFE");
  oHTTPServer.fStop();
  assert oHTTPServer.fbWait(nEndWaitTimeoutInSeconds), \
      "cHTTPServer instance did not stop in time";
  oConsole.fPrint("\xFE\xFE\xFE\xFE Stopping the cHTTPClient instance... ", sPadding = "\xFE");
  oHTTPClient.fStop();
  assert oHTTPClient.fbWait(nEndWaitTimeoutInSeconds), \
      "oHTTPClient instance did not stop in time";
