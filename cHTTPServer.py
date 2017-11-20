import os, socket, ssl, threading, time;
from cHTTPRequest import cHTTPRequest;
from fbExceptionIsReadTimeout import fbExceptionIsReadTimeout;

sLocalFolderPath = os.path.abspath(os.path.dirname(__file__));
gsKeyFilePath = os.path.join(sLocalFolderPath, "key+cert.pem");
gsCertFilePath = os.path.join(sLocalFolderPath, "key+cert.pem");

gnMaxWaitingForRequestTimeInSeconds = 20;
guPacketSize = 4096;

class cHTTPServer(object):
  def __init__(oSelf, sIP = None, uPort = None, bSecure = False):
    oSelf.__bBound = False;
    oSelf.__bTerminated = False;
    oSelf.__oTerminatedLock = threading.Lock();
    oSelf.__oTerminatedLock.acquire(); # Locked from the start, unlocked when the server is terminated.
    if not sIP:
      sIP = socket.gethostbyname(socket.gethostname());
    if not uPort:
      uPort = bSecure and 443 or 80;
    oSelf.__bSecure = bSecure and True or False;
    oSelf.__bStopping = False;
    oSelf.__bStarted = False;
    oSelf.__oServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0);
#    oSelf.__oServerSocket.settimeout(None);
#    oSelf.__oServerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0);
    oSelf.__oServerSocket.settimeout(0.1);
    oSelf.__oServerSocket.bind((sIP, uPort));
    oSelf.__bBound = True;
    oSelf.__dConnection_oThread_by_oSocket = {};
    oSelf.bDebugOutput = False;
  
  def __del__(oSelf):
    if oSelf.__bBound and not oSelf.__bTerminated:
      try:
        oSelf.__oServerSocket.close();
      except Exception:
        pass;
      for oSocket in oSelf.__dConnection_oThread_by_oSocket.keys():
        oSelf.__fCloseConnection(oSocket);
      raise AssertionError("cHTTPServer instance deleted without being terminated");
  
  @property
  def bTerminated(oSelf):
    return oSelf.__bTerminated;

  @property
  def bSecure(oSelf):
    return oSelf.__bSecure;
  @property
  def sAddress(oSelf):
    return "%s:%d" % oSelf.__oServerSocket.getsockname();
  
  def fsGetURL(oSelf, sRelativeURL = None):
    if not sRelativeURL:
      sRelativeURL = "";
    elif sRelativeURL[0] == "/":
      sRelativeURL = sRelativeURL[1:];
    return "http%s://%s/%s" % (oSelf.__bSecure and "s" or "", oSelf.sAddress, sRelativeURL);
  
  def fStart(oSelf, foRequestHandler):
    assert not oSelf.__bStopping, \
        "Cannot start after stopping";
    oSelf.__bStarted = True;
    oSelf.__foRequestHandler = foRequestHandler;
    if oSelf.bDebugOutput: print "Listening on %s" % oSelf.sAddress;
    oSelf.__oServerSocket.listen(1);
    oSelf.__oMainThread = threading.Thread(target = oSelf.__fMain);
    oSelf.__oMainThread.daemon = True;
    oSelf.__oMainThread.start();

  def fStop(oSelf):
    # Stop accepting new connections, close all connections that are not in the middle of reading a request or sending
    # a response, send "connection: close" header with all future responses and close all connections after responses
    # have been sent. (Effectively: handle any current requests, but stop accepting new ones and stop the server once
    # all current requests have been handled.
    if oSelf.bTerminated:
      return;
    if not oSelf.__bStopping:
      oSelf.__bStopping = True;
      try:
        oSelf.__oServerSocket.close();
      except:
        pass;
  
  def fTerminate(oSelf):
    if oSelf.__bTerminated:
      return;
    oSelf.__bStopping = True;
    try:
      oSelf.__oServerSocket.close();
    except:
      pass;
    if not oSelf.__bStarted:
      oSelf.__bStopping = True;
      oSelf.__bTerminated = True;
      return;
    # No new connections can be made, so the list of sockets cannot grow. Closing all sockets in the list should
    # result in termination of the server.
    aoSockets = oSelf.__dConnection_oThread_by_oSocket.keys()[:];
    for oSocket in aoSockets:
      try:
        oSocket.close();
      except:
        pass;
    oSelf.fWait();

  def fWait(oSelf):
    assert oSelf.__bStarted, \
        "You must start a server before you can wait for it."
    oSelf.__oTerminatedLock.acquire(); # Wait for this lock to be released
    oSelf.__oTerminatedLock.release(); # (release it again to maintain this state).
  
  def __fMain(oSelf):
    try:
      while 1:
        try:
          (oClientSocket, (sClientIP, uClientPort)) = oSelf.__oServerSocket.accept();
          oClientSocket.fileno(); # will throw "bad file descriptor" if the server socket was closed
        except socket.timeout, oTimeout:
          continue;
        except socket.error:
          break;
        if oSelf.bDebugOutput: print "New connection from %s:%d" % (sClientIP, uClientPort);
        try:
          if oSelf.__bSecure:
            oClientSocket = ssl.wrap_socket(
              sock = oClientSocket,
              keyfile = gsKeyFilePath,
              certfile = gsCertFilePath,
              server_side = True,
            );
        except Exception as oException:
          if oSelf.bDebugOutput: print "SSL handshake with %s:%d failed: %s(%s)" % \
              (sClientIP, uClientPort, oException.__class__.__name__, oException.message);
          oSelf.__fCloseConnection(oClientSocket);
        else:
          try:
            oThread = threading.Thread(target = oSelf.__fHandleConnection, args=(oClientSocket, sClientIP, uClientPort));
            oThread.daemon = True;
            oSelf.__dConnection_oThread_by_oSocket[oClientSocket] = oThread;
            oThread.start();
          except Exception as oException:
            if oSelf.bDebugOutput: print "Create thread failed: %s(%s)" % (oException.__class__.__name__, oException.message);
            oSelf.__fCloseConnection(oClientSocket);
    finally:
      try: 
        oSelf.__oServerSocket.close();
      except:
        pass;
      oSelf.__bStopping = True;
      aoThreads = oSelf.__dConnection_oThread_by_oSocket.values()[:];
      for oThread in aoThreads:
        try:
          oThread.join();
        except:
          pass;
      oSelf.__bTerminated = True;
      oSelf.__oTerminatedLock.release(); # Releasing this clock allows fWait to return.
  
  def __fHandleConnection(oSelf, oSocket, sClientIP, uClientPort):
    try:
      oSocket.settimeout(0.1);
      sBuffer = "";
      while 1:
        # Attempt to read a request from the connection
        nStartedWaitingForRequestTimeInSeconds = time.time();
        sMethod, sURL, sHTTPVersion = None, None, None;
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
              if not bStartOfHeadersFound and oSelf.__bStopping:
                  # No data for next request received yet and soft-terminating: close connection.
                return;
              if time.time() - nStartedWaitingForRequestTimeInSeconds > gnMaxWaitingForRequestTimeInSeconds:
                return;
              try:
                sPacket = oSocket.recv(guPacketSize);
              except Exception as oException:
                if fbExceptionIsReadTimeout(oException):
                  continue;
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
            elif sHTTPVersion is None: # first line: "[method] [url] [http version]"
              as_Method_URL_HTTPVersion = sLine.split(" ");
              if len(as_Method_URL_HTTPVersion) != 3:
                return; # Request first line is invalid: drop connection.
              sMethod, sURL, sHTTPVersion = as_Method_URL_HTTPVersion;
              sMethod = sMethod.upper();
              sHTTPVersion = sHTTPVersion.upper();
              if sMethod not in ["GET", "HEAD", "POST"]:
                return; # Request first line method is not GET or POST: drop connection.
              if sHTTPVersion not in ["HTTP/1.0", "HTTP/1.1"]:
                return; # Request first line HTTP version is not 1.0 or 1.1: drop connection.
            elif sLine[0] in " \t": # header continuation
              if sLastHeaderName is None:
                return; # First header line is continuation: drop connection.
              sHeaderValue = sLine.strip();
              dHeader_sValue_by_sName[sLastHeaderName] += " " + sHeaderValue;
            else: # header
              asHeaderNameAndValue = sLine.split(":", 1);
              if len(asHeaderNameAndValue) != 2:
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
        # The first line and headers are now all read
        # Check if the client requested a "100 Continue" response:
        for (sName, sValue) in dHeader_sValue_by_sName.items():
          if sName.lower() == "expect" and sValue.lower() == "100-continue":
            # We don't actually check the headers; we just send a "100 Continue" response to the client:
            try:
              oSocket.send(str(cHTTPResponse(sHTTPVersion, 100, "Continue", {}, "")));
            except:
              return; # The connection was closed.
            break;
        # Read body if present
        for (sName, sValue) in dHeader_sValue_by_sName.items():
          if sName.lower() == "content-length":
            try:
              uContentLength = long(sValue);
            except ValueError:
              return; # missing or invalid content-length: drop connection.
            while len(sBuffer) < uContentLength:
              while 1:
                if time.time() - nStartedWaitingForRequestTimeInSeconds > gnMaxWaitingForRequestTimeInSeconds:
                  return;
                try:
                  sData = oSocket.recv(uContentLength - len(sBuffer));
                except Exception as oException:
                  if fbExceptionIsReadTimeout(oException):
                    continue;
                  return; # Connection dropped.
                else:
                  break;
              sBuffer += sData;
            sBody = sBuffer[:uContentLength];
            sBuffer = sBuffer[uContentLength:];
            break;
        else:
          sBody = None;
        
        # Construct an object that represents the request
        oHTTPRequest = cHTTPRequest(sMethod, sURL, sHTTPVersion, dHeader_sValue_by_sName, sBody);
        if oSelf.bDebugOutput: print "New request from %s:%d => %s" % (sClientIP, uClientPort, oHTTPRequest);
        oHTTPResponse = oSelf.__foRequestHandler(oSelf, oHTTPRequest);
        # Generate a response string from the response object
        if oHTTPResponse is None:
          sResponse = "";
          bCloseAfterSendingResponse = True;
        elif type(oHTTPResponse) == str:
          sResponse = oHTTPResponse;
          bCloseAfterSendingResponse = True;
        else:
          if oSelf.__bStopping:
            oHTTPResponse.fsSetHeaderValue("Connection", "close");
          if sMethod == "HEAD":
            oHTTPResponse.sBody = "";
          sResponse = oHTTPResponse.fsToString();
          bCloseAfterSendingResponse = oHTTPResponse.fsGetHeaderValue("Connection").lower() != "keep-alive";
        if oSelf.bDebugOutput: print "Sending %d bytes response to %s:%d" % (len(sResponse), sClientIP, uClientPort);
        # Send the response to the client
        try:
          oSocket.send(sResponse);
        except:
          return; # The connection was closed.
        if bCloseAfterSendingResponse:
          return;
      # continue "while 1" loop
    finally:
      oSelf.__fCloseConnection(oSocket);
      del oSelf.__dConnection_oThread_by_oSocket[oSocket];
  
  def __fCloseConnection(oSelf, oSocket):
    try:
      oSocket.shutdown(socket.SHUT_RDWR);
    except:
      pass;
    try:
      oSocket.close();
    except:
      pass;
  
