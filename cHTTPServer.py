import socket;

try: # mDebugOutput use is Optional
  from mDebugOutput import *;
except: # Do nothing if not available.
  ShowDebugOutput = lambda fxFunction: fxFunction;
  fShowDebugOutput = lambda sMessage: None;
  fEnableDebugOutputForModule = lambda mModule: None;
  fEnableDebugOutputForClass = lambda cClass: None;
  fEnableAllDebugOutput = lambda: None;
  cCallStack = fTerminateWithException = fTerminateWithConsoleOutput = None;

from mHTTPConnections import cHTTPConnection, cHTTPConnectionAcceptor, cHTTPResponse, cURL;
from mMultiThreading import cLock, cThread, cWithCallbacks;

from .mExceptions import *;

# To turn access to data store in multiple variables into a single transaction, we will create locks.
# These locks should only ever be locked for a short time; if it is locked for too long, it is considered a "deadlock"
# bug, where "too long" is defined by the following value:
gnDeadlockTimeoutInSeconds = 1; # We're not doing anything time consuming, so this should suffice.

class cHTTPServer(cWithCallbacks):
  nzDefaultTransactionTimeoutInSeconds = 10;
  nzDefaultIdleTimeoutInSeconds = 60;
  
  @ShowDebugOutput
  def __init__(oSelf, ftxRequestHandler, szHostname = None, uzPort = None, ozSSLContext = None, nzTransactionTimeoutInSeconds = None, nzIdleTimeoutInSeconds = None):
    assert szHostname is None or isinstance(szHostname,  (str, unicode)), \
        "Invalid szHostname %s" % repr(szHostname);
    assert uzPort is None or isinstance(uzPort,  (int, long)), \
        "Invalid uPort %s" % repr(uzPort);
    oSelf.__ftxRequestHandler = ftxRequestHandler;
    uPort = uzPort if uzPort else 443 if ozSSLContext else 80;
    oSelf.__nzTransactionTimeoutInSeconds = nzTransactionTimeoutInSeconds if nzTransactionTimeoutInSeconds else oSelf.nzDefaultTransactionTimeoutInSeconds;
    oSelf.__nzIdleTimeoutInSeconds = nzIdleTimeoutInSeconds if nzIdleTimeoutInSeconds else oSelf.nzDefaultIdleTimeoutInSeconds;
    
    oSelf.__oPropertyAccessTransactionLock = cLock(
      "%s.__oPropertyAccessTransactionLock" % oSelf.__class__.__name__,
      nzDeadlockTimeoutInSeconds = gnDeadlockTimeoutInSeconds
    );
    
    oSelf.__aoConnections = [];
    oSelf.__aoConnectionThreads = [];
    
    oSelf.__bStopping = False;
    oSelf.__oTerminatedLock = cLock(
      "%s.__oTerminatedLock" % oSelf.__class__.__name__,
      bLocked = True
    );

    oSelf.fAddEvents(
      "new connection",
      "idle timeout",
      "request error", "request received",
      "response error", "response sent",
      "request received and response sent",
      "connection terminated",
      "terminated"
    );

    oSelf.__oConnectionAcceptor = cHTTPConnectionAcceptor(
      fNewConnectionHandler = oSelf.__fHandleNewConnection,
      szHostname = szHostname,
      uzPort = uPort,
      ozSSLContext = ozSSLContext,
      nzSecureTimeoutInSeconds = oSelf.__nzTransactionTimeoutInSeconds,
    );
    oSelf.__oConnectionAcceptor.fAddCallback("terminated", oSelf.__HandleTerminatedCallbackFromConnectionAcceptor);
  
  @property
  def sHostname(oSelf):
    return oSelf.__oConnectionAcceptor.sHostname;
  @property
  def uPort(oSelf):
    return oSelf.__oConnectionAcceptor.uPort;
  @property
  def ozSSLContext(oSelf):
    return oSelf.__oConnectionAcceptor.ozSSLContext;
  @property
  def bSecure(oSelf):
    return oSelf.__oConnectionAcceptor.bSecure;
  @property
  def sIPAddress(oSelf):
    return oSelf.__oConnectionAcceptor.sIPAddress;
  @property
  def bTerminated(oSelf):
    return not oSelf.__oTerminatedLock.bLocked;
  @property
  def oURL(oSelf):
    return oSelf.foGetURL();
  
  def foGetURL(oSelf, szPath = None, szQuery = None, szFragment = None):
    return cURL(
      sProtocol = "https" if oSelf.__oConnectionAcceptor.ozSSLContext else "http",
      sHostname = oSelf.sHostname,
      uzPort = oSelf.uPort,
      szPath = szPath,
      szQuery = szQuery,
      szFragment = szFragment
    );
  
  def foGetURLForRequest(oSelf, oRequest):
    return oSelf.oURL.foFromRelativeString(oRequest.sURL);
  
  @ShowDebugOutput
  def __fCheckForTermination(oSelf, bMustBeTerminated = False):
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      if oSelf.bTerminated:
        return fShowDebugOutput("Already terminated");
      if not oSelf.__bStopping:
        return fShowDebugOutput("Not stopping");
      if not oSelf.__oConnectionAcceptor.bTerminated:
        return fShowDebugOutput("We may still be accepting connections.");
      if len(oSelf.__aoConnections) > 0:
        fShowDebugOutput("There are %d open connections:" % len(oSelf.__aoConnections));
        for oConnection in oSelf.__aoConnections:
          fShowDebugOutput("  %s" % oConnection);
        return;
      if len(oSelf.__aoConnectionThreads) > 0:
        fShowDebugOutput("There are %d running connection threads:" % len(oSelf.__aoConnections));
        for oConnectionThread in oSelf.__aoConnectionThreads:
          fShowDebugOutput("  %s" % oConnectionThread);
        return;
      oSelf.__oTerminatedLock.fRelease();
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    fShowDebugOutput("%s terminating." % oSelf.__class__.__name__);
    oSelf.fFireCallbacks("terminated");
  
  def __HandleTerminatedCallbackFromConnectionAcceptor(oSelf, oConnectionAcceptor):
    oSelf.__fCheckForTermination();
  
  @ShowDebugOutput
  def fStop(oSelf):
    if oSelf.bTerminated:
      return fShowDebugOutput("Already terminated");
    if oSelf.__bStopping:
      return fShowDebugOutput("Already stopping");
    fShowDebugOutput("Stopping...");
    # Prevent any new requests from being processed.
    oSelf.__bStopping = True;
    # Prevent any new connections from being accepted.
    oSelf.__oConnectionAcceptor.fStop();
    # Get a list of existing connections that also need to be stopped.
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      aoConnections = oSelf.__aoConnections[:];
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if aoConnections:
      fShowDebugOutput("Stopping %d open connections..." % len(aoConnections));
      for oConnection in aoConnections:
        oConnection.fStop();
  
  @ShowDebugOutput
  def fTerminate(oSelf):
    if oSelf.bTerminated:
      return fShowDebugOutput("Already terminated");
    fShowDebugOutput("Terminating...");
    # Prevent any new connections from being accepted.
    oSelf.__oConnectionAcceptor.fTerminate();
    # Prevent any new connections from being accepted.
    oSelf.__bStopping = True;
    # Get a list of existing connections that also need to be terminated.
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      aoConnections = oSelf.__aoConnections[:];
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if aoConnections:
      fShowDebugOutput("Terminating %d open connections..." % len(aoConnections));
      for oConnection in aoConnections:
        oConnection.fTerminate();
  
  @ShowDebugOutput
  def fWait(oSelf):
    return oSelf.__oTerminatedLock.fWait();
  @ShowDebugOutput
  def fbWait(oSelf, nzTimeoutInSeconds):
    return oSelf.__oTerminatedLock.fbWait(nzTimeoutInSeconds);
  
  @ShowDebugOutput
  def __fHandleNewConnection(oSelf, oConnectionAcceptor, oConnection):
    fShowDebugOutput("New connection %s..." % (oConnection,));
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      assert not oSelf.bTerminated, \
        "Received a new connection after we've terminated!?";
      if oSelf.__bStopping:
        fDebugOutput("Stopping connection since we are stopping...");
        bHandleConnection = False;
      else:
        oThread = cThread(oSelf.__fConnectionThread, oConnection);
        oSelf.__aoConnections.append(oConnection);
        oSelf.__aoConnectionThreads.append(oThread);
        bHandleConnection = True;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    if bHandleConnection:
      oConnection.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
      oThread.fStart();
    else:
      oConnection.fStop();
  
  def __fHandleTerminatedCallbackFromConnection(oSelf, oConnection):
    assert oConnection in oSelf.__aoConnections, \
        "What!?";
    oSelf.__oPropertyAccessTransactionLock.fAcquire();
    try:
      oSelf.__aoConnections.remove(oConnection);
    finally:
      oSelf.__oPropertyAccessTransactionLock.fRelease();
    oSelf.fFireCallbacks("connection terminated", oConnection);
    oSelf.__fCheckForTermination();
  
  @ShowDebugOutput
  def __fConnectionThread(oSelf, oConnection):
    oThread = cThread.foGetCurrent();
    try:
      while not oSelf.__bStopping:
        # Wait for a request if needed and start a transaction, handle errors.
        bTransactionStarted = False;
        try:
          try:
            if not oConnection.fbBytesAreAvailableForReading():
              fShowDebugOutput("Waiting for request from %s..." % oConnection);
              bTransactionStarted = oConnection.fbWaitUntilBytesAreAvailableForReadingAndStartTransaction(
                nzWaitTimeoutInSeconds = oSelf.__nzIdleTimeoutInSeconds,
                nzTransactionTimeoutInSeconds = oSelf.__nzTransactionTimeoutInSeconds,
              );
            else:
              bTransactionStarted = oConnection.fbStartTransaction(oSelf.__nzTransactionTimeoutInSeconds);
          except cTCPIPConnectionShutdownException as oException:
            fShowDebugOutput("Connection %s was shutdown." % oConnection);
            if not bTransactionStarted:
              assert oConnection.fbStartTransaction(oSelf.__nzTransactionTimeoutInSeconds), \
                  "Cannot start a transaction to disconnect the connection!?";
            oConnection.fDisconnect();
            break;
        except cTCPIPConnectionDisconnectedException as oException:
          fShowDebugOutput("Connection %s was disconnected." % oConnection);
          break;
        except cTCPIPDataTimeoutException as oException:
          fShowDebugOutput("Wait for request from %s timed out: %s." % (oConnection, oException));
          oSelf.fFireCallbacks("idle timeout", oConnection);
          oConnection.fStop();
          break;
        # We should be the only ones using this connection, so we should always
        # be able to start a transaction. If this fails, some other code must
        # have start a transaction, or be waiting on bytes to do so.
        bTransactionStarted, \
            "Cannot start a transaction on %s!" % oConnection;
        # Read request, handle errors.
        fShowDebugOutput("Reading request from %s..." % oConnection);
        try:
          oRequest = oConnection.foReceiveRequest(bStartTransaction = False);
        except cTCPIPConnectionShutdownException as oException:
          fShowDebugOutput("Shutdown while reading request from %s: %s." % (oConnection, oException));
          oSelf.fFireCallbacks("request error", oConnection, oException);
          oConnection.fDisconnect();
          break;
        except cTCPIPConnectionDisconnectedException as oException:
          fShowDebugOutput("Disconnected while reading request from %s: %s." % (oConnection, oException));
          oSelf.fFireCallbacks("request error", oConnection, oException);
          break;
        except cHTTPInvalidMessageException as oException:
          fShowDebugOutput("Invalid request from %s: %s." % (oConnection, oException));
          oSelf.fFireCallbacks("request error", oConnection, oException);
          oConnection.fTerminate();
          break;
        except cTCPIPDataTimeoutException as oException:
          fShowDebugOutput("Reading request from %s timed out: %s." % (oConnection, oException));
          oSelf.fFireCallbacks("request error", oConnection, oException);
          oConnection.fTerminate();
          break;
        oSelf.fFireCallbacks("request received", oConnection, oRequest);
        
        # Have the request handler generate a response to the request object
        oResponse, bContinueHandlingRequests = oSelf.__ftxRequestHandler(oSelf, oConnection, oRequest);
        if oResponse is None:
          # The server should not sent a response.
          break;
        assert isinstance(oResponse, cHTTPResponse), \
            "Request handler must return a cHTTPResponse, got %s" % oResponse.__class__.__name__;
        if oSelf.__bStopping:
          oResponse.oHeaders.fbReplaceHeadersForName("Connection", "Close");
        # Send response, handle errors
        fShowDebugOutput("Sending response %s to %s..." % (oResponse, oConnection));
        try:
          oConnection.fSendResponse(oResponse, bEndTransaction = True);
        except Exception as oException:
          if isinstance(oException, cTCPIPConnectionShutdownException):
            fShowDebugOutput("Connection %s was shutdown while sending response %s." % (oConnection, oResponse));
          elif isinstance(oException, cTCPIPConnectionDisconnectedException):
            fShowDebugOutput("Connection %s was disconnected while sending response %s." % (oConnection, oResponse));
          elif isinstance(oException, cTCPIPDataTimeoutException):
            fShowDebugOutput("Sending response to %s timed out." % (oConnection, oException));
          else:
            raise;
          oSelf.fFireCallbacks("response error", oConnection, oException, oRequest, oResponse);
          if oConnection.bConnected: oConnection.fDisconnect();
          break;
        oSelf.fFireCallbacks("response sent", oConnection, oResponse);
        oSelf.fFireCallbacks("request received and response sent", oConnection, oRequest, oResponse);
        if not bContinueHandlingRequests:
          fShowDebugOutput("Stopped handling requests at the request of the request handler.");
          break;
    finally:
      oSelf.__oPropertyAccessTransactionLock.fAcquire();
      try:
        oSelf.__aoConnectionThreads.remove(oThread);
      finally:
        oSelf.__oPropertyAccessTransactionLock.fRelease();
      fShowDebugOutput("Connection thread terminated");
      oSelf.__fCheckForTermination();
  
  def fasGetDetails(oSelf):
    # This is done without a property lock, so race-conditions exist and it
    # approximates the real values.
    if oSelf.bTerminated:
      return ["terminated"];
    return [s for s in [
        str(oSelf.oURL),
        "stopping" if oSelf.__bStopping else None,
        "%s connections" % (len(oSelf.__aoConnections) or "no"),
        "%s connection threads" % (len(oSelf.__aoConnectionThreads) or "no"),
    ] if s];
  
  def __repr__(oSelf):
    sModuleName = ".".join(oSelf.__class__.__module__.split(".")[:-1]);
    return "<%s.%s#%X|%s>" % (sModuleName, oSelf.__class__.__name__, id(oSelf), "|".join(oSelf.fasGetDetails()));
  
  def __str__(oSelf):
    return "%s#%X{%s}" % (oSelf.__class__.__name__, id(oSelf), ", ".join(oSelf.fasGetDetails()));
