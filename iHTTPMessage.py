import base64, gzip, StringIO, urllib, zlib;
try:
  from .cBrotli import cBrotli;
except:
  cBrotli = None;
from mDebugOutput import cWithDebugOutput;
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
      "Pragma": "No-Cache",
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
  
  def __init__(oSelf, sHTTPVersion = None, dHeader_sValue_by_sName = None, sBody = None, sData = None, asBodyChunks = None, dxMetaData = None):
    assert sBody is None or sData is None, \
          "Cannot provide both sBody and sData!";
    assert sBody is None or asBodyChunks is None, \
          "Cannot provide both sBody and asBodyChunks!";
    assert sData is None or asBodyChunks is None, \
          "Cannot provide both sData and asBodyChunks!";
    oSelf.__sHTTPVersion = sHTTPVersion if sHTTPVersion else "HTTP/1.1";
    dDefaultHeader_sValue_by_sName = oSelf.ddDefaultHeader_sValue_by_sName_by_sHTTPVersion.get(oSelf.__sHTTPVersion);
    assert dDefaultHeader_sValue_by_sName, \
        "Invalid HTTP version %s" % sHTTPVersion;
    oSelf.__dHeader_sValue_by_sName = {};
    for (sName, sValue) in (dHeader_sValue_by_sName if dHeader_sValue_by_sName is not None else dDefaultHeader_sValue_by_sName).items():
      oSelf.__dHeader_sValue_by_sName[sName] = sValue;
    oSelf.__sBody = None;
    oSelf.__asBodyChunks = None;
    oSelf.__dxMetaData = dxMetaData or {};
    if sBody:
      oSelf.fSetBody(sBody);
    elif sData:
      oSelf.fSetData(sData);
    if asBodyChunks:
      oSelf.fSetBodyChunks(asBodyChunks);
  
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
  
  def fasGetHeaderNames(oSelf):
    return oSelf.__dHeader_sValue_by_sName.keys();
  def fbHasHeaderValue(oSelf, sName, sValue = None):
    sLowerName = sName.lower();
    for sName in oSelf.__dHeader_sValue_by_sName.keys():
      if sLowerName == sName.lower():
        return True if sValue is None else sValue.lower() == oSelf.__dHeader_sValue_by_sName[sName].strip().lower();
    return False;
  def fsGetHeaderValue(oSelf, sName):
    sLowerName = sName.lower();
    for (sName, sValue) in oSelf.__dHeader_sValue_by_sName.items():
      if sLowerName == sName.lower():
        return sValue;
    return None;
  def fSetHeaderValue(oSelf, sName, sValue):
    oSelf.fRemoveHeader(sName);
    oSelf.__dHeader_sValue_by_sName[sName] = sValue;
  def fRemoveHeader(oSelf, sName):
    oSelf.fbRemoveHeader(sName);
  def fbRemoveHeader(oSelf, sName):
    sLowerName = sName.lower();
    for sName in oSelf.__dHeader_sValue_by_sName.keys():
      if sLowerName == sName.lower():
        del oSelf.__dHeader_sValue_by_sName[sName];
        return True;
    return False;
  
  @property
  def sMediaType(oSelf):
    sContextTypeHeaderValue = oSelf.fsGetHeaderValue("Content-Type");
    return sContextTypeHeaderValue and sContextTypeHeaderValue.split(";")[0].strip();
  @sMediaType.setter
  def sMediaType(oSelf, sValue):
    sContextTypeHeaderValue = oSelf.fsGetHeaderValue("Content-Type");
    sAdditionalContentTypeValues = sContextTypeHeaderValue.split(";")[1:].join(";") if sContextTypeHeaderValue else "";
    sContentType = sValue + ("; %s" % sAdditionalContentTypeValues if sAdditionalContentTypeValues else "");
    oSelf.fSetHeaderValue("Content-Type", sContentType);
  
  @property
  def sCharset(oSelf):
    sContextTypeHeaderValue = oSelf.fsGetHeaderValue("Content-Type");
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
    return oSelf.fbHasHeaderValue("transfer-encoding", "chunked");

  @property
  def bCloseConnection(oSelf):
    return oSelf.fbHasHeaderValue("connection", "close");
  
  @property
  def bCompressed(oSelf):
    for sCompressionType in oSelf.asCompressionTypes:
      if sCompressionType != "identity":
        return True;
    return False;
  
  @property
  def asCompressionTypes(oself):
    sContentEncoding = oSelf.fsGetHeaderValue("Content-Encoding");
    return [s.strip().lower() for s in sContentEncoding.split(",")] if sContentEncoding else [];
  
  @property
  def sData(oSelf):
    # Returns decoded and decompressed body based on the Content-Encoding header.
    sData = oSelf.__sBody if not oSelf.bChunked else "".join(oSelf.__asBodyChunks);
    if sData is None:
      return None;
    sContentEncoding = oSelf.fsGetHeaderValue("Content-Encoding");
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
    sContentEncoding = oSelf.fsGetHeaderValue("Content-Encoding");
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
    return "".join([
      "%X\r\n%s\r\n" % (len(sBodyChunk), sBodyChunk) 
      for sBodyChunk in oSelf.__asBodyChunks
    ]) + "0\r\n\r\n";
  
  def fSetBody(oSelf, sBody, bCloseConnectionInsteadOfUsingContentLength = False):
    oSelf.fRemoveHeader("Transfer-Encoding");
    if oSelf.__sHTTPVersion.upper() != "HTTP/1.1":
      bCloseConnectionInsteadOfUsingContentLength = True;
    if bCloseConnectionInsteadOfUsingContentLength:
      oSelf.fSetHeaderValue("Connection", "close");
      oSelf.fRemoveHeader("Content-Length");
    else:
      oSelf.fSetHeaderValue("Content-Length", str(len(sBody)));
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
    oSelf.fRemoveHeader("Content-Length");
    oSelf.fSetHeaderValue("Transfer-Encoding", "chunked");
    oSelf.__sBody = None;
    oSelf.__asBodyChunks = asBodyChunks[:];
    
  def fAddBodyChunk(oSelf, sBodyChunk):
    assert sBodyChunk, \
        "Cannot add an empty chunk!"
    assert oSelf.__sBody is None, \
        "Cannot add a chunk if content is set";
    if not oSelf.bChunked:
      oSelf.fRemoveHeader("Content-Length");
      oSelf.fSetHeaderValue("Transfer-Encoding", "chunked");
      oSelf.__asBodyChunks = [sBodyChunk];
    else:
      oSelf.__asBodyChunks.append(sBodyChunk);
  
  def fRemoveBody(oSelf):
    oSelf.fRemoveHeader("Content-Encoding");
    oSelf.fRemoveHeader("Content-Length");
    oSelf.fRemoveHeader("Transfer-Encoding", "chunked");
    oSelf.__sBody = None;
    oSelf.__asBodyChunks = None;
  
  # application/x-www-form-urlencoded
  @property
  def dForm_sValue_by_sName(oSelf):
    # convert the decoded and decompressed body to form name-value pairs.
    assert oSelf.sMediaType == "application/x-www-form-urlencoded", \
        "Cannot get form data for Content-Type %s" % oSelf.fsGetHeaderValue("Content-Type");
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
    sLowerName = sName.lower();
    dForm_sValue_by_sName = oSelf.dForm_sValue_by_sName;
    for sOtherName in dForm_sValue_by_sName.keys():
      if sLowerName == sOtherName.lower():
        del dForm_sValue_by_sName[sOtherName];
    dForm_sValue_by_sName[sName] = sValue;
    oSelf.sData = fsURLEncodedStringFromNameValuePairs(dForm_sValue_by_sName);
  
  # Authorization
  def ftsGetBasicAuthorization(oSelf):
    sAuthorization = oSelf.fsGetHeaderValue("Authorization");
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
    oSelf.fSetHeaderValue("Authorization", "%s:%s" % (sUserName, sPassword));
  
  def fsSerialize(oSelf):
    return "\r\n".join([
      oSelf.fsGetStatusLine(),
    ] + [
      "%s: %s" % (sName, sValue) for (sName, sValue) in oSelf.__dHeader_sValue_by_sName.items()
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
