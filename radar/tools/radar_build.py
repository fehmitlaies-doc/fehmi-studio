# Radar — composition HyperFrames au style R7, calée sur la voix réelle.
# Usage : python3 radar_build.py <dossier>  (contient plans.json, assets/voice.*, assets/transcript.json)
import json, re, sys, os, unicodedata, difflib, subprocess, html as H

D = sys.argv[1]
W, HT = 1080, 1920
plans = json.load(open(f'{D}/plans.json'))
voice = next(f for f in os.listdir(f'{D}/assets') if f.startswith('voice.'))
asr = json.load(open(f'{D}/assets/transcript.json'))
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{D}/assets/{voice}']).decode())

KEY = {'colère', 'mâchoire', 'cœur', 'nez', 'deuxième', 'lentement', 'calme', 'frein', 'stanford', 'méditation', 'humeur', 'trois', 'professionnel', 'abonne-toi', 'longtemps'}
norm = lambda s: re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode())

# 1. mots du script (texte exact) + minutage aligné sur la transcription
words = []
for pi, p in enumerate(plans):
    for w in p['say'].split():
        if words and words[-1]['p'] == pi and re.fullmatch(r'[?!:;»]', w):
            words[-1]['t'] += '\u00a0' + w  # ponctuation française collée au mot précédent
        elif re.fullmatch(r'«', w):
            words.append({'t': w + '\u00a0', 'p': pi, 'glue': 1})
        elif words and words[-1].get('glue'):
            words[-1]['t'] += w; words[-1].pop('glue')
        else:
            words.append({'t': w, 'p': pi})
A = [norm(w['t']) for w in words]
B = [norm(x['text']) for x in asr]
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
        for k in range(i2 - i1):
            words[i1 + k]['s'], words[i1 + k]['e'] = asr[j1 + k]['start'], asr[j1 + k]['end']
    elif tag == 'replace' and j2 > j1:  # nombre différent : répartir l'intervalle
        s0, e0 = asr[j1]['start'], asr[j2 - 1]['end']
        n = i2 - i1
        for k in range(n):
            words[i1 + k]['s'], words[i1 + k]['e'] = s0 + (e0 - s0) * k / n, s0 + (e0 - s0) * (k + 1) / n
# trous : interpolation
for i, w in enumerate(words):
    if 's' not in w:
        prev = next((words[j]['e'] for j in range(i - 1, -1, -1) if 'e' in words[j]), 0.1)
        nxt = next((words[j]['s'] for j in range(i + 1, len(words)) if 's' in words[j]), dur)
        w['s'], w['e'] = prev, min(nxt, prev + 0.3)

starts = []
for pi in range(len(plans)):
    ws = [w for w in words if w['p'] == pi]
    starts.append(max(0, ws[0]['s'] - 0.2))
starts[0] = 0
END = dur + 1.6
ends = starts[1:] + [END]

# 2. groupes de sous-titres (3 mots, coupure sur ponctuation, jamais à cheval sur 2 plans)
groups, cur = [], []
for w in words:
    if cur and cur[-1]['p'] != w['p']:
        groups.append(cur); cur = []
    cur.append(w)
    if len(cur) == 3 or re.search(r'[.,:?!]$', w['t']):
        groups.append(cur); cur = []
if cur: groups.append(cur)

def word_html(t):
    k = norm(t)
    hot = any(norm(x) == k for x in KEY)
    return f'<span{" class=\"hot\"" if hot else ""}>{H.escape(t)}</span>'

css = f'''
@font-face{{font-family:"Fraunces";src:url("assets/Fraunces.ttf") format("truetype")}}
@font-face{{font-family:"Archivo";src:url("assets/Archivo.ttf") format("truetype")}}
body{{margin:0;width:{W}px;height:{HT}px;overflow:hidden;background:#17121C}}
#root{{position:relative;width:{W}px;height:{HT}px;background:#17121C;overflow:hidden;font-family:"Archivo",sans-serif}}
.ghost{{position:absolute;top:760px;left:0;white-space:nowrap;font-family:"Fraunces";font-size:520px;line-height:1;color:#F6EEE3;opacity:.04}}
.halo{{position:absolute;left:140px;top:470px;width:800px;height:800px;border-radius:50%;background:radial-gradient(circle,rgba(242,165,65,.30),rgba(242,165,65,.10) 40%,rgba(242,165,65,0) 68%)}}
.sig{{position:absolute;top:120px;left:110px;right:110px;text-align:center;font-family:"Archivo";font-size:30px;letter-spacing:4px;text-transform:uppercase;color:#A89AA6}}
.ttl{{position:absolute;top:190px;left:110px;right:110px;text-align:center;font-family:"Fraunces";font-size:78px;line-height:1.05;color:#F6EEE3;opacity:0}}
.ill{{position:absolute;left:150px;top:440px;width:780px;height:780px;opacity:0}}
.ill img{{width:100%;height:100%;display:block;-webkit-mask-image:radial-gradient(circle,#000 52%,transparent 71%);mask-image:radial-gradient(circle,#000 52%,transparent 71%)}}
.cap{{position:absolute;top:1330px;left:110px;right:110px;text-align:center;font-family:"Archivo";font-size:66px;line-height:1.12;color:#F6EEE3;opacity:0}}
.cap span{{display:inline-block;margin:0 9px}}
.hot{{color:#F2A541}}
.g{{position:absolute;left:0;right:0;opacity:0}}
.lbl{{font-family:"Archivo";font-size:38px;letter-spacing:3px;color:#F2A541;text-align:center}}
.card{{position:absolute;left:150px;right:150px;top:1040px;background:rgba(246,238,227,.07);border:2px solid rgba(242,165,65,.45);border-radius:28px;padding:26px 34px;text-align:center;opacity:0}}
.card b{{display:block;font-family:"Fraunces";font-size:46px;color:#F6EEE3}}
.card i{{display:block;font-style:normal;font-family:"Archivo";font-size:28px;color:#A89AA6;margin-top:10px}}
#fade{{position:absolute;inset:0;background:#17121C;opacity:0}}
'''

h = [f'<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>{css}</style></head><body>',
     f'<div id="root" data-composition-id="main" data-width="{W}" data-height="{HT}" data-start="0" data-duration="{END:.2f}">',
     f'<audio id="voice" data-start="0" data-duration="{dur:.2f}" data-track-index="1" src="assets/{voice}"></audio>',
     '<div class="ghost" id="ghost" data-layout-ignore>RESPIRE · RESPIRE · RESPIRE</div><div class="halo" id="halo" data-layout-ignore></div>',
     '<div class="sig" id="sig">Dr Fehmi · Psychologie</div>']
js = ['window.__timelines=window.__timelines||{};var tl=gsap.timeline({paused:true});',
      f'tl.fromTo("#ghost",{{x:0}},{{x:-2600,duration:{END:.2f},ease:"none"}},0);',
      f'tl.fromTo("#halo",{{scale:.92,opacity:.75}},{{scale:1.08,opacity:1,duration:2.2,ease:"sine.inOut",yoyo:true,repeat:{int(END / 2.2)}}},0);',
      'tl.from("#sig",{y:-20,opacity:0,duration:.6,ease:"power2.out"},0.1);']

# images : une balise par illustration distincte et consécutive
for i, p in enumerate(plans):
    h.append(f'<div class="ttl" id="t{i}">{H.escape(p["title"])}</div>')
    h.append(f'<div class="ill" id="i{i}"><img src="assets/{p["img"]}.png"></div>')
    a, b = starts[i], ends[i]
    fu = 0.45
    if i == 0 or plans[i - 1]['img'] != p['img']:
        js.append(f'tl.fromTo("#i{i}",{{opacity:0,y:40}},{{opacity:1,y:0,duration:{fu},ease:"power2.out"}},{a:.2f});')
    else:
        js.append(f'tl.set("#i{i}",{{opacity:1}},{a:.2f});')
    js.append(f'tl.fromTo("#i{i} img",{{scale:1}},{{scale:1.06,duration:{b - a + 0.5:.2f},ease:"sine.inOut"}},{a:.2f});')
    js.append(f'tl.fromTo("#t{i}",{{opacity:0,y:30}},{{opacity:1,y:0,duration:{fu},ease:"power3.out"}},{a + 0.05:.2f});')
    if i < len(plans) - 1:
        js.append(f'tl.set("#t{i}",{{opacity:0}},{b:.2f});tl.set("#i{i}",{{opacity:0}},{b + (fu if plans[i + 1]["img"] != p["img"] else 0):.2f});')

    g = p.get('gfx')
    if g == 'hook':  # anneau ambre qui se dessine autour de l'illustration
        h.append('<svg class="g" id="ring" style="top:430px;left:140px;width:800px;height:800px" viewBox="0 0 800 800"><circle cx="400" cy="400" r="380" fill="none" stroke="#F2A541" stroke-width="6" stroke-linecap="round" stroke-dasharray="2388" stroke-dashoffset="2388" transform="rotate(-90 400 400)"/></svg>')
        js.append(f'tl.set("#ring",{{opacity:1}},{a:.2f});tl.to("#ring circle",{{strokeDashoffset:0,duration:{b - a:.2f},ease:"none"}},{a:.2f});tl.set("#ring",{{opacity:0}},{b:.2f});')
    if g == 'pulse':  # le halo bat vite
        js.append(f'tl.to("#i{i} img",{{x:6,duration:.07,ease:"none",yoyo:true,repeat:{int((b - a) / .14) // 4 * 2 + 1},repeatDelay:.25}},{a + 0.3:.2f});')
    if g == 'breath':  # guide de respiration calé sur les mots
        tw = {norm(w['t']): w['s'] for w in words if w['p'] == i}
        t_in, t_in2, t_out = tw.get('inspire', a + .2), tw.get('deuxieme', a + 2), tw.get('expire', a + 4)
        h.append('<div class="g" id="br" style="top:470px;left:190px;width:700px;height:700px"><div id="brc" style="position:absolute;left:150px;top:150px;width:400px;height:400px;border-radius:50%;border:8px solid #F2A541;box-sizing:border-box"></div></div>')
        h.append(f'<div class="g lbl" id="bl0" style="top:1225px">INSPIRE</div><div class="g lbl" id="bl1" style="top:1225px">+ PETITE INSPIRATION</div><div class="g lbl" id="bl2" style="top:1225px">EXPIRE LENTEMENT…</div>')
        js.append(f'tl.set("#br",{{opacity:1}},{t_in - .1:.2f});tl.fromTo("#brc",{{scale:.7}},{{scale:1.2,duration:1.1,ease:"sine.out"}},{t_in:.2f});')
        js.append(f'tl.to("#brc",{{scale:1.38,duration:.5,ease:"sine.out"}},{t_in2:.2f});tl.to("#brc",{{scale:.7,duration:{max(2.5, b - t_out - .2):.2f},ease:"sine.inOut"}},{t_out:.2f});')
        js.append(f'tl.fromTo("#bl0",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,ease:"power2.out"}},{t_in:.2f});tl.set("#bl0",{{opacity:0}},{t_in2:.2f});')
        js.append(f'tl.fromTo("#bl1",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,ease:"power2.out"}},{t_in2:.2f});tl.set("#bl1",{{opacity:0}},{t_out:.2f});')
        js.append(f'tl.fromTo("#bl2",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,ease:"power2.out"}},{t_out:.2f});tl.set(["#bl2","#br"],{{opacity:0}},{b:.2f});')
    if g == 'cta':
        h.append('<div class="g" id="cta" style="top:1050px;text-align:center"><span style="display:inline-block;font-family:Fraunces;font-size:96px;color:#17121C;background:#F2A541;border-radius:999px;padding:6px 60px 18px">CALME</span></div>')
        js.append(f'tl.fromTo("#cta",{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:.5,ease:"back.out(2)"}},{a + .5:.2f});tl.set("#cta",{{opacity:0}},{b:.2f});')
    if g == 'ecg':  # rythme qui ralentit
        path = 'M0 70 H120 L140 70 L155 15 L172 125 L188 70 H330 L350 70 L365 15 L382 125 L398 70 H600 L620 70 L635 15 L652 125 L668 70 H860'
        h.append(f'<svg class="g" id="ecg" style="top:1110px;left:110px;width:860px;height:140px" viewBox="0 0 860 140"><path d="{path}" fill="none" stroke="#F2A541" stroke-width="7" stroke-linejoin="round" stroke-dasharray="1400" stroke-dashoffset="1400"/></svg>')
        js.append(f'tl.set("#ecg",{{opacity:1}},{a + .2:.2f});tl.to("#ecg path",{{strokeDashoffset:0,duration:{b - a - .4:.2f},ease:"power1.out"}},{a + .2:.2f});tl.set("#ecg",{{opacity:0}},{b:.2f});')
    if g == 'study':
        h.append('<div class="card" id="card"><b>5 min / jour pendant 1 mois</b><i>Balban et al., Cell Reports Medicine, 2023</i></div>')
        js.append(f'tl.fromTo("#card",{{opacity:0,y:40}},{{opacity:1,y:0,duration:.5,ease:"power3.out"}},{a + 1.2:.2f});tl.set("#card",{{opacity:0}},{b:.2f});')
    if g == 'x3':
        h.append('<div class="g" id="x3" style="top:1150px;display:flex;justify-content:center;gap:40px">' + ''.join(f'<div id="d{k}" style="width:70px;height:70px;border-radius:50%;border:6px solid #F2A541;box-sizing:border-box;font-family:Fraunces;font-size:40px;color:#17121C;display:flex;align-items:center;justify-content:center">{k + 1}</div>' for k in range(3)) + '</div>')
        js.append(f'tl.set("#x3",{{opacity:1}},{a + .3:.2f});')
        for k in range(3):
            js.append(f'tl.fromTo("#d{k}",{{scale:0,backgroundColor:"rgba(242,165,65,0)"}},{{scale:1,backgroundColor:"#F2A541",duration:.4,ease:"back.out(2.4)"}},{a + .5 + k * .45:.2f});')
        js.append(f'tl.set("#x3",{{opacity:0}},{b:.2f});')

for gi, gr in enumerate(groups):
    h.append(f'<div class="cap" id="c{gi}">' + ''.join(word_html(w['t']) for w in gr) + '</div>')
    s0, e0 = gr[0]['s'], gr[-1]['e'] + .12
    nxt = groups[gi + 1][0]['s'] if gi + 1 < len(groups) else END
    e0 = min(max(e0, s0 + .5), nxt)
    js.append(f'tl.fromTo("#c{gi}",{{opacity:0,y:16}},{{opacity:1,y:0,duration:.18,ease:"power2.out"}},{s0:.2f});tl.set("#c{gi}",{{opacity:0}},{e0:.2f});')

h.append('<div id="fade"></div>')
js.append(f'tl.to("#fade",{{opacity:1,duration:1.2,ease:"power1.in"}},{END - 1.3:.2f});')
js.append('window.__timelines["main"]=tl;')
h.append('</div><script>' + '\n'.join(js) + '</script></body></html>')
open(f'{D}/index.html', 'w').write('\n'.join(h))
json.dump({'starts': starts, 'dur': dur, 'words': words}, open(f'{D}/timing.json', 'w'), ensure_ascii=False)
print('plans', [round(s, 2) for s in starts], 'groups', len(groups), 'dur', round(END, 2))
