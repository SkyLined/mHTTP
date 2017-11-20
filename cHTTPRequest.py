import urllib;
from iHTTPMessage import iHTTPMessage;

class cHTTPRequest(iHTTPMessage):
  def __init__(oSelf, sMethod, sURL, sHTTPVersion, dHeader_sValue_by_sName, sBody):
    oSelf.sMethod = sMethod;
    oSelf.sHTTPVersion = sHTTPVersion;
    oSelf.sOriginalURL = sURL;
    if "?" not in sURL:
      sPath = sURL;
      oSelf.dQuery_sValue_by_sName = None;
    else:
      sPath, sQuery = sURL.split("?", 1);
      oSelf.dQuery_sValue_by_sName = oSelf.fdsNameValuePairsFromString(sQuery);
    oSelf.sPath = urllib.unquote(sPath);
    
    iHTTPMessage.__init__(oSelf, dHeader_sValue_by_sName, sBody);
  
  def fsGetQueryValue(oSelf, sName):
    if oSelf.dQuery_sValue_by_sName is None:
      return None;
    return oSelf.dQuery_sValue_by_sName.get(sName);
  
  def fSetQueryValue(oSelf, sName, sValue):
    if oSelf.dQuery_sValue_by_sName is None:
      oSelf.dQuery_sValue_by_sName = {sName: sValue};
    else:
      oSelf.dQuery_sValue_by_sName[sName] = sValue;
  
  @property
  def sURL(oSelf):
    sURL = urllib.quote(oSelf.sPath);
    if oSelf.dQuery_sValue_by_sName is not None:
      sURL += "?%s" % oSelf.fsStringFromNameValuePairs(oSelf.dQuery_sValue_by_sName);
    return sURL;
  
  def fsGetStatusLine(oSelf):
    return "%s %s %s" % (oSelf.sMethod, oSelf.sURL, oSelf.sHTTPVersion);
  
  def __str__(oSelf):
    return " ".join([s for s in [
      oSelf.sMethod,
      oSelf.sURL,
      oSelf.sBody and "(%d bytes data)" % len(oSelf.sBody) or None
    ] if s]);

  def foCreateReponse(oSelf, uStatusCode, sMediaType, sBody):
    from cHTTPResponse import cHTTPResponse;
    if sMediaType is None:
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
    dHeader_sValue_by_sName = {
      "Content-Length": len(sBody),
      "Content-Type": sMediaType,
      "Cache-Control": "no-cache, must-revalidate",
      "Expires": "Wed, 16 May 2012 04:01:53 GMT", # 1337
      "Pragma": "no-cache",
    };
    sConnection = oSelf.fsGetHeaderValue("Connection");
    if sConnection:
      dHeader_sValue_by_sName["Connection"] = sConnection;
    sReasonPhrase = None;
    return cHTTPResponse(oSelf.sHTTPVersion, uStatusCode, sReasonPhrase, dHeader_sValue_by_sName, sBody);
