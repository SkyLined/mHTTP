from fTestDependencies import fTestDependencies;
fTestDependencies();

from mDebugOutput import fEnableDebugOutputForClass, fEnableDebugOutputForModule, fTerminateWithException;
try:
  import os, sys;
  from oConsole import oConsole;
  from mMultiThreading import cLock;
  import mSSL;
  
  import mHTTP;
  
  from fTestClient import fTestClient;
  from fTestServer import fTestServer;
  from fTestProxyClientAndServer import fTestProxyClientAndServer;
  
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
  oConsole.fOutput("+ Done.");
except Exception as oException:
  fTerminateWithException(oException, bShowStacksForAllThread = True);

