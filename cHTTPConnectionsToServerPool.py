import time;
from .cHTTPConnection import cHTTPConnection;
from mDebugOutput import cWithDebugOutput;
from mMultiThreading import cLock, cWithCallbacks;

class cHTTPConnectionsToServerPool(cWithCallbacks, cWithDebugOutput):
  def __init__(oSelf, oServerBaseURL, uMaxConnectionsToServer, oSSLContext = None):
    oSelf.__oServerBaseURL = oServerBaseURL;
    oSelf.__uMaxConnectionsToServer = uMaxConnectionsToServer;
    oSelf.__oSSLContext = oSSLContext;
    
    oSelf.__oConnectionsLock = cLock("%s.__oConnectionsLock" % oSelf.__class__.__name__);
    oSelf.__aoConnections = [];
    
    oSelf.__bStopping = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    
    oSelf.fAddEvents("new connection", "request sent", "response received", "request sent and response received", "connection terminated", "terminated");
  
  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;
  
  @property
  def uConnectionsCount(oSelf):
    return len(oSelf.__aoConnections);
  
  def __fCheckForTermination(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      if not oSelf.__bStopping:
        return oSelf.fExitFunctionOutput("Not stopping");
      oSelf.__oConnectionsLock.fAcquire();
      try:
        uOpenConnections = len(oSelf.__aoConnections);
        bTerminated = uOpenConnections == 0 and not oSelf.__bTerminated;
        if bTerminated: oSelf.__bTerminated = True;
      finally:
        oSelf.__oConnectionsLock.fRelease();
      if bTerminated:
        oSelf.__oTerminatedLock.fRelease();
        oSelf.fFireCallbacks("terminated");
        return oSelf.fExitFunctionOutput("Terminated");
      return oSelf.fExitFunctionOutput("Not terminated; %d open connections." % uOpenConnections);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fStop(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      if oSelf.__bStopping:
        return oSelf.fExitFunctionOutput("Already stopping");
      oSelf.__bStopping = True;
      oSelf.__oConnectionsLock.fAcquire();
      try:
        aoConnections = oSelf.__aoConnections[:];
      finally:
        oSelf.__oConnectionsLock.fRelease();
      if aoConnections:
        oSelf.fStatusOutput("Stopping %d connections..." % len(aoConnections));
        for oConnection in aoConnections:
          oConnection.fStop();
      else:
        # If there were no connections after we set bStopping to True, we've stopped. However, we still need to
        # report this, so we call __fCheckForTermination which will detect and report it.
        oSelf.__fCheckForTermination();
      return oSelf.fExitFunctionOutput("Terminated" if oSelf.__bTerminated else "Stopping");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fTerminate(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      if oSelf.__bTerminated:
        return oSelf.fExitFunctionOutput("Already terminated");
      oSelf.__bStopping = True;
      oSelf.__oConnectionsLock.fAcquire();
      try:
        aoConnections = oSelf.__aoConnections[:];
      finally:
        oSelf.__oConnectionsLock.fRelease();
      oSelf.fStatusOutput("Terminating connections...");
      for oConnection in aoConnections:
        oConnection.fTerminate();
      oSelf.fStatusOutput("Waiting for termination...");
      oSelf.fWait();
      return oSelf.fExitFunctionOutput("Terminated");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fWait(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__oTerminatedLock.fWait();
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbWait(oSelf, nTimeoutInSeconds = 0):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds = nTimeoutInSeconds);
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetResponseForRequest(oSelf, oRequest, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostname = None):
    oSelf.fEnterFunctionOutput(oRequest = oRequest.fsToString(), nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostname = bCheckHostname);
    if bCheckHostname is None:
      # If not specified, always check the hostname when the connection is secure.
      bCheckHostname = oSelf.__oSSLContext;
    try:
      nMaxConnectEndTime = time.clock() + nConnectTimeoutInSeconds;
      while 1:
        nRemainingConnectTimeoutInSeconds = nMaxConnectEndTime - time.clock();
        if nRemainingConnectTimeoutInSeconds <= 0:
          raise cHTTPConnection.cConnectTimeoutException("Connect timeout while sending request.");
        # Returns False of request was not send.
        # Returns None of response was not received.
        # Returns cResponse instance if response was received.
        oSelf.fStatusOutput("Getting connection...");
        oConnection = oSelf.foGetConnectionAndStartTransaction(nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostname);
        if oConnection is None:
          assert oSelf.__bStopping, \
              "None is not expected unless we're stopping.";
          return oSelf.fxExitFunctionOutput(None, "Stopping.");
        try:
          if bCheckHostname:
            oConnection.fCheckHostname(); # closes connection and raises an exception if the hostname doesn't match
          oResponse = oConnection.foGetResponseForRequest(oRequest);
        finally:
          oConnection.fEndTransaction();
        # Response = None means request could not be sent; try another connection.
        if oResponse:
          break;
      oSelf.fFireCallbacks("request sent and response received", oConnection, oRequest, oResponse);
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetConnectionAndStartTransaction(oSelf, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostname, bNoSSLNegotiation = None):
    oSelf.fEnterFunctionOutput(nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostname = bCheckHostname, bNoSSLNegotiation = bNoSSLNegotiation);
    try:
      # We may have to wait for a connection to become available, so we'll calculate the remaining time until the
      # transaction should be finished each time to determining the remaining transaction time.
      nMaxEndTransactionTime = time.clock() + nTransactionTimeoutInSeconds;
      while 1:
        oSelf.__oConnectionsLock.fAcquire();
        if oSelf.__bStopping:
          return oSelf.fxExitFunctionOutput(None, "Stopping");
        try:
          nRemainingTransactionTimeoutInSeconds = nMaxEndTransactionTime - time.clock();
          if nRemainingTransactionTimeoutInSeconds <= 0:
            raise cHTTPConnection.cConnectTimeoutException(
              "Maximum number of active connections reached and all connections busy.",
              "timeout after %f seconds" % nTransactionTimeoutInSeconds
            );
          if not oSelf.__oSSLContext or not bNoSSLNegotiation:
            # If we are not estabilish secure connections, or reusing a secure connection is ok, try to do so:
            for oConnection in oSelf.__aoConnections:
              if oConnection.fbStartTransaction(nRemainingTransactionTimeoutInSeconds):
                # This socket is open and can be reused.
                return oSelf.fxExitFunctionOutput(oConnection, "Reuse");
          if len(oSelf.__aoConnections) < oSelf.__uMaxConnectionsToServer:
            oConnection = oSelf.__foCreateNewConnectionAndStartTransaction(min(nConnectTimeoutInSeconds, nRemainingTransactionTimeoutInSeconds), nRemainingTransactionTimeoutInSeconds, bCheckHostname, bNoSSLNegotiation);
            return oSelf.fxExitFunctionOutput(oConnection, "New");
        finally:
          oSelf.__oConnectionsLock.fRelease();
        # Ideally, we'd want to use some kind of lock to wait until a connection becomes free for re-use or is closed
        # but the wait needs to have a timeout. Unfortunately, the threading library does not appear to offer any lock
        # that we can try to acquire with a timeout...
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foCreateNewConnectionAndStartTransaction(oSelf, nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds, bCheckHostname, bNoSSLNegotiation):
    # ASSUMES __oConnectionsLock has been acquired!!
    oSelf.fEnterFunctionOutput(nConnectTimeoutInSeconds = nConnectTimeoutInSeconds, nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bCheckHostname = bCheckHostname, bNoSSLNegotiation = bNoSSLNegotiation);
    try:
      # Create a new socket and return that.
      nMaxEndTransactionTime = time.clock() + nTransactionTimeoutInSeconds;
      oSelf.fStatusOutput("Connecting to %s..." % oSelf.__oServerBaseURL);
      oConnection = cHTTPConnection.foConnectTo(
        sHostname = oSelf.__oServerBaseURL.sHostname,
        uPort = oSelf.__oServerBaseURL.uPort,
        oSSLContext = oSelf.__oSSLContext if not bNoSSLNegotiation else None,
        nConnectTimeoutInSeconds = nConnectTimeoutInSeconds,
        bCheckHostname = bCheckHostname,
      );
      if not oConnection:
        return oSelf.fxExitFunctionOutput(None, "Connection closed while negotiating secure connection");
      oConnection.fAddCallback("request sent", oSelf.__fHandleRequestSentCallbackFromConnection);
      oConnection.fAddCallback("response received", oSelf.__fHandleResponseReceivedCallbackFromConnection);
      oConnection.fAddCallback("terminated", oSelf.__fHandleTerminatedCallbackFromConnection);
      oSelf.__aoConnections.append(oConnection);
      oSelf.fFireCallbacks("new connection", oConnection);
      # Calculate remaining transaction time:
      nRemainingTransactionTimeoutInSeconds = nMaxEndTransactionTime - time.clock();
      if nRemainingTransactionTimeoutInSeconds <= 0:
        # Not enough for this transaction.
        return oSelf.fxExitFunctionOutput(None, "Transaction timeout while connecting");
      assert oConnection.fbStartTransaction(nRemainingTransactionTimeoutInSeconds), \
          "I'm a lollypop, watch me fly!";
      return oSelf.fxExitFunctionOutput(oConnection);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fHandleRequestSentCallbackFromConnection(oSelf, oConnection, oRequest):
    oSelf.fFireCallbacks("request sent", oConnection, oRequest);
  
  def __fHandleResponseReceivedCallbackFromConnection(oSelf, oConnection, oResponse):
    oSelf.fFireCallbacks("response received", oConnection, oResponse);
  
  def __fHandleTerminatedCallbackFromConnection(oSelf, oConnection):
    oSelf.fEnterFunctionOutput(oConnection = oConnection.fsToString());
    try:
      oSelf.__oConnectionsLock.fAcquire();
      try:
        assert not oSelf.__bTerminated, \
            "All connection should have been terminated when the connections to server pool has terminated, so this event is not expected!";
        oSelf.__aoConnections.remove(oConnection);
      finally:
        oSelf.__oConnectionsLock.fRelease();
      oSelf.fFireCallbacks("connection terminated", oConnection);
      oSelf.__fCheckForTermination();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fsToString(oSelf):
    asAttributes = [s for s in [
      "%d connections" % len(oSelf.__aoConnections) if not oSelf.__bTerminated else None,
      "secure" if oSelf.__oSSLContext else None,
      "terminated" if oSelf.__bTerminated else
          "stopping" if oSelf.__bStopping else None,
    ] if s];
    sDetails = oSelf.__oServerBaseURL.sBase + (" (%s)" % ", ".join(asAttributes) if asAttributes else "");
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
