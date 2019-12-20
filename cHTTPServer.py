import socket;
from .cHTTPConnection import cHTTPConnection;
from .cHTTPResponse import cHTTPResponse;
from .cSSLContext import cSSLContext;
from .cURL import cURL;
from .fbSocketExceptionIsTimeout import fbSocketExceptionIsTimeout;
from mDebugOutput import cWithDebugOutput;
from mMultiThreading import cLock, cThread, cWithCallbacks;

class cHTTPServer(cWithCallbacks, cWithDebugOutput):
  nDefaultWaitForRequestTimeoutInSeconds = 20;
  def __init__(oSelf, sHostname = None, uPort = None, oSSLContext = None, nWaitForRequestTimeoutInSeconds = None, bLocal = True):
    oSelf.__bBound = False;
    if sHostname is None:
      sHostname = "127.0.0.1" if bLocal else socket.gethostbyname(socket.gethostname());
    if uPort is None:
      uPort = oSSLContext and 443 or 80;
    oSelf.__oURL = cURL(sProtocol = "https" if oSSLContext else "http", sHostname = sHostname, uPort = uPort);
    oSelf.__oSSLContext = oSSLContext;
    oSelf.__nWaitForRequestTimeoutInSeconds = nWaitForRequestTimeoutInSeconds or oSelf.nDefaultWaitForRequestTimeoutInSeconds;
    
    oSelf.__bServerSocketClosed = False;

    oSelf.__oServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
    oSelf.__oServerSocket.settimeout(0);
    oSelf.__oMainLock = cLock("%s.__oMainLock" % oSelf.__class__.__name__);
    oSelf.__aoOpenConnections = [];
    oSelf.__aoRunningThreads = [];

    oSelf.__bStarted = False;
    oSelf.__bStopping = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    
    oSelf.fAddEvents("started", "new connection", "request received", "response sent", "request received and response sent", "connection terminated", "terminated");
  
  def __del__(oSelf):
    if oSelf.__bBound and not oSelf.__bTerminated:
      try:
        oSelf.__oServerSocket.shutdown();
      except Exception:
        pass;
      try:
        oSelf.__oServerSocket.close();
      except Exception:
        pass;
      if oSelf.__bStarted:
        for oConnection in oSelf.__aoOpenConnections:
          oConnection.fTerminate();
        raise AssertionError("cHTTPServer instance deleted without being terminated");
  
  def __fCheckForTermination(oSelf, bLockMain = True, bMustBeTerminated = False):
    oSelf.fEnterFunctionOutput();
    try:
      if bLockMain: oSelf.__oMainLock.fAcquire();
      try:
        if oSelf.__bTerminated:
          return oSelf.fExitFunctionOutput("Already terminated");
        if not oSelf.__bStopping:
          assert not bMustBeTerminated, \
              "The server is expected to have terminated at this point, but is not even stopping";
          return oSelf.fExitFunctionOutput("Not stopping");
        uOpenConnections = len(oSelf.__aoOpenConnections);
        uRunningThreads = len(oSelf.__aoRunningThreads);
        bTerminated = uRunningThreads == 0 and uOpenConnections == 0 and not oSelf.__bTerminated;
        if bTerminated: oSelf.__bTerminated = True;
      finally:
        if bLockMain: oSelf.__oMainLock.fRelease();
      if bTerminated:
        oSelf.__oTerminatedLock.fRelease();
        # We cannot hold the main lock while firing events. So, if the calling
        # function tells us it is locked, unlock it while we do so, then lock
        # it again.
        if not bLockMain: oSelf.__oMainLock.fRelease();
        try:
          oSelf.fFireCallbacks("terminated");
        finally:
          if not bLockMain: oSelf.__oMainLock.fAcquire();
        return oSelf.fExitFunctionOutput("Terminated");
      else:
        assert not bMustBeTerminated, \
            "The server is expected to have terminated at this point, but there are %d open connections and %d running threads remaining" \
            % (uOpenConnections, uRunningThreads);
      return oSelf.fExitFunctionOutput("Not terminated; %d connections, %d threads." % (uOpenConnections, uRunningThreads));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;

  @property
  def sAddress(oSelf):
    return "%s:%d" % oSelf.__oServerSocket.getsockname();
  @property
  def bSecure(oSelf):
    return oSelf.__oURL.bSecure;
  
  @property
  def sURL(oSelf):
    return oSelf.fsGetURL();
  def fsGetURL(oSelf, sPath = None, sQuery = None, sFragment = None):
    return "".join([
      oSelf.__oURL.sBase,
      "%s%s" % ("/" if sPath and sPath[:1] != "/" else "", sPath or ""),
      ("?%s" % sQuery) if sQuery else "",
      ("#%s" % sFragment) if sFragment else "",
    ]);
  def foGetURL(oSelf, sPath = None, sQuery = None, sFragment = None):
    return oSelf.__oURL.foClone(sPath = sPath, sQuery = sQuery, sFragment = sFragment);
  
  def fsGetRequestURL(oSelf, oRequest):
    return oSelf.__oURL.sBase + oRequest.sURL;
  
  def foGetRequestURL(oSelf, oRequest):
    return cURL.foFromString(oSelf.fsGetRequestURL(oRequest));
  
  def fStart(oSelf, foRequestHandler):
    oSelf.fEnterFunctionOutput(foRequestHandler = foRequestHandler);
    try:
      oSelf.__oMainLock.fAcquire();
      try:
        if not oSelf.__bBound:
          txAddress = (oSelf.__oURL.sHostname, oSelf.__oURL.uPort);
          oSelf.__oServerSocket.bind(txAddress);
          oSelf.__bBound = True;
        assert not oSelf.__bStopping, \
            "Cannot start after stopping";
        oSelf.__bStarted = True;
        oSelf.__foRequestHandler = foRequestHandler;
        oSelf.fStatusOutput("Starting server socket listening on %s..." % oSelf.sAddress);
        oSelf.__oServerSocket.listen(1);
        oSelf.__oMainThread = cThread(oSelf.__fMain);
        oSelf.__oMainThread.fStart(bVital = False);
      finally:
        oSelf.__oMainLock.fRelease();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fStop(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      # Stop accepting new connections, close all connections that are not in the middle of reading a request or sending
      # a response, send "connection: close" header with all future responses and close all connections after responses
      # have been sent. (Effectively: handle any current requests, but stop accepting new ones and stop the server once
      # all current requests have been handled.
      oSelf.__oMainLock.fAcquire();
      try:
        if oSelf.__bTerminated:
          return oSelf.fExitFunctionOutput("Already terminated");
        if oSelf.__bStopping:
          return oSelf.fExitFunctionOutput("Already stopping");
        oSelf.__bStopping = True;
        if not oSelf.__bStarted:
          oSelf.__fCheckForTermination(bLockMain = False, bMustBeTerminated = True); # This should fire terminated event
          return oSelf.fExitFunctionOutput("Never started");
        if not oSelf.__bServerSocketClosed:
          oSelf.fStatusOutput("Closing server socket...");
          try:
            oSelf.__oServerSocket.shutdown();
          except:
            pass;
          try:
            oSelf.__oServerSocket.close();
          except:
            pass;
          oSelf.__bServerSocketClosed = True;
        aoOpenConnections = oSelf.__aoOpenConnections[:];
      finally:
        oSelf.__oMainLock.fRelease();
      if aoOpenConnections:
        # Stop all connections
        for oConnection in oSelf.__aoOpenConnections:
          oConnection.fStop();
      else:
        # If there were no connections to clients after we set bStopping to True, we've stopped. However, we
        # still need to report this, so we call __fCheckForTermination which will detect and report it.
        oSelf.__fCheckForTermination();
      oSelf.fExitFunctionOutput("Stopping");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fTerminate(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__oMainLock.fAcquire();
      try:
        if oSelf.__bTerminated:
          return oSelf.fExitFunctionOutput("Already terminated");
        oSelf.__bStopping = True;
        try:
          oSelf.__oServerSocket.shutdown();
        except Exception:
          pass;
        try:
          oSelf.__oServerSocket.close();
        except:
          pass;
        oSelf.__bServerSocketClosed = True;
        if not oSelf.__bStarted:
          oSelf.__fCheckForTermination(bLockMain = False, bMustBeTerminated = True);
          return oSelf.fExitFunctionOutput("Never started");
        aoOpenConnections = oSelf.__aoOpenConnections[:];
      finally:
        oSelf.__oMainLock.fRelease();
      if aoOpenConnections:
        oSelf.fStatusOutput("Terminating connections from clients...");
        for oOpenConnection in aoOpenConnections:
          oOpenConnection.fTerminate();
        assert len(oSelf.__aoOpenConnections) == 0, \
            "No connections should remain open at this point!?";
      assert len(oSelf.__aoRunningThreads) == 0, \
          "No threads should remain running at this point!?";
      oSelf.__fCheckForTermination(bMustBeTerminated = True); # This will fire termination events
      return oSelf.fExitFunctionOutput("Terminated");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fWait(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      assert oSelf.__bStarted, \
          "You must start a server before you can wait for it."
      oSelf.__oTerminatedLock.fWait();
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbWait(oSelf, nTimeoutInSeconds = 0):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      assert oSelf.__bStarted, \
          "You must start a server before you can wait for it."
      oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds = nTimeoutInSeconds);
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fMain(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oThread = cThread.foGetCurrent();
      oSelf.fFireCallbacks("started");
      oSelf.fStatusOutput("Waiting for first incoming connection...");
      while not oSelf.__bServerSocketClosed and not oSelf.__bStopping:
        try:
          (oClientSocket, (sClientIP, uClientPort)) = oSelf.__oServerSocket.accept();
          oClientSocket.fileno(); # will throw "bad file descriptor" if the server socket was closed
        except socket.timeout:
          pass;
        except socket.error as oException:
          if not fbSocketExceptionIsTimeout(oException):
            oSelf.fStatusOutput("Exception: %s" % repr(oException));
            oSelf.fTerminate();
            break;
        else:
          oSelf.fStatusOutput("New connection from %s:%d..." % (sClientIP, uClientPort));
          oConnectionFromClient = cHTTPConnection(oClientSocket);
          oSelf.__oMainLock.fAcquire();
          try:
            oSelf.__aoOpenConnections.append(oConnectionFromClient);
            oConnectionFromClient.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
            oSelf.fStatusOutput("Starting new thread to handle connection from %s:%d..." % (sClientIP, uClientPort));
            oThread = cThread(oSelf.__fConnectionThread, oConnectionFromClient, sClientIP, uClientPort);
            oSelf.__aoRunningThreads.append(oThread);
            oThread.fStart();
          finally:
            oSelf.__oMainLock.fRelease();
          oSelf.fFireCallbacks("new connection", oConnectionFromClient);
          oSelf.fStatusOutput("Waiting for next incoming connection...");
      assert oSelf.__bStopping, \
          "PC LOAD LETTER";
      if not oSelf.__bServerSocketClosed:
        oSelf.fStatusOutput("Closing server socket...");
        try:
          oSelf.__oServerSocket.shutdown();
        except Exception:
          pass;
        try: 
          oSelf.__oServerSocket.close();
        except:
          pass;
        oSelf.__bServerSocketClosed = True;
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fHandleTerminatedCallbackFromConnection(oSelf, oConnectionFromClient):
    oSelf.__oMainLock.fAcquire();
    try:
      oSelf.__aoOpenConnections.remove(oConnectionFromClient);
      oSelf.__fCheckForTermination(bLockMain = False);
    finally:
      oSelf.__oMainLock.fRelease();
    oSelf.fFireCallbacks("connection terminated", oConnectionFromClient);
  
  def __fConnectionThread(oSelf, oConnectionFromClient, sClientIP, uClientPort):
    oSelf.fEnterFunctionOutput();
    try:
      oThread = cThread.foGetCurrent();
      try:
        if oSelf.bSecure:
          oSelf.fStatusOutput("Negotiating secure socket for %s..." % oConnectionFromClient.fsToString());
          assert oConnectionFromClient.fbStartTransaction(oSelf.__nWaitForRequestTimeoutInSeconds), \
              "Cannot start transaction";
          try:
            try:
              oConnectionFromClient.fWrapInSSLContext(oSelf.__oSSLContext);
            except oConnectionFromClient.cTransactionTimeoutException:
              return oSelf.fExitFunctionOutput("Transaction timeout while negotiating a secure connection with client %s." % oConnectionFromClient.fsToString());
            except oConnectionFromClient.cConnectionClosedException:
              return oSelf.fExitFunctionOutput("Connection closed while negotiating a secure connection with client %s." % oConnectionFromClient.fsToString());
            except oSelf.__oSSLContext.cSSLException as oException:
              return oSelf.fExitFunctionOutput("Could not negotiate a secure connection with the client. (error: %s)" % repr(oException));
          finally:
            oConnectionFromClient.fEndTransaction();
        while not oSelf.__bStopping:
          oSelf.fStatusOutput("Reading request from %s..." % oConnectionFromClient.fsToString());
          if not oConnectionFromClient.fbStartTransaction(oSelf.__nWaitForRequestTimeoutInSeconds):
            assert not oConnectionFromClient.bOpen, \
                "wut";
            oSelf.fStatusOutput("Connection %s closed." % oConnectionFromClient.fsToString());
            break;
          try:
            try:
              oRequest = oConnectionFromClient.foReceiveRequest();
            except oConnectionFromClient.cInvalidHTTPMessageException:
              oSelf.fStatusOutput("Invalid request from %s." % oConnectionFromClient.fsToString());
              break;
            except oConnectionFromClient.cTransactionTimeoutException:
              oSelf.fStatusOutput("Reading request from %s timed out; terminating connection..." % oConnectionFromClient.fsToString());
              break;
            if not oRequest:
              # The client closed the connection gracefully between requests.
              oSelf.fStatusOutput("Connection closed before request from %s was received." % oConnectionFromClient.fsToString());
              break;
            oSelf.fFireCallbacks("request received", oConnectionFromClient, oRequest);
            # Have the request handler generate a response to the request object
            oResponse = oSelf.__foRequestHandler(oSelf, oConnectionFromClient, oRequest);
            assert isinstance(oResponse, cHTTPResponse), \
                "Request handler must return a cHTTPResponse, got %s" % oResponse.__class__.__name__;
            if oSelf.__bStopping:
              oResponse.fsSetHeaderValue("Connection", "close");
            # Send the response to the client
            oSelf.fStatusOutput("Sending response to %s..." % oConnectionFromClient.fsToString());
            try:
              oConnectionFromClient.fSendResponse(oResponse);
            except oConnectionFromClient.cTransactionTimeoutException:
              oSelf.fStatusOutput("Transaction timeout while sending response to %s." % oConnectionFromClient.fsToString());
              break;
            except oConnectionFromClient.cConnectionClosedException:
              oSelf.fStatusOutput("Connection closed while sending response to %s." % oConnectionFromClient.fsToString());
              break;
          finally:
            oConnectionFromClient.fEndTransaction();
          oSelf.fFireCallbacks("response sent", oConnectionFromClient, oResponse);
          oSelf.fFireCallbacks("request received and response sent", oConnectionFromClient, oRequest, oResponse);
          if oResponse.fxGetMetaData("bStopHandlingHTTPMessages"):
            break;
          # continue "while 1" loop
        oSelf.fExitFunctionOutput();
      finally:
        oSelf.__oMainLock.fAcquire();
        try:
          oSelf.__aoRunningThreads.remove(oThread);
          oSelf.__fCheckForTermination(bLockMain = False);
        finally:
          oSelf.__oMainLock.fRelease();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsToString(oSelf):
    if oSelf.__bTerminated:
      sDetails = "terminated";
    else:
      asAttributes = [s for s in [
        oSelf.__oSSLContext and "secure" or "",
        oSelf.__bStopping and "stopping" or "",
        oSelf.__bServerSocketClosed and "closed" or "",
        "%s connections" % (len(oSelf.__aoOpenConnections) if oSelf.__aoOpenConnections else "no"),
      ] if s];
      sDetails = oSelf.__oURL.sAbsolute + (" (%s)" % ", ".join(asAttributes) if asAttributes else "");
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
