import socket, ssl, threading, time;
from cHTTPResponse import cHTTPResponse;
from fbExceptionIsReadTimeout import fbExceptionIsReadTimeout;

gnMaxWaitingForResponseTimeInSeconds = 20;
guPacketSize = 4096;

class cConnectionsToServer(object) :
  def __init__(oSelf, sIP, uPort, bSecure, bDebugOutput):
    oSelf.__sIP = sIP;
    oSelf.__uPort = uPort;
    oSelf.__bSecure = bSecure;
    oSelf.__oMainLock = threading.Lock(); # Used to control access to .__doSocket_by_oLock
    oSelf.__doSocket_by_oLock = {};
    oSelf.__bStopping = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = threading.Lock();
    oSelf.__oTerminatedLock.acquire();
    oSelf.bDebugOutput = bDebugOutput;
  
  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;
  
  def fStop(oSelf):
    # Stop accepting new connections, close all connections that are not in the middle of reading a request or sending
    # a response, send "connection: close" header with all future responses and close all connections after responses
    # have been sent. (Effectively: handle any current requests, but stop accepting new ones and stop the server once
    # all current requests have been handled.
    if oSelf.__bTerminated:
      return;
    if not oSelf.__bStopping:
      oSelf.__bStopping = True;
  
  def fTerminate(oSelf):
    if oSelf.__bTerminated:
      return;
    oSelf.__bStopping = True;
    # No new connections can be made, so the list of sockets cannot grow. Closing all sockets in the list should
    # result in termination of the server.
    oSelf.__oMainLock.acquire();
    try:
      for oSocket in oSelf.__doSocket_by_oLock.values():
        try:
          oSocket.close();
        except:
          pass;
    finally:
      oSelf.__oMainLock.release();
    oSelf.fWait();

  def fWait(oSelf):
    oSelf.__oTerminatedLock.acquire();
    oSelf.__oTerminatedLock.release();
  
  def foGetResponseForRequest(oSelf, oHTTPRequest):
    oSelf.__oMainLock.acquire();
    oLock = None;
    try:
      for oLock in oSelf.__doSocket_by_oLock:
        if oLock.acquire(False):
          # This socket may have been closed just now. In that case the entry
          # in the dict has been deleted. If this is not the case, we can use
          # the socket.
          oSocket = oSelf.__doSocket_by_oLock.get(oLock);
          if oSocket:
            break;
      else:
        # No free sockets: create a new one. Officially this should be limitted,
        # but we do not enforce any limit here. You will have to throttle your
        # requests yourself!
        oLock = threading.Lock();
        oLock.acquire();
        try:
          oSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
          if oSelf.bDebugOutput: print "Connecting to %s:%d..." % (oSelf.__sIP, oSelf.__uPort);
          try:
            oSocket.connect((oSelf.__sIP, oSelf.__uPort));
          except Exception as oException:
            if oSelf.bDebugOutput: print "Connecting to %s:%d failed: %s(%s)." % \
                (oSelf.__sIP, oSelf.__uPort, oException.__class__.__name__, oException.message);
            return;
          if oSelf.__bSecure:
            try:
              oSocket = ssl.wrap_socket(sock = oSocket);
            except Exception as oException:
              if oSelf.bDebugOutput: print "SSL handshake with %s:%d failed: %s(%s)." % \
                  (oSelf.__sIP, oSelf.__uPort, oException.__class__.__name__, oException.message);
              return;
          oSocket.settimeout(0.1);
          oSelf.__doSocket_by_oLock[oLock] = oSocket;
        except:
          oLock.release();
          raise;
    finally:
      oSelf.__oMainLock.release();
    try:
      bCloseConnection = False;
      # Generate a request string from the request object
      if type(oHTTPRequest) == str:
        sRequest = oHTTPRequest;
        bCloseAfterSendingRequest = True;
      else:
        if oSelf.__bStopping:
          oHTTPRequest.fsSetHeaderValue("Connection", "close");
        sRequest = oHTTPRequest.fsToString();
        bCloseAfterSendingRequest = oHTTPRequest.fsGetHeaderValue("Connection").lower() != "keep-alive";
      if oSelf.bDebugOutput: print "Sending %d bytes request to %s:%d" % (len(sRequest), oSelf.__sIP, oSelf.__uPort);
      # Send the request to the client
      try:
        oSocket.send(sRequest);
      except:
        if oSelf.bDebugOutput: print "Connection closed while sending %d bytes request to %s:%d" % (len(sRequest), oSelf.__sIP, oSelf.__uPort);
        bCloseConnection = True;
        return; # The connection was closed.
      if bCloseAfterSendingRequest:
        # We will not be sending anything after this request.
        oSocket.shutdown(SHUT_WR);
      sBuffer = "";
      while 1:
        if oSelf.bDebugOutput: print "Reading response first line from %s:%d..." % (oSelf.__sIP, oSelf.__uPort);
        # Attempt to read a response from the connection
        nStartedWaitingForResponseTimeInSeconds = time.time();
        sHTTPVersion, uStatusCode, sReasonPhrase = None, None, None;
        sLastHeaderName = None;
        dHeader_sValue_by_sName = {};
        bStartOfHeadersFound = False;
        bEndOfHeadersFound = False;
        while not bEndOfHeadersFound:
          uScanStartIndex = 0;
          while 1: # read into buffer until at least one CRLF is found.
            uCRLFIndex = sBuffer.find("\r\n", uScanStartIndex);
            if uCRLFIndex != -1:
              break;
            while 1:
              if time.time() - nStartedWaitingForResponseTimeInSeconds > gnMaxWaitingForResponseTimeInSeconds:
                if oSelf.bDebugOutput: print "No response received witin acceptable time from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
                bCloseConnection = True;
                return;
              try:
                sPacket = oSocket.recv(guPacketSize);
              except Exception as oException:
                if fbExceptionIsReadTimeout(oException):
                  continue;
                if oSelf.bDebugOutput: print "Unable to read response headers from %s:%d: %s(%s)." % \
                    (oSelf.__sIP, oSelf.__uPort, oException.__class__.__name__, oException.message);
                bCloseConnection = True;
                return;
              else:
                if sPacket:
                  break;
            bStartOfHeadersFound = True;
            uScanStartIndex = max(len(sBuffer) - 1, 0);
            sBuffer += sPacket;
          while uCRLFIndex != -1: # remove lines from start of buffer until no more CRLFs or an empty line are found
            sLine = sBuffer[:uCRLFIndex];
            sBuffer = sBuffer[uCRLFIndex + 2:];
            if sLine == "": # empty line: end of headers
              bEndOfHeadersFound = True;
              break;
            elif sHTTPVersion is None: # first line: "[http version] [status code] [reason phrase]"
              as_HTTPVersion_StatusCode_ReasonPhrase = sLine.split(" ", 2);
              if len(as_HTTPVersion_StatusCode_ReasonPhrase) != 3:
                if oSelf.bDebugOutput: print "Invalid first response line from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sLine));
                bCloseConnection = True;
                return; # Response first line is invalid: drop connection.
              sHTTPVersion, sStatusCode, sReasonPhrase = as_HTTPVersion_StatusCode_ReasonPhrase;
              sHTTPVersion = sHTTPVersion.upper();
              if sHTTPVersion not in ["HTTP/1.0", "HTTP/1.1"]:
                if oSelf.bDebugOutput: print "Invalid HTTP version from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sHTTPVersion));
                bCloseConnection = True;
                return; # Response first line HTTP version is not 1.0 or 1.1: drop connection.
              try:
                uStatusCode = long(sStatusCode);
                if uStatusCode not in xrange(100, 1000):
                  if oSelf.bDebugOutput: print "Invalid HTTP status code from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sStatusCode));
                  bCloseConnection = True;
                  return; # Response first line status code is not a valid number: drop connection.
              except:
                if oSelf.bDebugOutput: print "Invalid HTTP status code from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sStatusCode));
                bCloseConnection = True;
                return; # Response first line status code is not a number: drop connection.
            elif sLine[0] in " \t": # header continuation
              if sLastHeaderName is None:
                if oSelf.bDebugOutput: print "First header line is a continuation from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sLine));
                bCloseConnection = True;
                return; # First header line is continuation: drop connection.
              sHeaderValue = sLine.strip();
              dHeader_sValue_by_sName[sLastHeaderName] += " " + sHeaderValue;
            else: # header
              asHeaderNameAndValue = sLine.split(":", 1);
              if len(asHeaderNameAndValue) != 2:
                if oSelf.bDebugOutput: print "Header line is invalid from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sLine));
                bCloseConnection = True;
                return; # Header line has no colon: drop connection.
              sHeaderName, sHeaderValue = asHeaderNameAndValue;
              sHeaderValue = sHeaderValue.strip();
              if sHeaderName in dHeader_sValue_by_sName: # multiple values are concatinated
                dHeader_sValue_by_sName[sHeaderName] += " " + sHeaderValue;
              else:
                dHeader_sValue_by_sName[sHeaderName] = sHeaderValue;
              sLastHeaderName = sHeaderName;
            uCRLFIndex = sBuffer.find("\r\n");
          # continue "while not bEndOfHeadersFound" loop
        # first line and headers read: read body
        for (sName, sValue) in dHeader_sValue_by_sName.items():
          if sName.lower() == "content-length":
            try:
              uContentLength = long(sValue);
              if uContentLength < 0:
                if oSelf.bDebugOutput: print "Invalid content length from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sValue));
            except ValueError:
              if oSelf.bDebugOutput: print "Invalid content length from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sValue));
              bCloseConnection = True;
              return; # missing or invalid content-length: drop connection.
            while len(sBuffer) < uContentLength:
              while 1:
                if time.time() - nStartedWaitingForResponseTimeInSeconds > gnMaxWaitingForResponseTimeInSeconds:
                  if oSelf.bDebugOutput: print "No response body received within acceptable time from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
                  bCloseConnection = True;
                  return;
                try:
                  sData = oSocket.recv(uContentLength - len(sBuffer));
                except Exception as oException:
                  if fbExceptionIsReadTimeout(oException):
                    continue;
                  if oSelf.bDebugOutput: print "Unable to read response body from %s:%d: %s(%s)." % \
                      (oSelf.__sIP, oSelf.__uPort, oException.__class__.__name__, oException.message);
                  bCloseConnection = True;
                  return; # Connection dropped.
                else:
                  break;
              sBuffer += sData;
            sBody = sBuffer[:uContentLength];
            sBuffer = sBuffer[uContentLength:];
            break;
        else:
          sBody = None;
        bCloseAfterReceivingResponse = False;
        for (sName, sValue) in dHeader_sValue_by_sName.items():
          if sName.lower() == "connection":
            bCloseAfterReceivingResponse = sValue.lower() == "keep-alive";
            break;
        if uStatusCode == 100 and not bCloseAfterReceivingResponse:
          # The server decided to send us a "100 Continue" response. Regardless of whether that is appropriate, we will
          # discard it and read another response if the server does not want to close the connection.
          continue;
        bCloseConnection = bCloseAfterSendingRequest or bCloseAfterReceivingResponse;
        # Construct an object that represents the response
        oHTTPResponse = cHTTPResponse(sHTTPVersion, uStatusCode, sReasonPhrase, dHeader_sValue_by_sName, sBody);
        if oSelf.bDebugOutput: print "New response from %s:%d => %s" % (oSelf.__sIP, oSelf.__uPort, oHTTPResponse);
        return oHTTPResponse;
      # continue "while 1" loop
    finally:
      if bCloseConnection:
        try:
          oSocket.shutdown(socket.SHUT_RDWR);
        except:
          pass;
        try:
          oSocket.close();
        except:
          pass;
        # Remove it from the list so when another thread acquires this lock and
        # tries to find the accompanying socket, it'll not find and, which
        # indicates the socket is closed and can no longer be used.
        del oSelf.__doSocket_by_oLock[oLock];
      oLock.release();

