import json, re;
from .cBufferedSocket import cBufferedSocket;
from .cHTTPHeaders import cHTTPHeaders;
from .cHTTPRequest import cHTTPRequest;
from .cHTTPResponse import cHTTPResponse;
from .cProtocolException import cProtocolException;
from .iHTTPMessage import iHTTPMessage;
from mMultiThreading import cWithCallbacks;

gnDefaultReadHTTPMessageTimeoutInSeconds = 10;
guDefaultMaxReasonPhraseSize = 1000;
guDefaultMaxHeaderNameSize = 10*1000;
guDefaultMaxHeaderValueSize = 10*1000;
guDefaultMaxNumberOfHeaders = 256;
guDefaultMaxBodySize = 10*1000*1000;
guDefaultMaxChunkSize = 10*1000*1000;
guDefaultMaxNumberOfChunks = 1000;
# The HTTP RFC does not provide an upper limit to the maximum number of characters a chunk size can contain.
# So, by padding a valid chunk size on the left with "0", one could theoretically create a valid chunk header that has
# an infinite size. To prevent us accepting such an obviously invalid value, we will accept no chunk size containing
# more than 8 chars (i.e. 32-bit numbers).
guMaxChunkSizeCharacters = 8;

gbDebugOutputFullHTTPMessages = True;

class cHTTPConnection(cBufferedSocket):
  class cOutOfBandDataException(cProtocolException):
    pass; # The remote send data when it was not expected to do so (i.e. the server send data before a request was made).
  
  def __init__(oSelf, oPythonSocket, bCreatedLocally = None, dxMetaData = None):
    oSelf.__dxMetaData = dxMetaData or {};
    
    cBufferedSocket.__init__(oSelf, oPythonSocket, bCreatedLocally);
    oSelf.fAddEvents("message sent", "request sent", "response sent", "message received", "request received", "response received");
    
  def fbHasMetaData(oSelf, sName):
    return sName in oSelf.__dxMetaData;
  def fxGetMetaData(oSelf, sName):
    return oSelf.__dxMetaData.get(sName);
  def fSetMetaData(oSelf, sName, xValue):
    oSelf.__dxMetaData[sName] = xValue;
  
  # Send HTTP Messages
  def fbSendRequest(oSelf, oRequest):
    oSelf.fEnterFunctionOutput(oRequest = oRequest.fsToString());
    try:
       # The server should only send data in response to a request; if it send out-of-band data we close the connection.
      if oSelf.bHasData:
        oSelf.fClose();
        sOutOfBandData = oSelf.fsReadBufferedData();
        raise cHTTPConnection.cOutOfBandDataException(
          "Out-of-band data was received.",
          sOutOfBandData,
        );
      # it's ok if a connection is dropped by a server before a request is sent.
      bSent = oSelf.__fbSendHTTPMessage(oRequest, bMessageMustBeSentToRemote = False);
      if bSent:
        oSelf.fFireCallbacks("request sent", oRequest);
      return oSelf.fxExitFunctionOutput(bSent);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fSendResponse(oSelf, oResponse):
    oSelf.fEnterFunctionOutput(oResponse = oResponse.fsToString());
    try:
      # it's not ok if a connection is dropped by a client before a response is sent.
      assert oSelf.__fbSendHTTPMessage(oResponse, bMessageMustBeSentToRemote = True), \
          "This must not return False";
      oSelf.fFireCallbacks("response sent", oResponse);
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fbSendHTTPMessage(oSelf, oMessage, bMessageMustBeSentToRemote):
    oSelf.fEnterFunctionOutput(oMessage = oMessage.fsToString(), bMessageMustBeSentToRemote = bMessageMustBeSentToRemote);
    try:
      if not oSelf.bOpenForWriting:
        oSelf.fClose();
        oMessage.fSetMetaData("bStopHandlingHTTPMessages", True);
        if bMessageMustBeSentToRemote:
          raise cBufferedSocket.cConnectionClosedException("Connection closed before message could be sent.", None);
        return oSelf.fxExitFunctionOutput(False, "Connection closed before message could be sent.");
      # Determine if connection should be closed for writing after sending the message
      bCloseConnection = oMessage.fxGetMetaData("bCloseConnection");
      if bCloseConnection is None:
        bHasConnectionHeader = oMessage.oHTTPHeaders.fbHasValue("Connection");
        if bHasConnectionHeader:
          bCloseConnection = oMessage.oHTTPHeaders.fbHasValue("Connection", "Close");
        else:
          bCloseConnection = oMessage.sHTTPVersion.lower() == "HTTP/1.0";
        oMessage.fSetMetaData("bCloseConnection", bCloseConnection);
      # Serialize and send the cHTTPMessage instance
      sMessage = oMessage.fsSerialize();
      try:
        oSelf.fWrite(sMessage);
      except cBufferedSocket.cTransactionTimeoutException as oException:
        oSelf.fClose();
        oMessage.fSetMetaData("bStopHandlingHTTPMessages", True);
        raise;
      except cBufferedSocket.cConnectionClosedException as oException:
        oMessage.fSetMetaData("bStopHandlingHTTPMessages", True);
        raise;
      # Add this connection to the list of connections the message was send through in the metadata.
      aoSendToConnections = oMessage.fxGetMetaData("aoSendToConnections") or [];
      aoSendToConnections.append(oSelf);
      oMessage.fSetMetaData("aoSendToConnections", aoSendToConnections);
      # Close the connection for writing if needed.
      if bCloseConnection:
        oSelf.fCloseForWriting();
        oMessage.fSetMetaData("bStopHandlingHTTPMessages", True);
      oSelf.fStatusOutput("%s sent to %s." % (oMessage.fsToString(), oSelf.fsToString()), bVerbose = False);
      if gbDebugOutputFullHTTPMessages:
        oSelf.fStatusOutput(oMessage.fsSerialize(), bVerbose = False);
      oSelf.fFireCallbacks("message sent");
      return oSelf.fxExitFunctionOutput(True);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetResponseForRequest(oSelf, oRequest):
    oSelf.fEnterFunctionOutput(oRequest = oRequest.fsToString());
    try:
      if not oSelf.fbSendRequest(oRequest):
        return oSelf.fxExitFunctionOutput(None, "Request cannot be sent");
      oResponse = oSelf.foReceiveResponse();
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  # Read HTTP Messages
  def foReceiveRequest(oSelf,
      uMaxReasonPhraseSize = None,
      uMaxHeaderNameSize = None, uMaxHeaderValueSize = None, uMaxNumberOfHeaders = None,
      uMaxBodySize = None, uMaxChunkSize = None, uMaxNumberOfChunks = None,
  ):
    oSelf.fEnterFunctionOutput(
      uMaxReasonPhraseSize = uMaxReasonPhraseSize,
      uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders,
      uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks,
    );
    try:
      oRequest = oSelf.__foReceiveHTTPMessage(
        # it's ok if a connection is dropped by a client before a request is received, so the above can return None.
        cHTTPRequest, bMessageMustBeReceived = False,
        uMaxReasonPhraseSize = uMaxReasonPhraseSize,
        uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders,
        uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks,
      );
      if oRequest:
        oSelf.fFireCallbacks("request received", oRequest);
      return oSelf.fxExitFunctionOutput(oRequest);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foReceiveResponse(oSelf,
    uMaxReasonPhraseSize = None,
    uMaxHeaderNameSize = None, uMaxHeaderValueSize = None, uMaxNumberOfHeaders = None,
    uMaxBodySize = None, uMaxChunkSize = None, uMaxNumberOfChunks = None,
  ):
    oSelf.fEnterFunctionOutput(
      uMaxReasonPhraseSize = uMaxReasonPhraseSize,
      uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders,
      uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks,
    );
    try:
      try:
        oResponse = oSelf.__foReceiveHTTPMessage(
          # it's not ok if a connection is dropped by a server before a response is received, so the above cannot return None.
          cHTTPResponse, bMessageMustBeReceived = True,
          uMaxReasonPhraseSize = uMaxReasonPhraseSize,
          uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders,
          uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks,
        );
      except cBufferedSocket.cConnectionClosedException as oException:
        oException.sMessage = "Connection closed while receiving reponse.";
        raise;
      oSelf.fFireCallbacks("response received", oResponse);
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __foReceiveHTTPMessage(oSelf,
    cHTTPMessage, bMessageMustBeReceived,
    uMaxReasonPhraseSize,
    uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders,
    uMaxBodySize, uMaxChunkSize, uMaxNumberOfChunks,
  ):
    oSelf.fEnterFunctionOutput(
      cHTTPMessage = cHTTPMessage, bMessageMustBeReceived = bMessageMustBeReceived,
      uMaxReasonPhraseSize = uMaxReasonPhraseSize,
      uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders,
      uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks,
    );
    uMaxStatusLineSize = len("HTTP/1.x ### ") + (uMaxReasonPhraseSize if uMaxReasonPhraseSize is not None else guDefaultMaxReasonPhraseSize);
    uMaxHeaderNameSize = uMaxHeaderNameSize if uMaxHeaderNameSize is not None else guDefaultMaxHeaderNameSize;
    uMaxHeaderValueSize = uMaxHeaderValueSize if uMaxHeaderValueSize is not None else guDefaultMaxHeaderValueSize;
    uMaxNumberOfHeaders = uMaxNumberOfHeaders if uMaxNumberOfHeaders is not None else guDefaultMaxNumberOfHeaders;
    uMaxBodySize = uMaxBodySize if uMaxBodySize is not None else guDefaultMaxBodySize;
    uMaxChunkSize = uMaxChunkSize if uMaxChunkSize is not None else guDefaultMaxChunkSize;
    uMaxNumberOfChunks = uMaxNumberOfChunks if uMaxNumberOfChunks is not None else guDefaultMaxNumberOfChunks;
    try:
      oSelf.fStatusOutput("Reading status line...");
      try:
        sStatusLine = oSelf.fsReadUntil("\r\n", uMaxStatusLineSize + 2);
      except cBufferedSocket.cTooMuchDataException as oException:
        raise iHTTPMessage.cInvalidHTTPMessageException(
          "The status line was too large (>%d bytes)." % len(uMaxStatusLineSize),
          None,
        );
      except cBufferedSocket.cTransactionTimeoutException as oException:
        sBufferedData = oSelf.fsReadBufferedData()
        # It's never ok to close the connection in the middle of a HTTP message or when one is expected
        if sBufferedData or bMessageMustBeReceived:
          oException.sMessage += " (attempt to read status line)";
          raise oException;
        return oSelf.fxExitFunctionOutput(None, "Transaction timeout");
      except cBufferedSocket.cConnectionClosedException:
        sBufferedData = oSelf.fsReadBufferedData()
        if sBufferedData:
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "Connection closed while reading status line.",
            "received status line = %s" % repr(sBufferedData),
          );
        if bMessageMustBeReceived:
          raise cBufferedSocket.cConnectionClosedException(
            "Connection closed while reading status line",
            "received status line = %s" % repr(sBufferedData),
          );
        return oSelf.fxExitFunctionOutput(None, "Connection closed by remote");
      try:
        dxHTTPMessageStatusLineArguments = cHTTPMessage.fdxParseStatusLine(sStatusLine[:-2]);
      except iHTTPMessage.cInvalidHTTPMessageException:
        oSelf.fClose();
        raise;
      oSelf.fStatusOutput("Reading headers...");
      oHTTPHeaders = oSelf.__foReadHeaders(uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders);
      # Find out what headers are present
      sContentLengthHeaderValue = oHTTPHeaders.fsGet("Content-Length");
      bTransferEncodingChunkedHeaderPresent = oHTTPHeaders.fbHasValue("Transfer-Encoding", "Chunked");
      bConnectionCloseHeaderPresent = oHTTPHeaders.fbHasValue("Connection", "Close");
      sBody = None;
      asBodyChunks = None;
      
      # Parse Content-Length header value if any
      if sContentLengthHeaderValue is not None:
        try:
          uContentLengthHeaderValue = long(sContentLengthHeaderValue);
          if uContentLengthHeaderValue < 0:
            raise ValueError();
        except ValueError:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "The Content-Length header value was invalid.",
            "%s: %s" % (oHTTPHeaders.fsGetNameCasing("Content-Length"), sContentLengthHeaderValue),
          );
        if uContentLengthHeaderValue > uMaxBodySize:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "The Content-Length header value was too large (>%d bytes)." % uMaxBodySize,
            "%s: %s" % (oHTTPHeaders.fsGetNameCasing("Content-Length"), sContentLengthHeaderValue),
          );
      else:
        uContentLengthHeaderValue = None;
      # Read body
      if bTransferEncodingChunkedHeaderPresent:
        # Having both Content-Length and Transfer-Encoding: chunked headers is really weird but AFAICT not illegal.
        asBodyChunks = oSelf.__fasReadBodyChunks(uMaxBodySize, uMaxChunkSize, uMaxNumberOfChunks, uContentLengthHeaderValue);
        # More "headers" may follow.
        oAdditionalHTTPHeaders = oSelf.__foReadHeaders(uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders);
        for sIllegalName in ["Transfer-Encoding", "Content-Length"]:
          sIllegalValue = oAdditionalHTTPHeaders.fsGet(sIllegalName);
          if sIllegalValue is not None:
            raise cBufferedSocket.cInvalidHTTPMessageException(
              "The message was not valid because it contained a %s header after the chunked body." % sIllegalName,
              "%s: %s" % (repr(oAdditionalHTTPHeaders.fsGetNameCasing(sIllegalName)), repr(sIllegalValue)),
            );
        oHTTPHeaders.fUpdate(oAdditionalHTTPHeaders, bAppend = True);
      elif uContentLengthHeaderValue is not None:
        oSelf.fStatusOutput("Reading %d bytes response body..." % uContentLengthHeaderValue);
        try:
          sBody = oSelf.fsReadBytes(uContentLengthHeaderValue);
        except cBufferedSocket.cTransactionTimeoutException as oException:
          sReceivedBody = oSelf.fsReadBufferedData();
          raise cBufferedSocket.cTransactionTimeoutException(
            "The body was not received because the transaction timed out after receiving %d/%d bytes." % (len(sReceivedBody), uContentLengthHeaderValue),
            "received body = %d bytes (%s)" % (len(sReceivedBody), repr(sReceivedBody)),
          );
        except cBufferedSocket.cConnectionClosedException as oException:
          sReceivedBody = oSelf.fsReadBufferedData();
          raise cBufferedSocket.cInvalidHTTPMessageException(
            "The body was not received because the connection was closed by remote after sending %d/%d bytes." % (len(sReceivedBody), uContentLengthHeaderValue),
            "received body = %d bytes (%s)" % (len(sReceivedBody), repr(sReceivedBody)),
          );
      elif bConnectionCloseHeaderPresent:
        oSelf.fStatusOutput("Reading response body until connection is closed...");
        try:
          sBody = oSelf.fsRead(uMaxNumberOfBytes = uMaxBodySize);
        except cBufferedSocket.cTooMuchDataException as oException:
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "The body was too large (>%d bytes)." % len(uMaxBodySize),
            None,
          );
        except cBufferedSocket.cTransactionTimeoutException as oException:
          sReceivedBody = oSelf.fsReadBufferedData();
          raise cBufferedSocket.cTransactionTimeoutException(
            "The body was not received because the transaction timed out after receiving %d bytes." % len(sReceivedBody),
            "received body = %d bytes (%s)" % (len(sReceivedBody), repr(sReceivedBody)),
          );
      if oSelf.bHasData:
        # This socket received out-of-band data from the server and can no longer be used; close it.
        oSelf.fClose();
        raise iHTTPMessage.cInvalidHTTPMessageException(
          "Out-of-band data was received.",
          oSelf.fsReadBufferedData(),
        );
      if bConnectionCloseHeaderPresent:
        oSelf.fCloseForReading();
      oMessage = cHTTPMessage(
        # (note: status line arguments are provided at the end)
        oHTTPHeaders = oHTTPHeaders,
        sBody = sBody,
        asBodyChunks = asBodyChunks,
        dxMetaData = {
          "oReceivedFromConnection": oSelf,
          "bCloseConnection": bConnectionCloseHeaderPresent,
        },
        **dxHTTPMessageStatusLineArguments
      );
      oMessage.fSetMetaData("oReadFromConnection", oSelf);
      oSelf.fStatusOutput("%s received from %s." % (oMessage.fsToString(), oSelf.fsToString()), bVerbose = False);
      if gbDebugOutputFullHTTPMessages:
        oSelf.fStatusOutput(oMessage.fsSerialize(), bVerbose = False);
      oSelf.fFireCallbacks("message received", oMessage);
      return oSelf.fxExitFunctionOutput(oMessage);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def __foReadHeaders(oSelf, uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders):
    oSelf.fEnterFunctionOutput(uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders);
    # Given the max size of a name and value and allowing for ": " between them, we can calculate the max size of a header line.
    uMaxHeaderLineSize = uMaxHeaderNameSize + 2 + uMaxHeaderValueSize;
    try:
      oHTTPHeaders = cHTTPHeaders();
      sLastHeaderName = None;
      uMaxHeaderLineSize = uMaxHeaderNameSize  + uMaxHeaderValueSize;
      while 1:
        oSelf.fStatusOutput("Reading header line...");
        try:
          sLine = oSelf.fsReadUntil("\r\n", uMaxNumberOfBytes = uMaxHeaderLineSize + 2);
        except cBufferedSocket.cTooMuchDataException as oException:
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A header line was too large (>%d bytes)." % len(uMaxHeaderLineSize),
            None,
          );
        except cBufferedSocket.cTransactionTimeoutException as oException:
          oException.sMessage += " (attempt to read header line)";
          raise oException;
        except cBufferedSocket.cConnectionClosedException as oException:
          sBufferedData = oSelf.fsReadBufferedData()
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "Connection closed by remote while reading header line.",
            "status line read = %s" % repr(sBufferedData),
          );
        sLine = sLine[:-2];
        if sLine == "":
          oSelf.fStatusOutput("Encountered end of headers.");
          break; # Empty line == end of headers;
        if sLine[0] in " \t": # header continuation
          if sLastHeaderName is None:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A header line continuation was sent on the first header line, which is not valid.",
              sLine,
            );
          sHeaderName = sLastHeaderName;
          sHeaderValue = sLine; # leading (and trailing) spaces will be stripped later.
        else: # header
          asHeaderNameAndValue = sLine.split(":", 1);
          if len(asHeaderNameAndValue) != 2:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A header line was invalid.",
              sLine,
            );
          sHeaderName, sHeaderValue = asHeaderNameAndValue;
          sLastHeaderName = sHeaderName;
        # oHTTPHeaders takes care of headers with the same name but different casing and strips leading/trailing spaces
        # from names and values automatically.
        oHTTPHeaders.fbSet(sHeaderName, sHeaderValue, bAppend = True); # multiple values with the same name are concatinated
      return oSelf.fxExitFunctionOutput(oHTTPHeaders);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fasReadBodyChunks(oSelf, uMaxBodySize, uMaxChunkSize, uMaxNumberOfChunks, uContentLengthHeaderValue):
    oSelf.fEnterFunctionOutput(uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks, uContentLengthHeaderValue = uContentLengthHeaderValue);
    try:
      if uContentLengthHeaderValue is not None:
        oSelf.fStatusOutput("Reading chunked response body WITH Content-Length = %d..." % uContentLengthHeaderValue);
      else:
        oSelf.fStatusOutput("Reading chunked response body...");
      asBodyChunks = [];
      uContentLengthRemaining = uContentLengthHeaderValue;
      # The chunk size can be zero padded More than this many chars in the 
      uTotalChunksSize = 0;
      while 1:
        oSelf.fStatusOutput("Reading response body chunk header line...");
        # Read size in the chunk header
        uMaxChunkHeaderLineSize = guMaxChunkSizeCharacters + 2;
        if uContentLengthRemaining is not None:
          if uContentLengthRemaining < 5: # minimum is "0\r\n\r\n"
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "The body chunks were larger than the Content-Length (>%d bytes)." % uContentLengthHeaderValue,
              sData,
            );
          if uContentLengthRemaining < uMaxChunkHeaderLineSize:
            uMaxChunkHeaderLineSize = uContentLengthRemaining;
        try:
          sChunkHeader = oSelf.fsReadUntil("\r\n", uMaxChunkHeaderLineSize);
        except cBufferedSocket.cTooMuchDataException as oException:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk header line was too large (>%d bytes)." % guMaxChunkSizeCharacters if uContentLengthHeaderValue is None
                else "The body chunks were larger than the Content-Length (>%d bytes)." % uContentLengthHeaderValue,
            str(oException),
          );
        except cBufferedSocket.cTransactionTimeoutException as oException:
          oSelf.fClose();
          oException.sMessage += " (attempt to read body chunk header line)";
          raise oException;
        except cBufferedSocket.cConnectionClosedException as oException:
          sBufferedData = oSelf.fsReadBufferedData();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "Connection closed while reading body chunk header.",
            "chunk header read = %s" % repr(sBufferedData),
          );
        
        if uContentLengthRemaining is not None:
          uContentLengthRemaining -= len(sChunkHeader);
        if ";" in sChunkHeader:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk header line contained an extension, which is not supported.",
            sChunkHeader,
          );
        sChunkSize = sChunkHeader.strip();
        if not re.match("^[0-9A-F]+$", sChunkSize):
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk header line contained an invalid character in the chunk size.",
            sChunkHeader,
          );
        uChunkSize = long(sChunkSize, 16);
        if uChunkSize == 0:
          break;
        if uContentLengthRemaining is not None and uChunkSize + 7 > uContentLengthRemaining: # minimum after this chunk is "\r\n0\r\n\r\n"
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "The body chunks were larger than the Content-Length (>%d bytes)." % uContentLengthHeaderValue,
            str(oException),
          );
        if uMaxChunkSize is not None and uChunkSize > uMaxChunkSize:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk was too large (>%d bytes)." % uMaxChunkSize,
            uChunkSize,
          );
        # Check chunk size and number of chunks
        if uTotalChunksSize + uChunkSize > uMaxBodySize:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "The body was too large (>%d bytes)." % uMaxBodySize,
          );
        if uMaxNumberOfChunks is not None and len(asBodyChunks) == uMaxNumberOfChunks:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "Too many (>%d) body chunks were received." % uMaxNumberOfChunks,
          );
        # Read the chunk
        oSelf.fStatusOutput("Reading response body chunk (%d bytes)..." % uChunkSize);
        try:
          sChunkAndCRLF = oSelf.fsReadBytes(uChunkSize + 2);
        except cBufferedSocket.cTransactionTimeoutException as oException:
          oException.sMessage += " (attempt to read body chunk)";
          raise oException;
        except cBufferedSocket.cConnectionClosedException as oException:
          sBufferedData = oSelf.fsReadBufferedData()
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "Connection closed while reading body chunk header.",
            "chunk header read = %s" % repr(sBufferedData),
          );
        if uContentLengthRemaining is not None:
          uContentLengthRemaining -= uChunkSize + 2;
        if sChunkAndCRLF[-2:] != "\r\n":
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk CRLF was not found where it was expected.",
            sChunkAndCRLF[-2:],
          );
        asBodyChunks.append(sChunkAndCRLF[:-2]);
      if uContentLengthRemaining: # neither None or 0
        raise iHTTPMessage.cInvalidHTTPMessageException(
          "The body chunks were smaller than the Content-Length.",
          # (body chunks size, content length)
          (uContentLengthHeaderValue - uContentLengthRemaining, uContentLengthHeaderValue),
        );
      
      return oSelf.fxExitFunctionOutput(asBodyChunks);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
    