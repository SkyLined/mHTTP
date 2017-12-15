import base64, urllib;

def fsASCII(sData, sDataTypeDescription):
  try:
    return str(sData or "");
  except:
    raise AssertionError("%s cannot contain Unicode characters: %s" % (sDataTypeDescription, repr(sData)));

class iHTTPMessage(object):
  @staticmethod 
  def fdsNameValuePairsFromString(sData):
    dsValue_by_sName = {};
    for sNameEqualsValue in sData.split("&"):
      if "=" in sNameEqualsValue:
        sName, sValue = sNameEqualsValue.split("=", 1);
        sValue = urllib.unquote(sValue);
      else:
        sName = sNameEqualsValue;
        sValue = None;
      dsValue_by_sName[urllib.unquote(sName)] = sValue;
    return dsValue_by_sName;
  
  @staticmethod
  def fsStringFromNameValuePairs(dsValue_by_sName):
    asData = [];
    for (sName, sValue) in dsValue_by_sName.items():
      sData = urllib.quote(sName);
      if sValue is not None:
        sData += "=%s" % urllib.quote(sValue);
      asData.append(sData);
    return "&".join(asData);
  
  def __init__(oSelf, dHeader_sValue_by_sName, sContent = None, asContentChunks = None):
    oSelf.dHeader_sValue_by_sName = dHeader_sValue_by_sName or {};
    if asContentChunks is not None:
      assert sContent is None, \
          "Cannot provide both sContent and asContentChunks!";
      oSelf.asContentChunks = asContentChunks;
    else:
      oSelf.__asContentChunks = None;
      if sContent: 
        oSelf.sContent = sContent;
      else:
        oSelf.__sContent = None;
  
  def fsGetHeaderValue(oSelf, sName):
    sLowerName = sName.lower();
    for (sName, sValue) in oSelf.dHeader_sValue_by_sName.items():
      if sLowerName == sName.lower():
        return sValue;
  
  def fSetHeaderValue(oSelf, sName, sValue):
    sLowerName = sName.lower();
    for sOtherName in oSelf.dHeader_sValue_by_sName.keys():
      if sLowerName == sOtherName.lower():
        del oSelf.dHeader_sValue_by_sName[sOtherName];
    oSelf.dHeader_sValue_by_sName[sName] = sValue;
  
  def fRemoveHeader(oSelf, sName):
    sLowerName = sName.lower();
    for sOtherName in oSelf.dHeader_sValue_by_sName.keys():
      if sLowerName == sOtherName.lower():
        del oSelf.dHeader_sValue_by_sName[sOtherName];
  
  @property
  def sMediaType(oSelf):
    sMediaType = oSelf.fsGetHeaderValue("Content-Type");
    return sMediaType and sMediaType.lower() or None;
  @sMediaType.setter
  def sMediaType(oSelf, sValue):
    oSelf.fSetHeaderValue("Content-Type", sValue);
  
  @property
  def bChunked(oSelf):
    sTransferEncodingHeader = oSelf.fsGetHeaderValue("Transfer-Encoding");
    return sTransferEncodingHeader and sTransferEncodingHeader.strip().lower() == "chunked";

  @property
  def bCloseConnection(oSelf):
    sConnectionHeader = oSelf.fsGetHeaderValue("Connection");
    return sConnectionHeader and sConnectionHeader.strip().lower() == "close";
  
  @property
  def sContent(oSelf):
    if oSelf.bChunked:
      return "".join(oSelf.__asContentChunks);
    return oSelf.__sContent;
  @sContent.setter
  def sContent(oSelf, sContent):
    oSelf.fRemoveHeader("Transfer-Encoding");
    if not oSelf.bCloseConnection:
      oSelf.fSetHeaderValue("Content-Length", str(len(sContent)));
    oSelf.__sContent = fsASCII(sContent, "Content");
    oSelf.__asContentChunks = None;
  
  @property
  def asContentChunks(oSelf):
    assert oSelf.bChunked, \
        "Cannot get content chunks when chunked encoding is not enabled";
    return oSelf.__asContentChunks[:];
  @asContentChunks.setter
  def asContentChunks(oSelf, asContentChunks):
    oSelf.fRemoveHeader("Content-Length");
    oSelf.fSetHeaderValue("Transfer-Encoding", "chunked");
    oSelf.__sContent = None;
    oSelf.__asContentChunks = [];
    for sContentChunk in asContentChunks:
      oSelf.fAddContentChunk(sContentChunk);
    
  def fAddContentChunk(oSelf, sContentChunk):
    assert sContentChunk, \
        "Cannot add an empty chunk!"
    if not oSelf.bChunked:
      oSelf.fRemoveHeader("Content-Length");
      oSelf.fSetHeaderValue("Transfer-Encoding", "chunked");
      oSelf.__sContent = None;
      oSelf.__asContentChunks = [sContentChunk];
    else:
      oSelf.__asContentChunks.append(sContentChunk);
    
  @property
  def sBody(oSelf):
    if oSelf.bChunked:
      return "".join([
        "%X\r\n%s\r\n" % (len(sContentChunk), sContentChunk) for sContentChunk in oSelf.__asContentChunks
      ]) + "0\r\n\r\n";
    return oSelf.__sContent or "";
  
  # x-www-form-urlencoded
  @property
  def dForm_sValue_by_sName(oSelf):
    assert oSelf.sMediaType == "application/x-www-form-urlencoded", \
        "Cannot get form data for Content-Type %s" % oSelf.fsGetHeaderValue("Content-Type");
    return iHTTPMessage.fdsNameValuePairsFromString(oSelf.sContent);
  
  def fsGetFormValue(oSelf, sName):
    sLowerCaseName = sName.lower();
    for (sName, sValue) in oSelf.dForm_sValue_by_sName.items():
      if sLowerCaseName == sName.lower():
        return sValue;
  
  def fSetFormValue(oSelf, sName, sValue):
    sLowerName = sName.lower();
    dForm_sValue_by_sName = oSelf.dForm_sValue_by_sName;
    for sOtherName in dForm_sValue_by_sName.keys():
      if sLowerName == sOtherName.lower():
        del dForm_sValue_by_sName[sOtherName];
    dForm_sValue_by_sName[sName] = sValue;
    oSelf.sContent = iHTTPMessage.fsStringFromNameValuePairs(dForm_sValue_by_sName);
  
  def ftsGetBasicAuthorization(oSelf):
    sAuthorization = oSelf.fsGetHeaderValue("Authorization");
    if sAuthorization is None or sAuthorization[:6].lower() != "basic ":
      return (None, None);
    try:
      sUserNameColonPassword = base64.b64decode(sAuthorization[6:].strip());
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
  
  def fsToString(oSelf):
    return "\r\n".join([
      oSelf.fsGetStatusLine(),
    ] + [
      "%s: %s" % (sName, sValue) for (sName, sValue) in oSelf.dHeader_sValue_by_sName.items()
    ] + [
      "",
      oSelf.sBody,
    ]);
