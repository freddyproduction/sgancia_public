"""Passive PDF reports: local fonts, escaped text, no uploaded markup/resources."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from decimal import Decimal
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle

font_dir=Path(reportlab.__file__).parent/'fonts'
for name,file in (('Sgancia','Vera.ttf'),('SganciaBold','VeraBd.ttf')):
    if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(font_dir/file)))
GREEN=colors.HexColor('#145d48');PALE=colors.HexColor('#ecf2df')


def text(value):
    widths=pdfmetrics.getFont('Sgancia').face.charWidths
    value=''.join(c if c=='\n' or ord(c) in widths else f'[U+{ord(c):04X}]' for c in str(value) if ord(c)>=32 or c=='\n')
    return escape(value).replace('\n','<br/>')


def amount(value,currency):return f'{Decimal(value)/100:.2f} {currency}'


def report_pdf(data):
    output=BytesIO();styles={
        'title':ParagraphStyle('title',fontName='SganciaBold',fontSize=23,leading=29,textColor=GREEN,spaceAfter=12),
        'heading':ParagraphStyle('heading',fontName='SganciaBold',fontSize=12,leading=18,textColor=GREEN,spaceBefore=15,spaceAfter=7,keepWithNext=True),
        'body':ParagraphStyle('body',fontName='Sgancia',fontSize=9,leading=14,spaceAfter=6,splitLongWords=True),
        'cell':ParagraphStyle('cell',fontName='Sgancia',fontSize=8,leading=12,splitLongWords=True),
    }
    p=lambda value,style='body':Paragraph(text(value),styles[style])
    story=[p('sgancia.','title'),p(data['group']['name'],'heading'),p(data.get('notice','Solo dati visibili al tuo account. Questo report non sostituisce un backup.')),
           p(f"Totale spese: {amount(data['total'],data['group']['currency'])}"),'']
    story.pop()
    if data.get('finance'):
        summary=data['finance'].get('summary')
        if summary:story.append(p(f"Hai pagato: {amount(summary['paid'],data['group']['currency'])} - La tua quota: {amount(summary['owed'],data['group']['currency'])} - Da ricevere: {amount(summary['receivable'],data['group']['currency'])} - Da restituire: {amount(summary['payable'],data['group']['currency'])}"))
    rows=[[p(v,'cell') for v in ('Data','Spesa / categoria','Importo')]]
    for row in data['expenses']:
        rows.append([p(row['date'],'cell'),p(row['title']+'\n'+(row.get('category') or ''),'cell'),p(amount(row['total'],data['group']['currency']),'cell')])
    if len(rows)>1:
        table=LongTable(rows,colWidths=[65,330,100],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dfe6db'))]))
        story.extend([Spacer(1,12),table])
    else:story.append(p('Nessuna spesa nel riepilogo.'))
    detailed=[r for r in data['expenses'] if r.get('draft')]
    if detailed:story.append(p('Dettagli delle spese','heading'))
    people={p['ref']:p['name'] for p in data.get('participants',[]) if isinstance(p,dict)}
    for row in detailed:
        draft=row['draft'];story.append(p(row['title'],'heading'))
        story.append(p('Riservata alle persone selezionate' if draft.get('audience') is not None else 'Spesa pubblica'))
        if draft.get('description'):story.append(p(draft['description']))
        if draft.get('tags'):story.append(p('Tag: '+', '.join(draft['tags'])))
        conversion=row.get('conversion')
        if conversion:story.append(p(f"Cambio conservato: 1 {conversion['base']} = {conversion['rate']} {conversion['quote']} - {conversion['source']} - {conversion['date']}"))
        for index,item in enumerate(draft['items'],1):
            story.append(p(f"{index}. {item['title'] or 'Voce'}: {item['amount']} {draft.get('currency') or data['group']['currency']}"))
            for label,mapping in (('Pagatori',item.get('payers') or {}),('Quote ('+item['mode']+')',item['shares'])):
                story.append(p(label+': '+', '.join(people.get(k,k)+': '+(v or 'automatico') for k,v in mapping.items())))
    if data.get('finance'):
        story.append(p('Rimborsi ancora da effettuare','heading'))
        for row in data['finance']['transfers']:story.append(p(f"{people.get(row['from'],row['from'])} -> {people.get(row['to'],row['to'])}: {amount(row['amount'],data['group']['currency'])}"))
        if not data['finance']['transfers']:story.append(p('Nessun trasferimento residuo visibile.'))
    def footer(canvas,doc):
        canvas.setFont('Sgancia',8);canvas.setFillColor(GREEN);canvas.drawString(40,25,'Sgancia - riepilogo esportato');canvas.drawRightString(A4[0]-40,25,str(doc.page))
    SimpleDocTemplate(output,pagesize=A4,leftMargin=40,rightMargin=40,topMargin=35,bottomMargin=45,title='Sgancia - report',author='Sgancia').build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
