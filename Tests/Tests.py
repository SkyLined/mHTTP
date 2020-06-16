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
        # This is optional, not required:
        "oConsole", 
        # These built-in modules are expected:
        "base64", "binascii", "cStringIO", "collections", "contextlib",
        "ctypes", "datetime", "dis", "future__", "hashlib", "gc", "gzip",
        "heapq", "imp", "inspect", "io", "itertools", "json", "keyword",
        "math", "msvcrt", "nturl2path", "opcode", "platform", "random",
        "Queue", "select", "socket", "ssl", "string", "StringIO", "strop",
        "struct", "subprocess", "textwrap", "thread", "threading", "time",
        "timeit", "token", "tokenize", "urllib", "urlparse", "zlib"
      ]
    )
  )
]));
assert len(asUnexpectedModules) == 0, \
      "Module(s) %s was/were unexpectedly loaded!" % ", ".join(sorted(asUnexpectedModules));
for sModuleName in dxProductDetails["asDependentOnProductNames"]:
  assert sModuleName in sys.modules, \
      "%s is listed as a dependency but not loaded by the module!" % sModuleName;

from mDebugOutput import fEnableDebugOutputForClass, fEnableDebugOutputForModule, fTerminateWithException;
try:
  from oConsole import oConsole;
  
  import mHTTP, mSSL;
  
  from fTestClient import fTestClient;
  from fTestServer import fTestServer;
  from fTestProxyClientAndServer import fTestProxyClientAndServer;
  
  from mMultiThreading import cLock;
  
  def fLogEvents(oWithCallbacks, sWithCallbacks = None):
    def fAddCallback(sEventName):
      def fOutputEventDetails(oWithCallbacks, *txArguments, **dxArguments):
        oConsole.fPrint(sWithCallbacks or str(oWithCallbacks), " => ", repr(sEventName));
        for xValue in txArguments:
          oConsole.fPrint("  ", str(xValue));
        for (sName, xValue) in dxArguments.items():
          oConsole.fPrint("  ", sName, " = ", str(xValue));
      
      oWithCallbacks.fAddCallback(sEventName, fOutputEventDetails);
    
    for sEventName in oWithCallbacks.fasGetEventNames():
      fAddCallback(sEventName);

  bTestClient = None;
  bTestServer = None;
  bTestProxy = None;
  fzLogEvents = None;
  # Enable/disable output for all classes
  for sArgument in sys.argv[1:]:
    if sArgument == "--quick": 
      pass; # Always quick :)
    elif sArgument == "--events":
      fzLogEvents = fLogEvents;
    elif sArgument == "--debug":
      # Turn on debugging for various classes, including a few that are not directly exported.
      import mTCPIPConnections, mHTTPConnections, mHTTPProtocol;
      fEnableDebugOutputForModule(mHTTP);
      fEnableDebugOutputForModule(mHTTPConnections);
#      fEnableDebugOutputForClass(mHTTPProtocol.cHTTPHeader);
#      fEnableDebugOutputForClass(mHTTPProtocol.cHTTPHeaders);
      fEnableDebugOutputForClass(mHTTPProtocol.cHTTPRequest);
      fEnableDebugOutputForClass(mHTTPProtocol.cHTTPResponse);
      fEnableDebugOutputForClass(mHTTPProtocol.iHTTPMessage);
      fEnableDebugOutputForModule(mTCPIPConnections);
      fEnableDebugOutputForModule(mSSL);
      # Outputting debug information is slow, so increase the timeout!
      mHTTP.cHTTPClient.nDefaultConnectTimeoutInSeconds = 100;
      mHTTP.cHTTPClient.nDefaultTransactionTimeoutInSeconds = 100;
    elif sArgument == "--client":
      if bTestClient is None:
        bTestServer = False;
        bTestProxy = False;
      bTestClient = True;
    elif sArgument == "--server":
      if bTestClient is None:
        bTestClient = False;
        bTestProxy = False;
      bTestServer = True;
    elif sArgument == "--proxy":
      if bTestClient is None:
        bTestClient = False;
        bTestServer = False;
      bTestProxy = True;
    else:
      raise AssertionError("Unknown argument %s" % sArgument);
  
  nEndWaitTimeoutInSeconds = 10;
  sCertificatesPath = os.path.join(sTestsFolderPath, "Certificates");

  oLocalNonSecureURL = mHTTP.cURL.foFromString("http://localhost:28876/local-non-secure");
  oLocalSecureURL = mHTTP.cURL.foFromString("https://localhost:28876/local-secure");
  oProxyServerURL = mHTTP.cURL.foFromString("https://localhost:28876");
  oConsole.fOutput("\xFE\xFE\xFE\xFE Creating a cCertificateStore instance ".ljust(160, "\xFE"));
  oCertificateStore = mSSL.cCertificateStore();
  oCertificateStore.fAddCertificateAuthority(mSSL.oCertificateAuthority);
  oConsole.fOutput("  oCertificateStore = %s" % oCertificateStore);
  # Reset the certificate authority and generate an SSL certificate and key
  # for "localhost".
  oConsole.fOutput("\xFE\xFE\xFE\xFE Resetting oCertificateAuthority...".ljust(160, "\xFE"));
  oConsole.fOutput("  oCertificateAuthority = %s" % mSSL.oCertificateAuthority);
  mSSL.oCertificateAuthority.fReset();
  oConsole.fOutput(("\xFE\xFE\xFE\xFE Getting a certificate for %s " % oLocalSecureURL.sHostname).ljust(160, "\xFE"));
  mSSL.oCertificateAuthority.foGenerateSSLContextForServerWithHostname(oLocalSecureURL.sHostname);
  
  if bTestClient is not False:
    oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClient instance ", sPadding = "\xFE");
    oHTTPClient = mHTTP.cHTTPClient(oCertificateStore);
    if fzLogEvents: fzLogEvents(oHTTPClient);
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTP client");
    oConsole.fOutput("\xFE" * 160);
    fTestClient(oHTTPClient, oCertificateStore, nEndWaitTimeoutInSeconds);
  
  if bTestServer is not False:
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTP server");
    oConsole.fOutput("\xFE" * 160);
    fTestServer(mHTTP.cHTTPServer, mHTTP.cHTTPClient, oCertificateStore, oLocalNonSecureURL, nEndWaitTimeoutInSeconds, fzLogEvents);
    
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTPS server");
    oConsole.fOutput("\xFE" * 160);
    fTestServer(mHTTP.cHTTPServer, mHTTP.cHTTPClient, oCertificateStore, oLocalSecureURL, nEndWaitTimeoutInSeconds, fzLogEvents);
  
  if bTestProxy is not False:
    for oCertificateAuthority in [None, mSSL.oCertificateAuthority]:
      oConsole.fOutput("\xFE" * 160);
      oConsole.fOutput(" Test HTTP client proxy server%s." % (" with intercepted HTTPS connections" if oCertificateAuthority else ""));
      oConsole.fOutput("\xFE" * 160);
      fTestProxyClientAndServer(oProxyServerURL, oCertificateStore, oCertificateAuthority, nEndWaitTimeoutInSeconds, fzLogEvents);
except Exception as oException:
  fTerminateWithException(oException, bShowStacksForAllThread = True);
else:
  oConsole.fOutput("+ Done.");