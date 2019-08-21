import json, os, sys;

# Augment the search path to make the test subject a package and have access to its modules folder.
sTestsFolderPath = os.path.dirname(os.path.abspath(__file__));
sMainFolderPath = os.path.dirname(sTestsFolderPath);
sParentFolderPath = os.path.dirname(sMainFolderPath);
sModulesFolderPath = os.path.join(sMainFolderPath, "modules");
asOriginalSysPath = sys.path[:];
sys.path = [sParentFolderPath, sModulesFolderPath] + asOriginalSysPath;
# Load product details
oProductDetailsFile = open(os.path.join(sMainFolderPath, "dxProductDetails.json"), "rb");
try:
  dxProductDetails = json.load(oProductDetailsFile);
finally:
  oProductDetailsFile.close();
# Save the list of names of loaded modules:
asOriginalModuleNames = sys.modules.keys();

__import__(dxProductDetails["sProductName"], globals(), locals(), [], -1);

# Sub-packages should load all modules relative, or they will end up in the global namespace, which means they may get
# loaded by the script importing it if it tries to load a differnt module with the same name. Obviously, that script
# will probably not function when the wrong module is loaded, so we need to check that we did this correctly.
asUnexpectedModules = list(set([
  sModuleName.lstrip("_").split(".", 1)[0] for sModuleName in sys.modules.keys()
  if not (
    sModuleName in asOriginalModuleNames # This was loaded before
    or sModuleName.lstrip("_").split(".", 1)[0] in (
      [dxProductDetails["sProductName"]] +
      dxProductDetails["asDependentOnProductNames"] +
      [
        # These are optional, not required:
        "oConsole", "mWindowsSDK",
        # These built-in modules are expected:
        "Queue", "StringIO", "base64", "binascii", "cStringIO", "collections",
        "contextlib", "ctypes", "gc", "gzip", "heapq", "io", "itertools",
        "json", "keyword", "msvcrt", "nturl2path", "platform", "socket", "ssl",
        "string", "strop", "struct", "subprocess", "textwrap", "thread",
        "threading", "time", "urllib", "urlparse", "zlib"
      ]
    )
  )
]));
assert len(asUnexpectedModules) == 0, \
      "Module(s) %s was/were unexpectedly loaded!" % ", ".join(sorted(asUnexpectedModules));

#Import the test subject
import mHTTP;

# Restore the search path
sys.path = asOriginalSysPath;

from mDebugOutput import fDebugOutput, fFatalExceptionOutput, fShowFileDebugOutputForClass;
try:
  from mHTTP import cBufferedSocket, cCertificateAuthority, cCertificateStore, cHTTPClient, cHTTPClientProxyServer, \
      cHTTPClientUsingProxyServer, cHTTPServer, cHTTPConnection, cURL;
  from fTestClient import fTestClient;
  from fTestServer import fTestServer;
  from fTestProxyServer import fTestProxyServer;
  
  from mHTTP.cHTTPConnectionsToServerPool import cHTTPConnectionsToServerPool;
  from mHTTP.cHTTPRequest import cHTTPRequest;
  from mHTTP.cHTTPResponse import cHTTPResponse;
  from mHTTP.cSSLContext import cSSLContext;
  from mHTTP.iHTTPMessage import iHTTPMessage;
  from mMultiThreading import cLock;

  # Enable/disable output for all classes
#  fShowFileDebugOutputForClass(cBufferedSocket);
#  fShowFileDebugOutputForClass(cCertificateAuthority);
#  fShowFileDebugOutputForClass(cCertificateStore);
#  fShowFileDebugOutputForClass(cHTTPClient);
#  fShowFileDebugOutputForClass(cHTTPClientProxyServer);
#  fShowFileDebugOutputForClass(cHTTPClientUsingProxyServer);
#  fShowFileDebugOutputForClass(cHTTPConnection);
#  fShowFileDebugOutputForClass(cHTTPConnectionsToServerPool);
#  fShowFileDebugOutputForClass(cHTTPRequest);
#  fShowFileDebugOutputForClass(cHTTPResponse);
#  fShowFileDebugOutputForClass(cHTTPServer);
#  fShowFileDebugOutputForClass(cLock);
#  fShowFileDebugOutputForClass(cURL);
#  fShowFileDebugOutputForClass(iHTTPMessage);

  sCertificatesPath = os.path.join(sMainFolderPath, "Certificates");

  if __name__ == "__main__":
    fDebugOutput("**** Creating a cCertificateAuthority instance ".ljust(160, "*"));
    oCertificateAuthority = cCertificateAuthority(sCertificatesPath);
    fDebugOutput("**** Creating a cCertificateStore instance ".ljust(160, "*"));
    oCertificateStore = cCertificateStore();
    oCertificateStore.fAddCertificateAuthority(oCertificateAuthority);
    fDebugOutput("**** Creating test URLs ".ljust(160, "*"));
    oExampleURL = cURL.foFromString("http://example.com");
    oSecureExampleURL = cURL.foFromString("https://example.com");
    oProxyServerURL = cURL.foFromString("http://localhost:8080");
    oLocalNonSecureURL = cURL.foFromString("http://localhost:28876/local-non-secure");
    oLocalSecureURL = cURL.foFromString("https://localhost:28876/local-secure");

    oUnknownAddressURL = cURL.foFromString("http://does.not.exist.example.com/unknown-address");
    oInvalidAddressURL = cURL.foFromString("http://0.0.0.0/invalid-address");
    oConnectionRefusedURL = cURL.foFromString("http://localhost:28081/connection-refused");
    oConnectionTimeoutURL = cURL.foFromString("http://example.com:1"); # Not sure how to do this locally :(
    oConnectionClosedURL = cURL.foFromString("http://localhost:28083/close-connection");
    oOutOfBandDataURL = cURL.foFromString("http://localhost:28084/out-of-band-data");
    oInvalidHTTPMessageURL = cURL.foFromString("http://localhost:28085/invalid-response");
    # Generate a valid SSL certificate and key for "localhost" and load it into the certificate store.
    fDebugOutput(("**** Getting a certificate for %s " % oLocalSecureURL.sHostName).ljust(160, "*"));
    oCertificateAuthority.foGenerateSSLContextForServerWithHostName(oLocalSecureURL.sHostName);
    
    fDebugOutput("@" * 160);
    fDebugOutput(" Test HTTP client");
    fDebugOutput("@" * 160);
    fTestClient(oCertificateStore, oExampleURL, oSecureExampleURL, oUnknownAddressURL, oInvalidAddressURL, oConnectionRefusedURL, oConnectionTimeoutURL, oConnectionClosedURL, oOutOfBandDataURL, oInvalidHTTPMessageURL);
    fDebugOutput("@" * 160);
    fDebugOutput(" Test HTTP server");
    fDebugOutput("@" * 160);
    fTestServer(oCertificateStore, oLocalNonSecureURL);
    fDebugOutput("@" * 160);
    fDebugOutput(" Test HTTPS server");
    fDebugOutput("@" * 160);
    fTestServer(oCertificateStore, oLocalSecureURL);
    fDebugOutput("@" * 160);
    fDebugOutput(" Test HTTP client proxy server");
    fDebugOutput("@" * 160);
    fTestProxyServer(oProxyServerURL, oCertificateStore, oExampleURL, oSecureExampleURL);
    fDebugOutput("@" * 160);
    fDebugOutput(" Test HTTP client proxy server with intercepted HTTPS connections");
    fDebugOutput("@" * 160);
    fTestProxyServer(oProxyServerURL, oCertificateStore, oExampleURL, oSecureExampleURL, oInterceptSSLConnectionsCertificateAuthority = oCertificateAuthority);
except Exception as oException:
  fFatalExceptionOutput(oException);
else:
  fDebugOutput("+ Done.");