from .dasMediaTypes_by_sExtension import dasMediaTypes_by_sExtension;

def fsGetMediaTypeForExtension(sExtension):
  # You can also specify a path and a file name; the code will extract the extension from this:
  uLastDotIndex = sExtension.rfind(".");
  if uLastDotIndex > -1:
    sExtension = sExtension[uLastDotIndex + 1:];
  return dasMediaTypes_by_sExtension.get(sExtension.lower(), [None])[0];
