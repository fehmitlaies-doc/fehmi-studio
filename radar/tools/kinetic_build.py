# Format « Mots » (9:16) : la voix s'affiche mot à mot en très gros, un pictogramme simple illustre chaque idée,
# chapitres numérotés en haut avec barre de progression. Fond noir, une seule couleur d'accent.
# Usage : python3 kinetic_build.py <dossier>
#   <dossier>/job.json  {lang, accent, chapters:[], plans:[{say, ch, hot:[], picto:{t, ...}}], music}
#   <dossier>/assets/voice.m4a + transcript.json (mots horodatés)
# Sortie : index.html, assets/mix.m4a
import json, os, re, sys, subprocess, unicodedata, difflib, html as H

D = sys.argv[1]
W, HT = 1080, 1920
job = json.load(open(f'{D}/job.json'))
AR = job.get('lang') == 'ar'
ACC = '#E5484D' if job.get('accent') == 'rouge' else '#F2A541'
plans = [p for p in job.get('plans', []) if str(p.get('say', '')).strip()]
CH = [str(c) for c in job.get('chapters') or []]
esc = lambda s: H.escape(str(s or ''))
probe = lambda f: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode())

def norm(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\W_]+', '', s)

# 1. mots du script calés sur la voix réelle
words = []
for pi, p in enumerate(plans):
    for w in str(p['say']).split():
        if words and words[-1]['p'] == pi and re.fullmatch(r'[?!:;»…؟،.,]+', w): words[-1]['t'] += ' ' + w
        else: words.append({'t': w, 'p': pi})
VOICE = os.path.exists(f'{D}/assets/voice.m4a')
if not VOICE:  # texte seul : rythme de lecture
    t = .3
    for i, w in enumerate(words):
        if i and w['p'] != words[i - 1]['p']: t += .55
        w['s'], w['e'] = t, t + .3; t += .38 if len(w['t']) < 8 else .5
    dur = t + .4
else: dur = probe(f'{D}/assets/voice.m4a')
try: asr = [w for w in json.load(open(f'{D}/assets/transcript.json')) if str(w.get('text', '')).strip()]
except Exception: asr = []
A, B = [norm(w['t']) for w in words], [norm(x['text']) for x in asr] if VOICE else []
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
    if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
        for k in range(i2 - i1): words[i1 + k]['s'], words[i1 + k]['e'] = asr[j1 + k]['start'], asr[j1 + k]['end']
    elif tag == 'replace' and i2 > i1 and j2 > j1:
        s0, e0, n = asr[j1]['start'], asr[j2 - 1]['end'], i2 - i1
        for k in range(n): words[i1 + k]['s'], words[i1 + k]['e'] = s0 + (e0 - s0) * k / n, s0 + (e0 - s0) * (k + 1) / n
if VOICE and not any('s' in w for w in words):
    for k, w in enumerate(words): w['s'], w['e'] = .2 + (dur - .4) * k / len(words), .2 + (dur - .4) * (k + 1) / len(words)
for i, w in enumerate(words):
    if 's' not in w:
        prev = next((words[j]['e'] for j in range(i - 1, -1, -1) if 'e' in words[j]), .1)
        w['s'], w['e'] = prev, prev + .25
for a, b in zip(words, words[1:]):  # toujours croissant
    if b['s'] < a['s']: b['s'] = a['s']
    if b['e'] < b['s'] + .05: b['e'] = b['s'] + .05
END = dur + .9
starts = [next(w['s'] for w in words if w['p'] == pi) for pi in range(len(plans))]
starts[0] = 0
ends = starts[1:] + [END - .2]

# 2. découpage en blocs de 1 à 2 mots (les petits mots restent collés au mot suivant)
SMALL = set('le la les un une des de du d l à au aux et ou en ce ça je tu il on ne n se s y que qu ton ta tes ma mon mes sa son ses'.split()) | set('و في من على إلى أن لا ما'.split())
chunks, cur = [], []
for w in words:
    if cur and (cur[-1]['p'] != w['p'] or len(cur) >= 2 and norm(cur[-1]['t']) not in SMALL): chunks.append(cur); cur = []
    cur.append(w)
    if re.search(r'[.?!؟…:]$', w['t']) or (len(cur) >= 2 and norm(cur[0]['t']) not in SMALL and norm(w['t']) not in SMALL): chunks.append(cur); cur = []
if cur: chunks.append(cur)
HOT = [{norm(x) for h in p.get('hot', []) for x in str(h).split() if len(norm(x)) > 2} for p in plans]
is_hot = lambda w: (k := norm(w['t'])) and any(k == h or (len(h) > 3 and k.startswith(h)) for h in HOT[w['p']])

# 3. styles
BIG = '"Cairo"' if AR else '"Anton"'
css = f'''
@font-face{{font-family:"Anton";src:url("assets/Anton.woff2") format("woff2")}}
@font-face{{font-family:"Mono";src:url("assets/Mono.ttf") format("truetype")}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-ar.ttf") format("truetype");unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-la.ttf") format("truetype");unicode-range:U+0000-024F,U+2000-206F,U+20AC}}
#root{{position:relative;width:{W}px;height:{HT}px;overflow:hidden;background:#0A090C}}
.vig{{position:absolute;inset:0;background:radial-gradient(ellipse 75% 55% at 50% 45%,rgba(40,34,46,.55),rgba(10,9,12,0) 70%)}}
.flash{{position:absolute;inset:0;background:{ACC};opacity:0}}
.chl{{position:absolute;left:70px;top:150px;font-family:"Mono";font-size:30px;letter-spacing:.22em;color:rgba(246,242,234,.8);opacity:0;direction:ltr}}
.chl b{{display:inline-block;width:14px;height:14px;background:{ACC};margin-right:14px;vertical-align:1px}}
.bar{{position:absolute;left:70px;right:70px;top:200px;height:3px;background:rgba(246,242,234,.15)}}
.bar i{{position:absolute;left:0;top:0;bottom:0;width:100%;background:{ACC};transform-origin:0 50%;transform:scaleX(0)}}
.pic{{position:absolute;left:{(W - 560) // 2}px;top:430px;width:560px;height:560px;opacity:0}}
.pic svg{{width:100%;height:100%;overflow:visible}}
.ring{{position:absolute;left:{W // 2 - 260}px;top:{1210 - 260}px;width:520px;height:520px;border-radius:50%;border:4px solid {ACC};opacity:0}}
.w{{position:absolute;left:40px;right:40px;top:1080px;height:260px;display:flex;align-items:center;justify-content:center;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{BIG};font-weight:{800 if AR else 400};line-height:1;color:#F6F2EA;text-transform:uppercase;opacity:0;white-space:nowrap}}
.w span span.hot{{color:{ACC}}}
.src{{position:absolute;left:0;right:0;top:1010px;text-align:center;font-family:"Mono";font-size:22px;letter-spacing:.16em;color:{ACC};opacity:0}}
.wm{{position:absolute;left:0;right:0;top:1790px;text-align:center;font-family:"Mono";font-size:20px;letter-spacing:.5em;color:rgba(246,242,234,.25)}}
'''
h = [f'<!DOCTYPE html><html lang="{"ar" if AR else "fr"}"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>{css}</style></head><body>',
     f'<div id="root" data-composition-id="main" data-width="{W}" data-height="{HT}" data-start="0" data-duration="{END:.2f}">',
     f'<audio id="mix" data-start="0" data-duration="{END:.2f}" data-track-index="1" src="assets/mix.m4a"></audio>',
     '<div class="vig"></div><div class="flash" id="flash"></div><div class="bar"><i id="prog"></i></div><div class="ring" id="ring"></div>']
js = ['window.__timelines=window.__timelines||{};var tl=gsap.timeline({paused:true});', f'tl.to("#prog",{{scaleX:1,duration:{END:.2f},ease:"none"}},0);']
SFX = []

# 4. chapitres : étiquette « 01 TITRE », flash à chaque changement
chs = []
for i, p in enumerate(plans):
    c = int(p.get('ch', 0))
    if not chs or chs[-1][0] != c: chs.append((c, starts[i]))
for n, (c, t0) in enumerate(chs):
    t1 = chs[n + 1][1] if n + 1 < len(chs) else END
    h.append(f'<div class="chl" id="chl{n}"><b></b>{c + 1:02d} · {esc(CH[c] if c < len(CH) else "")}</div>')
    js.append(f'tl.fromTo("#chl{n}",{{opacity:0,x:-20}},{{opacity:1,x:0,duration:.35}},{t0:.2f});tl.set("#chl{n}",{{opacity:0}},{t1:.2f});')
    if n:
        js.append(f'tl.fromTo("#flash",{{opacity:.35}},{{opacity:0,duration:.35,immediateRender:false}},{t0:.2f});')
        SFX.append(('whoosh', max(0, t0 - .1), -18))

# 5. pictogrammes (dessinés en SVG, 560×560), un par idée
WH, AC = '#F6F2EA', ACC
def fig(x, y, s=1, fill=WH, extra=''):
    return f'<g transform="translate({x},{y}) scale({s})" {extra}><circle cx="0" cy="-95" r="38" fill="{fill}"/><rect x="-52" y="-48" width="104" height="150" rx="36" fill="{fill}"/><rect x="-44" y="92" width="36" height="90" rx="16" fill="{fill}"/><rect x="8" y="92" width="36" height="90" rx="16" fill="{fill}"/></g>'
def picto(i, p, a, b):
    P = p.get('picto') or {}; t = P.get('t'); u = f'p{i}'; d = b - a
    if t == 'figures':
        n = max(2, min(5, int(P.get('n', 3)))); gap = 480 / n
        s = ''.join(fig(40 + gap * (k + .5), 300, .75, extra=f'id="{u}f{k}"') for k in range(n))
        for k in range(n): js.append(f'tl.from("#{u}f{k}",{{y:"+=40",opacity:0,duration:.3,ease:"back.out(2)"}},{a + .1 + k * .12:.2f});')
        return s
    if t == 'figure':
        s = (f'<defs><clipPath id="{u}c"><rect id="{u}r" x="-80" y="200" width="160" height="0"/></clipPath></defs><g transform="translate(280,270)">'
             + fig(0, 0, 1.25) + f'<g clip-path="url(#{u}c)">' + fig(0, 0, 1.25, AC) + '</g></g>')
        js.append(f'tl.fromTo("#{u}r",{{attr:{{y:240,height:0}}}},{{attr:{{y:-180,height:420}},duration:{max(.8, d * .7):.2f},ease:"power2.in"}},{a + .3:.2f});')
        return s
    if t == 'face':
        mood = P.get('mood', 'neutral'); mouth = {'sad': 'M-60,70 Q0,30 60,70', 'tears': 'M-60,70 Q0,30 60,70', 'shock': 'M-25,55 Q0,95 25,55 Q0,35 -25,55'}.get(mood, 'M-60,55 L60,55')
        s = (f'<g transform="translate(250,280)"><circle r="170" fill="{WH}"/><circle cx="-60" cy="-30" r="20" fill="#0A090C"/><circle cx="60" cy="-30" r="20" fill="#0A090C"/>'
             f'<path d="{mouth}" stroke="#0A090C" stroke-width="12" fill="none" stroke-linecap="round"/>')
        if mood == 'tears':
            for k, x in enumerate((-60, 60)):
                s += f'<path id="{u}t{k}" d="M{x},0 q-14,26 0,40 q14,-14 0,-40z" fill="{AC}" opacity="0"/>'
                js.append(f'tl.fromTo("#{u}t{k}",{{opacity:1,y:0}},{{opacity:0,y:120,duration:.9,repeat:{max(1, int(d / .9) - 1)},ease:"power1.in",immediateRender:false}},{a + .4 + k * .3:.2f});')
        s += '</g>' + f'<path id="{u}w" d="M440,280 l14,-30 l14,60 l14,-60 l14,60 l14,-30" stroke="{AC}" stroke-width="8" fill="none" stroke-linejoin="round"/>'
        js.append(f'tl.fromTo("#{u}w",{{scaleY:.4,transformOrigin:"50% 50%"}},{{scaleY:1.3,duration:.12,yoyo:true,repeat:{max(1, int(d / .12)) | 1},immediateRender:false}},{a + .2:.2f});')
        return s
    if t == 'gauge':
        f0, f1 = float(P.get('from', .2)), float(P.get('to', .9))
        s = (f'<path d="M80,360 A200,200 0 0 1 480,360" stroke="{WH}" stroke-width="22" fill="none" stroke-linecap="round"/>'
             f'<path d="M418,218 A200,200 0 0 1 480,360" stroke="{AC}" stroke-width="22" fill="none" stroke-linecap="round"/>'
             f'<g id="{u}n"><line x1="280" y1="360" x2="120" y2="360" stroke="{AC}" stroke-width="10" stroke-linecap="round"/></g><circle cx="280" cy="360" r="22" fill="{WH}"/>'
             f'<text x="80" y="420" fill="{WH}" font-family="Mono" font-size="24" text-anchor="middle">{esc(P.get("l", ""))}</text><text x="480" y="420" fill="{AC}" font-family="Mono" font-size="24" text-anchor="middle">{esc(P.get("r", ""))}</text>')
        js.append(f'tl.fromTo("#{u}n",{{rotation:{f0 * 180:.0f},svgOrigin:"280 360"}},{{rotation:{f1 * 180:.0f},svgOrigin:"280 360",duration:{max(.8, d * .75):.2f},ease:"power2.inOut",immediateRender:true}},{a + .2:.2f});')
        return s
    if t == 'heart':
        s = f'<g id="{u}h" transform="translate(280,290)"><path d="M0,90 C-170,-20 -110,-170 0,-80 C110,-170 170,-20 0,90z" fill="{AC}"/></g>'
        js.append(f'tl.to("#{u}h",{{scale:1.12,transformOrigin:"50% 50%",duration:.18,yoyo:true,repeat:{max(1, int(d / .36) * 2 - 1)},ease:"power1.inOut"}},{a + .2:.2f});')
        SFX.append(('heartbeat', a + .2, -16))
        return s
    if t == 'bubble':
        txt = esc(P.get('text', ''))[:28]; fs = 64 if len(txt) < 12 else 46 if len(txt) < 20 else 36
        return (f'<path d="M60,120 h440 a30,30 0 0 1 30,30 v170 a30,30 0 0 1 -30,30 h-300 l-70,70 v-70 h-70 a30,30 0 0 1 -30,-30 v-170 a30,30 0 0 1 30,-30z" fill="none" stroke="{WH}" stroke-width="10"/>'
                f'<text x="280" y="250" fill="{AC}" font-family="{"Cairo" if AR else "Anton"}" font-size="{fs}" text-anchor="middle" dominant-baseline="middle">{txt}</text>')
    if t == 'brain':
        s = (f'<g transform="translate(280,280)" fill="none" stroke="{WH}" stroke-width="10" stroke-linecap="round">'
             '<path d="M0,-150 C-80,-175 -175,-120 -170,-30 C-205,20 -170,110 -90,120 C-60,160 -10,150 0,120"/>'
             '<path d="M0,-150 C80,-175 175,-120 170,-30 C205,20 170,110 90,120 C60,160 10,150 0,120"/>'
             '<path d="M0,-150 V120"/><path d="M-120,-60 C-80,-40 -60,-80 -30,-60"/><path d="M120,-60 C80,-40 60,-80 30,-60"/></g>'
             f'<circle id="{u}a" cx="225" cy="330" r="34" fill="{AC}"/><circle id="{u}g" cx="225" cy="330" r="34" fill="none" stroke="{AC}" stroke-width="6"/>')
        js.append(f'tl.fromTo("#{u}g",{{scale:1,opacity:.9,svgOrigin:"225 330"}},{{scale:3,opacity:0,svgOrigin:"225 330",duration:.9,repeat:1,immediateRender:false}},{a + .3:.2f});')
        js.append(f'tl.to("#{u}a",{{opacity:.25,duration:{max(.6, d * .5):.2f}}},{a + d * .45:.2f});')
        if P.get('src'): h.append(f'<div class="src" id="{u}s">{esc(P["src"])}</div>'); js.append(f'tl.fromTo("#{u}s",{{opacity:0}},{{opacity:1,duration:.3}},{a + .4:.2f});tl.set("#{u}s",{{opacity:0}},{b:.2f});')
        return s
    if t == 'clock':
        s = (f'<circle cx="280" cy="280" r="190" fill="none" stroke="{WH}" stroke-width="14"/>' + ''.join(f'<line x1="280" y1="110" x2="280" y2="135" stroke="{WH}" stroke-width="8" transform="rotate({k * 30} 280 280)"/>' for k in range(12))
             + f'<line id="{u}m" x1="280" y1="280" x2="280" y2="140" stroke="{AC}" stroke-width="12" stroke-linecap="round"/><line x1="280" y1="280" x2="370" y2="280" stroke="{WH}" stroke-width="12" stroke-linecap="round"/><circle cx="280" cy="280" r="16" fill="{AC}"/>')
        if P.get('text'): s += f'<text x="280" y="530" fill="{AC}" font-family="Anton" font-size="56" text-anchor="middle">{esc(P["text"])[:14]}</text>'
        js.append(f'tl.to("#{u}m",{{rotation:360,svgOrigin:"280 280",duration:{max(.8, d):.2f},ease:"none"}},{a:.2f});'); SFX.append(('tick', a + .2, -20))
        return s
    if t == 'phone':
        s = (f'<rect x="170" y="70" width="220" height="420" rx="36" fill="none" stroke="{WH}" stroke-width="14"/><rect x="195" y="110" width="170" height="320" rx="10" fill="{AC}" opacity=".18"/>'
             + ''.join(f'<rect id="{u}n{k}" x="205" y="{125 + k * 70}" width="150" height="52" rx="12" fill="{AC if k == 0 else WH}" opacity="0"/>' for k in range(4)))
        for k in range(4): js.append(f'tl.fromTo("#{u}n{k}",{{opacity:0,x:-30}},{{opacity:.95,x:0,duration:.2,immediateRender:false}},{a + .2 + k * min(.4, d / 5):.2f});')
        SFX.append(('phone', a + .2, -20)); return s
    if t == 'shield':
        s = (f'<path d="M280,60 L460,130 V270 C460,390 370,470 280,510 C190,470 100,390 100,270 V130 Z" fill="none" stroke="{WH}" stroke-width="14" stroke-linejoin="round"/>'
             f'<path id="{u}c" d="M190,280 L255,345 L380,215" fill="none" stroke="{AC}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="320" stroke-dashoffset="320"/>')
        js.append(f'tl.to("#{u}c",{{strokeDashoffset:0,duration:.5,ease:"power2.out"}},{a + .35:.2f});'); return s
    if t == 'bolt':
        s = f'<path id="{u}b" d="M320,40 L150,300 H270 L230,520 L420,230 H300 Z" fill="{AC}"/>'
        js.append(f'tl.fromTo("#{u}b",{{opacity:.2}},{{opacity:1,duration:.08,yoyo:true,repeat:5,immediateRender:false}},{a + .15:.2f});'); SFX.append(('impact', a + .15, -18)); return s
    if t == 'weight':
        s = (f'<g id="{u}w"><path d="M210,170 a70,60 0 0 1 140,0" fill="none" stroke="{WH}" stroke-width="22"/><path d="M130,200 H430 L470,470 H90 Z" fill="{WH}"/>'
             f'<text x="280" y="360" fill="#0A090C" font-family="{"Cairo" if AR else "Anton"}" font-size="{60 if len(str(P.get("text", ""))) < 9 else 42}" text-anchor="middle">{esc(P.get("text", ""))[:14]}</text></g>')
        js.append(f'tl.fromTo("#{u}w",{{y:-300}},{{y:0,duration:.35,ease:"power3.in",immediateRender:false}},{a + .05:.2f});'); SFX.append(('impact', a + .38, -14)); return s
    if t == 'times':
        return f'<text x="280" y="330" fill="{AC}" font-family="Anton" font-size="260" text-anchor="middle">{esc(P.get("text", "×10"))[:5]}</text>'
    if t == 'number':
        return f'<text x="280" y="360" fill="{WH}" font-family="Anton" font-size="340" text-anchor="middle">{esc(P.get("text", "3"))[:4]}</text>'
    if t == 'check':
        items = [str(x)[:22] for x in (P.get('items') or ['', '', ''])][:3]; s = ''
        for k, it in enumerate(items):
            y = 120 + k * 140
            s += (f'<g id="{u}i{k}" opacity="0"><rect x="40" y="{y}" width="90" height="90" rx="16" fill="none" stroke="{WH}" stroke-width="10"/><path d="M60,{y + 45} L82,{y + 68} L118,{y + 22}" fill="none" stroke="{AC}" stroke-width="14" stroke-linecap="round"/>'
                  f'<text x="160" y="{y + 62}" fill="{WH}" font-family="{"Cairo" if AR else "Anton"}" font-size="52">{esc(it)}</text></g>')
            js.append(f'tl.to("#{u}i{k}",{{opacity:1,duration:.2}},{a + .2 + k * max(.35, d / 4):.2f});'); SFX.append(('pop', a + .2 + k * max(.35, d / 4), -20))
        return s
    if t == 'battery':
        f0, f1 = float(P.get('from', .9)), float(P.get('to', .1))
        s = (f'<rect x="80" y="170" width="380" height="220" rx="30" fill="none" stroke="{WH}" stroke-width="16"/><rect x="460" y="230" width="34" height="100" rx="10" fill="{WH}"/>'
             f'<rect id="{u}l" x="104" y="194" width="{332 * f0:.0f}" height="172" rx="16" fill="{AC}"/>')
        js.append(f'tl.to("#{u}l",{{attr:{{width:{max(10, 332 * f1):.0f}}},duration:{max(.8, d * .7):.2f},ease:"power1.inOut"}},{a + .2:.2f});'); return s
    if t == 'moon':
        s = f'<path d="M330,90 A190,190 0 1 0 470,380 A150,150 0 1 1 330,90 Z" fill="{WH}"/>' + ''.join(f'<text id="{u}z{k}" x="{380 + k * 40}" y="{170 - k * 50}" fill="{AC}" font-family="Anton" font-size="{50 + k * 14}" opacity="0">Z</text>' for k in range(3))
        for k in range(3): js.append(f'tl.fromTo("#{u}z{k}",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,immediateRender:false}},{a + .3 + k * .3:.2f});')
        return s
    if t == 'cloud':
        s = f'<path d="M140,300 a90,90 0 0 1 40,-170 a110,110 0 0 1 200,10 a80,80 0 0 1 40,160 Z" fill="{WH}"/>' + ''.join(f'<line id="{u}r{k}" x1="{170 + k * 55}" y1="330" x2="{150 + k * 55}" y2="390" stroke="{AC}" stroke-width="10" stroke-linecap="round"/>' for k in range(5))
        for k in range(5): js.append(f'tl.fromTo("#{u}r{k}",{{y:0,opacity:1}},{{y:120,opacity:0,duration:.6,repeat:{max(1, int(d / .6) - 1)},ease:"none",immediateRender:false}},{a + k * .12:.2f});')
        return s
    if t == 'arrow':
        up = P.get('dir', 'up') != 'down'
        s = f'<g id="{u}a" transform="rotate({0 if up else 180} 280 280)"><path d="M280,60 L460,280 H350 V500 H210 V280 H100 Z" fill="{AC}"/></g>'
        js.append(f'tl.fromTo("#{u}a",{{y:{60 if up else -60}}},{{y:0,duration:.4,ease:"back.out(2)",immediateRender:false}},{a + .05:.2f});'); return s
    if t == 'breath':
        s = f'<circle id="{u}o" cx="280" cy="280" r="120" fill="{AC}" opacity=".85"/><circle cx="280" cy="280" r="230" fill="none" stroke="{WH}" stroke-width="6" opacity=".4"/>'
        js.append(f'tl.fromTo("#{u}o",{{attr:{{r:110}}}},{{attr:{{r:220}},duration:2,yoyo:true,repeat:{max(1, int(d / 2)) | 1},ease:"sine.inOut",immediateRender:false}},{a + .2:.2f});'); SFX.append(('breath', a + .2, -18)); return s
    if t == 'cross':
        s = f'<g id="{u}x" stroke="{"#E5484D"}" stroke-width="40" stroke-linecap="round"><line x1="130" y1="130" x2="430" y2="430"/><line x1="430" y1="130" x2="130" y2="430"/></g>'
        if P.get('text'): s += f'<text x="280" y="530" fill="{WH}" font-family="{"Cairo" if AR else "Anton"}" font-size="56" text-anchor="middle" text-decoration="line-through">{esc(P["text"])[:16]}</text>'
        js.append(f'tl.fromTo("#{u}x",{{scale:1.6,opacity:0,svgOrigin:"280 280"}},{{scale:1,opacity:1,svgOrigin:"280 280",duration:.25,ease:"back.out(2)",immediateRender:false}},{a + .2:.2f});'); SFX.append(('impact', a + .3, -16)); return s
    return fig(280, 300, 1)
for i, p in enumerate(plans):
    a, b = starts[i], ends[i]
    h.append(f'<div class="pic" id="pic{i}"><svg viewBox="0 0 560 560">{picto(i, p, a, b)}</svg></div>')
    js.append(f'tl.fromTo("#pic{i}",{{opacity:0,scale:.7}},{{opacity:1,scale:1,duration:.35,ease:"back.out(1.8)"}},{a + .02:.2f});tl.to("#pic{i}",{{scale:1.06,duration:{max(.4, b - a - .4):.2f},ease:"sine.inOut"}},{a + .37:.2f});tl.set("#pic{i}",{{opacity:0}},{b:.2f});')
    SFX.append(('pop', a + .05, -24))

# 6. les mots, calés sur la voix
for gi, g in enumerate(chunks):
    txt = ' '.join(f'<span class="hot">{esc(w["t"])}</span>' if is_hot(w) else esc(w['t']) for w in g)
    raw = ' '.join(w['t'] for w in g)
    fs = min(170 if not AR else 130, int(1000 / max(1, len(raw) * (.47 if not AR else .55))))
    h.append(f'<div class="w" id="w{gi}" style="font-size:{fs}px"><span>{txt}</span></div>')  # un seul enfant : les espaces restent
    s0 = g[0]['s']; nxt = min([x[0]['s'] for x in chunks[gi + 1:]] + [END])
    e0 = min(max(g[-1]['e'] + .25, s0 + .35), nxt)
    if e0 - s0 < .08: continue
    js.append(f'tl.fromTo("#w{gi}",{{opacity:0,scale:1.18}},{{opacity:1,scale:1,duration:.12,ease:"power2.out"}},{s0:.2f});tl.set("#w{gi}",{{opacity:0}},{e0:.2f});')
    if any(is_hot(w) for w in g):
        js.append(f'tl.fromTo("#ring",{{opacity:.8,scale:.4}},{{opacity:0,scale:1.2,duration:.6,ease:"power2.out",immediateRender:false}},{s0:.2f});')
h.append('<div class="wm">' + ('د. فهمي' if AR else 'DR FEHMI') + '</div>')
js.append('window.__timelines["main"]=tl;')
h.append('</div><script>' + '\n'.join(js) + '</script></body></html>')
open(f'{D}/index.html', 'w').write('\n'.join(h))

# 7. mixage : voix + musique discrète + effets
Aa = f'{D}/assets'; music = job.get('music') or 'tension'
inp, fc, lab = (['-i', f'{Aa}/voice.m4a'], ['[0:a]apad[v]'], ['[v]']) if VOICE else ([], [], [])
if music != 'none' and os.path.exists(f'{Aa}/music_{music}.m4a'):
    mi = len([x for x in inp if x == '-i']); inp += ['-stream_loop', '-1', '-i', f'{Aa}/music_{music}.m4a']
    fc.append(f'[{mi}:a]atrim=0:{END:.2f},volume={-22 if VOICE else -13}dB,afade=t=in:d=1,afade=t=out:st={END - 2:.2f}:d=2[m]'); lab.append('[m]')
for s, t, g in SFX:
    if not os.path.exists(f'{Aa}/sfx_{s}.m4a') or t >= END: continue
    i = len([x for x in inp if x == '-i']); inp += ['-i', f'{Aa}/sfx_{s}.m4a']
    fc.append(f'[{i}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={g}dB[x{i}]'); lab.append(f'[x{i}]')
fc.append(''.join(lab) + f'amix=inputs={len(lab)}:normalize=0,atrim=0:{END:.2f}[out]')
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{Aa}/mix.m4a'], check=True)
print('mots', len(words), 'blocs', len(chunks), 'idées', len(plans), 'durée', round(END, 2))
