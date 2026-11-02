"""Read dimensions without decoding pixels; Pillow is an optional format supplement."""
import io,re,struct,xml.etree.ElementTree as ET

def dimensions(data,suffix,declared=None):
    size=None
    try:
        if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>=24:size=struct.unpack('>II',data[16:24])
        elif data[:6] in (b'GIF87a',b'GIF89a') and len(data)>=10:size=struct.unpack('<HH',data[6:10])
        elif suffix=='.svg':
            root=ET.fromstring(data)
            def number(v):
                m=re.fullmatch(r'([\d.]+)(?:px)?',v or '')
                return float(m[1]) if m else 0
            width,height=number(root.get('width')),number(root.get('height'))
            if not width or not height:
                box=[float(v) for v in re.split(r'[,\s]+',root.get('viewBox','').strip())]
                if len(box)==4 and box[2]>0 and box[3]>0:
                    if width and not height:height=width*box[3]/box[2]
                    elif height and not width:width=height*box[2]/box[3]
            if width and height and width.is_integer() and height.is_integer():size=(int(width),int(height))
        else:
            try:
                from PIL import Image
                with Image.open(io.BytesIO(data)) as image:size=image.size
            except ImportError:pass
    except (ValueError,struct.error,ET.ParseError,OSError):pass
    if size is None and declared:
        size=(declared.get('width'),declared.get('height'))
    if size and all(type(n) is int and 0<n<=1000000 for n in size):return {'width':size[0],'height':size[1]}
    return {}
