import re, urllib;
from mDebugOutput import cWithDebugOutput;
from .cException import cException;
from .fdsURLDecodedNameValuePairsFromString import fdsURLDecodedNameValuePairsFromString;
from .fsURLEncodedStringFromNameValuePairs import fsURLEncodedStringFromNameValuePairs;

gdtxDefaultPortAndSecure_by_sProtocol = {
  "http": (80, False),
  "https": (443, True),
};

UNSPECIFIED = {};

class cURL(cWithDebugOutput):
  class cInvalidURLException(cException):
    pass;
  
  @staticmethod
  def foFromString(sURL):
    if not isinstance(sURL, (str, unicode)):
      raise cURL.cInvalidURLException("Invalid URL", repr(sURL));
    oURLMatch = re.match("^(?:%s)$" % "".join([
      r"(%s)://" % "|".join([re.escape(sProtocol) for sProtocol in gdtxDefaultPortAndSecure_by_sProtocol.keys()]),
      r"(%s)" % "|".join([
        r"\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}", # IP v4
        # TODO: IP v6
        r"(?:[a-z][a-z0-9\-]*\.)*[a-z][a-z0-9\-]+", # DNS
      ]),
      r"(?:\:(\d+))?",
      r"(\/[^#?]*)?"
      r"(?:\?([^#]*))?",
      r"(?:\#(.*))?",
    ]), sURL);
    if not oURLMatch:
      raise cURL.cInvalidURLException("Invalid URL", sURL);
    (sProtocol, sHostName, sPort, sPath, sQuery, sFragment) = oURLMatch.groups();
    return cURL(sProtocol, sHostName, long(sPort) if sPort is not None else None, sPath, sQuery, sFragment);
  # There is also a non-static version that allows relative URLs:
  def foFromRelativeString(oSelf, sURL, bMustBeRelative = False):
    if not isinstance(sURL, (str, unicode)):
      raise cURL.cInvalidURLException("Invalid relative URL", repr(sURL));
    oRelativeURLMatch = re.match("^(?:%s)$" % "".join([
      r"(\/?[^:#?]*)?",
      r"(?:\?([^#]*))?",
      r"(?:\#(.*))?",
    ]), sURL);
    if not oRelativeURLMatch:
      if bMustBeRelative:
        raise cURL.cInvalidURLException("Invalid relative URL", repr(sURL));
      return cURL.foFromString(sURL);
    (sPath, sQuery, sFragment) = oRelativeURLMatch.groups();
    if sPath and not sPath.startswith("/"):
      # Path is relative too
      sPath = "/" + "/".join(oSelf.asPath[:-1] + [sPath]);
    return oSelf.foClone(
      sPath = sPath if sPath is not None else UNSPECIFIED,
      # specifying the path but not the query will remove the query
      sQuery = sQuery if sPath or sQuery is not None else UNSPECIFIED,
      # specifying the path or query but not the fragment will remove the fragment
      sFragment = sFragment if sPath or sQuery or sFragment is not None else UNSPECIFIED,
    );
  
  def __init__(oSelf, sProtocol, sHostName, uPort = None, sPath = None, sQuery = None, sFragment = None):
    assert isinstance(sProtocol, str), \
        "sProtocol must be an sASCII string, not %s" % repr(sProtocol);
    assert isinstance(sHostName, str), \
        "sHostName must be an sASCII string, not %s" % repr(sHostName);
    assert uPort is None or isinstance(uPort, (int, long)), \
        "uPort must be None, an int or a long, not %s" % repr(uPort);
    assert sPath is None or isinstance(sPath, str), \
        "sPath must be None or an ASCII string, not %s" % repr(uPort);
    assert sQuery is None or isinstance(sQuery, str), \
        "sQuery must be None or an ASCII string, not %s" % repr(sQuery);
    assert sFragment is None or isinstance(sFragment, str), \
        "sFragment must be None or an ASCII string, not %s" % repr(sFragment);
    oSelf.__sProtocol = sProtocol;
    oSelf.__sHostName = sHostName;
    oSelf.__uPort = uPort;
    oSelf.sPath = sPath; # Use setter so we can reuse code that guarantees this starts with "/"
    oSelf.__sQuery = sQuery;
    oSelf.__sFragment = sFragment;
  
  def foClone(oSelf, sProtocol = UNSPECIFIED, sHostName = UNSPECIFIED, uPort = UNSPECIFIED, sPath = UNSPECIFIED, sQuery = UNSPECIFIED, sFragment = UNSPECIFIED):
    return cURL(
      sProtocol = sProtocol if sProtocol is not UNSPECIFIED else oSelf.__sProtocol,
      sHostName = sHostName if sHostName is not UNSPECIFIED else oSelf.__sHostName,
      uPort = uPort if uPort is not UNSPECIFIED else oSelf.__uPort,
      sPath = sPath if sPath is not UNSPECIFIED else oSelf.__sPath,
      sQuery = sQuery if sQuery is not UNSPECIFIED else oSelf.__sQuery,
      sFragment = sFragment if sFragment is not UNSPECIFIED else oSelf.__sFragment,
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
    assert isinstance(sHostName, str), \
        "sHostName must be an sASCII string, not %s" % repr(sHostName);
    oSelf.__sHostName = sHostName;
  
  ### Port #####################################################################
  @property
  def uPort(oSelf):
    return oSelf.__uPort if oSelf.__uPort is not None else gdtxDefaultPortAndSecure_by_sProtocol[oSelf.__sProtocol][0];
  @uPort.setter
  def uPort(oSelf, uPort):
    assert uPort is None or isinstance(uPort, (int, long)), \
        "uPort must be None, an int or a long, not %s" % repr(uPort);
    oself.__uPort = uPort;
  
  ### Path #####################################################################
  @property
  def sURLDecodedPath(oSelf):
    return urllib.unquote(oSelf.__sPath);
  
  @property
  def sPath(oSelf):
    return oSelf.__sPath;
  @sPath.setter
  def sPath(oSelf, sPath):
    assert sPath is None or isinstance(sPath, str), \
        "sPath must be None an sASCII string, not %s" % repr(sPath);
    oSelf.__sPath = ("/" if (not sPath or sPath[0] != "/") else "") + (sPath or "");
  
  @property
  def asPath(oSelf):
    return oSelf.__sPath[1:].split("/") if oSelf.__sPath != "/" else [];
  @asPath.setter
  def asPath(oSelf, asPath):
    assert isinstance(asPath, list), \
        "asPath must be a list of strings, not %s" % repr(asPath);
    for sComponent in asPath:
      assert isinstance(sComponent, str), \
          "asPath must be a list of strings, not %s" % repr(asPath);
    oSelf.__sPath = "/" + "/".join(asPath);
  
  ### Query ####################################################################
  @property
  def sQuery(oSelf):
    return oSelf.__sQuery;
  @sQuery.setter
  def sQuery(oSelf, sQuery):
    assert sQuery is None or isinstance(sQuery, str), \
        "sQuery must be None or an sASCII string, not %s" % repr(sQuery);
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
    assert sFragment is None or isinstance(sFragment, str), \
        "sFragment must be None or an sASCII string, not %s" % repr(sFragment);
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
    return "%s%s%s" % (
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
