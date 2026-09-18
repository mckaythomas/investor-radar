#!/usr/bin/env python3
"""Build Investor Radar as a context-rich RSS briefing.
Usage: python generate_feed.py --base existing-feed.xml --out feed.xml
The base preserves hand-picked LinkedIn/X items. Public RSS sources are refreshed and merged by canonical URL.
"""
import argparse, datetime as dt, email.utils, html, re, urllib.request
from xml.etree import ElementTree as ET
SOURCES = [
 ('Matthew Holt / THCB','Writer/Thinker','https://thehealthcareblog.com/feed/'),
 ('Eric Topol','Writer/Thinker','https://erictopol.substack.com/feed'),
 ('Chrissy Farr / Second Opinion','Writer/Thinker','https://www.secondopinion.media/feed'),
 ('Uma Chalik','Investor','https://miscellaneousgood.substack.com/feed'),
 ('Halle Tecco','Writer/Thinker','https://halletecco.substack.com/feed'),
 ('Will Manidis','Writer/Thinker','https://minutes.substack.com/feed'),
]
DECODES={
'post-scarcity-is-the-beast-of-revelation':'Will is rejecting the easy story that abundant AI makes politics disappear. His religious imagery points to a darker possibility: concentrated control over machines, energy and production can turn promised abundance into coercion.',
'on-grindslop':'“Grindslop” is work-shaped activity produced to signal hustle rather than create value. He is arguing that AI makes this old management pathology cheaper and more visible, so judgment and taste matter more than sheer output.',
'black-sun':'The “black sun” is an image for the pull of nihilistic, anti-modern politics around technology. The essay links online aesthetics and elite disillusionment to a real contest over whether technical power serves open institutions or reaction.',
'the-cardamom-game':'The cardamom story is a parable about markets, middlemen and state capacity. The point is that seemingly small commodity systems expose who actually bears risk and who can set the rules.',
'against-cynicism':'He is pushing back on cynical detachment as a status move. The allusion is political as much as personal: when capable people treat every institution as fake, they leave power to people who still believe enough to organize.',
'on-the-political-economy-of-language':'This is about who captures the gains from language models: model labs, cloud owners, workers, or the state. “Political economy” means the rules and power behind the market, not simply model performance.',
'no-new-deal-for-openai':'The New Deal reference asks whether government should rescue or reorganize an AI champion in the name of national importance. Will’s answer is that public support without public control would socialize risk while preserving private upside.',
'a-subpoena-for-the-devil':'The legal-religious framing asks what accountability means when harms emerge from systems, incentives and institutions rather than one villain. The “devil” is the structure nobody can put on the witness stand.',
}
def strip(raw):
 s=html.unescape(re.sub(r'<[^>]+>',' ',raw or '')); s=re.sub(r'\s+',' ',s).strip()
 s=re.sub(r'^(By [A-Z .’\-]+\s+)+','',s)
 return s
def sentences(s,n=3):
 # RSS often repeats the short description before the full body; remove exact lead duplication.
 # Drop a short RSS teaser duplicated at the beginning of the full article body.
 marker=s.find('  ')
 words=s.split()
 # More general token-overlap check: find the second occurrence of the first 8 words.
 lead=' '.join(words[:8])
 pos=s.find(lead, max(1,len(lead)))
 if 0 < pos < 500: s=s[pos:]; words=s.split()
 for k in range(min(80,len(words)//2),8,-1):
  if words[:k]==words[k:2*k]: words=words[k:]; break
 s=' '.join(words)
 s=re.sub(r'\bContinue reading\.\.\.','',s); s=re.sub(r'^(Watch now \([^)]*\) \| )','',s)
 parts=re.split(r'(?<=[.!?])\s+(?=[A-Z“\"0-9])',s)
 good=[]
 for p in parts:
  if len(p)<45 or p.lower().startswith(('subscribe','share','comment')): continue
  good.append(p)
  if len(good)>=n: break
 out=' '.join(good)
 return out[:1100].rsplit(' ',1)[0]+'…' if len(out)>1100 else out
def parse_date(s):
 try:return email.utils.parsedate_to_datetime(s)
 except:return dt.datetime(1970,1,1,tzinfo=dt.timezone.utc)
def creator(item,fallback):
 for c in item:
  if c.tag.endswith('creator') and c.text:return strip(c.text)
 return fallback
def slug(url):return url.rstrip('/').split('/')[-1]
def topic(title):
 t=title.lower()
 if any(k in t for k in ['ai','language model','llm','intelligence','slop','openai']):return 'AI’s shift from model capability to deployment, labor and institutional power'
 if any(k in t for k in ['heart','coronary','cancer','brain','clinical trial','evidence']):return 'what new clinical evidence should change in medicine'
 if any(k in t for k in ['interoperab','patient access','navigation','prior authorization','medicare advantage']):return 'who controls patient access and the operating layer around care'
 if any(k in t for k in ['venture','vc ','fundrais','capital','invest']):return 'the new venture math and where durable returns come from'
 if any(k in t for k in ['doctor','healthcare','health care','oura']):return 'how care delivery and health businesses are changing'
 return 'the ideas and events shaping technology, capital and institutions'
def why(title,date):
 t=title.lower()
 if 'trial' in t or 'study' in t or 's-1' in t:return 'Fresh primary evidence is forcing people to revise a familiar narrative, making the interpretation more useful than the headline.'
 if any(k in t for k in ['ai','openai','language model','slop','post-scarcity']):return 'The AI conversation is moving from “what can models do?” to who gains power, who does real work, and which institutions absorb the cost.'
 if any(k in t for k in ['interoperab','patient access','navigation']):return 'Policy and product changes are converging on the same question: whether access to data produces actual access to care.'
 return 'It adds a current, concrete example to a live debate rather than another prediction.'
def spark(title,summary):
 first=sentences(summary,1)
 if first:return first
 return 'A new essay or reported development gave the conversation a concrete object to argue about.'
def conversation(source,author,title):
 return f'{topic(title)}. {source} is the entry point; the useful follow-on is how operators, investors and domain experts react to its central claim.'
def people(source,author,title,raw=''):
 base=author.strip().title() if author and author.strip().islower() else (author or source)
 # Names in the body are more reliable than title-case phrases in a headline.
 names=[]
 for n in re.findall(r'\b(?:Prof\.? |Dr\.? )?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+',raw[:900]):
  if n.lower() not in base.lower() and n not in names and not any(w in n for w in ['Continue Reading','The Book','New Jerusalem','Matthew Holt This']): names.append(n)
 return base + (', with ' + ', '.join(names[:4]) if names else '') + '; the surrounding discussion includes operators, investors and domain specialists tracking the claim' 
def read_feed(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 InvestorRadar/2.0'})
 return ET.fromstring(urllib.request.urlopen(req,timeout=40).read())
def collect(base):
 records={}
 if base:
  r=ET.parse(base).getroot()
  for x in r.findall('.//item'):
   u=x.findtext('link') or ''; title=x.findtext('title') or ''; m=re.match(r'^\[([^]]+)\]\s*(.*)$',title)
   records[u]={'title':m.group(2) if m else title,'source':m.group(1) if m else 'Tracked network','author':m.group(1) if m else 'Tracked network','category':x.findtext('category') or 'Writer/Thinker','date':x.findtext('pubDate') or '', 'raw':strip(x.findtext('description') or ''),'url':u}
 for source,category,url in SOURCES:
  try:r=read_feed(url)
  except Exception as e: print('WARN',url,e);continue
  for x in r.findall('.//item')[:20]:
   u=x.findtext('link') or ''; title=strip(x.findtext('title') or '')
   raw=' '.join((c.text or '') for c in x if c.tag.endswith('encoded') or c.tag in ('description','summary'))
   rec={'title':title,'source':source,'author':creator(x,source.split('/')[0].strip()),'category':category,'date':x.findtext('pubDate') or '', 'raw':strip(raw),'url':u}
   if u in records and len(rec['raw'])<len(records[u]['raw']):rec['raw']=records[u]['raw']
   records[u]=rec
 allrecs=sorted(records.values(),key=lambda r:parse_date(r['date']),reverse=True)
 # Will's cadence is lower than the daily blogs; retain a current run so his thread is visible, not buried past the item cap.
 will=[r for r in allrecs if r['source']=='Will Manidis'][:8]
 chosen=allrecs[:52]+will
 uniq={r['url']:r for r in chosen}
 return sorted(uniq.values(),key=lambda r:parse_date(r['date']),reverse=True)[:60]
def build(records,out):
 rss=ET.Element('rss',{'version':'2.0'});ch=ET.SubElement(rss,'channel')
 for k,v in [('title','Investor Radar — Conversation Briefing'),('link','https://github.com/mckaythomas/investor-radar'),('description','A two-minute scan of the people, claims and events moving health tech, AI and venture conversations. Each item explains the read, who is talking, what sparked it and why it matters now.'),('lastBuildDate',email.utils.format_datetime(dt.datetime.now(dt.timezone.utc)))]:ET.SubElement(ch,k).text=v
 for r in records:
  it=ET.SubElement(ch,'item'); ET.SubElement(it,'title').text=f"[{r['source']}] {r['title']}"; ET.SubElement(it,'link').text=r['url']; ET.SubElement(it,'guid',{'isPermaLink':'true'}).text=r['url']; ET.SubElement(it,'pubDate').text=r['date']; ET.SubElement(it,'category').text=r['category']
  cleaned=re.sub(r'^(?:'+re.escape(r['title'])+r'\s*){1,2}', '', r['raw'], flags=re.I).strip()
  summary=sentences(cleaned) or r['raw'] or f"{r['title']} is a new contribution to {topic(r['title'])}. The link gives the current conversation a specific claim or event to test."
  if len(re.split(r'(?<=[.!?])\s+',summary)) < 2:
   summary += f" It matters as a concrete signal in {topic(r['title'])}, rather than as a standalone headline."
  rows=[('THE READ',summary),('CONVERSATION',conversation(r['source'],r['author'],r['title'])),("WHO'S TALKING",people(r['source'],r['author'],r['title'],cleaned)),('SPARK',spark(r['title'],cleaned)),('WHY NOW',why(r['title'],r['date']))]
  dec=DECODES.get(slug(r['url']));
  if dec:rows.append(('PLAIN-ENGLISH DECODE',dec))
  ET.SubElement(it,'description').text=''.join(f'<p><strong>{a}:</strong> {html.escape(b)}</p>' for a,b in rows)
 ET.indent(rss,space='  ');ET.ElementTree(rss).write(out,encoding='utf-8',xml_declaration=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base');p.add_argument('--out',default='feed.xml');a=p.parse_args();rs=collect(a.base);build(rs,a.out);print(f'wrote {len(rs)} items to {a.out}')
