import socket, time;
from .cConnectionException import cConnectionException;
from .fbSocketExceptionIsClosedConnection import fbSocketExceptionIsClosedConnection;
from .fbSocketExceptionIsTimeout import fbSocketExceptionIsTimeout;
from mDebugOutput import cWithDebugOutput;
from mMultiThreading import cLock, cWithCallbacks;

class cBufferedSocket(cWithCallbacks, cWithDebugOutput):
  nDefaultConnectTimeoutInSeconds = 5;
  uSocketReceiveChunkSize = 0x10000; # How many bytes to try to read if we do not know how many are comming.
  
  class cConnectToUnknownAddressException(cConnectionException):
    pass;
  class cConnectToInvalidAddressException(cConnectionException):
    pass;
  class cConnectTimeoutException(cConnectionException):
    pass;
  class cConnectionRefusedException(cConnectionException):
    pass;
  class cTransactionTimeoutException(cConnectionException):
    pass;
  class cConnectionClosedException(cConnectionException):
    pass;
  class cTooMuchDataException(cConnectionException):
    pass;
  
  @classmethod
  def foConnectTo(cClass, sHostname, uPort, oSSLContext = None, nConnectTimeoutInSeconds = None, bCheckHostname = None):
    if nConnectTimeoutInSeconds is None:
      nConnectTimeoutInSeconds = oSelf.nDefaultConnectTimeoutInSeconds;
    oPythonSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
    nMaxConnectEndTime = time.clock() + nConnectTimeoutInSeconds;
    try:
      oPythonSocket.settimeout(nConnectTimeoutInSeconds);
      oPythonSocket.connect((sHostname, uPort));
    except socket.gaierror as oException:
      raise cClass.cConnectToUnknownAddressException(
        "Cannot resolve hostname",
        "hostname = %s" % sHostname,
      );
    except socket.timeout as oException:
      raise cClass.cConnectTimeoutException(
        "Cannot connect to server",
        "hostname = %s, port = %d, timeout = %s seconds" % (sHostname, uPort, nConnectTimeoutInSeconds),
      );
    except socket.error as oException:
      if oException.errno == 10061:
        raise cClass.cConnectionRefusedException(
          "Connection refused by remote host",
          "hostname = %s, port = %d, exception = %s" % (sHostname, uPort, repr(oException))
        );
      raise cClass.cConnectToInvalidAddressException(
        "Invalid server address",
        "hostname = %s, port = %d, exception = %s" % (sHostname, uPort, repr(oException))
      );
    oBufferedSocket = cClass(oPythonSocket, bCreatedLocally = True);
    if oSSLContext:
      nRemainingTimeoutInSeconds = nMaxConnectEndTime - time.clock();
      assert oBufferedSocket.fbStartTransaction(nRemainingTimeoutInSeconds), \
          "Inversed polarity on the manifold; transwarp offline";
      try:
        oBufferedSocket.fWrapInSSLContext(oSSLContext, bCheckHostname);
      finally:
        oBufferedSocket.fEndTransaction();
    return oBufferedSocket;
  
  def __init__(oSelf, oPythonSocket, bCreatedLocally = None):
    # We will keep a copy of the original, non-SSL socket.
    oSelf.__oPythonNonSSLSocket = oPythonSocket;
    # We will also keep a copy of the SSL socket should we be asked to create one.
    oSelf.__oPythonSSLSocket = None;
    # Only when we explicitly need to refer to the SSL or non-SSL socket will we use either of the above. But for
    # most operations, will use __oPythonSocket, which has the SSL socket if one is created and otherwise the non-SSL.
    oSelf.__oPythonSocket = oPythonSocket;
    oSelf.__bCreatedLocally = bCreatedLocally or False;
    oSelf.__oTransactionLock = cLock("%s.__oTransactionLock" % oSelf.__class__.__name__); # Use to serialize transactions
    oSelf.__oTransactionStartedLock = cLock("%s.__oTransactionStartedLock" % oSelf.__class__.__name__); # Use to indicate a transaction is taking place.
    oSelf.__sBuffer = "";
    oSelf.__bInTransaction = False;
    oSelf.__nMaxCurrentTransactionEndTime = None;
    oSelf.__bStopping = False;
    oSelf.__bOpenForReading = True;
    oSelf.__bOpenForWriting = True;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = cLock("%s.__oTerminatedLock" % oSelf.__class__.__name__, bLocked = True);
    oSelf.txLocalAddress = oSelf.__oPythonNonSSLSocket.getsockname();
    oSelf.sLocalAddress = "%s:%d" % oSelf.txLocalAddress;
    oSelf.txRemoteAddress = oSelf.__oPythonNonSSLSocket.getpeername();
    oSelf.sRemoteAddress = "%s:%d" % oSelf.txRemoteAddress;
    oSelf.fAddEvents("terminated");
  
  @property
  def bSecure(oSelf):
    return oSelf.__oPythonSSLSocket is not None;
  
  def fStop(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      # Mark us as stopping, so the connection will be closed as soon as the active transaction is finished.
      oSelf.__bStopping = True;
      # If there is no active transaction, close the socket immediately.
      if oSelf.__oTransactionLock.fbAcquire():
        oSelf.fStatusOutput("* No active transaction; closing immediately...");
        oSelf.fClose();
      elif oSelf.__oTransactionStartedLock.fbAcquire():
        # There is still a race-condition here, but that will have to be fixed when it turns out to be a problem.
        oSelf.fStatusOutput("* Active transaction not started; closing immediately...");
        oSelf.fClose();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fTerminate(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      # Mark us as stopping
      oSelf.__bStopping = True;
      # Close the connection.
      oSelf.__fClosePythonSocket();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fWait(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      oSelf.__oTerminatedLock.fWait();
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbWait(oSelf, nTimeoutInSeconds = 0):
    oSelf.fEnterFunctionOutput(nTimeoutInSeconds = nTimeoutInSeconds);
    try:
      oSelf.__oTerminatedLock.fbWait(nTimeoutInSeconds = nTimeoutInSeconds);
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fWrapInSSLContext(oSelf, oSSLContext, bCheckHostname = None):
    oSelf.fEnterFunctionOutput(oSSLContext = oSSLContext.fsToString());
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      assert not oSelf.__sBuffer, \
          "This method cannot be called with buffered data (%s)" % repr(oSelf.__sBuffer);
      if oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
        oSelf.fStatusOutput("Transaction started.");
      # We will wrap __oPythonSocket, as this allows us to wrap a socket in SSL any number of times.
      # Note that we do not keep a reference to any SSL socket wrappers but the last one.
      oSelf.__oPythonSSLSocket = oSSLContext.foWrapSocket(oSelf.__oPythonSocket, oSelf.nRemainingTransactionTimeoutInSeconds, bCheckHostname = bCheckHostname);
      oSelf.__oPythonSocket = oSelf.__oPythonSSLSocket;
      oSelf.__oSSLContext = oSSLContext;
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fStatusOutput("Could not secure %s with %s: %s." % (oSelf.fsToString(), oSSLContext.fsToString(), repr(oException)), bVerbose = False);
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fCheckHostname(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      try:
        oSelf.__oSSLContext.fCheckHostname(oSelf.__oPythonSocket);
      except oException:
        oSelf.fTerminate();
        raise;
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbStartTransaction(oSelf, nTransactionTimeoutInSeconds = None, bWait = False):
    oSelf.fEnterFunctionOutput(nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds, bWait = bWait);
    try:
      assert nTransactionTimeoutInSeconds is None or nTransactionTimeoutInSeconds > 0, \
          "You cannot start a transaction with a timeout of %s" % nTransactionTimeoutInSeconds;
      nMaxTransactionEndTime = time.clock() + nTransactionTimeoutInSeconds if nTransactionTimeoutInSeconds else None;
      if not oSelf.__oTransactionLock.fbAcquire(nTimeoutInSeconds = nTransactionTimeoutInSeconds if bWait else 0):
        # This Socket is locked
        return oSelf.fxExitFunctionOutput(False, "Already locked (by %s)" % oSelf.__oTransactionLock.sLockedBy);
      assert oSelf.__nMaxCurrentTransactionEndTime is None, \
          "This is unexpected";
      # If the connection is not open, we cannot start a transaction.
      if not oSelf.bOpen:
        return oSelf.fxExitFunctionOutput(False, "Already closed");
      oSelf.__nTransactionTimeoutInSeconds = nTransactionTimeoutInSeconds;
      oSelf.__nMaxCurrentTransactionEndTime = nMaxTransactionEndTime;
      oSelf.__bInTransaction = True;
      return oSelf.fxExitFunctionOutput(True, "Locked for transaction");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  @property
  def nRemainingTransactionTimeoutInSeconds(oSelf):
    if oSelf.__nMaxCurrentTransactionEndTime is None:
      return None;
    return oSelf.__nMaxCurrentTransactionEndTime - time.clock();
  
  def fbTransactionTimeout(oSelf):
    return oSelf.__nMaxCurrentTransactionEndTime is not None and time.clock() > oSelf.__nMaxCurrentTransactionEndTime;
  
  def fEndTransaction(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      assert oSelf.__bInTransaction, \
          "You cannot end a transaction that has not been started.";
#      assert oSelf.__oTransactionStartedLock.bLocked, \
#          "Nothing happened during the current transaction.";
      oSelf.__nMaxCurrentTransactionEndTime = None;
      if oSelf.__bStopping:
        oSelf.fClose();
      if oSelf.__oTransactionStartedLock.bLocked:
        oSelf.__oTransactionStartedLock.fRelease();
      oSelf.__oTransactionLock.fRelease();
      oSelf.__bInTransaction = False;
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  @property
  def bOpenForReading(oSelf):
# This function's debug output would not add much useful information , so I've opted to disable debug output.
# You can uncomment the relevant lines to reactivate debug output.
#    oSelf.fEnterFunctionOutput();
#    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      if not oSelf.__bOpenForReading:
#        oSelf.fxExitFunctionOutput(False, "Already closed for reading");
        return False;
      # If the socket is supposed to be open for reading, we can try to read a byte. If this works or it times out, 
      # the connection is indeed still open.
      try:
        oSelf.__oPythonSocket.settimeout(0);
        oSelf.__sBuffer += oSelf.__oPythonSocket.recv(0);
      except Exception as oException:
        if not fbSocketExceptionIsTimeout(oException):
          # It is not actually open anymore which means it was disconnected.
          oSelf.__bOpenForReading = False;
#          oSelf.fxExitFunctionOutput(False, "Exception: %s" % repr(oException));
          return False;
      if oSelf.__sBuffer and oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
        oSelf.fStatusOutput("Transaction started.");
#      oSelf.fxExitFunctionOutput(True);
      return True;
#    except Exception as oException:
#      oSelf.fxRaiseExceptionOutput(oException);
#      raise;
  
  @property
  def bOpenForWriting(oSelf):
# This function's debug output would not add much useful information , so I've opted to disable debug output.
# You can uncomment the relevant lines to reactivate debug output.
#    oSelf.fEnterFunctionOutput();
#    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      if not oSelf.__bOpenForWriting:
#        oSelf.fxExitFunctionOutput(False);
        return False;
      # If we write an empty string to the SSL socket, we will get an 'EOF occurred in violation of protocol' error.
      # But we can write it to the non-SSL socket without having this problem.
      try:
        oSelf.__oPythonNonSSLSocket.send("");
      except Exception as oException:
        if not fbSocketExceptionIsTimeout(oException):
          # It is not actually open anymore which means it was disconnected.
          oSelf.__bOpenForWriting = False;
#          oSelf.fxExitFunctionOutput(False, "Exception: %s" % repr(oException));
          return False;
#      oSelf.fxExitFunctionOutput(True);
      return True;
#    except Exception as oException:
#      oSelf.fxRaiseExceptionOutput(oException);
#      raise;
  
  @property
  def bOpen(oSelf):
# This function's debug output would not add much useful information , so I've opted to disable debug output.
# You can uncomment the relevant lines to reactivate debug output.
#    oSelf.fEnterFunctionOutput();
#    try:
      # Returns true if the connection is open for reading and writing.
      bResult = oSelf.bOpenForReading and oSelf.bOpenForWriting;
#      oSelf.fxExitFunctionOutput(bResult);
      return bResult;
#    except Exception as oException:
#      oSelf.fxRaiseExceptionOutput(oException);
#      raise;
  
  @property
  def bHalfOpen(oSelf):
# This function's debug output would not add much useful information , so I've opted to disable debug output.
# You can uncomment the relevant lines to reactivate debug output.
#    oSelf.fEnterFunctionOutput();
#    try:
      # Returns true if the connection is open for reading and writing.
      bResult = oSelf.bOpenForReading or oSelf.bOpenForWriting;
#      oSelf.fxExitFunctionOutput(bResult);
      return bResult;
#    except Exception as oException:
#      oSelf.fxRaiseExceptionOutput(oException);
#      raise;
  
  @property
  def bHasBufferedData(oSelf):
    return len(oSelf.__sBuffer) > 0;
  
  @property
  def bHasData(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      # Returns True if we can buffer at least 1 byte of data or there is data in the buffer.
      # (i.e. when fsReadBytes(1) will return a byte).
      # !!NOTE!! This will buffer data. Do not use before trying to set up SSL, as this would cause the SSL
      # negotiation data to be read into the buffer instead of being processed by the SSL negotiation code.
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      if len(oSelf.__sBuffer) == 0 and oSelf.__bOpenForReading:
        try:
          oSelf.__oPythonSocket.settimeout(0);
          oSelf.__sBuffer += oSelf.__oPythonSocket.recv(1);
        except Exception as oException:
          if not fbSocketExceptionIsTimeout(oException):
            oSelf.fStatusOutput("Exception %s while attempting to read data." % repr(oException));
            oSelf.fCloseForReading();
      bHasData = len(oSelf.__sBuffer) > 0;
      if bHasData and oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
        oSelf.fStatusOutput("Transaction started.");
      return oSelf.fxExitFunctionOutput(bHasData, "%d bytes buffered" % len(oSelf.__sBuffer));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fsReadBufferedData(oSelf):
    oSelf.fEnterFunctionOutput();
    try:
      sData = oSelf.__sBuffer;
      oSelf.__sBuffer = "";
      return oSelf.fxExitFunctionOutput(sData);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fRaiseTransactionTimeoutExceptionIfApplicable(oSelf, sWhile):
    if oSelf.fbTransactionTimeout():
      oSelf.fClose();
      raise cBufferedSocket.cTransactionTimeoutException(
        "Transaction timeout %s" % sWhile,
        "timeout = %ss, buffered data = %d bytes (%s)" % (oSelf.__nTransactionTimeoutInSeconds, len(oSelf.__sBuffer), repr(oSelf.__sBuffer)),
      );
  
  def __fRaiseConnectionClosedWhileReadingExceptionIfApplicable(oSelf, sWhile):
    if not oSelf.bOpenForReading:
      oSelf.fClose();
      raise cBufferedSocket.cConnectionClosedException(
        "Connection closed %s" % sWhile,
        "buffered data = %d bytes (%s)" % (len(oSelf.__sBuffer), repr(oSelf.__sBuffer)),
      );
  
  def __fRaiseConnectionClosedWhileWritingExceptionIfApplicable(oSelf, sWhile):
    if not oSelf.bOpenForWriting:
      oSelf.fClose();
      raise cBufferedSocket.cConnectionClosedException(
        "Connection closed %s" % sWhile,
        "",
      );

  def fsRead(oSelf, uMaxNumberOfBytes = None):
    oSelf.fEnterFunctionOutput(uMaxNumberOfBytes = uMaxNumberOfBytes);
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      sExceptionWhile = "while reading%s data" % (" at most %d bytes of" % uMaxNumberOfBytes if uMaxNumberOfBytes is not None else ""),
      while 1:
        if oSelf.__sBuffer and oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
          oSelf.fStatusOutput("Transaction started.");
        if not oSelf.bOpenForReading:
          break;
        oSelf.__fRaiseTransactionTimeoutExceptionIfApplicable(sExceptionWhile);
        uNumberOfBytes = uMaxNumberOfBytes and (uMaxNumberOfBytes + 1 - len(oSelf.__sBuffer)) or oSelf.uSocketReceiveChunkSize;
        try:
          oSelf.__oPythonSocket.settimeout(0);
          oSelf.__sBuffer += oSelf.__oPythonSocket.recv(uNumberOfBytes);
        except Exception as oException:
          if not fbSocketExceptionIsTimeout(oException):
            oSelf.fCloseForReading();
            break;
        if len(oSelf.__sBuffer) > uMaxNumberOfBytes:
          oSelf.fClose();
          raise cBufferedSocket.cTooMuchDataException(
            "Received too much data %s" % sExceptionWhile,
            "buffered data = %d bytes (%s)" % (len(oSelf.__sBuffer), repr(oSelf.__sBuffer)),
          );
      sData = oSelf.__sBuffer;
      oSelf.__sBuffer = "";
      return oSelf.fxExitFunctionOutput(sData);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsReadBytes(oSelf, uBytes):
    oSelf.fEnterFunctionOutput(uBytes = uBytes);
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      sExceptionWhile = "while reading %d bytes of data" % uBytes,
      while 1:
        if oSelf.__sBuffer and oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
          oSelf.fStatusOutput("Transaction started.");
        uBytesLeft = uBytes - len(oSelf.__sBuffer);
        if uBytesLeft <= 0:
          sData = oSelf.__sBuffer[:uBytes];
          oSelf.__sBuffer = oSelf.__sBuffer[uBytes:];
          return oSelf.fxExitFunctionOutput(sData);
        oSelf.__fRaiseConnectionClosedWhileReadingExceptionIfApplicable(sExceptionWhile);
        oSelf.__fRaiseTransactionTimeoutExceptionIfApplicable(sExceptionWhile);
        try:
          oSelf.__oPythonSocket.settimeout(0);
          oSelf.__sBuffer += oSelf.__oPythonSocket.recv(uBytesLeft);
        except Exception as oException:
          if not fbSocketExceptionIsTimeout(oException):
            oSelf.fClose();
            oSelf.__fRaiseConnectionClosedWhileReadingExceptionIfApplicable(sExceptionWhile); # Always applicable.
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fsReadUntil(oSelf, sBytes, uMaxNumberOfBytes = None):
    oSelf.fEnterFunctionOutput(sBytes = sBytes, uMaxNumberOfBytes = uMaxNumberOfBytes);
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      assert uMaxNumberOfBytes is None or uMaxNumberOfBytes >= len(sBytes), \
          "It is impossible to find %d bytes without reading more than %d bytes" % (len(sBytes), uMaxNumberOfBytes);
      sExceptionWhile = "while reading%s until %s is found" % (" at most %d bytes" % uMaxNumberOfBytes if uMaxNumberOfBytes is not None else "", repr(sBytes));
      uNextFindStartIndex = 0;
      if oSelf.__sBuffer and oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
        oSelf.fStatusOutput("Transaction started.");
      while 1:
        # We need to read enough bytes to be able to start another search (i.e. one).
        while 1:
          uBytesToRead = uNextFindStartIndex + len(sBytes) - len(oSelf.__sBuffer);
          if uBytesToRead <= 0:
            break;
          if uMaxNumberOfBytes is not None and len(oSelf.__sBuffer) + uBytesToRead > uMaxNumberOfBytes:
            oSelf.fClose();
            raise cBufferedSocket.cTooMuchDataException(
              "Start of %d byte marker not found after reading %d/%d bytes." % \
                  (len(sBytes), len(oSelf.__sBuffer), uMaxNumberOfBytes),
              "buffered data = %d bytes (%s)" % (len(oSelf.__sBuffer), repr(oSelf.__sBuffer)),
            );
          oSelf.__fRaiseConnectionClosedWhileReadingExceptionIfApplicable(sExceptionWhile);
          oSelf.__fRaiseTransactionTimeoutExceptionIfApplicable(sExceptionWhile);
          try:
            oSelf.__oPythonSocket.settimeout(0);
            sNewData = oSelf.__oPythonSocket.recv(uBytesToRead);
          except Exception as oException:
            if not fbSocketExceptionIsTimeout(oException):
              oSelf.fClose();
              oSelf.__fRaiseConnectionClosedWhileReadingExceptionIfApplicable(sExceptionWhile); # Always applicable
          else:
            if sNewData:
              if not oSelf.__sBuffer and oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
                oSelf.fStatusOutput("Transaction started.");
              oSelf.__sBuffer += sNewData;
        uStartIndex = oSelf.__sBuffer.find(sBytes, uNextFindStartIndex);
        if uStartIndex != -1:
          uEndIndex = uStartIndex + len(sBytes);
          sData = oSelf.__sBuffer[:uEndIndex];
          oSelf.__sBuffer = oSelf.__sBuffer[uEndIndex:];
          return oSelf.fxExitFunctionOutput(sData, "Marker found at %d/%d bytes" % (uStartIndex, len(sData)));
        # The next find operation will not need to scan the entire buffer again:
        uNextFindStartIndex = max(0, len(oSelf.__sBuffer) - len(sBytes) + 1);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fWrite(oSelf, sBytes):
    oSelf.fEnterFunctionOutput(sBytes = sBytes);
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      sExceptionWhile = " while writing %d bytes" % len(sBytes);
      if oSelf.__oTransactionStartedLock.fbAcquire(0): # lock if not already locked.
        oSelf.fStatusOutput("Transaction started.");
      oSelf.__fRaiseConnectionClosedWhileWritingExceptionIfApplicable(sExceptionWhile);
      sRemainingBytes = sBytes;
      uTotalBytesSent = 0;
      while 1:
        oSelf.__fRaiseTransactionTimeoutExceptionIfApplicable(sExceptionWhile);
        if sRemainingBytes == "":
          # For non-SSL sockets we could simply send an empty string but for SSL sockets, this would cause an
          # 'EOF occurred in violation of protocol' error for unknown reasons. So let's just not send anything:
          return oSelf.fxExitFunctionOutput(True, "%s written" % ("Nothing" if uTotalBytesSent == 0 else "%d bytes" % uTotalBytesSent));
        try:
          oSelf.__oPythonSocket.settimeout(oSelf.nRemainingTransactionTimeoutInSeconds);
          uBytesSent = oSelf.__oPythonSocket.send(sRemainingBytes);
        except Exception as oException:
          oSelf.__fRaiseTransactionTimeoutExceptionIfApplicable(sExceptionWhile);
          assert not fbSocketExceptionIsTimeout(oException), \
              "wut";
          oSelf.__fRaiseConnectionClosedWhileWritingExceptionIfApplicable(sExceptionWhile); # Always applicable
        sRemainingBytes = sRemainingBytes[uBytesSent:];
        uTotalBytesSent += uBytesSent;
        sExceptionWhile = " while writing %d bytes after sending %s bytes" % (len(sRemainingBytes), uTotalBytesSent);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
    
  def fCloseForReading(oSelf):
# This function gets called often to make sure the connection is closed and its debug output would not add much useful
# information in such cases, so I've opted to add a fast path that does not produce debug output.
    if oSelf.__oTransactionLock.bLocked and not oSelf.__bOpenForReading:
      return;
    oSelf.fEnterFunctionOutput();
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      if not oSelf.__bOpenForReading:
        return oSelf.fExitFunctionOutput("Already %s." % ("closed for reading" if oSelf.__bOpenForWriting else "fully closed"));
      if not oSelf.__bOpenForWriting:
        oSelf.__fClosePythonSocket();
        return oSelf.fExitFunctionOutput("Fully closed.");
      try:
        oSelf.__oPythonSocket.shutdown(socket.SHUT_RD);
      except Exception as oException:
        if fbSocketExceptionIsClosedConnection(oException):
          oSelf.__fClosePythonSocket();
          return oSelf.fExitFunctionOutput("Fully closed.");
        raise;
      oSelf.__bOpenForReading = False;
      oSelf.fExitFunctionOutput("Closed for reading.");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fCloseForWriting(oSelf):
# This function gets called often to make sure the connection is closed and its debug output would not add much useful
# information in such cases, so I've opted to add a fast path that does not produce debug output.
    if oSelf.__oTransactionLock.bLocked and not oSelf.__bOpenForWriting:
      return;
    oSelf.fEnterFunctionOutput();
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      if not oSelf.__bOpenForWriting:
        return oSelf.fExitFunctionOutput("Already %s." % ("closed for writing" if oSelf.__bOpenForReading else "fully closed" ));
      if not oSelf.__bOpenForReading:
        oSelf.__fClosePythonSocket();
        return oSelf.fExitFunctionOutput("Fully closed.");
      try:
        oSelf.__oPythonSocket.shutdown(socket.SHUT_WR);
      except Exception as oException:
        if fbSocketExceptionIsClosedConnection(oException):
          oSelf.__fClosePythonSocket();
          return oSelf.fExitFunctionOutput("Fully closed.");
        raise;
      oSelf.__bOpenForWriting = False;
      oSelf.fExitFunctionOutput("Closed for writing.");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fClose(oSelf):
# This function gets called often to make sure the connection is closed and its debug output would not add much useful
# information in such cases, so I've opted to add a fast path that does not produce debug output.
    if oSelf.__oTransactionLock.bLocked and not oSelf.__bOpenForReading and not oSelf.__bOpenForWriting:
      return;
    oSelf.fEnterFunctionOutput();
    try:
      if not oSelf.__oTransactionLock.bLocked:
        assert oSelf.__bStopping, \
            "This method cannot be called without first calling fbStartTransaction and it must return True";
      if not oSelf.__bOpenForReading and not oSelf.__bOpenForWriting:
        oSelf.fExitFunctionOutput("Already fully closed");
      else:
        oSelf.__fClosePythonSocket();
        oSelf.fExitFunctionOutput("Fully closed");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fClosePythonSocket(oSelf):
# This function gets called often to make sure the connection is closed and its debug output would not add much useful
# information in such cases, so I've opted to add a fast path that does not produce debug output.
    if oSelf.__bTerminated:
      return;
    # This closes __oPythonSocket, which is either the socket itself, or the SSL wrapper. Closing the later also
    # close the socket itself, so we do not need to explicitly close both.
    oSelf.fEnterFunctionOutput();
    try:
      try:
        if oSelf.__bOpenForReading:
          if oSelf.__bOpenForWriting:
            oSelf.fStatusOutput("Shutdown connection for reading and writing...");
            oSelf.__oPythonSocket.shutdown(socket.SHUT_RDWR);
          else:
            oSelf.fStatusOutput("Shutdown connection for reading...");
            oSelf.__oPythonSocket.shutdown(socket.SHUT_RD);
        elif oSelf.__bOpenForWriting:
          oSelf.fStatusOutput("Shutdown connection for writing...");
          oSelf.__oPythonSocket.shutdown(socket.SHUT_WR);
      except Exception as oException:
        if not fbSocketExceptionIsClosedConnection(oException):
          raise;
      oSelf.__bOpenForReading = False;
      oSelf.__bOpenForWriting = False;
      oSelf.__oPythonSocket.close();
      if not oSelf.__bTerminated:
        oSelf.__bTerminated = True;
        oSelf.__oTerminatedLock.fRelease();
        oSelf.fStatusOutput("Firing callbacks...");
        oSelf.fFireCallbacks("terminated");
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fPipe(oSelf, oOther, nConnectionTimeoutInSeconds, nIdleTimeoutInSeconds):
    oSelf.fEnterFunctionOutput(oOther = oOther.fsToString(), nConnectionTimeoutInSeconds = nConnectionTimeoutInSeconds, nIdleTimeoutInSeconds = nIdleTimeoutInSeconds);
    try:
      assert oSelf.__bInTransaction, \
          "Sockets must be in a transaction!!";
      assert oOther.__bInTransaction, \
          "Sockets must be in a transaction!!";
      oSelf.fStatusOutput("Piping connections %s and %s." % (oSelf.fsToString(), oOther.fsToString()), bVerbose = False);
      oSelf.__oTransactionStartedLock.fbAcquire(0);
      oOther.__oTransactionStartedLock.fbAcquire(0);
      nMaxConnectionEndTime = time.clock() + nConnectionTimeoutInSeconds if nConnectionTimeoutInSeconds else None;
      nMaxIdleEndTime = time.clock() + nIdleTimeoutInSeconds if nIdleTimeoutInSeconds else None;
      def ftxForwardData(oSource, oDestination, nMaxIdleEndTime):
        if nMaxConnectionEndTime is not None and time.clock() > nMaxConnectionEndTime:
#          oSelf.fStatusOutput("Connection timeout.", bCalledFromSubFunction = True);
          oSource.fClose();
          oDestination.fClose();
          return (0, 0);
        if nMaxIdleEndTime is not None and time.clock() > nMaxIdleEndTime:
#          oSelf.fStatusOutput("Connection idle timeout.", bCalledFromSubFunction = True);
          oSource.fClose();
          oDestination.fClose();
          return (0, 0);
        if not oDestination.__bOpenForWriting:
          # If the destination is closed we cannot forward data, so we will close the source.
          oSource.fCloseForReading();
          return (0, 0);
        if not oSource.__bOpenForReading:
          # If the source is closed and there is no more data to forward, we will close the destination.
          if oSource.__sBuffer == "":
            oDestination.fCloseForWriting();
            return (0, 0);
#          oSelf.fStatusOutput("Buffered: %s." % repr(oSource.__sBuffer), bCalledFromSubFunction = True);
        else:
#          oSelf.fStatusOutput("Buffered: %s." % repr(oSource.__sBuffer), bCalledFromSubFunction = True);
          try:
            oSelf.__oPythonSocket.settimeout(0);
            sReceived = oSource.__oPythonSocket.recv(oSource.uSocketReceiveChunkSize);
          except Exception as oException:
            if not fbSocketExceptionIsTimeout(oException):
              # If we cannot read from the source, we will close it.
              oSource.fStatusOutput("Exception while reading: %s." % repr(oException), bCalledFromSubFunction = True);
              oSource.fCloseForReading();
            sReceived = "";
          uBytesReceived = len(sReceived);
          oSource.__sBuffer += sReceived;
#        oSelf.fStatusOutput("Received: %s." % repr(sReceived), bCalledFromSubFunction = True);
        if oSource.__sBuffer:
          try:
            oOther.__oPythonSocket.settimeout(0);
            uBytesSent = oDestination.__oPythonSocket.send(oSource.__sBuffer);
          except Exception as oException:
            oSelf.fStatusOutput("Exception while writing: %s." % repr(oException), bCalledFromSubFunction = True);
            # If we cannot write to the destination we cannot forward data, so we will close both the source and the destination.
            oSource.fCloseForReading();
            oDestination.fCloseForWriting();
            uBytesSent = 0;
        else:
          uBytesSent = 0;
#        oSelf.fStatusOutput("Send: %s." % repr(oSelf.__sBuffer[:uBytesSent]), bCalledFromSubFunction = True);
        oSource.__sBuffer = oSelf.__sBuffer[uBytesSent:];
        return (uBytesReceived, uBytesSent);
      # Forward data while this is potentially possible.
      while oSelf.bHalfOpen or oOther.bHalfOpen:
        (uBytesReceivedFromSelf, uBytesSentToOther) = ftxForwardData(oSelf, oOther, nMaxIdleEndTime);
        if uBytesSentToOther or uBytesReceivedFromSelf:
          oSelf.fStatusOutput("%s =%d/%d=> %s" % (oSelf.fsToString(), uBytesSentToOther, uBytesReceivedFromSelf, oOther.fsToString()));
          nMaxIdleEndTime = time.clock() + nIdleTimeoutInSeconds if nIdleTimeoutInSeconds else None;
        (uBytesReceivedFromOther, uBytesSentToSelf) = ftxForwardData(oOther, oSelf, nMaxIdleEndTime);
        if uBytesSentToSelf or uBytesReceivedFromOther:
          oSelf.fStatusOutput("%s <=%d/%d= %s" % (oSelf.fsToString(), uBytesSentToSelf, uBytesReceivedFromOther, oOther.fsToString()));
          nMaxIdleEndTime = time.clock() + nIdleTimeoutInSeconds if nIdleTimeoutInSeconds else None;
      # No more data can be forwarded; make sure both connections are fully closed
      oSelf.fClose();
      oOther.fClose();
      oSelf.fExitFunctionOutput("Stopped piping connections %s and %s." % (oSelf.fsToString(), oOther.fsToString()));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fsGetDetails(oSelf):
    # We do not hold an exclusive lock, so values can change while we read them. To prevent a double fetch from causing
    # problems (e.g. a value is check to not be None, but then output after it has been changed to None). we will read
    # all values once. This does not protect against race conditions that make the information contradictory (e.g. the
    # transaction lock being read as not locked, but the timeout being read as not None because the socket was locked
    # between the two reads). However, this function is a half-hearted attempt to get some potentially useful debug
    # information and its output is not vital to the functioning of the object, so it'll have to do for now.
    bTransactionPlanned = oSelf.__oTransactionLock.bLocked;
    bTransactionStarted = oSelf.__oTransactionStartedLock.bLocked;
    nRemainingTransactionTimeoutInSeconds = oSelf.nRemainingTransactionTimeoutInSeconds;
    bOpenForReading = oSelf.__bOpenForReading;
    bOpenForWriting = oSelf.__bOpenForWriting;
    bStopping = oSelf.__bStopping;
    sBuffer = oSelf.__sBuffer;
    oPythonSSLSocket = oSelf.__oPythonSSLSocket;
    asAttributes = [s for s in [
      "in transaction" if bTransactionStarted else 
          "waiting for transaction" if bTransactionPlanned else 
          "idle",
      "timeout in %fs" % nRemainingTransactionTimeoutInSeconds if nRemainingTransactionTimeoutInSeconds is not None else 
          "no timeout" if bTransactionPlanned else 
          None,
      "%s buffered" % ("%d bytes" % len(sBuffer) if sBuffer else "nothing"),
      "secure" if oPythonSSLSocket else "",
      "read-only" if bOpenForReading and not bOpenForWriting else "",
      "write-only" if not bOpenForReading and bOpenForWriting else "",
      "closed" if not bOpenForWriting and not bOpenForReading else "",
      "stopping" if bStopping else "",
      "terminated" if oSelf.__bTerminated else "",
    ] if s];
    return "%s%s%s%s" % (
      oSelf.sLocalAddress or "??",
      oSelf.__bCreatedLocally and "=>" or "<=",
      oSelf.sRemoteAddress or "??",
      " (%s)" % ", ".join(asAttributes) if asAttributes else "",
    );
  
  def fsToString(oSelf):
    return "%s{%s}" % (oSelf.__class__.__name__, oSelf.__fsGetDetails());
  
  def __repr__(oSelf):
    return "<%s %s>" % (oSelf.__class__.__name__, oSelf.__fsGetDetails());
  
  def str(oSelf):
    return "%s %s" % (oSelf.__class__.__name__, oSelf.__fsGetDetails());
