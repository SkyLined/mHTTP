from fTestDependencies import fTestDependencies;
fTestDependencies();

try:
  import mDebugOutput;
except:
  mDebugOutput = None;
try:
  try:
    from oConsole import oConsole;
  except:
    import sys, threading;
    oConsoleLock = threading.Lock();
    class oConsole(object):
      @staticmethod
      def fOutput(*txArguments, **dxArguments):
        sOutput = "";
        for x in txArguments:
          if isinstance(x, (str, unicode)):
            sOutput += x;
        sPadding = dxArguments.get("sPadding");
        if sPadding:
          sOutput.ljust(120, sPadding);
        oConsoleLock.acquire();
        print sOutput;
        sys.stdout.flush();
        oConsoleLock.release();
      fPrint = fOutput;
      @staticmethod
      def fStatus(*txArguments, **dxArguments):
        pass;
  
  import os, sys;
  from mMultiThreading import cLock;
  import mSSL;
  
  import mHTTP;
  
  from fTestClient import fTestClient;
  from fTestServer import fTestServer;
  from fTestAutomaticProxyClient import fTestAutomaticProxyClient;
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
  bTestAutoProxy = True;
  f0LogEvents = None;
  # Enable/disable output for all classes
  for sArgument in sys.argv[1:]:
    if sArgument == "--quick": 
      pass; # Always quick :)
    elif sArgument == "--events":
      f0LogEvents = fLogEvents;
    elif sArgument == "--debug":
      assert mDebugOutput, \
          "mDebugOutput module is not available";
      # Turn on debugging for various classes, including a few that are not directly exported.
      import mTCPIPConnections, mHTTPConnections, mHTTPProtocol;
      mDebugOutput.fEnableDebugOutputForModule(mHTTP);
      mDebugOutput.fEnableDebugOutputForModule(mHTTPConnections);
#      mDebugOutput.fEnableDebugOutputForClass(mHTTPProtocol.cHTTPHeader);
#      mDebugOutput.fEnableDebugOutputForClass(mHTTPProtocol.cHTTPHeaders);
      mDebugOutput.fEnableDebugOutputForClass(mHTTPProtocol.cHTTPRequest);
      mDebugOutput.fEnableDebugOutputForClass(mHTTPProtocol.cHTTPResponse);
      mDebugOutput.fEnableDebugOutputForClass(mHTTPProtocol.iHTTPMessage);
      mDebugOutput.fEnableDebugOutputForModule(mTCPIPConnections);
      mDebugOutput.fEnableDebugOutputForModule(mSSL);
      # Outputting debug information is slow, so increase the timeout!
      mHTTP.cHTTPClient.nDefaultConnectTimeoutInSeconds = 100;
      mHTTP.cHTTPClient.nDefaultTransactionTimeoutInSeconds = 100;
    else:
      # We assume this is a flag that enables a specific test. If this is the
      # first such flag, we will disable all tests to make sure we only run the
      # tests that are explicitly enabled.
      if bTestClient is None:
        bTestClient = False;
        bTestServer = False;
        bTestProxy = False;
        bTestAutoProxy = False;
      if sArgument == "--client":
        bTestClient = True;
      elif sArgument == "--server":
        bTestServer = True;
      elif sArgument == "--proxy":
        bTestProxy = True;
      elif sArgument == "--auto-proxy":
        bTestAutoProxy = True;
      else:
        raise AssertionError("Unknown argument %s" % sArgument);
  
  nEndWaitTimeoutInSeconds = 10;
  sCertificatesPath = os.path.join(os.path.dirname(__file__), "Certificates");

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
  mSSL.oCertificateAuthority.foGenerateServersideSSLContextForHostname(oLocalSecureURL.sHostname);
  
  if bTestClient is not False:
    oConsole.fPrint("\xFE\xFE\xFE\xFE Creating a cHTTPClient instance ", sPadding = "\xFE");
    oHTTPClient = mHTTP.cHTTPClient(
      o0zCertificateStore = oCertificateStore,
      n0zConnectTimeoutInSeconds = 1, # Make sure connection attempts time out quickly to trigger a timeout exception.
    );
    if f0LogEvents: f0LogEvents(oHTTPClient);
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTP client");
    oConsole.fOutput("\xFE" * 160);
    fTestClient(oHTTPClient, oCertificateStore, nEndWaitTimeoutInSeconds);
  
  if bTestServer is not False:
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTP server");
    oConsole.fOutput("\xFE" * 160);
    fTestServer(mHTTP.cHTTPServer, mHTTP.cHTTPClient, oCertificateStore, oLocalNonSecureURL, nEndWaitTimeoutInSeconds, f0LogEvents);
    
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTPS server");
    oConsole.fOutput("\xFE" * 160);
    fTestServer(mHTTP.cHTTPServer, mHTTP.cHTTPClient, oCertificateStore, oLocalSecureURL, nEndWaitTimeoutInSeconds, f0LogEvents);
  
  if bTestProxy is not False:
    for oCertificateAuthority in [None, mSSL.oCertificateAuthority]:
      oConsole.fOutput("\xFE" * 160);
      oConsole.fOutput(" Test HTTP client and proxy server%s." % (" with intercepted HTTPS connections" if oCertificateAuthority else ""));
      oConsole.fOutput("\xFE" * 160);
      fTestProxyClientAndServer(oProxyServerURL, oCertificateStore, oCertificateAuthority, nEndWaitTimeoutInSeconds, f0LogEvents);
  
  if bTestAutoProxy is not False:
    oConsole.fOutput("\xFE" * 160);
    oConsole.fOutput(" Test HTTP client with automatic proxy.");
    oConsole.fOutput("\xFE" * 160);
    fTestAutomaticProxyClient(oCertificateStore, nEndWaitTimeoutInSeconds, f0LogEvents);
    
  
  oConsole.fOutput("+ Done.");
  
except Exception as oException:
  if mDebugOutput:
    mDebugOutput.fTerminateWithException(oException, bShowStacksForAllThread = True);
  raise;
