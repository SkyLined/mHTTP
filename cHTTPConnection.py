import json;
from .cBufferedSocket import cBufferedSocket;
from .cProtocolException import cProtocolException;
from .cHTTPRequest import cHTTPRequest;
from .cHTTPResponse import cHTTPResponse;
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
        sConnectionHeaderValue = oMessage.fsGetHeaderValue("Connection");
        if sConnectionHeaderValue:
          bCloseConnection = sConnectionHeaderValue.strip().lower() == "close";
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
      dHeader_sValue_by_sLowerName = oSelf.__fdsReadHeaders(uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders);
      # Find out what headers are present
      uContentLengthHeaderValue = None;
      bTransferEncodingChunkedHeaderPresent = None;
      bConnectionCloseHeaderPresent = None;
      for (sLowerName, sValue) in dHeader_sValue_by_sLowerName.items():
        if sLowerName == "content-length":
          if bTransferEncodingChunkedHeaderPresent:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "Both a \"content-length\" and \"transfer-encoding: chunked\" header were received, which is invalid.",
            );
          try:
            uContentLengthHeaderValue = long(sValue);
            if uContentLengthHeaderValue < 0:
              raise ValueError();
          except ValueError:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "The content-length header value was invalid.",
              sValue,
            );
          if uContentLengthHeaderValue > uMaxBodySize:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "The content-length header value was too large (>%d bytes)." % uMaxBodySize,
              uContentLengthHeaderValue,
            );
        elif sLowerName == "transfer-encoding" and sValue.lower() == "chunked":
          bTransferEncodingChunkedHeaderPresent = True;
        elif sLowerName == "connection" and sValue.lower() == "close":
          bConnectionCloseHeaderPresent = True;
      
      sBody = None;
      asBodyChunks = None;
      
      if bTransferEncodingChunkedHeaderPresent:
        if uContentLengthHeaderValue is not None and uContentLengthHeaderValue < uMaxBodySize:
          oSelf.fStatusOutput("Reading chunked response body WITH Content-Length = %d..." % uContentLengthHeaderValue);
          uMaxBodySize = uContentLengthHeaderValue;
        else:
          oSelf.fStatusOutput("Reading chunked response body...");
        asBodyChunks = oSelf.__fasReadBodyChunks(uMaxBodySize, uMaxChunkSize, uMaxNumberOfChunks);
        # More "headers" may follow. I am not sure how to handle multiple
        # Note: we should really check the value here and handle duplicates;
        # we are simply overwriting the values, so we may have just read a
        # chunked-encoded body and now remove the header that
        for (sLowerName, sValue) in oSelf.__fdsReadHeaders(uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders):
          if sLowerName in ("transfer-encoding", "content-length"):
            raise cBufferedSocket.cInvalidHTTPMessageException(
              "The message was not valid because it contained a %s header after the chunked body." % sLowerName,
              "%s: %s" % (repr(sLower), repr(sValue)),
            );
          if sLowername in dHeader_sValue_by_sLowerName:
            dHeader_sValue_by_sLowerName[sLowerName] += " " + sValue;
          else:
            dHeader_sValue_by_sLowerName[sLowerName] = sValue;
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
        dHeader_sValue_by_sName = dHeader_sValue_by_sLowerName,
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

  def __fdsReadHeaders(oSelf, uMaxHeaderNameSize, uMaxHeaderValueSize, uMaxNumberOfHeaders):
    oSelf.fEnterFunctionOutput(uMaxHeaderNameSize = uMaxHeaderNameSize, uMaxHeaderValueSize = uMaxHeaderValueSize, uMaxNumberOfHeaders = uMaxNumberOfHeaders);
    # Given the max size of a name and value and allowing for ": " between them, we can calculate the max size of a header line.
    uMaxHeaderLineSize = uMaxHeaderNameSize + 2 + uMaxHeaderValueSize;
    try:
      dHeader_sValue_by_sLowerName = {};
      sLastHeaderLowerName = None;
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
          if sLastHeaderLowerName is None:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A header line continuation was sent on the first header line, which is not valid.",
              sLine,
            );
          dHeader_sValue_by_sLowerName[sLastHeaderLowerName] += sLine.rstrip();
        else: # header
          asHeaderNameAndValue = sLine.split(":", 1);
          if len(asHeaderNameAndValue) != 2:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A header line was invalid.",
              sLine,
            );
          sHeaderName, sHeaderValue = asHeaderNameAndValue;
          sHeaderLowerName = sHeaderName.lower();
          sHeaderValue = sHeaderValue.strip();
          if sHeaderLowerName == sLastHeaderLowerName: # multiple values with the same name are concatinated
            dHeader_sValue_by_sLowerName[sHeaderLowerName] += " " + sHeaderValue;
          else:
            dHeader_sValue_by_sLowerName[sHeaderLowerName] = sHeaderValue;
          sLastHeaderLowerName = sHeaderLowerName;
      return oSelf.fxExitFunctionOutput(dHeader_sValue_by_sLowerName);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fasReadBodyChunks(oSelf, uMaxBodySize, uMaxChunkSize, uMaxNumberOfChunks):
    oSelf.fEnterFunctionOutput(uMaxBodySize = uMaxBodySize, uMaxChunkSize = uMaxChunkSize, uMaxNumberOfChunks = uMaxNumberOfChunks);
    try:
      asBodyChunks = [];
      # The chunk size can be zero padded More than this many chars in the 
      uTotalChunksSize = 0;
      while 1:
        oSelf.fStatusOutput("Reading response body chunk header line...");
        # Read size in the chunk header
        try:
          sChunkHeader = oSelf.fsReadUntil("\r\n", guMaxChunkSizeCharacters + 2);
        except cBufferedSocket.cTooMuchDataException as oException:
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk header line was too large (>%d bytes)." % guMaxChunkSizeCharacters,
            str(oException),
          );
        except cBufferedSocket.cTransactionTimeoutException as oException:
          oException.sMessage += " (attempt to read body chunk header line)";
          raise oException;
        except cBufferedSocket.cConnectionClosedException as oException:
          sBufferedData = oSelf.fsReadBufferedData()
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "Connection closed by remote while reading body chunk header.",
            "chunk header read = %s" % repr(sBufferedData),
          );
          
        if sChunkHeader is None:
          sData = oSelf.fsReadBufferedData();
          if len(sData) >= guMaxChunkSizeCharacters:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A body chunk header line was too large (>%d bytes)." % guMaxChunkSizeCharacters,
              sData,
            );
          elif not oSelf.bOpenForReading:
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A body chunk header line was not received because the remote closed the connection.",
              sData,
            );
          else:
            oSelf.fClose();
            raise cBufferedSocket.cTransactionTimeoutException(
              "A body chunk header line was not received because the transaction timed out.",
              sData,
            );
        if ";" in sChunkHeader:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk header line contained an extension, which is not supported.",
            sChunkHeader,
          );
        sChunkSize = sChunkHeader[:-2];
        for sByte in sChunkSize:
          if sByte.lower() not in "0123456789abcdef":
            oSelf.fClose();
            raise iHTTPMessage.cInvalidHTTPMessageException(
              "A body chunk header line contained an invalid character in the chunk size.",
              sChunkHeader,
            );
        uChunkSize = long(sChunkSize, 16);
        if uMaxChunkSize is not None and uChunkSize > uMaxChunkSize:
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk was too large (>%d bytes)." % uMaxChunkSize,
            uChunkSize,
          );
        if uChunkSize == 0:
          break;
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
        if sChunkAndCRLF[-2:] != "\r\n":
          oSelf.fClose();
          raise iHTTPMessage.cInvalidHTTPMessageException(
            "A body chunk CRLF was not found where it was expected.",
            sChunkAndCRLF[-2:],
          );
        asBodyChunks.append(sChunkAndCRLF[:-2]);
      return oSelf.fxExitFunctionOutput(asBodyChunks);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
