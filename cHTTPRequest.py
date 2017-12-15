import urllib;
from iHTTPMessage import iHTTPMessage;

class cHTTPRequest(iHTTPMessage):
  def __init__(oSelf, sMethod, sURL, sHTTPVersion = None, dHeader_sValue_by_sName = None, sContent = None, asContentChunks = None):
    oSelf.sMethod = sMethod;
    oSelf.sHTTPVersion = sHTTPVersion or "HTTP/1.0";
    oSelf.sOriginalURL = sURL;
    oSelf.__sURLProtocol = None;
    oSelf.__sURLHost = None;
    oSelf.__uURLPort = None;
    #oSelf.__asURLPath = None; # always set later
    oSelf.__dURLQuery_sValue_by_sName = None;
    asProtocol_sHostPortPathQuery = sURL.split("//", 1);
    if len(asProtocol_sHostPortPathQuery) == 2:
      oSelf.__sURLProtocol, sHostPortPathQuery = asProtocol_sHostPortPathQuery;
      asHostPort_sPathQuery = sHostPortPathQuery.split("/", 1);
      if len(asHostPort_sPathQuery) == 2:
        sHostPort, sPathQuery = asHostPort_sPathQuery;
      else:
        asHostPort_sQuery = sHostPortPathQuery.split("?", 1);
        if len(asHostPort_sQuery) == 2:
          sHostPort, sQuery = asHostPort_sQuery;
          sPathQuery = "?" + sQuery;
        else:
          sHostPort = sHostPortPathQuery;
          sPathQuery = "";
      asHost_sPost = sHostPort.split(":", 1);
      if len(asHost_sPost) == 2:
        oSelf.__sURLHost, sURLPort = asHost_sPost;
        oSelf.__uURLPort = long(sURLPort);
      else:
        oSelf.__sURLHost = sHostPort;
    else:
      sPathQuery = sURL;
    asPath_sQuery = sPathQuery.split("?", 1);
    if len(asPath_sQuery) == 2:
      sURLPath, sQuery = asPath_sQuery;
      oSelf.__dURLQuery_sValue_by_sName = oSelf.fdsNameValuePairsFromString(sQuery);
    else:
      sURLPath = asPath_sQuery[0];
    if sURLPath[0] == "/":
      sURLPath = sURLPath[1:];
    oSelf.__asURLPath = [urllib.unquote(s) for s in sURLPath.split("/")];
    if dHeader_sValue_by_sName is None:
      dHeader_sValue_by_sName = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "no-cache, must-revalidate",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
      };
    iHTTPMessage.__init__(oSelf, dHeader_sValue_by_sName, sContent, asContentChunks);
  
  def foClone(oSelf):
    if oSelf.bChunked:
      return cHTTPRequest(oSelf.sMethod, oSelf.sURL, oSelf.sHTTPVersion, oSelf.dHeader_sValue_by_sName, asContentChunks = oSelf.asContentChunks);
    return cHTTPRequest(oSelf.sMethod, oSelf.sURL, oSelf.sHTTPVersion, oSelf.dHeader_sValue_by_sName, sContent = oSelf.sContent);

  def fsGetQueryValue(oSelf, sName):
    if oSelf.__dURLQuery_sValue_by_sName is None:
      return None;
    return oSelf.__dURLQuery_sValue_by_sName.get(sName);
  
  def fSetQueryValue(oSelf, sName, sValue):
    if oSelf.__dURLQuery_sValue_by_sName is None:
      oSelf.__dURLQuery_sValue_by_sName = {sName: sValue};
    else:
      oSelf.__dURLQuery_sValue_by_sName[sName] = sValue;
  
  @property
  def sPath(oSelf):
    return "/" + "/".join([urllib.quote(s) for s in oSelf.__asURLPath]);
  @property
  def sRelativeURL(oSelf):
    return oSelf.sPath + (
      oSelf.__dURLQuery_sValue_by_sName is not None # optional ?query
         and "?%s" % oSelf.fsStringFromNameValuePairs(oSelf.__dURLQuery_sValue_by_sName)
         or ""
    );
  @property
  def sURL(oSelf):
    return (
      oSelf.__sURLProtocol # optional protocol://host:port
        and "%s//%s%s" % (
          oSelf.__sURLProtocol,
          oSelf.__sURLHost,
          oSelf.__uURLPort is not None and ":%d" % oSelf.__uURLPort or "",
        )
        or ""
    ) + (
      oSelf.sRelativeURL
    );
  
  def fsGetStatusLine(oSelf):
    return "%s %s %s" % (oSelf.sMethod, oSelf.sURL, oSelf.sHTTPVersion);
  
  def __str__(oSelf):
    return " ".join([s for s in [
      oSelf.sMethod,
      oSelf.sURL,
      oSelf.sContent and "(%d bytes data)" % len(oSelf.sContent) or None
    ] if s]);

  def foCreateReponse(oSelf, uStatusCode, sMediaType, sContent = None, asContentChunks = None):
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
      "Content-Type": sMediaType,
      "Cache-Control": "no-cache, must-revalidate",
      "Expires": "Wed, 16 May 2012 04:01:53 GMT", # 1337
      "Pragma": "no-cache",
    };
    sConnection = oSelf.fsGetHeaderValue("Connection");
    if sConnection:
      dHeader_sValue_by_sName["Connection"] = sConnection;
    sReasonPhrase = None;
    return cHTTPResponse(oSelf.sHTTPVersion, uStatusCode, sReasonPhrase, dHeader_sValue_by_sName, sContent, asContentChunks);
