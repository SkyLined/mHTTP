from mDebugOutput import cWithDebugOutput;

class cHTTPHeaders(cWithDebugOutput):
  ddDefaultHeader_sValue_by_sName_by_sHTTPVersion = {
    "HTTP/1.0": {
      "Connection": "Close",
      "Cache-Control": "No-Cache, Must-Revalidate",
      "Expires": "Wed, 16 May 2012 04:01:53 GMT", # 1337
      "Oragma": "No-Cache",
    },
    "HTTP/1.1": {
      "Connection": "Keep-Alive",
      "Cache-Control": "No-Cache, Must-Revalidate",
      "Expires": "Wed, 16 May 2012 04:01:53 GMT", # 1337
      "Pragma": "No-Cache",
    },
  };
  
  @classmethod
  def foDefaultHeadersForHTTPVersion(cClass, sHTTPVersion):
    dDefaultHeader_sValue_by_sName = cClass.ddDefaultHeader_sValue_by_sName_by_sHTTPVersion.get(sHTTPVersion);
    assert dDefaultHeader_sValue_by_sName, \
        "Invalid HTTP version %s" % sHTTPVersion;
    return cClass(dDefaultHeader_sValue_by_sName);
  
  def __init__(oSelf, dsValue_by_sName = None):
    oSelf.__dsStrippedValue_by_sStrippedName = {};
    oSelf.__dsStrippedName_by_sLowerStrippedName = {};
    if dsValue_by_sName is not None:
      oSelf.fUpdate(dsValue_by_sName);
  
  def foClone(oSelf):
    oClone = oSelf.__class__();
    oClone.__dsStrippedValue_by_sStrippedName = oSelf.__dsStrippedValue_by_sStrippedName;
    oClone.__dsStrippedName_by_sLowerStrippedName = oSelf.__dsStrippedName_by_sLowerStrippedName;
    return oClone;
  
  def fasGetNames(oSelf):
    return oSelf.__dsStrippedValue_by_sStrippedName.keys();
  
  def fatsGetNamesAndValues(oSelf):
    return oSelf.__dsStrippedValue_by_sStrippedName.items();
  
  def fsGetNameCasing(oSelf, sName):
    assert isinstance(sName, str), \
        "HTTP header names must be strings, not %s" % repr(sName);
    return oSelf.__dsStrippedName_by_sLowerStrippedName.get(sName.strip().lower());
  
  def ftsGetNameCasingAndValue(oSelf, sName):
    assert isinstance(sName, str), \
        "HTTP header names must be strings, not %s" % repr(sName);
    sNameCasing = oSelf.__dsStrippedName_by_sLowerStrippedName.get(sName.strip().lower());
    sValue = oSelf.__dsStrippedValue_by_sStrippedName.get(sNameCasing);
    return (sNameCasing, sValue);
  
  def fbSet(oSelf, sName, sValue, bAppend = False):
    oSelf.fEnterFunctionOutput(sName = sName, sValue = sValue, bAppend = bAppend);
    try:
      assert isinstance(sName, str), \
          "HTTP header names must be strings, not %s" % repr(sName);
      assert isinstance(sValue, str), \
          "HTTP header values must be strings, not %s" % repr(sValue);
      sStrippedName = sName.strip();
      bValueUpdated = oSelf.__fbSet(sStrippedName, sStrippedName.lower(), sValue.strip(), bAppend);
      return oSelf.fxExitFunctionOutput(bValueUpdated, "updated value" if bValueUpdated else "new value");
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def __fbSet(oSelf, sStrippedName, sLowerStrippedName, sStrippedValue, bAppend):
    oSelf.fEnterFunctionOutput(sStrippedName = sStrippedName, sLowerStrippedName = sLowerStrippedName, sStrippedValue = sStrippedValue, bAppend = bAppend);
    try:
      # Deleting existing header if it has different casing:
      sExistingName = oSelf.__dsStrippedName_by_sLowerStrippedName.get(sLowerStrippedName);
      bOverwritten = False;
      bConcatinated = False;
      if sExistingName is not None:
        if bAppend:
          bConcatinated = True;
          sStrippedValue = oSelf.__dsStrippedValue_by_sStrippedName[sExistingName] + " " + sStrippedValue;
          # Deleting existing header if it has different casing:
          if sExistingName is not sStrippedName:
            del oSelf.__dsStrippedValue_by_sStrippedName[sExistingName];
        else:
          bOverwritten = True;
          if sExistingName is not sStrippedName:
            del oSelf.__dsStrippedValue_by_sStrippedName[sExistingName];
      # Set the header:
      oSelf.__dsStrippedValue_by_sStrippedName[sStrippedName] = sStrippedValue;
      oSelf.__dsStrippedName_by_sLowerStrippedName[sLowerStrippedName] = sStrippedName;
      return oSelf.fxExitFunctionOutput(
        bOverwritten or bConcatinated,
        "overwritten value %s=%s" % (repr(sExistingName), repr(sStrippedValue)) if bOverwritten
            else "concatinated to value %s=%s" % (repr(sExistingName), repr(sStrippedValue)) if bConcatinated
            else "new value %s=%s" % (repr(sStrippedName), repr(sStrippedValue))
      );
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsGet(oSelf, sName):
    oSelf.fEnterFunctionOutput(sName = sName);
    try:
      assert isinstance(sName, str), \
          "HTTP header names must be strings, not %s" % repr(sName);
      sLowerStrippedName = sName.strip().lower();
      sExistingName = oSelf.__dsStrippedName_by_sLowerStrippedName.get(sLowerStrippedName);
      if sExistingName is None:
        return oSelf.fxExitFunctionOutput(None, "no %s header" % repr(sLowerStrippedName));
      return oSelf.fxExitFunctionOutput(oSelf.__dsStrippedValue_by_sStrippedName[sExistingName], "header name = %s" % repr(sExistingName));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fbDelete(oSelf, sName):
    oSelf.fEnterFunctionOutput(sName = sName);
    try:
      assert isinstance(sName, str), \
          "HTTP header names must be strings, not %s" % repr(sName);
      sLowerStrippedName = sName.strip().lower();
      sExistingName = oSelf.__dsStrippedName_by_sLowerStrippedName.get(sLowerStrippedName);
      if sExistingName is None:
        return oSelf.fxExitFunctionOutput(None, "no %s header found" % repr(sLowerStrippedName));
      del oSelf.__dsStrippedValue_by_sStrippedName[sExistingName];
      del oSelf.__dsStrippedName_by_sLowerStrippedName[sLowerStrippedName];
      return oSelf.fxExitFunctionOutput(True, "header name = %s" % repr(sExistingName));
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
    
  def fbHasValue(oSelf, sName, sValue = None):
    oSelf.fEnterFunctionOutput(sName = sName, sValue = sValue);
    try:
      assert isinstance(sName, str), \
          "HTTP header names must be strings, not %s" % repr(sName);
      assert sValue is None or isinstance(sValue, str), \
          "HTTP header values must be strings, not %s" % repr(sValue);
      sLowerStrippedName = sName.strip().lower();
      sExistingName = oSelf.__dsStrippedName_by_sLowerStrippedName.get(sLowerStrippedName);
      if sExistingName is None:
        # No header with this name exists.
        return oSelf.fxExitFunctionOutput(False, "no %s header found" % repr(sLowerStrippedName));
      # sValue == None means does a header with this name exist
      # Otherwise check if the header value is the same as the provided value, ignoring case (!).
      if sValue is None:
        return oSelf.fxExitFunctionOutput(True, "header name = %s" % repr(sExistingName));
      sLowerStrippedValue = sValue.strip().lower();
      sExistingValue = oSelf.__dsStrippedValue_by_sStrippedName[sExistingName];
      return oSelf.fxExitFunctionOutput(
        sExistingValue.lower() == sLowerStrippedValue, \
        "header name = %s, value = %s" % (repr(sExistingName), repr(sExistingValue))
      );
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fUpdate(oSelf, dsValue_by_sName_or_oHTTPHeaders, bAppend = False):
    oSelf.fEnterFunctionOutput(dsValue_by_sName_or_oHTTPHeaders = dsValue_by_sName_or_oHTTPHeaders, bAppend = bAppend);
    try:
      if isinstance(dsValue_by_sName_or_oHTTPHeaders, cHTTPHeaders):
        oHTTPHeaders = dsValue_by_sName_or_oHTTPHeaders;
        for (sStrippedName, sStrippedValue) in oHTTPHeaders.__dsStrippedValue_by_sStrippedName.items():
          oSelf.__fbSet(sStrippedName, sStrippedName.lower(), sStrippedValue, bAppend);
      else:
        dsValue_by_sName = dsValue_by_sName_or_oHTTPHeaders;
        assert isinstance(dsValue_by_sName, dict), \
            "dsValue_by_sName must be an instance of dict, not %s" % repr(dsValue_by_sName);
        dsAddedName_by_sLowerStrippedName = {};
        for (sName, sValue) in dsValue_by_sName.items():
          assert isinstance(sName, str), \
              "HTTP header names must be strings, not %s" % repr(sName);
          assert isinstance(sValue, str), \
              "HTTP header values must be strings, not %s" % repr(sValue);
          sStrippedName = sName.strip();
          sLowerStrippedName = sStrippedName.lower();
          # Check that the dct does not contain two headers with the same name:
          sAddedName = dsAddedName_by_sLowerStrippedName.get(sLowerStrippedName);
          assert sAddedName is None, \
              "HTTP header names must be unique; you're trying to add %s and %s" % (repr(sAddedName), repr(sName));
          dsAddedName_by_sLowerStrippedName[sLowerStrippedName] = sName;
          oSelf.__fbSet(sStrippedName, sLowerStrippedName, sValue.strip(), bAppend);  
      return oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;

  def fsToString(oSelf):
    return "%s{%d headers}" % (oSelf.__class__.__name__, len(oSelf.__dsStrippedValue_by_sStrippedName));
