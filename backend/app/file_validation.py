"""Bounded subprocess: inspect files locally; images get metadata-free re-encoding."""
import io,json,sys,warnings,resource
if sys.platform=='linux':resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
resource.setrlimit(resource.RLIMIT_CPU,(6,6))
from PIL import Image,ImageOps
Image.MAX_IMAGE_PIXELS=40_000_000
warnings.simplefilter('error',Image.DecompressionBombWarning)


def validate(raw,limit):
    if not raw or len(raw)>limit:raise ValueError()
    if raw.startswith(b'%PDF-'):
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw),strict=True)
        if reader.is_encrypted or not 1<=len(reader.pages)<=50:raise ValueError()
        forbidden={'/JavaScript','/JS','/OpenAction','/AA','/Launch','/EmbeddedFiles','/RichMedia','/XFA','/AcroForm','/SubmitForm','/GoToR','/URI'}
        seen=set();count=0
        def walk(node,depth=0):
            nonlocal count
            count+=1
            if count>40000 or depth>40:raise ValueError()
            if hasattr(node,'idnum'):
                key=(node.idnum,node.generation)
                if key in seen:return
                seen.add(key);node=node.get_object()
            if isinstance(node,dict):
                if any(str(k) in forbidden for k in node):raise ValueError()
                for value in node.values():walk(value,depth+1)
            elif isinstance(node,(list,tuple)):
                for value in node:walk(value,depth+1)
        walk(reader.trailer)
        return raw,b'','application/pdf','pdf'
    with Image.open(io.BytesIO(raw),formats=['PNG','JPEG','WEBP']) as image:
        if image.width*image.height>40_000_000:raise ValueError()
        image.load();image=ImageOps.exif_transpose(image);image.thumbnail((4096,4096))
        alpha=image.mode in ('RGBA','LA') or 'transparency' in image.info
        clean=Image.new('RGBA' if alpha else 'RGB',image.size);clean.paste(image.convert(clean.mode))
        out=io.BytesIO();clean.save(out,format='PNG' if alpha else 'JPEG',**({} if alpha else {'quality':94}))
        clean.thumbnail((640,640));preview=io.BytesIO();clean.convert('RGB').save(preview,format='JPEG',quality=85)
        if len(out.getvalue())>limit:raise ValueError()
        return out.getvalue(),preview.getvalue(),'image/png' if alpha else 'image/jpeg','png' if alpha else 'jpg'

if __name__=='__main__':
    try:
        limit=int(sys.argv[1]);raw=sys.stdin.buffer.read(limit+1)
        data,preview,mime,extension=validate(raw,limit)
        sys.stdout.buffer.write(json.dumps({'size':len(data),'preview_size':len(preview),'media_type':mime,'extension':extension}).encode()+b'\n'+data+preview)
    except Exception:sys.exit(1)
