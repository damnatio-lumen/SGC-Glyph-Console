#!/usr/bin/env python3
"""Build SGC Glyph TTF/WOFF2 from the original numbered SVG glyph set.

Downloads glyphs 01..39 from Wikimedia Commons (SGC.Alex, CC BY-SA 3.0),
then maps them to an Italian keyboard while preserving vector numbering.
"""
from __future__ import annotations
import argparse, json, math, os, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.svgLib.path import parse_path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source_svg'
OUTPUT = ROOT / 'output'
FONT_NAME = 'SGC Glyph'
UNITS = 1000


def mapping_rows():
    rows=[]
    for n in range(1,40):
        if n <= 9: key=str(n)
        elif n == 10: key='0'
        elif n <= 36: key=chr(ord('A')+n-11)
        elif n == 37: key=','
        elif n == 38: key='.'
        else: key='-'
        rows.append({'vector_number':f'{n:02d}','keyboard_key':key,'unicode':f'U+{ord(key):04X}',
                     'source_file':f'Stargate SG·1 symbol {n:02d}.svg',
                     'role':'Earth / point of origin' if n==1 else 'Milky Way glyph'})
    return rows


def _contact_user_agent() -> str:
    """Return an identifying User-Agent; contact is supplied by the operator."""
    contact = os.environ.get('SGC_GLYPH_CONTACT', '').strip()
    if not contact:
        raise RuntimeError(
            'Manca il contatto per identificare il programma a Wikimedia.\n'
            'In PowerShell imposta prima: $env:SGC_GLYPH_CONTACT = "tuo-email@example.com"\n'
            'Puoi usare anche un URL pubblico di progetto al posto dell’email.'
        )
    if '@' in contact and not contact.lower().startswith('mailto:'):
        contact = 'mailto:' + contact
    return f'SGC-Glyph-Font-Builder/0.5 ({contact}) Python-urllib'


def _retry_after_seconds(exc: HTTPError, attempt: int) -> float:
    """Use Retry-After when supplied; otherwise apply exponential backoff."""
    value = exc.headers.get('Retry-After') if exc.headers else None
    if value:
        try:
            return max(5.0, float(value))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return max(5.0, (dt - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                pass
    return max(5.0, 10.0 * (2 ** attempt))


def download_svg(n: int, force: bool=False) -> Path:
    SOURCE.mkdir(parents=True, exist_ok=True)
    filename=f'Stargate SG·1 symbol {n:02d}.svg'
    target=SOURCE / f'glyph_{n:02d}.svg'
    if target.exists() and target.stat().st_size > 100 and not force:
        print(f'[CACHE] Glifo {n:02d} già presente, riutilizzo.', flush=True)
        return target

    url='https://commons.wikimedia.org/wiki/Special:Redirect/file/' + urllib.parse.quote(filename, safe='')
    user_agent = _contact_user_agent()
    max_attempts = 6
    for attempt in range(max_attempts):
        req=urllib.request.Request(url, headers={
            'User-Agent': user_agent,
            'Accept': 'image/svg+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                data=response.read()
            if b'<svg' not in data[:10000].lower():
                raise RuntimeError(f'La risposta per glyph {n:02d} non sembra un SVG valido.')
            temp = target.with_suffix('.svg.part')
            temp.write_bytes(data)
            temp.replace(target)
            print(f'[OK] Glifo {n:02d} scaricato ({len(data):,} byte).', flush=True)
            # Download in serie, circa 12 richieste al minuto.
            time.sleep(5.0)
            return target
        except HTTPError as exc:
            if exc.code not in (429, 503):
                raise RuntimeError(f'Download fallito per glyph {n:02d}: HTTP {exc.code} {exc.reason}') from exc
            delay = _retry_after_seconds(exc, attempt)
            if delay > 300:
                raise RuntimeError(
                    f'Wikimedia ha restituito HTTP {exc.code} e chiede di attendere {delay:.0f} secondi. '
                    'Interrompo qui; riprova più tardi. Gli SVG già scaricati verranno conservati.'
                ) from exc
            print(f'[WAIT] Wikimedia HTTP {exc.code}; nuovo tentativo tra {delay:.0f} secondi '
                  f'({attempt+1}/{max_attempts}).', flush=True)
            time.sleep(delay)
        except URLError as exc:
            if attempt == max_attempts - 1:
                raise RuntimeError(f'Errore di rete per glyph {n:02d}: {exc}') from exc
            delay = max(5.0, 10.0 * (2 ** attempt))
            print(f'[WAIT] Errore di rete; nuovo tentativo tra {delay:.0f} secondi '
                  f'({attempt+1}/{max_attempts}).', flush=True)
            time.sleep(delay)
    raise RuntimeError(f'Download fallito per glyph {n:02d} dopo {max_attempts} tentativi.')


def mat_mul(A, B):
    a,b,c,d,e,f=A; g,h,i,j,k,l=B
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)


def parse_transform(value: str | None):
    result=(1,0,0,1,0,0)
    if not value: return result
    for name, raw in re.findall(r'([A-Za-z]+)\s*\(([^)]*)\)', value):
        vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?', raw)]
        name=name.lower()
        if name=='matrix' and len(vals)==6: t=tuple(vals)
        elif name=='translate': t=(1,0,0,1,vals[0],vals[1] if len(vals)>1 else 0)
        elif name=='scale': t=(vals[0],0,0,vals[1] if len(vals)>1 else vals[0],0,0)
        elif name=='rotate':
            ang=math.radians(vals[0]); c=math.cos(ang); s=math.sin(ang)
            rot=(c,s,-s,c,0,0)
            if len(vals)>=3:
                cx,cy=vals[1],vals[2]
                t=mat_mul(mat_mul((1,0,0,1,cx,cy),rot),(1,0,0,1,-cx,-cy))
            else: t=rot
        elif name=='skewx': t=(1,0,math.tan(math.radians(vals[0])),1,0,0)
        elif name=='skewy': t=(1,math.tan(math.radians(vals[0])),0,1,0,0)
        else: continue
        result=mat_mul(result,t)
    return result


def svg_length(v: str | None, default: float=0.0) -> float:
    if not v: return default
    m=re.match(r'\s*([-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?)',v)
    return float(m.group(1)) if m else default


def shape_path(el):
    tag=el.tag.rsplit('}',1)[-1]
    if tag=='path': return el.attrib.get('d','')
    if tag in ('polygon','polyline'):
        nums=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',el.attrib.get('points',''))]
        if len(nums)<4: return ''
        parts=[f'M {nums[0]} {nums[1]}']
        for i in range(2,len(nums),2): parts.append(f'L {nums[i]} {nums[i+1]}')
        if tag=='polygon': parts.append('Z')
        return ' '.join(parts)
    if tag=='line':
        a=el.attrib; return f"M {svg_length(a.get('x1'))} {svg_length(a.get('y1'))} L {svg_length(a.get('x2'))} {svg_length(a.get('y2'))}"
    if tag=='rect':
        a=el.attrib; x=svg_length(a.get('x')); y=svg_length(a.get('y')); w=svg_length(a.get('width')); h=svg_length(a.get('height'))
        if not w or not h: return ''
        return f'M{x} {y} H{x+w} V{y+h} H{x} Z'
    return ''


def iter_paths(root):
    found=[]
    def walk(el, inherited):
        local=el.attrib.get('transform')
        combined=mat_mul(inherited, parse_transform(local))
        tag=el.tag.rsplit('}',1)[-1]
        d=shape_path(el)
        if d:
            style=el.attrib.get('style','')
            fill=el.attrib.get('fill')
            if fill is None:
                m=re.search(r'(?:^|;)\s*fill\s*:\s*([^;]+)',style)
                fill=m.group(1).strip() if m else '#000000'
            if fill.lower()!='none' and fill.lower() not in ('white','#fff','#ffffff'):
                found.append((d,combined))
        for child in list(el): walk(child,combined)
    walk(root,(1,0,0,1,0,0))
    return found


def build_glyph(svg_path: Path, name: str):
    try: root=ET.parse(svg_path).getroot()
    except Exception as exc: raise RuntimeError(f'SVG non leggibile: {svg_path.name}: {exc}')
    paths=iter_paths(root)
    if not paths: raise RuntimeError(f'Nessun tracciato compatibile trovato in {svg_path.name}')
    bounds=BoundsPen(None)
    for d,m in paths:
        parse_path(d, TransformPen(bounds,m))
    if bounds.bounds is None: raise RuntimeError(f'Nessuna geometria in {svg_path.name}')
    x0,y0,x1,y1=bounds.bounds
    w=max(x1-x0,1); h=max(y1-y0,1)
    scale=min(760/h, 820/w)
    xoff=(UNITS-w*scale)/2 - x0*scale
    baseline=105 + (760-h*scale)/2
    # SVG y grows down; font coordinates grow up.
    final=(scale,0,0,-scale,xoff,baseline+y1*scale)
    # SVG paths commonly contain cubic Bezier curves (C/c and S/s).
    # TrueType glyf outlines require quadratic curves, so convert the
    # transformed outline through Cu2QuPen before it reaches TTGlyphPen.
    pen=TTGlyphPen(None)
    cu2qu_pen=Cu2QuPen(pen, max_err=1.0, reverse_direction=False)
    for d,m in paths:
        composed=mat_mul(final,m)
        parse_path(d, TransformPen(cu2qu_pen,composed))
    return pen.glyph(), 1000


def build_font():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    rows=mapping_rows()
    glyph_order=['.notdef','space']+[f'glyph{n:02d}' for n in range(1,40)]
    glyphs={'.notdef':TTGlyphPen(None).glyph(),'space':TTGlyphPen(None).glyph()}
    metrics={'.notdef':(600,0),'space':(400,0)}
    cmap={0x20:'space'}
    for row in rows:
        n=int(row['vector_number']); name=f'glyph{n:02d}'
        svg=SOURCE/f'glyph_{n:02d}.svg'
        if not svg.exists(): raise RuntimeError(f'Manca {svg}. Esegui prima il download degli SVG.')
        glyphs[name],_=build_glyph(svg,name)
        metrics[name]=(1000,0)
        key=row['keyboard_key']
        cmap[ord(key)]=name
        if key.isalpha(): cmap[ord(key.lower())]=name
    fb=FontBuilder(UNITS,isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900,descent=-200)
    fb.setupNameTable({'familyName':FONT_NAME,'styleName':'Regular','uniqueFontIdentifier':'SGC Glyph 0.5','fullName':'SGC Glyph Regular','psName':'SGCGlyph-Regular','version':'Version 0.5'})
    fb.setupOS2(sTypoAscender=900,sTypoDescender=-200,usWinAscent=900,usWinDescent=200)
    fb.setupPost()
    fb.setupMaxp()
    font=fb.font
    ttf=OUTPUT/'SGC_Glyph.ttf'
    font.save(ttf)
    try:
        font.flavor='woff2'
        font.save(OUTPUT/'SGC_Glyph.woff2')
    except Exception as exc:
        print(f'[WARN] WOFF2 non creato: {exc}')
    print(f'[OK] Font creato: {ttf}')


def main():
    p=argparse.ArgumentParser(description='Genera il font SGC Glyph per tastiera italiana')
    p.add_argument('--skip-download',action='store_true',help='usa gli SVG già presenti in source_svg')
    p.add_argument('--force-download',action='store_true',help='riscarica tutti gli SVG')
    p.add_argument('--version',action='version',version='SGC Glyph Font Builder 0.4')
    args=p.parse_args()
    SOURCE.mkdir(exist_ok=True)
    if not args.skip_download:
        for n in range(1,40):
            print(f'[DOWNLOAD] Glifo vettoriale {n:02d}/39',flush=True)
            download_svg(n,force=args.force_download)
    build_font()

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(f'ERRORE: {e}',file=sys.stderr)
        sys.exit(1)
