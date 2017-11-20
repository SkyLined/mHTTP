import base64, urllib;

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
  
  def __init__(oSelf, dHeader_sValue_by_sName, sBody):
    if sBody is None:
      oSelf.sBody = "";
    else:
      cType = type(sBody);
      if cType == unicode:
        try:
          oSelf.sBody = str(sBody);
        except:
          raise AssertionError("Body cannot contain Unicode characters");
      else:
        assert cType == str, \
            "Body must be a string, not %s" % repr(sBody);
        oSelf.sBody = sBody;
    oSelf.dHeader_sValue_by_sName = dHeader_sValue_by_sName;
  
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
  
  @property
  def sMediaType(oSelf):
    sMediaType = oSelf.fsGetHeaderValue("Content-Type");
    return sMediaType and sMediaType.lower() or None;
  @sMediaType.setter
  def sMediaType(oSelf, sValue):
    oSelf.fSetHeaderValue("Content-Type", sValue);
  
  # Body
  def fSetBody(oSelf, sBody):
    # Set the body and update the content-length header.
    oSelf.sBody = sBody;
    oSelf.fSetHeaderValue("Content-Length", len(oSelf.sBody));
  
  # x-www-form-urlencoded
  @property
  def dForm_sValue_by_sName(oSelf):
    assert oSelf.sMediaType == "application/x-www-form-urlencoded", \
        "Cannot get form data for Content-Type %s" % oSelf.fsGetHeaderValue("Content-Type");
    return iHTTPMessage.fdsNameValuePairsFromString(oSelf.sBody);
  
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
    oSelf.fSetBody(iHTTPMessage.fsStringFromNameValuePairs(dForm_sValue_by_sName));
  
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
