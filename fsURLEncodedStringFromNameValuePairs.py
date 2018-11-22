import urllib;

def fsURLEncodedStringFromNameValuePairs(dsValue_by_sName):
  asData = [];
  for (sName, sValue) in dsValue_by_sName.items():
    sData = urllib.quote(sName);
    if sValue is not None:
      sData += "=%s" % urllib.quote(sValue);
    asData.append(sData);
  return "&".join(asData);
