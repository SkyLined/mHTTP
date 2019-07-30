import re;
from mDebugOutput import cWithDebugOutput;
from .cException import cException;
from .fdsURLDecodedNameValuePairsFromString import fdsURLDecodedNameValuePairsFromString;
from .fsURLEncodedStringFromNameValuePairs import fsURLEncodedStringFromNameValuePairs;

gdtxDefaultPortAndSecure_by_sProtocol = {
  "http": (80, False),
  "https": (443, True),
};

class cURL(cWithDebugOutput):
  class cInvalidURLException(cException):
    pass;
  
  @staticmethod
  def foFromString(sURL):
    oURLMatch = re.match("^(?:%s)$" % "".join([
      r"(%s)://" % "|".join([re.escape(sProtocol) for sProtocol in gdtxDefaultPortAndSecure_by_sProtocol.keys()]),
      r"(%s)" % "|".join([
        r"\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}", # IP v4
        # TODO: IP v6
        r"(?:[a-z][a-z0-9\-]*\.)*[a-z][a-z0-9\-]+", # DNS
      ]),
      r"(?:\:(\d+))?",
      r"(?:\/(%s))?" % r"[^#?]*",
      r"(?:\?(%s))?" % r"[^#]*",
      r"(?:\#(%s))?" % r".*",
    ]), sURL);
    if not oURLMatch:
      raise cURL.cInvalidURLException("Invalid URL", sURL);
    (sProtocol, sHostName, sPort, sPath, sQuery, sFragment) = oURLMatch.groups();
    return cURL(sProtocol, sHostName, long(sPort) if sPort is not None else None, sPath, sQuery, sFragment);
  
  def __init__(oSelf, sProtocol, sHostName, uPort = None, sPath = "/", sQuery = None, sFragment = None):
    oSelf.__sProtocol = sProtocol;
    oSelf.__sHostName = sHostName;
    oSelf.__uPort = uPort;
    oSelf.sPath = sPath; # Use setter so we can reuse code that guarantees this starts with "/"
    oSelf.__sQuery = sQuery;
    oSelf.__sFragment = sFragment;
  
  def foClone(oSelf, sProtocol = None, sHostName = None, uPort = None, sPath = None, sQuery = None, sFragment = None):
    return cURL(
      sProtocol = sProtocol if sProtocol is not None else oSelf.__sProtocol,
      sHostName = sHostName if sHostName is not None else oSelf.__sHostName,
      uPort = uPort if uPort is not None else oSelf.__uPort,
      sPath = sPath if sPath is not None else oSelf.__sPath,
      sQuery = sQuery if sQuery is not None else oSelf.__sQuery,
      sFragment = sFragment if sFragment is not None else oSelf.__sFragment,
    );
  
  ### Protocol #################################################################
  @property
  def sProtocol(oSelf):
    return oSelf.__sProtocol;
  
  @property
  def bSecure(oSelf):
    return gdtxDefaultPortAndSecure_by_sProtocol[oSelf.__sProtocol][1];
  
  ### Hostname #################################################################
  @property
  def sHostName(oSelf):
    return oSelf.__sHostName;
  @sHostName.setter
  def sHostName(oSelf, sHostName):
    oSelf.__sHostName = sHostName;
  
  ### Port #####################################################################
  @property
  def uPort(oSelf):
    return oSelf.__uPort if oSelf.__uPort is not None else gdtxDefaultPortAndSecure_by_sProtocol[oSelf.__sProtocol][0];
  @uPort.setter
  def uPort(oSelf, uPort):
    oself.__uPort = uPort;
  
  ### Path #####################################################################
  @property
  def sPath(oSelf):
    return oSelf.__sPath;
  @sPath.setter
  def sPath(oSelf, sPath):
    oSelf.__sPath = ("/" if (not sPath or sPath[0] != "/") else "") + (sPath or "");
  
  @property
  def asPath(oSelf):
    return oSelf.__sPath[1:].split("/") if oSelf.__sPath != "/" else [];
  @asPath.setter
  def asPath(oSelf, asPath):
    oSelf.__sPath = "/" + "/".join(asPath);
  
  ### Query ####################################################################
  @property
  def sQuery(oSelf):
    return oSelf.__sQuery;
  @sQuery.setter
  def sQuery(oSelf, sQuery):
    oSelf.__sQuery = sQuery;
  @property
  def dsQueryValue_by_sName(oSelf):
    return fdsURLDecodedNameValuePairsFromString(oSelf.__sQuery) if oSelf.__sQuery else {};
  @dsQueryValue_by_sName.setter
  def dsQueryValue_by_sName(oSelf, dsQueryValue_by_sName):
    oSelf.__sQuery = fsURLEncodedStringFromNameValuePairs(dsQueryValue_by_sName);
  
  def fsGetQueryValue(oSelf, sName):
    return oSelf.dsQueryValue_by_sName.get(sName);
  
  def fSetQueryValue(oSelf, sName, sValue):
    dsQueryValue_by_sName = oSelf.dsQueryValue_by_sName;
    dsQueryValue_by_sName[sName] = sValue;
    oSelf.dsQueryValue_by_sName = dsQueryValue_by_sName;

  ### Fragment #################################################################
  @property
  def sFragment(oSelf):
    return oSelf.__sFragment;
  @sFragment.setter
  def sFragment(oSelf, sFragment):
    oSelf.__sFragment = sFragment;
    
  ### Convenience ##############################################################
  @property
  def sAddress(oSelf):
    return "%s:%d" % (oSelf.__sHostName, oSelf.__uPort);
  
  @property
  def sHostNameAndPort(oSelf):
    bNonDefaultPort = oSelf.__uPort not in [None, gdtxDefaultPortAndSecure_by_sProtocol[oSelf.__sProtocol][0]];
    return oSelf.__sHostName + (":%d" % oSelf.__uPort if bNonDefaultPort else "");
  
  @property
  def oBase(oSelf):
    return cURL(sProtocol = oSelf.__sProtocol, sHostName = oSelf.sHostName, uPort = oSelf.uPort);
  
  @property
  def sBase(oSelf):
    return oSelf.__sProtocol + "://" + oSelf.sHostNameAndPort;
  
  @property
  def sRelative(oSelf):
    return "/%s%s%s" % (
      oSelf.__sPath,
      ("?%s" % oSelf.__sQuery) if oSelf.__sQuery is not None else "",
      ("#%s" % oSelf.__sFragment) if oSelf.__sFragment is not None else "",
    );
  
  @property
  def sAbsolute(oSelf):
    return oSelf.sBase + oSelf.sRelative;
  def __str__(oSelf):
    return oSelf.sAbsolute;
  
  def fasDump(oSelf):
    return [
      "sProtocol: %s" % repr(oSelf.__sProtocol),
      "sHostName: %s" % repr(oSelf.__sHostName),
      "uPort: %s" % repr(oSelf.__uPort),
      "sPath: %s" % repr(oSelf.__sPath),
      "sQuery: %s" % repr(oSelf.__sQuery),
      "sFragment: %s" % repr(oSelf.__sFragment),
    ];
  
  def fsToString(oSelf):
    sDetails = oSelf.sAbsolute;
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
