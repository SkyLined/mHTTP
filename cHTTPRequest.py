from .cHTTPHeaders import cHTTPHeaders;
from .iHTTPMessage import iHTTPMessage;

class cHTTPRequest(iHTTPMessage):
  @staticmethod
  def fdxParseStatusLine(sStatusLine):
    asComponents = sStatusLine.split(" ", 2);
    if len(asComponents) != 3:
      raise iHTTPMessage.cInvalidHTTPMessageException("The remote send an invalid status line.", sStatusLine);
    sMethod, sURL, sHTTPVersion = asComponents;
    if sHTTPVersion not in ["HTTP/1.0", "HTTP/1.1"]:
      raise iHTTPMessage.cInvalidHTTPMessageException("The remote send an invalid HTTP version in the status line.", sHTTPVersion);
    return {"sMethod": sMethod, "sURL": sURL, "sHTTPVersion": sHTTPVersion};
  
  def __init__(oSelf, sURL, sMethod = None, sHTTPVersion = None, oHTTPHeaders = None, sBody = None, sData = None, asBodyChunks = None, dxMetaData = None):
    oSelf.__sURL = sURL;
    oSelf.__sMethod = sMethod or ("POST" if (sBody or sData or asBodyChunks) else "GET");
    if oHTTPHeaders is None:
      oHTTPHeaders = cHTTPHeaders({
        "Accept": "*/*",
        "Accept-Encoding": ", ".join(oSelf.asSupportedCompressionTypes),
        "Cache-Control": "No-Cache, Must-Revalidate",
        "Connection": "Keep-Alive",
        "Pragma": "No-Cache",
      });
    iHTTPMessage.__init__(oSelf, sHTTPVersion, oHTTPHeaders, sBody, sData, asBodyChunks, dxMetaData);
  
  @property
  def sURL(oSelf):
    return oSelf.__sURL;
  @sURL.setter
  def sURL(oSelf, sURL):
    oSelf.__sURL = sURL;
  @property
  def sMethod(oSelf):
    return oSelf.__sMethod;
  @sMethod.setter
  def sMethod(oSelf, sMethod):
    oSelf.__sMethod = sMethod;
  
  def foClone(oSelf):
    if oSelf.bChunked:
      return cHTTPRequest(oSelf.sURL, oSelf.sMethod, oSelf.sHTTPVersion, oSelf.oHTTPHeaders.foClone(), asBodyChunks = oSelf.asBodyChunks);
    return cHTTPRequest(oSelf.sURL, oSelf.sMethod, oSelf.sHTTPVersion, oSelf.oHTTPHeaders.foClone(), sBody = oSelf.sBody);

  def fsGetStatusLine(oSelf):
    return "%s %s %s" % (oSelf.sMethod, oSelf.sURL, oSelf.sHTTPVersion);
  
  def __str__(oSelf):
    return " ".join([s for s in [
      oSelf.sMethod,
      oSelf.sURL,
      oSelf._fsBodyStr(),
    ] if s]);
  
  def foCreateReponse(oSelf, uStatusCode, sMediaType = None, sBody = None, sHTTPVersion = None, sReasonPhrase = None, oHTTPHeaders = None, sData = None,
      asBodyChunks = None, dxMetaData = None):
    oSelf.fEnterFunctionOutput(uStatusCode = uStatusCode, sMediaType = sMediaType, sBody = sBody, sHTTPVersion = sHTTPVersion, sReasonPhrase = sReasonPhrase, 
        oHTTPHeaders = oHTTPHeaders, sData = sData, asBodyChunks = asBodyChunks, dxMetaData = dxMetaData);
    try:
      if sHTTPVersion is None:
        sHTTPVersion = oSelf.sHTTPVersion;
      from cHTTPResponse import cHTTPResponse;
      if sMediaType is None:
        if sBody is not None:
          sMediaType = "text/plain";
      else:
        cType = type(sMediaType);
        if cType == unicode:
          try:
            sMediaType = str(sMediaType);
          except:
            raise AssertionError("sMediaType cannot contain Unicode characters");
        else:
          assert cType == str, \
              "sMediaType must be a string, not %s" % repr(sMediaType);
      oHTTPHeaders = oHTTPHeaders or cHTTPHeaders(iHTTPMessage.ddDefaultHeader_sValue_by_sName_by_sHTTPVersion[sHTTPVersion]);
      if sMediaType:
        oHTTPHeaders.fbSet("Content-Type", sMediaType);
      oResponse = cHTTPResponse(
        sHTTPVersion = sHTTPVersion,
        uStatusCode = uStatusCode,
        sReasonPhrase = sReasonPhrase,
        oHTTPHeaders = oHTTPHeaders,
        sBody = sBody,
        sData = sData,
        asBodyChunks = asBodyChunks,
        dxMetaData = dxMetaData,
      );
      return oSelf.fxExitFunctionOutput(oResponse);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsToString(oSelf):
    return "%s{%s %s %s}" % (oSelf.__class__.__name__, oSelf.sMethod, oSelf.sURL, oSelf.sHTTPVersion);
  
