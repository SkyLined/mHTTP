from cHTTPClient import cHTTPClient;
from cHTTPServer import cHTTPServer;
from cHTTPRequest import cHTTPRequest;

def foRequestHandler(oHTTPServer, oHTTPRequest):
  return oHTTPRequest.foCreateReponse(200, "text/plain", "OK");

oHTTPClient = cHTTPClient();

oHTTPServer = cHTTPServer();
oHTTPServer.fStart(foRequestHandler);
oHTTPResponse = oHTTPClient.foGetResponseForURL(oHTTPServer.fsGetURL());
assert oHTTPResponse.uStatusCode == 200 and oHTTPResponse.sBody == "OK", \
    "Failed";
oHTTPServer.fStop();

oHTTPSServer = cHTTPServer(bSecure = True);
oHTTPSServer.fStart(foRequestHandler);
oHTTPResponse = oHTTPClient.foGetResponseForURL(oHTTPSServer.fsGetURL());
assert oHTTPResponse.uStatusCode == 200 and oHTTPResponse.sBody == "OK", \
    "Failed";
oHTTPSServer.fStop();

oHTTPServer.fWait();
oHTTPSServer.fWait();
