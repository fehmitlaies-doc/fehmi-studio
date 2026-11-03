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
dur = probe(f'{D}/assets/voice.m4a')
try: asr = [w for w in json.load(open(f'{D}/assets/transcript.json')) if str(w.get('text', '')).strip()]
except Exception: asr = []
A, B = [norm(w['t']) for w in words], [norm(x['text']) for x in asr]
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
    if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
        for k in range(i2 - i1): words[i1 + k]['s'], words[i1 + k]['e'] = asr[j1 + k]['start'], asr[j1 + k]['end']
    elif tag == 'replace' and i2 > i1 and j2 > j1:
        s0, e0, n = asr[j1]['start'], asr[j2 - 1]['end'], i2 - i1
        for k in range(n): words[i1 + k]['s'], words[i1 + k]['e'] = s0 + (e0 - s0) * k / n, s0 + (e0 - s0) * (k + 1) / n
if not any('s' in w for w in words):
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
    return fig(280, 300, 1)
for i, p in enumerate(plans):
    a, b = starts[i], ends[i]
    h.append(f'<div class="pic" id="pic{i}"><svg viewBox="0 0 560 560">{picto(i, p, a, b)}</svg></div>')
    js.append(f'tl.fromTo("#pic{i}",{{opacity:0,scale:.7}},{{opacity:1,scale:1,duration:.35,ease:"back.out(1.8)"}},{a + .02:.2f});tl.set("#pic{i}",{{opacity:0}},{b:.2f});')
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
inp, fc, lab = ['-i', f'{Aa}/voice.m4a'], ['[0:a]apad[v]'], ['[v]']
if music != 'none' and os.path.exists(f'{Aa}/music_{music}.m4a'):
    inp += ['-stream_loop', '-1', '-i', f'{Aa}/music_{music}.m4a']
    fc.append(f'[1:a]atrim=0:{END:.2f},volume=-22dB,afade=t=in:d=1,afade=t=out:st={END - 2:.2f}:d=2[m]'); lab.append('[m]')
for s, t, g in SFX:
    if not os.path.exists(f'{Aa}/sfx_{s}.m4a') or t >= END: continue
    i = len([x for x in inp if x == '-i']); inp += ['-i', f'{Aa}/sfx_{s}.m4a']
    fc.append(f'[{i}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={g}dB[x{i}]'); lab.append(f'[x{i}]')
fc.append(''.join(lab) + f'amix=inputs={len(lab)}:normalize=0,atrim=0:{END:.2f}[out]')
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{Aa}/mix.m4a'], check=True)
print('mots', len(words), 'blocs', len(chunks), 'idées', len(plans), 'durée', round(END, 2))
