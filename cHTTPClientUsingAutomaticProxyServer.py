import re;

from mWindowsSDK import *;

try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mMultiThreading import cLock, cWithCallbacks;
from mHTTPProtocol import cURL;

from .cHTTPClient import cHTTPClient;
from .cHTTPClientUsingProxyServer import cHTTPClientUsingProxyServer;
from .iHTTPClient import iHTTPClient;
from .mNotProvided import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cHTTPClientUsingAutomaticProxyServer(iHTTPClient, cWithCallbacks):
  u0zDefaultMaxNumberOfConnectionsToServerWithoutProxy = 10;
  u0zDefaultMaxNumberOfConnectionsToProxy = 10; # zNotProvided => use value from 
  n0zDefaultConnectTimeoutInSeconds = 10;
  n0zDefaultSecureTimeoutInSeconds = 5;
  n0zDefaultTransactionTimeoutInSeconds = 10;
  n0zDefaultConnectToProxyTimeoutInSeconds = 10;
  n0zDefaultSecureConnectionToProxyTimeoutInSeconds = 5;
  n0zDefaultSecureConnectionToServerTimeoutInSeconds = 5;
  
  @ShowDebugOutput
  def __init__(oSelf,
    o0zCertificateStore = zNotProvided, 
    bAllowUnverifiableCertificatesForProxy = False, bCheckProxyHostname = True,
    u0zMaxNumberOfConnectionsToServerWithoutProxy = zNotProvided,
    u0zMaxNumberOfConnectionsToProxy = zNotProvided,
    n0zConnectTimeoutInSeconds = zNotProvided, n0zSecureTimeoutInSeconds = zNotProvided, n0zTransactionTimeoutInSeconds = zNotProvided,
    n0zConnectToProxyTimeoutInSeconds = zNotProvided, n0zSecureConnectionToProxyTimeoutInSeconds = zNotProvided,
    n0zSecureConnectionToServerTimeoutInSeconds = zNotProvided,
    bAllowUnverifiableCertificates = False, bCheckHostname = True,
  ):
    oSelf.__oWinHTTPDLL = foLoadWinHTTPDLL();
    oSelf.__hInternet = oSelf.__oWinHTTPDLL.WinHttpOpen(
      foCreateBuffer("User-Agent", bUnicode = True).foCreatePointer(LPCWSTR), # LPCWSTR pszAgentW
      WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY, # DWORD dwAccessType
      WINHTTP_NO_PROXY_NAME, # LPCWSTR pszProxyW
      WINHTTP_NO_PROXY_BYPASS, # LPCWSTR pszProxyBypassW
      NULL, # DWORD dwFlags
    );
    if oSelf.__hInternet == NULL:
      oKernel32 = foLoadKernel32DLL();
      odwLastError = oKernel32.GetLastError();
      raise AssertionError("Cannot initialize WinHTTP: error 0x%X" % (odwLastError.value,));
    # This code will instantiate other classes to make requests. A single certificate store instance is used by all
    # these instances.
    oSelf.__o0CertificateStore = (
      o0zCertificateStore if fbIsProvided(o0zCertificateStore) else
      czCertificateStore() if czCertificateStore else
      None
    );
    oSelf.__bAllowUnverifiableCertificatesForProxy = bAllowUnverifiableCertificatesForProxy;
    oSelf.__bCheckProxyHostname = bCheckProxyHostname;
    #
    oSelf.__u0zMaxNumberOfConnectionsToServerWithoutProxy = fxzGetFirstProvidedValueIfAny(u0zMaxNumberOfConnectionsToServerWithoutProxy, oSelf.u0zDefaultMaxNumberOfConnectionsToServerWithoutProxy);
    #
    oSelf.__u0zMaxNumberOfConnectionsToProxy = fxzGetFirstProvidedValueIfAny(u0zMaxNumberOfConnectionsToProxy, oSelf.u0zDefaultMaxNumberOfConnectionsToProxy);
    # Timeouts can be provided through class default, instance defaults, or method call arguments.
    oSelf.__n0zConnectTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zConnectTimeoutInSeconds, oSelf.n0zDefaultConnectTimeoutInSeconds);
    oSelf.__n0zSecureTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureTimeoutInSeconds, oSelf.n0zDefaultSecureTimeoutInSeconds);
    oSelf.__n0zTransactionTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zTransactionTimeoutInSeconds, oSelf.n0zDefaultTransactionTimeoutInSeconds);
    #
    oSelf.__n0zConnectToProxyTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zConnectToProxyTimeoutInSeconds, oSelf.n0zDefaultConnectToProxyTimeoutInSeconds);
    oSelf.__n0zSecureConnectionToProxyTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureConnectionToProxyTimeoutInSeconds, oSelf.n0zDefaultSecureConnectionToProxyTimeoutInSeconds);
    #
    oSelf.__n0zSecureConnectionToServerTimeoutInSeconds = fxzGetFirstProvidedValueIfAny(n0zSecureConnectionToServerTimeoutInSeconds, oSelf.n0zDefaultSecureConnectionToServerTimeoutInSeconds);
    #
    oSelf.__bAllowUnverifiableCertificates = bAllowUnverifiableCertificates;
    oSelf.__bCheckHostname = bCheckHostname;
    #############################
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      n0DeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    oSelf.__oDirectHTTPClient = None;
    oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL = {};
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    
    oSelf.fAddEvents(
      "new direct client", "new client using proxy server",
      "connect failed", "new connection",
      "request sent", "response received", "request sent and response received",
      "secure connection established",
      "connection terminated",
      "direct client terminated", "client using proxy server terminated",
      "terminated",
    );
  
  @property
  def bStopping(oSelf):
    return oSelf.__bStopping;
  
  @ShowDebugOutput
  def fStop(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated");
      if oSelf.__bStopping:
        return fShowDebugOutput("Already stopping");
      fShowDebugOutput("Stopping...");
      # Prevent any new cHTTPConnectionsToServerPool instances from being created.
      oSelf.__bStopping = True;
      oDirectHTTPClient = oSelf.__oDirectHTTPClient;
      aoHTTPClientsUsingProxyServer = oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL.values();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if not oDirectHTTPClient:
      if len(aoHTTPClientsUsingProxyServer) == 0:
        # We stopped when there were no clients: we are terminated.
        fShowDebugOutput("Terminated.");
        oSelf.__oTerminatedLock.fRelease();
        oSelf.fFireEvent("terminated");
    else:
      oDirectHTTPClient.fStop();
    for oHTTPClientUsingProxyServer in aoHTTPClientsUsingProxyServer:
      oHTTPClientUsingProxyServer.fStop();
  
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated.");
      fShowDebugOutput("Terminating...");
      oSelf.__bStopping = True;
      oDirectHTTPClient = oSelf.__oDirectHTTPClient;
      aoHTTPClientsUsingProxyServer = oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL.values();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if not oDirectHTTPClient:
      if len(aoHTTPClientsUsingProxyServer) == 0:
        # We terminated when there were no clients: we are terminated.
        fShowDebugOutput("Terminated.");
        oSelf.__oTerminatedLock.fRelease();
        oSelf.fFireEvent("terminated");
    else:
      oDirectHTTPClient.fTerminate();
    for oHTTPClientUsingProxyServer in aoHTTPClientsUsingProxyServer:
      oHTTPClientUsingProxyServer.fTerminate();
    return;
  
  @ShowDebugOutput
  def fWait(oSelf):
    return oSelf.__oTerminatedLock.fWait();
  @ShowDebugOutput
  def fbWait(oSelf, n0TimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(n0TimeoutInSeconds);
  
  def fo0GetProxyServerURLForURL(oSelf, oURL):
    dwAutoProxyFlags = DWORD(
      WINHTTP_AUTOPROXY_ALLOW_AUTOCONFIG
      | WINHTTP_AUTOPROXY_ALLOW_CM
      | WINHTTP_AUTOPROXY_ALLOW_STATIC
      | WINHTTP_AUTOPROXY_AUTO_DETECT
      | WINHTTP_AUTOPROXY_SORT_RESULTS
    );
    dwAutoDetectFlags = DWORD(
      WINHTTP_AUTO_DETECT_TYPE_DHCP
      | WINHTTP_AUTO_DETECT_TYPE_DNS_A
    );
    oWinHTTPAutoProxyOptions = WINHTTP_AUTOPROXY_OPTIONS(
      dwAutoProxyFlags, # DWORD   dwFlags;
      dwAutoDetectFlags, # DWORD   dwAutoDetectFlags;
      NULL, # LPCWSTR lpszAutoConfigUrl;
      NULL, # LPVOID  lpvReserved;
      NULL, # DWORD   dwReserved;
      True, # BOOL    fAutoLogonIfChallenged;
    );
    oWinHTTPProxyInfo = WINHTTP_PROXY_INFO();
    bSuccess = oSelf.__oWinHTTPDLL.WinHttpGetProxyForUrl(
      oSelf.__hInternet, # HINTERNET hSession
      foCreateBuffer(str(oURL), bUnicode = True).foCreatePointer(LPCWSTR), # LPCWSTRlpcwszUrl
      oWinHTTPAutoProxyOptions.foCreatePointer(), # WINHTTP_AUTOPROXY_OPTIONS *pAutoProxyOptions,
      oWinHTTPProxyInfo.foCreatePointer(), # WINHTTP_PROXY_INFO *pProxyInfo
    );
    if not bSuccess:
      oKernel32 = foLoadKernel32DLL();
      odwLastError = oKernel32.GetLastError();
      raise AssertionError("Cannot call WinHttpGetProxyForUrl for URL %s: error 0x%X" % (oURL, odwLastError.value));
     
    if oWinHTTPProxyInfo.dwAccessType == WINHTTP_ACCESS_TYPE_NO_PROXY:
      return None;
    assert oWinHTTPProxyInfo.dwAccessType == WINHTTP_ACCESS_TYPE_NAMED_PROXY, \
        "Unexpected oWinHTTPProxyInfo.dwAccessType (0x%X)" % oWinHTTPProxyInfo.dwAccessType;
    assert not oWinHTTPProxyInfo.lpszProxy.fbIsNULLPointer(), \
        "Unexpected oWinHTTPProxyInfo.lpszProxy == NULL";
    assert oWinHTTPProxyInfo.lpszProxyBypass.fbIsNULLPointer(), \
        "Unexpected oWinHTTPProxyInfo.lpszProxyBypass == %s" % repr(oWinHTTPProxyInfo.lpszProxyBypass.fsGetString());
    sProxyInformation = str(oWinHTTPProxyInfo.lpszProxy.fsGetString());
#    print "-" * 80;
#    print repr(sProxyInformation);
#    print "-" * 80;
    # We get a list of proxy servers, separated by whitespace and/or semi-colons.
    # We will only use the first and discard the rest.
    oProxyInformationMatch = re.match(
      r"^"
      r"(?:" r"(\w+)=" r")?"    # optional "<scheme>="
      r"(?:" r"(\w+)://" r")?"  # optional "scheme://"
      r"([\w\-\.]+)"            # "<hostname>"
      r"(?:" r":(\d+)" r")?"    # optional ":<port>"
      r"(?:[\s;].*)?"           # optional (" " or ";") "<more proxy information>"
      r"$",
      sProxyInformation,
    );
    assert oProxyInformationMatch, \
        "Badly formed proxy information: %s" % repr(sProxyInformation);
    (s0Scheme1, s0Scheme2, sHostname, s0Port) = oProxyInformationMatch.groups();
    oProxyURL = cURL(
      sProtocol = s0Scheme1 or s0Scheme2 or "http", #oURL.sProtocol,
      sHostname = sHostname,
      u0Port = long(s0Port) if s0Port else None,
    );
    return oProxyURL;
    
  def fo0GetResponseForRequestAndURL(oSelf, 
    oRequest, oURL,
    u0zMaxStatusLineSize = zNotProvided,
    u0zMaxHeaderNameSize = zNotProvided,
    u0zMaxHeaderValueSize = zNotProvided,
    u0zMaxNumberOfHeaders = zNotProvided,
    u0zMaxBodySize = zNotProvided,
    u0zMaxChunkSize = zNotProvided,
    u0zMaxNumberOfChunks = zNotProvided,
    u0MaxNumberOfChunksBeforeDisconnecting = None, # disconnect and return response once this many chunks are received.
  ):
    if oSelf.__bStopping:
      fShowDebugOutput("Stopping.");
      return None;
    o0ProxyServerURL = oSelf.fo0GetProxyServerURLForURL(oURL);
    bNewClient = False;
    if o0ProxyServerURL is None:
      if oSelf.__oDirectHTTPClient is None:
        oHTTPClient = oSelf.__oDirectHTTPClient = cHTTPClient(
          o0zCertificateStore = oSelf.__o0CertificateStore,
          u0zMaxNumberOfConnectionsToServer = oSelf.__u0zMaxNumberOfConnectionsToServerWithoutProxy,
          n0zConnectTimeoutInSeconds = oSelf.__n0zConnectTimeoutInSeconds,
          n0zSecureTimeoutInSeconds = oSelf.__n0zSecureTimeoutInSeconds,
          n0zTransactionTimeoutInSeconds = oSelf.__n0zTransactionTimeoutInSeconds,
          bAllowUnverifiableCertificates = oSelf.__bAllowUnverifiableCertificates,
          bCheckHostname = oSelf.__bCheckHostname,
        );
        oHTTPClient.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromDirectHTTPClient);
        oSelf.fFireCallbacks("new direct client", oHTTPClient);
        bNewClient = True;
      else:
        oHTTPClient = oSelf.__oDirectHTTPClient;
    else:
      sLowerPorxyServerURL = str(o0ProxyServerURL).lower();
      oHTTPClient = oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL.get(sLowerPorxyServerURL);
      if oHTTPClient is None:
        oHTTPClient = oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL[sLowerPorxyServerURL] = cHTTPClientUsingProxyServer(
          o0ProxyServerURL,
          bAllowUnverifiableCertificatesForProxy = oSelf.__bAllowUnverifiableCertificatesForProxy,
          bCheckProxyHostname = oSelf.__bCheckProxyHostname,
          o0zCertificateStore = oSelf.__o0CertificateStore,
          u0zMaxNumberOfConnectionsToProxy = oSelf.__u0zMaxNumberOfConnectionsToProxy,
          n0zConnectToProxyTimeoutInSeconds = oSelf.__n0zConnectToProxyTimeoutInSeconds,
          n0zSecureConnectionToProxyTimeoutInSeconds = oSelf.__n0zSecureConnectionToProxyTimeoutInSeconds,
          n0zSecureConnectionToServerTimeoutInSeconds = oSelf.__n0zSecureConnectionToServerTimeoutInSeconds,
          n0zTransactionTimeoutInSeconds = oSelf.__n0zTransactionTimeoutInSeconds,
          bAllowUnverifiableCertificates = oSelf.__bAllowUnverifiableCertificates,
          bCheckHostname = oSelf.__bCheckHostname,
        );
        oHTTPClient.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromHTTPClientUsingProxyServer);
        oSelf.fFireCallbacks("new client using proxy server", oHTTPClient);
        bNewClient = True;
    
    if bNewClient:
      oHTTPClient.fAddCallback("connect failed", oSelf.__fHandleConnectFailedCallbackFromHTTPClient);
      oHTTPClient.fAddCallback("new connection", oSelf.__fHandleNewConnectionCallbackFromHTTPClient);
      oHTTPClient.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromHTTPClient);
      oHTTPClient.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromHTTPClient);
      oHTTPClient.fAddCallback("request sent and response received", oSelf.__fHandleRequestSentAndResponseReceivedCallbackFromHTTPClient);
      oHTTPClient.fAddCallback("connection terminated", oSelf.__fHandleConnectionTerminatedCallbackFromHTTPClient);
    
    return oHTTPClient.fo0GetResponseForRequestAndURL(
      oRequest, oURL,
      u0zMaxStatusLineSize = u0zMaxStatusLineSize,
      u0zMaxHeaderNameSize = u0zMaxHeaderNameSize,
      u0zMaxHeaderValueSize = u0zMaxHeaderValueSize,
      u0zMaxNumberOfHeaders = u0zMaxNumberOfHeaders,
      u0zMaxBodySize = u0zMaxBodySize,
      u0zMaxChunkSize = u0zMaxChunkSize,
      u0zMaxNumberOfChunks = u0zMaxNumberOfChunks,
      u0MaxNumberOfChunksBeforeDisconnecting = u0MaxNumberOfChunksBeforeDisconnecting,
    );
  
  def __fHandleConnectFailedCallbackFromHTTPClient(oSelf, oHTTPClient, sHostname, uPort, oException):
    oSelf.fFireCallbacks("connect failed", oHTTPClient, sHostname, uPort, oException);
  def __fHandleNewConnectionCallbackFromHTTPClient(oSelf, oHTTPClient, oConnection):
    oSelf.fFireCallbacks("new connection", oHTTPClient, oConnection);
  def __fHandleRequestSentCallbackFromHTTPClient(oSelf, oHTTPClient, oConnection, oRequest):
    oSelf.fFireCallbacks("request sent", oHTTPClient, oConnection, oRequest);
  def __fHandleResponseReceivedCallbackFromHTTPClient(oSelf, oHTTPClient, oConnection, oReponse):
    oSelf.fFireCallbacks("response received", oHTTPClient, oConnection, oReponse);
  def __fHandleRequestSentAndResponseReceivedCallbackFromHTTPClient(oSelf, oHTTPClient, oConnection, oRequest, oReponse):
    oSelf.fFireCallbacks("request sent and response received", oHTTPClient, oConnection, oRequest, oReponse);
  def __fHandleConnectionTerminatedCallbackFromHTTPClient(oSelf, oHTTPClient, oConnection):
    oSelf.fFireCallbacks("connection terminated", oHTTPClient, oConnection);
    
  def __fHandleTerminatedCallbackFromDirectHTTPClient(oSelf, oHTTPClient):
    oSelf.fFireCallbacks("direct client terminated", oHTTPClient);
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      oSelf.__oDirectHTTPClient = None;
      # Return if we are not stopping or if there are other connections open:
      if not oSelf.__bStopping:
        return;
      if oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL:
        return;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    # We are stopping and the last connection just terminated: we are terminated.
    fShowDebugOutput("Terminated.");
    oSelf.__oTerminatedLock.fRelease();
    oSelf.fFireCallbacks("terminated");
  
  def __fHandleTerminatedCallbackFromHTTPClientUsingProxyServer(oSelf, oHTTPClient):
    oSelf.fFireCallbacks("client using proxy server terminated", oHTTPClient);
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      for sURL in oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL:
        if oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL[sURL] == oHTTPClient:
          del oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL[sURL];
          break;
      # Return if we are not stopping or if there are other connections open:
      if not oSelf.__bStopping:
        return;
      if oSelf.__oDirectHTTPClient:
        return;
      if oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL:
        return;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    # We are stopping and the last connection just terminated: we are terminated.
    fShowDebugOutput("Terminated.");
    oSelf.__oTerminatedLock.fRelease();
    oSelf.fFireCallbacks("terminated");
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    if oSelf.bTerminated:
      return ["terminated"];
    return [s for s in [
      "direct client" if oSelf.__oDirectHTTPClient else None,
      "%d proxy clients" % (len(oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL),) if oSelf.__doHTTPClientUsingProxyServer_by_sLowerProxyServerURL else None,
      "stopping" if oSelf.__bStopping else None,
    ] if s];

