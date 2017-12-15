from iHTTPMessage import iHTTPMessage;

class cHTTPResponse(iHTTPMessage):
  def __init__(oSelf, sHTTPVersion, uStatusCode, sReasonPhrase, dHeader_sValue_by_sName = None, sContent = None, asContentChunks = None):
    assert (isinstance(uStatusCode, long) or isinstance(uStatusCode, int)) and uStatusCode in xrange(100, 1000), \
        "Status code must be an unsigned integer in the range 100-999, not %s" % repr(uStatusCode);

    oSelf.sHTTPVersion = sHTTPVersion;
    oSelf.uStatusCode = uStatusCode;
    oSelf.sReasonPhrase = sReasonPhrase;
    
    iHTTPMessage.__init__(oSelf, dHeader_sValue_by_sName, sContent, asContentChunks);
  
  def fsGetStatusLine(oSelf):
    return "%s %03d %s" % (oSelf.sHTTPVersion, oSelf.uStatusCode, oSelf.sReasonPhrase);
  
  def __str__(oSelf):
    return "%03d %d bytes %s" % (oSelf.uStatusCode, len(oSelf.sBody), oSelf.sMediaType or "");
