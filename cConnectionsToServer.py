import re, socket, ssl, threading, time;
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
            if oSelf.bDebugOutput: print "Reusing connection to %s:%d..." % (oSelf.__sIP, oSelf.__uPort);
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
            if oSelf.bDebugOutput: print "Securing connection...";
            try:
              oSSLContext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2);
              oSocket = oSSLContext.wrap_socket(sock = oSocket);
#              oSocket = ssl.wrap_socket(sock = oSocket);
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
    bCloseConnection = False;
    try:
      bRawRequest = type(oHTTPRequest) == str;
      # Generate a request string from the request object
      if bRawRequest:
        sRequest = oHTTPRequest;
        bCloseConnection = True;
      else:
        if oSelf.__bStopping:
          oHTTPRequest = oHTTPRequest.foClone();
          oHTTPRequest.fsSetHeaderValue("Connection", "close");
        sRequest = oHTTPRequest.fsToString();
        bCloseConnection = oHTTPRequest.bCloseConnection;
      if oSelf.bDebugOutput:
        print "Sending %d bytes request to %s:%d" % (len(sRequest), oSelf.__sIP, oSelf.__uPort);
        print repr(sRequest);
      # Send the request to the client
      try:
        oSocket.send(sRequest);
      except:
        if oSelf.bDebugOutput: print "Connection closed while sending %d bytes request to %s:%d" % (len(sRequest), oSelf.__sIP, oSelf.__uPort);
        bCloseConnection = True;
        return; # The connection was closed.
      if bRawRequest or oHTTPRequest.bCloseConnection:
        # We will not be sending anything after this request.
        if oSelf.bDebugOutput: print "Shutting down our side of the connection...";
        oSocket.shutdown(socket.SHUT_WR);
        bCloseConnection = True;
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
        sContent = None;
        asContentChunks = None;
        uContentLengthHeaderValue = None;
        bTransferEncodingChunkedHeaderPresent = False;
        bConnectionCloseHeaderPresent = False;
        for (sName, sValue) in dHeader_sValue_by_sName.items():
          sLowerName = sName.lower();
          if sLowerName == "content-length":
            try:
              uContentLengthHeaderValue = long(sValue);
              if uContentLengthHeaderValue < 0:
                if oSelf.bDebugOutput: print "Invalid content length from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sContentLengthHeaderValue));
                bCloseConnection = True;
                return; # missing or invalid content-length: drop connection.
            except ValueError:
              if oSelf.bDebugOutput: print "Invalid content length from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sContentLengthHeaderValue));
              bCloseConnection = True;
              return; # missing or invalid content-length: drop connection.
            sContentLengthHeaderValue = sValue;
          else:
            sLowerValue = sValue.lower();
            if sLowerName == "transfer-encoding" and sLowerValue == "chunked":
              bTransferEncodingChunkedHeaderPresent = True;
            elif sLowerName == "connection" and sLowerValue == "close":
              bConnectionCloseHeaderPresent = True;
              bCloseConnection = True;
        if uContentLengthHeaderValue is not None:
          if bTransferEncodingChunkedHeaderPresent:
            if oSelf.bDebugOutput: print "Content length and tranfser encoding chunked headers found in the same request from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort);
            bCloseConnection = True;
            return; # missing or invalid content-length: drop connection.
          while len(sBuffer) < uContentLengthHeaderValue:
            while 1:
              if time.time() - nStartedWaitingForResponseTimeInSeconds > gnMaxWaitingForResponseTimeInSeconds:
                if oSelf.bDebugOutput: print "No response body received within acceptable time from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
                bCloseConnection = True;
                return;
              try:
                sData = oSocket.recv(uContentLengthHeaderValue - len(sBuffer));
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
          sContent = sBuffer[:uContentLengthHeaderValue];
          sBuffer = sBuffer[uContentLengthHeaderValue:];
        elif bTransferEncodingChunkedHeaderPresent:
          asContentChunks = [];
          while 1:
            if oSelf.bDebugOutput: print "Reading response body chunk header from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
            while "\r\n" not in sBuffer:
              if sBuffer and not re.match(r"^ *[a-f0-9]+ *\r?$", sBuffer, re.I):
                if oSelf.bDebugOutput: print "Invalid response body chunk header from %s:%d: %s." % (oSelf.__sIP, oSelf.__uPort, repr(sBuffer));
                bCloseConnection = True;
                return; # Connection dropped.
              if time.time() - nStartedWaitingForResponseTimeInSeconds > gnMaxWaitingForResponseTimeInSeconds:
                if oSelf.bDebugOutput: print "No response body chunk header received within acceptable time from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
                bCloseConnection = True;
                return;
              try:
                sBuffer += oSocket.recv(1);
              except Exception as oException:
                if fbExceptionIsReadTimeout(oException):
                  continue;
                if oSelf.bDebugOutput: print "Unable to read response body chunk header from %s:%d: %s(%s)." % \
                    (oSelf.__sIP, oSelf.__uPort, oException.__class__.__name__, oException.message);
                bCloseConnection = True;
                return; # Connection dropped.
            sChunkHeader, sBuffer = sBuffer.split("\r\n", 1);
            sChunkHeader = sChunkHeader.strip(" ");
            if len(sChunkHeader) > 6:
              if oSelf.bDebugOutput: print "Invalid read response body chunk header from %s:%d: %s." % \
                  (oSelf.__sIP, oSelf.__uPort, repr(sChunkHeader));
              bCloseConnection = True;
              return; # Connection dropped.
            uChunkSize = long(sChunkHeader, 16);
            if oSelf.bDebugOutput: print "Reading response body chunk of %d bytes from %s:%d." % (uChunkSize, oSelf.__sIP, oSelf.__uPort);
            while len(sBuffer) < uChunkSize + 2:
              if time.time() - nStartedWaitingForResponseTimeInSeconds > gnMaxWaitingForResponseTimeInSeconds:
                if oSelf.bDebugOutput: print "No response body chunk header received within acceptable time from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
                bCloseConnection = True;
                return;
              try:
                sBuffer += oSocket.recv(uChunkSize + 2 - len(sBuffer));
              except Exception as oException:
                if fbExceptionIsReadTimeout(oException):
                  continue;
                if oSelf.bDebugOutput: print "Unable to read response body chunk header from %s:%d: %s(%s)." % \
                    (oSelf.__sIP, oSelf.__uPort, oException.__class__.__name__, oException.message);
                bCloseConnection = True;
                return; # Connection dropped.
            if sBuffer[uChunkSize:uChunkSize + 2] != "\r\n":
              if oSelf.bDebugOutput: print "Invalid response body chunk data from %s:%d: missing CRLF." % \
                  (oSelf.__sIP, oSelf.__uPort);
              bCloseConnection = True;
              return; # Connection dropped.
            asContentChunks.append(sBuffer[:uChunkSize]);
            sBuffer = sBuffer[uChunkSize + 2:];
            if uChunkSize == 0:
              break;
        elif bConnectionCloseHeaderPresent:
          while 1:
            if time.time() - nStartedWaitingForResponseTimeInSeconds > gnMaxWaitingForResponseTimeInSeconds:
              if oSelf.bDebugOutput: print "No response body received within acceptable time from %s:%d." % (oSelf.__sIP, oSelf.__uPort);
              bCloseConnection = True;
              return;
            try:
              sBuffer += oSocket.recv(guPacketSize);
            except Exception as oException:
              if fbExceptionIsReadTimeout(oException):
                continue;
              bCloseConnection = True;
              break; # Connection dropped.
          sContent = sBuffer;
        oHTTPResponse = cHTTPResponse(sHTTPVersion, uStatusCode, sReasonPhrase, dHeader_sValue_by_sName, sContent, asContentChunks);
        # Construct an object that represents the response
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

