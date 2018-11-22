from .dsHTTPCommonReasonPhrase_by_uStatusCode import dsHTTPCommonReasonPhrase_by_uStatusCode;
from .iHTTPMessage import iHTTPMessage;

class cHTTPResponse(iHTTPMessage):
  @staticmethod
  def fdxParseStatusLine(sStatusLine):
    asComponents = sStatusLine.split(" ", 2);
    if len(asComponents) != 3:
      raise iHTTPMessage.cInvalidHTTPMessageException("The remote send an invalid status line.", sStatusLine);
    sHTTPVersion, sStatusCode, sReasonPhrase = asComponents;
    if sHTTPVersion not in ["HTTP/1.0", "HTTP/1.1"]:
      raise iHTTPMessage.cInvalidHTTPMessageException("The remote send an invalid HTTP version in the status line.", sHTTPVersion);
    try:
      if len(sStatusCode) != 3:
        raise ValueError();
      uStatusCode = long(sStatusCode);
      if uStatusCode < 100 or uStatusCode > 599:
        raise ValueError();
    except ValueError:
      raise iHTTPMessage.cInvalidHTTPMessageException("The remote send an invalid status code in the status line.", sStatusCode);
    return {"sHTTPVersion": sHTTPVersion, "uStatusCode": uStatusCode, "sReasonPhrase": sReasonPhrase};
  
  def __init__(oSelf, sHTTPVersion = None, uStatusCode = None, sReasonPhrase = None, dHeader_sValue_by_sName = None, sBody = None, sData = None, asBodyChunks = None, dxMetaData = None):
    if uStatusCode is None:
      uStatusCode = 200;
    else:
      assert (isinstance(uStatusCode, long) or isinstance(uStatusCode, int)) and uStatusCode in xrange(100, 600), \
          "Status code must be an unsigned integer in the range 100-999, not %s" % repr(uStatusCode);

    oSelf.__uStatusCode = uStatusCode;
    oSelf.__sReasonPhrase = sReasonPhrase or dsHTTPCommonReasonPhrase_by_uStatusCode.get(uStatusCode, "Unspecified");
    
    iHTTPMessage.__init__(oSelf, sHTTPVersion, dHeader_sValue_by_sName, sBody, sData, asBodyChunks, dxMetaData);
  
  @property
  def uStatusCode(oSelf):
    return oSelf.__uStatusCode;
  @uStatusCode.setter
  def uStatusCode(oSelf, uStatusCode):
    oSelf.__uStatusCode = uStatusCode;
  
  @property
  def sReasonPhrase(oSelf):
    return oSelf.__sReasonPhrase;
  @sReasonPhrase.setter
  def sReasonPhrase(oSelf, sReasonPhrase):
    oSelf.__sReasonPhrase = sReasonPhrase;
  
  def fsGetStatusLine(oSelf):
    sReasonPhrase = oSelf.sReasonPhrase or dsHTTPCommonResponseMessage_by_uStatusCode.get(oSelf.uStatusCode, "Unknown");
    return "%s %03d %s" % (oSelf.sHTTPVersion, oSelf.uStatusCode, sReasonPhrase);
  
  def __str__(oSelf):
    return " ".join([s for s in [
      "%03d" % oSelf.uStatusCode,
      oSelf._fsBodyStr(),
    ] if s]);
  
  def fsToString(oSelf):
    return "%s{%s %03d %s}" % (oSelf.__class__.__name__, oSelf.sHTTPVersion, oSelf.uStatusCode, oSelf.sReasonPhrase);
