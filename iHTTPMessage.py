import base64, gzip, StringIO, urllib, zlib;
try:
  from .cBrotli import cBrotli;
except:
  cBrotli = None;
from mDebugOutput import cWithDebugOutput;
from .cHTTPHeaders import cHTTPHeaders;
from .cProtocolException import cProtocolException;
from .fsURLEncodedStringFromNameValuePairs import fsURLEncodedStringFromNameValuePairs;
from .fdsURLDecodedNameValuePairsFromString import fdsURLDecodedNameValuePairsFromString;

guBrotliCompressionQuality = 5;
guGZipCompressionLevel = 5;
guZLibCompressionLevel = 5;
guDeflateCompressionLevel = 5;

def fsASCII(sData, sDataTypeDescription):
  try:
    return str(sData or "");
  except:
    raise AssertionError("%s cannot contain Unicode characters: %s" % (sDataTypeDescription, repr(sData)));

class iHTTPMessage(cWithDebugOutput):
  asSupportedCompressionTypes = ["deflate", "gzip", "x-gzip", "zlib"] + (["br"] if cBrotli else []);
  ddDefaultHeader_sValue_by_sName_by_sHTTPVersion = {
    "HTTP/1.0": {
      "Connection": "Close",
      "Cache-Control": "No-Cache, Must-Revalidate",
      "Expires": "Wed, 16 May 2012 04:01:53 GMT", # 1337
      "Oragma": "No-Cache",
    },
    "HTTP/1.1": {
      "Connection": "Keep-Alive",
      "Cache-Control": "No-Cache, Must-Revalidate",
      "Expires": "Wed, 16 May 2012 04:01:53 GMT", # 1337
      "Pragma": "No-Cache",
    },
  };
  
  class cInvalidHTTPMessageException(cProtocolException):
    pass;
  
  def __init__(oSelf, sHTTPVersion = None, oHTTPHeaders = None, sBody = None, sData = None, asBodyChunks = None, dxMetaData = None):
    assert sBody is None or sData is None, \
          "Cannot provide both sBody (%s) and sData (%s)!" % (repr(sBody), repr(sData));
    assert sBody is None or asBodyChunks is None, \
          "Cannot provide both sBody (%s) and asBodyChunks (%s)!" % (repr(sBody), repr(asBodyChunks));
    assert sData is None or asBodyChunks is None, \
          "Cannot provide both sData (%s) and asBodyChunks (%s)!" % (repr(sData), repr(asBodyChunks));
    oSelf.__sHTTPVersion = sHTTPVersion if sHTTPVersion else "HTTP/1.1";
    dDefaultHeader_sValue_by_sName = oSelf.ddDefaultHeader_sValue_by_sName_by_sHTTPVersion.get(oSelf.__sHTTPVersion);
    assert dDefaultHeader_sValue_by_sName, \
        "Invalid HTTP version %s" % sHTTPVersion;
    oSelf.oHTTPHeaders = oHTTPHeaders or cHTTPHeaders(dDefaultHeader_sValue_by_sName);
    oSelf.__sBody = None;
    oSelf.__asBodyChunks = None;
    oSelf.__dxMetaData = dxMetaData or {};
    if sBody is not None:
      oSelf.fSetBody(sBody);
    elif sData is not None:
      oSelf.fSetData(sData);
    if asBodyChunks is not None:
      oSelf.fSetBodyChunks(asBodyChunks);
    if oSelf.bChunked:
      assert oSelf.__asBodyChunks is not None, \
          "Missing asBodyChunks!?";
    else:
      assert oSelf.__asBodyChunks is  None, \
          "Unexpected asBodyChunks";
  
  def fbHasMetaData(oSelf, sName):
    return sName in oSelf.__dxMetaData;
  def fxGetMetaData(oSelf, sName):
    return oSelf.__dxMetaData.get(sName);
  def fSetMetaData(oSelf, sName, xValue):
    oSelf.__dxMetaData[sName] = xValue;
  
  @property
  def sHTTPVersion(oSelf):
    return oSelf.__sHTTPVersion;
  @sHTTPVersion.setter
  def sHTTPVersion(oSelf, sHTTPVersion):
    oSelf.__sHTTPVersion = sHTTPVersion;
  
  @property
  def sMediaType(oSelf):
    sContextTypeHeaderValue = oSelf.oHTTPHeaders.fsGet("Content-Type");
    return sContextTypeHeaderValue and sContextTypeHeaderValue.split(";")[0].strip();
  @sMediaType.setter
  def sMediaType(oSelf, sValue):
    sContextTypeHeaderValue = oSelf.oHTTPHeaders.fsGet("Content-Type");
    sAdditionalContentTypeValues = sContextTypeHeaderValue.split(";")[1:].join(";") if sContextTypeHeaderValue else "";
    sContentType = sValue + ("; %s" % sAdditionalContentTypeValues if sAdditionalContentTypeValues else "");
    oSelf.oHTTPHeaders.fbSet("Content-Type", sContentType);
  
  @property
  def sCharset(oSelf):
    sContextTypeHeaderValue = oSelf.oHTTPHeaders.fsGet("Content-Type");
    sCharSet = None;
    if sContextTypeHeaderValue:
      for sNameValuePair in sContextTypeHeaderValue.split(";")[1:]:
        tsNameValuePair = sNameValuePair.split("=", 1);
        if len(tsNameValuePair) == 2:
          sName, sValue = tsNameValuePair;
          if sName.strip().lower() == "charset":
            sCharSet = sValue;
            # don't break: when multiple values are provided the last one counts.
    return sCharSet;
  
  @property
  def bChunked(oSelf):
    return oSelf.oHTTPHeaders.fbHasValue("transfer-encoding", "chunked");

  @property
  def bCloseConnection(oSelf):
    return oSelf.oHTTPHeaders.fbHasValue("connection", "close");
  
  @property
  def bCompressed(oSelf):
    for sCompressionType in oSelf.asCompressionTypes:
      if sCompressionType != "identity":
        return True;
    return False;
  
  @property
  def asCompressionTypes(oself):
    sContentEncoding = oSelf.oHTTPHeaders.fsGet("Content-Encoding");
    return [s.strip().lower() for s in sContentEncoding.split(",")] if sContentEncoding else [];
  
  @property
  def sData(oSelf):
    # Returns decoded and decompressed body based on the Content-Encoding header.
    sData = oSelf.__sBody if not oSelf.bChunked else "".join(oSelf.__asBodyChunks);
    if sData is None:
      return None;
    sContentEncoding = oSelf.oHTTPHeaders.fsGet("Content-Encoding");
    if sContentEncoding:
      for sEncodingType in reversed([s.strip().lower() for s in sContentEncoding.split(",")]):
        if cBrotli and sEncodingType == "br":
          oBrotli = cBrotli();
          sData = oBrotli.decompress(sData) + oBrotli.flush();
        elif sEncodingType == "deflate":
          sData = zlib.decompress(sData, -zlib.MAX_WBITS);
        elif sEncodingType in ["gzip", "x-gzip"]:
          sData = zlib.decompress(sData, zlib.MAX_WBITS | 0x10);
        elif sEncodingType == "identity":
          pass; # No compression.
        elif sEncodingType == "zlib":
          sData = zlib.decompress(sData, zlib.MAX_WBITS);
        else:
          raise NotImplementedError("Content encoding %s is not supported" % sEncodingType);
    sCharset = oSelf.sCharset;
    if sCharset:
      # Convert bytes to unicode using charset defined in Content-Type header.
      sData = unicode(sData, sCharset, "replace");
    return sData;

  def fSetData(oSelf, sData, bCloseConnectionInsteadOfUsingContentLength = False):
    sCharset = oSelf.sCharset;
    if sCharset:
      # Convert unicode to bytes using charset defined in Content-Type header.
      sData = str(sData, sCharset);
    # Sets the (optionally) compressed body of the message.
    sContentEncoding = oSelf.oHTTPHeaders.fsGet("Content-Encoding");
    if sContentEncoding:
      for sEncodingType in [s.strip().lower() for s in sContentEncoding.split(",")]:
        if cBrotli and sEncodingType == "br":
          sData = cBrotli().compress(sData, guBrotliCompressionQuality);
        elif sEncodingType == "deflate":
          oCompressionObject = zlib.compressobj(guDeflateCompressionLevel, zlib.DEFLATED, -zlib.MAX_WBITS);
          sData = oCompressionObject.compress(sData) + oCompressionObject.flush();
        elif sEncodingType in ["gzip", "x-gzip"]:
          oCompressionObject = zlib.compressobj(guGZipCompressionLevel, zlib.DEFLATED, zlib.MAX_WBITS | 0x10);
          sData = oCompressionObject.compress(sData) + oCompressionObject.flush();
        elif sEncodingType == "identity":
          pass; # No compression.
        elif sEncodingType == "zlib":
          oCompressionObject = zlib.compressobj(guZLibCompressionLevel, zlib.DEFLATED, zlib.MAX_WBITS);
          sData = oCompressionObject.compress(sData) + oCompressionObject.flush();
        else:
          raise NotImplementedError("Content encoding %s is not supported" % sEncodingType);
    oSelf.fSetBody(sData, bCloseConnectionInsteadOfUsingContentLength);

  @property
  def sBody(oSelf):
    if not oSelf.bChunked:
      return oSelf.__sBody;
    assert not oSelf.bChunked or oSelf.__asBodyChunks is not None, \
        "wtf!?";
    return "".join([
      "%X\r\n%s\r\n" % (len(sBodyChunk), sBodyChunk) 
      for sBodyChunk in oSelf.__asBodyChunks
    ]) + "0\r\n\r\n";
  
  def fSetBody(oSelf, sBody, bCloseConnectionInsteadOfUsingContentLength = False):
    oSelf.oHTTPHeaders.fbDelete("Transfer-Encoding");
    if oSelf.__sHTTPVersion.upper() != "HTTP/1.1":
      bCloseConnectionInsteadOfUsingContentLength = True;
    if bCloseConnectionInsteadOfUsingContentLength:
      oSelf.oHTTPHeaders.fbSet("Connection", "Close");
      oSelf.oHTTPHeaders.fbDelete("Content-Length");
    else:
      oSelf.oHTTPHeaders.fbSet("Content-Length", str(len(sBody)));
    oSelf.__sBody = fsASCII(sBody, "Body");
    oSelf.__asBodyChunks = None;

  @property
  def asBodyChunks(oSelf):
    assert oSelf.bChunked, \
        "Cannot get body chunks when chunked encoding is not enabled";
    return oSelf.__asBodyChunks[:];
  def fSetBodyChunks(oSelf, asBodyChunks):
    for sBodyChunk in asBodyChunks:
      assert sBodyChunk, \
          "Cannot add empty body chunks";
    oSelf.oHTTPHeaders.fbDelete("Content-Length");
    oSelf.oHTTPHeaders.fbSet("Transfer-Encoding", "Chunked");
    oSelf.__sBody = None;
    oSelf.__asBodyChunks = asBodyChunks[:];
    
  def fAddBodyChunk(oSelf, sBodyChunk):
    assert sBodyChunk, \
        "Cannot add an empty chunk!"
    assert oSelf.__sBody is None, \
        "Cannot add a chunk if content is set";
    if not oSelf.bChunked:
      oSelf.oHTTPHeaders.fbDelete("Content-Length");
      oSelf.oHTTPHeaders.fbSet("Transfer-Encoding", "Chunked");
      oSelf.__asBodyChunks = [sBodyChunk];
    else:
      oSelf.__asBodyChunks.append(sBodyChunk);
  
  def fRemoveBody(oSelf):
    oSelf.oHTTPHeaders.fbDelete("Content-Encoding");
    oSelf.oHTTPHeaders.fbDelete("Content-Length");
    oSelf.oHTTPHeaders.fbDelete("Transfer-Encoding", "Chunked");
    oSelf.__sBody = None;
    oSelf.__asBodyChunks = None;
  
  # application/x-www-form-urlencoded
  @property
  def dForm_sValue_by_sName(oSelf):
    # convert the decoded and decompressed body to form name-value pairs.
    assert oSelf.sMediaType.lower() == "application/x-www-form-urlencoded", \
        "Cannot get form data for Content-Type %s" % oSelf.oHTTPHeaders.fsGet("Content-Type");
    return fdsURLDecodedNameValuePairsFromString(oSelf.sData);
  
  def fsGetFormValue(oSelf, sName):
    # convert the decoded and decompressed body to form name-value pairs and return the value for the given name
    # or None if there is no such value.
    sLowerCaseName = sName.lower();
    for (sName, sValue) in oSelf.dForm_sValue_by_sName.items():
      if sLowerCaseName == sName.lower():
        return sValue;
  
  def fSetFormValue(oSelf, sName, sValue):
    # convert the decoded and decompressed body to form name-value pairs, set the given name to the given value 
    # and update the optionally compressed body to match.
    sLowerStrippedName = sName.strip().lower();
    dForm_sValue_by_sName = oSelf.dForm_sValue_by_sName;
    for sOtherName in dForm_sValue_by_sName.keys():
      if sLowerStrippedName == sOtherName.lower():
        del dForm_sValue_by_sName[sOtherName];
    dForm_sValue_by_sName[sName] = sValue;
    oSelf.sData = fsURLEncodedStringFromNameValuePairs(dForm_sValue_by_sName);
  
  # Authorization
  def ftsGetBasicAuthorization(oSelf):
    sAuthorization = oSelf.oHTTPHeaders.fsGet("Authorization");
    if sAuthorization is None:
      return (None, None);
    sBasic, sBase64EncodedUserNameColonPassword = sAuthorization.strip().split(" ", 1);
    if sBasic.lower() != "basic ":
      return (None, None);
    try:
      sUserNameColonPassword = base64.b64decode(sBase64EncodedUserNameColonPassword.lstrip());
    except Exception as oException:
      return (None, None);
    if ":" in sUserNameColonPassword:
      sUserName, sPassword = sUserNameColonPassword.split(":", 1);
    else:
      sUserName = sUserNameColonPassword;
      sPassword = None;
    return (sUserName, sPassword);

  def fSetBasicAuthorization(oSelf, sUserName, sPassword):
    oSelf.oHTTPHeaders.fbSet("Authorization", "%s:%s" % (sUserName, sPassword));
  
  def fsSerialize(oSelf):
    return "\r\n".join([
      oSelf.fsGetStatusLine(),
    ] + [
      "%s: %s" % (sName, sValue) for (sName, sValue) in oSelf.oHTTPHeaders.fatsGetNamesAndValues()
    ] + [
      "",
      oSelf.sBody or "",
    ]);
  
  def _fsBodyStr(oSelf):
    sBody = oSelf.sBody;
    if sBody is None:
      return "no body";
    asBodyStr = [];
    if oSelf.bCompressed:
      asBodyStr.append("%d bytes data %s compressed into" % (len(oSelf.sData), ">".join(oSelf.asCompressionTypes)));
    if oSelf.bChunked:
      asBodyStr.append("%d bytes" % sum([len(s) for s in oSelf.__asBodyChunks]));
      if not oSelf.bCompressed:
        asBodyStr.append("data");
      asBodyStr.append("in %d chunks in" % len(oSelf.__asBodyChunks));
    if asBodyStr:
      asBodyStr.append("a");
    asBodyStr.append("%d bytes" % len(sBody));
    sMediaType = oSelf.sMediaType;
    if sMediaType:
      asBodyStr.append(sMediaType);
    asBodyStr.append("body");
    # "10 bytes data [br] compressed into 8 bytes in 3 chunks in a 26 bytes [text/plain] body"
    return " ".join(asBodyStr);
