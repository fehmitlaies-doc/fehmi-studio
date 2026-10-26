# Radar — composition HyperFrames au style R7, calée sur la voix réelle.
# Usage : python3 radar_build.py <dossier>
#   <dossier>/job.json              {lang, ghost, plans:[{say, title, _file, gfx, hot, cta, card, count, steps}]}
#   <dossier>/assets/voice.m4a      voix (la tienne ou la voix clonée)
#   <dossier>/assets/transcript.json  mots horodatés (hyperframes transcribe)
# Sortie : index.html, assets/voice_final.m4a (prises ratées et longs silences coupés), timing.json
import json, os, re, sys, subprocess, unicodedata, difflib, html as H

D = sys.argv[1]
W, HT = 1080, 1920
job = json.load(open(f'{D}/job.json'))
plans, AR = job['plans'], job.get('lang') == 'ar'
try:
    asr = [w for w in json.load(open(f'{D}/assets/transcript.json')) if str(w.get('text', '')).strip()]
except Exception:
    asr = []  # transcription absente : minutage réparti sur la durée
probe = lambda f: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode())
src_dur = probe(f'{D}/assets/voice.m4a')

def nb(t):  # espace insécable avant ? ! : ; » et après « (jamais de « ? » seul en début de ligne)
    return re.sub(r'\s+([?!:;»؟])', '\u00a0\\1', re.sub(r'«\s+', '«\u00a0', str(t)))

def norm(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\W_]+', '', s)

# 1. mots du script (texte exact, ponctuation française collée au mot)
words = []
for pi, p in enumerate(plans):
    for w in p['say'].split():
        if words and words[-1]['p'] == pi and re.fullmatch(r'[?!:;»؟،.,…]+', w):
            words[-1]['t'] += ' ' + w
        elif w == '«':
            words.append({'t': w + ' ', 'p': pi, 'glue': 1})
        elif words and words[-1].get('glue'):
            words[-1]['t'] += w; words[-1].pop('glue')
        else:
            words.append({'t': w, 'p': pi})

# 2. prises recommencées (« tu sens ta… tu sens ta mâchoire qui… ») : on garde la dernière
cuts = []
SN = [norm(w['t']) for w in words]
def in_script(seq, g):  # la répétition est-elle voulue dans le texte ?
    n = len(seq)
    return any(SN[i:i + n] == seq and SN[i + n + g:i + 2 * n + g] == seq for i in range(len(SN)))
j = 0
while j < len(asr):
    hit = None
    for n in range(8, 1, -1):
        for g in range(0, 3):  # jusqu'à 2 mots d'hésitation entre les deux prises
            k = j + n + g
            seq = [norm(x['text']) for x in asr[j:j + n]]
            if k + n <= len(asr) and seq == [norm(x['text']) for x in asr[k:k + n]] and not in_script(seq, g):
                hit = (n, g); break
        if hit: break
    if hit:
        n, g = hit
        cuts.append((asr[j]['start'], asr[j + n + g]['start']))
        del asr[j:j + n + g]
    else:
        j += 1

# 3. alignement script ↔ transcription ; les autres mots en trop sont coupés
A, B = [norm(w['t']) for w in words], [norm(x['text']) for x in asr]
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
    if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
        for k in range(i2 - i1):
            words[i1 + k]['s'], words[i1 + k]['e'] = asr[j1 + k]['start'], asr[j1 + k]['end']
    elif tag == 'replace':
        if i2 > i1 and j2 > j1:
            s0, e0, n = asr[j1]['start'], asr[j2 - 1]['end'], i2 - i1
            for k in range(n):
                words[i1 + k]['s'], words[i1 + k]['e'] = s0 + (e0 - s0) * k / n, s0 + (e0 - s0) * (k + 1) / n
    elif tag == 'insert' and j2 - j1 >= 2 and j2 < len(asr):
        # mots en trop coupés seulement s'ils reprennent la suite du texte (début de phrase raté) ;
        # une phrase ajoutée librement reste dans la vidéo
        nxt = set(A[i1:i1 + 8])
        if sum(b in nxt for b in B[j1:j2]) >= max(2, (j2 - j1) // 2) and asr[j2]['start'] - asr[j1]['start'] < 8:
            cuts.append((asr[j1]['start'], asr[j2]['start']))
if not any('s' in w for w in words):  # rien de reconnu : répartition proportionnelle
    n = len(words); span = max(1.0, src_dur - 0.6)
    for k, w in enumerate(words):
        w['s'], w['e'] = 0.3 + span * k / n, 0.3 + span * (k + 1) / n
for i, w in enumerate(words):  # mots non reconnus : entre leurs voisins
    if 's' not in w:
        prev = next((words[j]['e'] for j in range(i - 1, -1, -1) if 'e' in words[j]), 0.1)
        nxt = next((words[j]['s'] for j in range(i + 1, len(words)) if 's' in words[j]), src_dur)
        w['s'], w['e'] = prev, min(nxt, prev + 0.3)

# silences de plus de 0,55 s ramenés à 0,3 s : rythme serré, meilleure rétention
for a, b in zip(words, words[1:]):
    if b['s'] - a['e'] > 0.55 and not any(c0 <= a['e'] < c1 for c0, c1 in cuts):
        cuts.append((a['e'] + 0.15, b['s'] - 0.15))
lead = max(0, words[0]['s'] - 0.25)
if lead > 0.05: cuts.append((0, lead))
cuts = sorted((max(0, a), min(src_dur, b)) for a, b in cuts if b - a > 0.08)
merged = []
for a, b in cuts:
    if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
    else: merged.append((a, b))
tail = min(src_dur, words[-1]['e'] + 0.6)
keep, t = [], 0.0
for a, b in merged:
    if a > t: keep.append((t, a))
    t = max(t, b)
if tail > t + 0.05: keep.append((t, tail))
if not keep: keep = [(0, src_dur)]
shift = lambda x: sum(min(b, x) - a for a, b in keep if a < x)
for w in words:
    w['s'], w['e'] = round(shift(w['s']), 3), round(shift(w['e']), 3)
fc = ''.join(f'[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:st={max(0, b - a - 0.015):.3f}:d=0.015[k{i}];' for i, (a, b) in enumerate(keep))
fc += ''.join(f'[k{i}]' for i in range(len(keep))) + f'concat=n={len(keep)}:v=0:a=1[out]'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{D}/assets/voice.m4a', '-filter_complex', fc, '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{D}/assets/voice_final.m4a'], check=True)
dur = probe(f'{D}/assets/voice_final.m4a')

END = dur + 1.6
SFX = []  # (son, instant, gain dB) — placés automatiquement selon les animations
sfx_on = job.get('sfx', True) is not False

starts = [0] + [max(0, next(w for w in words if w['p'] == pi)['s'] - 0.2) for pi in range(1, len(plans))]
ends = starts[1:] + [END]

# 4. sous-titres de 3 mots, jamais à cheval sur deux plans
groups, cur = [], []
for w in words:
    if cur and cur[-1]['p'] != w['p']: groups.append(cur); cur = []
    cur.append(w)
    if len(cur) == 3 or re.search(r'[.,:?!؟،]$', w['t']): groups.append(cur); cur = []
if cur: groups.append(cur)
HOT = [{norm(x) for h in p.get('hot', []) for x in str(h).split() if len(norm(x)) > 2} for p in plans]  # expressions → mots
def word_html(w):
    k = norm(w['t'])
    hot = k and any(k == h or (len(h) > 3 and k.startswith(h)) for h in HOT[w['p']])
    return f'<span{" class=\"hot\"" if hot else ""}>{H.escape(w["t"])}</span>'

TF, CF = ('Cairo', 'Cairo') if AR else ('Fraunces', 'Archivo')
DIR = 'rtl' if AR else 'ltr'
css = f'''
@font-face{{font-family:"Fraunces";src:url("assets/Fraunces.ttf") format("truetype")}}
@font-face{{font-family:"Archivo";src:url("assets/Archivo.ttf") format("truetype")}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-ar.ttf") format("truetype");unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-la.ttf") format("truetype");unicode-range:U+0000-024F,U+2000-206F,U+20AC}}
body{{margin:0;width:{W}px;height:{HT}px;overflow:hidden;background:#17121C}}
#root{{position:relative;width:{W}px;height:{HT}px;background:#17121C;overflow:hidden;font-family:"{CF}",sans-serif}}
.dust{{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(242,165,65,.55),rgba(242,165,65,.12) 45%,rgba(242,165,65,0) 70%)}}
.vign{{position:absolute;inset:0;background:radial-gradient(ellipse 75% 60% at 50% 45%,rgba(23,18,28,0) 55%,rgba(10,7,12,.75) 100%)}}
.halo{{position:absolute;left:140px;top:470px;width:800px;height:800px;border-radius:50%;background:radial-gradient(circle,rgba(242,165,65,.30),rgba(242,165,65,.10) 40%,rgba(242,165,65,0) 68%)}}
.ttl{{position:absolute;top:190px;left:110px;right:110px;text-align:center;direction:{DIR};font-family:"{TF}";font-weight:800;font-size:{74 if AR else 78}px;line-height:{1.25 if AR else 1.05};color:#F6EEE3;opacity:0}}
.ill{{position:absolute;left:150px;top:440px;width:780px;height:780px;opacity:0}}
.ill img{{width:100%;height:100%;object-fit:cover;display:block;-webkit-mask-image:radial-gradient(circle,#000 52%,transparent 71%);mask-image:radial-gradient(circle,#000 52%,transparent 71%)}}
.cap{{position:absolute;top:1330px;left:110px;right:110px;text-align:center;direction:{DIR};font-family:"{CF}";font-weight:800;font-size:66px;line-height:{1.35 if AR else 1.12};color:#F6EEE3;opacity:0}}
.cap span{{display:inline-block;margin:0 9px}}
.hot{{color:#F2A541}}
.g{{position:absolute;left:0;right:0;opacity:0}}
.lbl{{font-family:"{CF}";font-weight:800;font-size:38px;letter-spacing:{0 if AR else 3}px;color:#F2A541;text-align:center;direction:{DIR}}}
.card{{position:absolute;left:150px;right:150px;top:1040px;background:rgba(23,18,28,.9);border:2px solid rgba(242,165,65,.45);border-radius:28px;padding:26px 34px;text-align:center;direction:{DIR};opacity:0}}
.card b{{display:block;font-family:"{TF}";font-weight:800;font-size:46px;color:#F6EEE3}}
.card i{{display:block;font-style:normal;font-family:"Archivo","Cairo";font-weight:800;font-size:28px;color:#A89AA6;margin-top:10px}}
#fade{{position:absolute;inset:0;background:#17121C;opacity:0}}
#prog{{position:absolute;left:0;top:0;height:10px;width:{W}px;background:#F2A541;transform-origin:{"right" if AR else "left"} center;opacity:.9}}
.panel{{position:absolute;left:130px;right:130px;top:1010px;background:rgba(23,18,28,.82);border:2px solid rgba(242,165,65,.35);border-radius:28px;padding:22px 30px;direction:{DIR};opacity:0}}
.it{{display:flex;align-items:center;gap:20px;font-family:"{CF}";font-weight:800;font-size:42px;color:#F6EEE3;padding:8px 0}}
.it b{{flex:none;width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:34px;color:#17121C;background:#F2A541}}
.it.no b{{background:#3A2E40;color:#A89AA6}}
.split{{position:absolute;left:110px;right:110px;top:1000px;display:flex;gap:24px;direction:{DIR}}}
.split div{{flex:1;border-radius:26px;padding:22px 24px;text-align:center;opacity:0}}
.split small{{display:block;font-family:"Archivo","Cairo";font-weight:800;font-size:26px;letter-spacing:{0 if AR else 2}px;text-transform:uppercase;margin-bottom:8px}}
.split p{{margin:0;font-family:"{TF}";font-weight:800;font-size:40px;line-height:1.15;color:#F6EEE3}}
.sl{{background:rgba(58,46,64,.92)}} .sl small{{color:#A89AA6}}
.sr{{background:rgba(242,165,65,.16);border:2px solid #F2A541}} .sr small{{color:#F2A541}}
.quote{{position:absolute;left:120px;right:120px;top:1020px;background:rgba(23,18,28,.85);border-radius:26px;padding:10px 24px 24px;text-align:center;direction:{DIR};font-family:"{TF}";font-weight:800;font-style:{"normal" if AR else "italic"};font-size:50px;line-height:1.2;color:#F6EEE3;opacity:0}}
.quote:before{{content:"“";display:block;font-size:110px;line-height:.6;color:#F2A541}}
.bigw{{position:absolute;left:0;right:0;top:700px;text-align:center;font-family:"{TF}";font-weight:800;font-size:{150 if AR else 170}px;line-height:1;color:#F2A541;text-shadow:0 10px 40px rgba(23,18,28,.9),0 0 4px #17121C;opacity:0}}
.stamp{{position:absolute;right:120px;top:560px;font-family:"{TF}";font-weight:800;font-size:110px;color:#F2A541;border:10px solid #F2A541;border-radius:18px;padding:0 30px;background:rgba(23,18,28,.85);opacity:0}}
.timer{{position:absolute;left:440px;top:1040px;width:200px;height:200px;opacity:0}}
.timer span{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:"Fraunces";font-weight:800;font-size:96px;color:#F6EEE3}}
'''
# fond : poussières de lumière ambrée qui montent lentement (positions fixes, pas de hasard au rendu)
import random
RND = random.Random(7)
dust = []
for k in range(16):
    size = RND.choice([10, 14, 18, 26, 40, 60])
    dust.append((k, RND.randint(40, W - 60), RND.randint(300, HT - 100), size, RND.uniform(.25, .7), RND.randint(160, 420), RND.uniform(6, 11)))
h = [f'<!DOCTYPE html><html lang="{"ar" if AR else "fr"}"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>{css}</style></head><body>',
     f'<div id="root" data-composition-id="main" data-width="{W}" data-height="{HT}" data-start="0" data-duration="{END:.2f}">',
     '<!-- audio : ajouté après le mixage -->',
     ''.join(f'<div class="dust" id="du{k}" data-layout-ignore style="left:{x}px;top:{y}px;width:{sz}px;height:{sz}px;opacity:{op:.2f}"></div>' for k, x, y, sz, op, _, _ in dust),
     '<div class="vign" data-layout-ignore></div><div class="halo" id="halo" data-layout-ignore></div>',
     '<div id="prog"></div>']
js = ['window.__timelines=window.__timelines||{};var tl=gsap.timeline({paused:true});',
      *[f'tl.fromTo("#du{k}",{{y:0}},{{y:-{rise},duration:{END:.2f},ease:"none"}},0);tl.to("#du{k}",{{x:{RND.choice([-1, 1]) * RND.randint(14, 36)},duration:{per:.2f},ease:"sine.inOut",yoyo:true,repeat:{int(END / per)}}},0);' for k, x, y, sz, op, rise, per in dust],
      f'tl.fromTo("#halo",{{scale:.92,opacity:.75}},{{scale:1.08,opacity:1,duration:2.2,ease:"sine.inOut",yoyo:true,repeat:{int(END / 2.2)}}},0);',
      f'tl.fromTo("#prog",{{scaleX:0}},{{scaleX:1,duration:{END:.2f},ease:"none"}},0);']

for i, p in enumerate(plans):
    a, b, fu = starts[i], ends[i], 0.45
    same_prev = i and plans[i - 1]['_file'] == p['_file']
    same_next = i < len(plans) - 1 and plans[i + 1]['_file'] == p['_file']
    h.append(f'<div class="ttl" id="t{i}">{H.escape(nb(p.get("title", "")))}</div>')
    h.append(f'<div class="ill" id="i{i}"><img src="assets/{p["_file"]}"></div>')
    if i == 0:  # accroche : image visible dès la 1re image, coup de zoom (pas de fondu depuis le noir)
        js.append('tl.fromTo("#i0",{opacity:1,scale:1.18},{opacity:1,scale:1,duration:.5,ease:"expo.out"},0);')
        js.append('tl.fromTo("#t0",{opacity:1,scale:1.12},{opacity:1,scale:1,duration:.45,ease:"expo.out"},0);')
        SFX.append(('impact', 0.0, -9))
    else:
        js.append(f'tl.set("#i{i}",{{opacity:1}},{a:.2f});' if same_prev else f'tl.fromTo("#i{i}",{{opacity:0,y:40}},{{opacity:1,y:0,duration:{fu},ease:"power2.out"}},{a:.2f});')
        js.append(f'tl.fromTo("#t{i}",{{opacity:0,y:30}},{{opacity:1,y:0,duration:{fu},ease:"power3.out"}},{a + 0.05:.2f});')
        if not same_prev: SFX.append(('whoosh', max(0, a - 0.25), -17))
    # mouvement de caméra varié d'un plan à l'autre (zoom avant, arrière, glissement gauche/droite)
    mv = ['{scale:1,x:0},{scale:1.08,x:0', '{scale:1.1,x:0},{scale:1,x:0', '{scale:1.06,x:-24},{scale:1.06,x:24', '{scale:1.06,x:24},{scale:1.06,x:-24'][i % 4]
    js.append(f'tl.fromTo("#i{i} img",{mv},duration:{b - a + 0.5:.2f},ease:"sine.inOut"}},{a:.2f});')
    img = p.get('img', '')
    if img in ('scroll_bed', 'phone_night', 'screens'): SFX.append(('phone', a + 0.3, -16))
    if img in ('journal',): SFX.append(('scribble', a + 0.4, -18))
    if img in ('clock_night',): SFX.append(('tick', a + 0.3, -14)); SFX.append(('tick', a + 1.3, -14))
    if i < len(plans) - 1:
        js.append(f'tl.set("#t{i}",{{opacity:0}},{b:.2f});tl.set("#i{i}",{{opacity:0}},{b + (0 if same_next else fu):.2f});')
    pw = [w for w in words if w['p'] == i]
    g = p.get('gfx') or 'none'
    if g == 'ring':  # anneau ambre qui se dessine pendant le plan
        h.append(f'<svg class="g" id="ring{i}" style="top:430px;left:140px;width:800px;height:800px" viewBox="0 0 800 800"><circle cx="400" cy="400" r="380" fill="none" stroke="#F2A541" stroke-width="6" stroke-linecap="round" stroke-dasharray="2388" stroke-dashoffset="2388" transform="rotate(-90 400 400)"/></svg>')
        SFX.append(('riser', max(0, b - 2.2), -20))
        js.append(f'tl.set("#ring{i}",{{opacity:1}},{a:.2f});tl.to("#ring{i} circle",{{strokeDashoffset:0,duration:{b - a:.2f},ease:"none"}},{a:.2f});tl.set("#ring{i}",{{opacity:0}},{b:.2f});')
    elif g == 'pulse':  # le personnage tremble : tension
        SFX.append(('heartbeat', a + 0.2, -12))
        js.append(f'tl.to("#i{i} img",{{x:6,duration:.07,ease:"none",yoyo:true,repeat:{max(1, int((b - a) / .39)) * 2 - 1},repeatDelay:.25}},{a + 0.3:.2f});')
    elif g == 'breath':  # cercle qui gonfle / se vide, étiquettes sur les mots-clés
        steps = (p.get('steps') or ['INSPIRE', 'EXPIRE'])[:3]
        at = []
        for k, s in enumerate(steps):
            kw = norm(s.split()[-1]) if s.split() else ''
            hit = next((w['s'] for w in pw if kw and norm(w['t']).startswith(kw[:5])), None)
            at.append(hit if hit is not None and (not at or hit > at[-1]) else a + 0.3 + (b - a - 0.6) * k / len(steps))
        scales = [1.2, 1.38, .7] if len(steps) == 3 else [1.25, .7] if len(steps) == 2 else [1.2]
        h.append(f'<div class="g" id="br{i}" style="top:470px;left:190px;width:700px;height:700px"><div id="brc{i}" style="position:absolute;left:150px;top:150px;width:400px;height:400px;border-radius:50%;border:8px solid #F2A541;box-sizing:border-box"></div></div>')
        js.append(f'tl.set("#br{i}",{{opacity:1}},{at[0] - .1:.2f});tl.set("#brc{i}",{{scale:.7}},{at[0] - .1:.2f});')
        for k, s in enumerate(steps):
            nxt = at[k + 1] if k + 1 < len(steps) else b
            last = k == len(steps) - 1
            js.append(f'tl.to("#brc{i}",{{scale:{scales[k]},duration:{max(.4, (nxt - at[k] - .1) if last else min(1.1, nxt - at[k])):.2f},ease:"sine.inOut"}},{at[k]:.2f});')
            h.append(f'<div class="g lbl" id="bl{i}_{k}" style="top:1225px">{H.escape(nb(s))}</div>')
            js.append(f'tl.fromTo("#bl{i}_{k}",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,ease:"power2.out"}},{at[k]:.2f});tl.set("#bl{i}_{k}",{{opacity:0}},{nxt:.2f});')
        js.append(f'tl.set("#br{i}",{{opacity:0}},{b:.2f});')
        SFX.append(('breath', at[-1], -16))
    elif g == 'cta':  # mot à écrire en commentaire
        h.append(f'<div class="g" id="cta{i}" style="top:1050px;text-align:center"><span style="display:inline-block;font-family:{TF};font-weight:800;font-size:96px;color:#17121C;background:#F2A541;border-radius:999px;padding:6px 60px 18px">{H.escape(p.get("cta", ""))}</span></div>')
        SFX.append(('pop', a + .5, -10))
        js.append(f'tl.fromTo("#cta{i}",{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:.5,ease:"back.out(2)"}},{a + .5:.2f});tl.set("#cta{i}",{{opacity:0}},{b:.2f});')
    elif g == 'ecg':  # rythme cardiaque qui ralentit
        path = 'M0 70 H120 L140 70 L155 15 L172 125 L188 70 H330 L350 70 L365 15 L382 125 L398 70 H600 L620 70 L635 15 L652 125 L668 70 H860'
        h.append(f'<svg class="g" id="ecg{i}" style="top:1110px;left:110px;width:860px;height:140px" viewBox="0 0 860 140"><path d="{path}" fill="none" stroke="#F2A541" stroke-width="7" stroke-linejoin="round" stroke-dasharray="1400" stroke-dashoffset="1400"/></svg>')
        SFX.append(('heartbeat', a + .2, -13))
        js.append(f'tl.set("#ecg{i}",{{opacity:1}},{a + .2:.2f});tl.to("#ecg{i} path",{{strokeDashoffset:0,duration:{max(1, b - a - .4):.2f},ease:"power1.out"}},{a + .2:.2f});tl.set("#ecg{i}",{{opacity:0}},{b:.2f});')
    elif g == 'card' and p.get('card'):  # source, chiffre ou conseil
        c = p['card']
        sub = f'<i>{H.escape(c["i"])}</i>' if c.get('i') else ''
        h.append(f'<div class="card" id="card{i}"><b>{H.escape(nb(c.get("b", "")))}</b>{sub}</div>')
        SFX.append(('pop', a + min(1.2, (b - a) / 3), -14))
        js.append(f'tl.fromTo("#card{i}",{{opacity:0,y:40}},{{opacity:1,y:0,duration:.5,ease:"power3.out"}},{a + min(1.2, (b - a) / 3):.2f});tl.set("#card{i}",{{opacity:0}},{b:.2f});')
    elif g == 'count':  # 1 · 2 · 3
        n = max(2, min(5, int(p.get('count') or 3)))
        h.append(f'<div class="g" id="x{i}" style="top:1150px;display:flex;justify-content:center;gap:40px;direction:{DIR}">' + ''.join(f'<div id="d{i}_{k}" style="width:70px;height:70px;border-radius:50%;border:6px solid #F2A541;box-sizing:border-box;font-family:Fraunces;font-weight:800;font-size:40px;color:#17121C;display:flex;align-items:center;justify-content:center">{k + 1}</div>' for k in range(n)) + '</div>')
        js.append(f'tl.set("#x{i}",{{opacity:1}},{a + .3:.2f});')
        for k in range(n):
            js.append(f'tl.fromTo("#d{i}_{k}",{{scale:0,backgroundColor:"rgba(242,165,65,0)"}},{{scale:1,backgroundColor:"#F2A541",duration:.4,ease:"back.out(2.4)"}},{a + .5 + k * min(.45, (b - a - 1) / n):.2f});')
            SFX.append(('ding', a + .5 + k * min(.45, (b - a - 1) / n), -17))
        js.append(f'tl.set("#x{i}",{{opacity:0}},{b:.2f});')
    elif g == 'check' and p.get('items'):  # liste ✓ / ✗ qui apparaît élément par élément
        items = p['items'][:3]
        h.append(f'<div class="panel" id="ck{i}">' + ''.join(f'<div class="it{"" if it.get("ok", True) else " no"}" id="ck{i}_{k}"><b>{"✓" if it.get("ok", True) else "✗"}</b><span>{H.escape(str(it.get("t", "")))}</span></div>' for k, it in enumerate(items)) + '</div>')
        js.append(f'tl.fromTo("#ck{i}",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.35,ease:"power3.out"}},{a + .3:.2f});tl.set("#ck{i}",{{opacity:0}},{b:.2f});')
        step = min(1.1, max(.5, (b - a - 1) / max(1, len(items))))
        for k in range(len(items)):
            t0 = a + .5 + k * step
            js.append(f'tl.from("#ck{i}_{k}",{{opacity:0,x:{40 if AR else -40},duration:.3,ease:"back.out(1.8)"}},{t0:.2f});')
            SFX.append(('pop', t0, -15))
    elif g == 'split' and p.get('left') and p.get('right'):  # avant / après, mythe / vérité
        L, Rr = p['left'], p['right']
        h.append(f'<div class="split"><div class="sl" id="sl{i}"><small>{H.escape(str(L.get("label", "")))}</small><p>{H.escape(str(L.get("t", "")))}</p></div><div class="sr" id="sr{i}"><small>{H.escape(str(Rr.get("label", "")))}</small><p>{H.escape(str(Rr.get("t", "")))}</p></div></div>')
        t1 = a + .3; t2 = a + max(.9, (b - a) * .45)
        js.append(f'tl.fromTo("#sl{i}",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.35,ease:"power3.out"}},{t1:.2f});tl.fromTo("#sr{i}",{{opacity:0,scale:.8}},{{opacity:1,scale:1,duration:.45,ease:"back.out(2)"}},{t2:.2f});')
        js.append(f'tl.set(["#sl{i}","#sr{i}"],{{opacity:0}},{b:.2f});')
        SFX.append(('whoosh', t1, -20)); SFX.append(('pop', t2, -12))
    elif g == 'quote' and p.get('quote'):  # phrase à retenir
        h.append(f'<div class="quote" id="q{i}">{H.escape(nb(p["quote"]))}</div>')
        js.append(f'tl.fromTo("#q{i}",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.6,ease:"power2.out"}},{a + .3:.2f});tl.set("#q{i}",{{opacity:0}},{b:.2f});')
    elif g == 'bigword' and p.get('word'):  # mot-choc géant : rupture de rythme
        kw = norm(str(p['word']).split()[0])
        t0 = next((w['s'] for w in pw if kw and norm(w['t']).startswith(kw[:5])), a + .4)
        h.append(f'<div class="bigw" id="bw{i}">{H.escape(str(p["word"]))}</div>')
        js.append(f'tl.fromTo("#bw{i}",{{opacity:0,scale:2.2}},{{opacity:1,scale:1,duration:.3,ease:"expo.out"}},{t0:.2f});tl.to("#bw{i}",{{opacity:0,scale:.9,duration:.3,ease:"power2.in"}},{min(b - .1, t0 + 1.4):.2f});')
        js.append(f'tl.fromTo("#i{i}",{{x:0}},{{x:10,duration:.05,yoyo:true,repeat:5,ease:"none"}},{t0:.2f});')
        SFX.append(('impact', t0, -10))
    elif g == 'stamp' and p.get('stamp'):  # tampon FAUX / VRAI / MYTHE
        kw = norm(str(p['stamp']).split()[0])
        t0 = next((w['s'] for w in pw if kw and norm(w['t']).startswith(kw[:4])), a + .5)
        h.append(f'<div class="stamp" id="st{i}">{H.escape(str(p["stamp"]))}</div>')
        js.append(f'tl.fromTo("#st{i}",{{opacity:0,scale:2.4,rotation:-26}},{{opacity:1,scale:1,rotation:-10,duration:.32,ease:"back.out(2.2)"}},{t0:.2f});tl.set("#st{i}",{{opacity:0}},{b:.2f});')
        SFX.append(('impact', t0, -11))
    elif g == 'timer':  # compte à rebours (ex. « 5 secondes »)
        n = max(3, min(10, int(p.get('seconds') or 5)))
        circ = 565
        h.append(f'<div class="timer" id="tm{i}"><svg viewBox="0 0 200 200" width="200" height="200"><circle cx="100" cy="100" r="90" fill="none" stroke="#3A2E40" stroke-width="10"/><circle id="tmc{i}" cx="100" cy="100" r="90" fill="none" stroke="#F2A541" stroke-width="10" stroke-linecap="round" stroke-dasharray="{circ}" stroke-dashoffset="0" transform="rotate(-90 100 100)"/></svg>' + ''.join(f'<span id="tn{i}_{k}" style="opacity:0">{n - k}</span>' for k in range(n)) + '</div>')
        t0 = a + .3; span = min(n, max(2.0, b - a - .6))
        js.append(f'tl.set("#tm{i}",{{opacity:1}},{t0:.2f});tl.to("#tmc{i}",{{strokeDashoffset:{circ},duration:{span:.2f},ease:"none"}},{t0:.2f});tl.set("#tm{i}",{{opacity:0}},{b:.2f});')
        for k in range(n):
            tk = t0 + k * span / n
            js.append(f'tl.set("#tn{i}_{k}",{{opacity:1}},{tk:.2f});tl.set("#tn{i}_{k}",{{opacity:0}},{tk + span / n:.2f});')
            SFX.append(('tick', tk, -16))

for gi, gr in enumerate(groups):
    h.append(f'<div class="cap" id="c{gi}">' + ''.join(word_html(w).replace('<span class="hot"', f'<span class="hot" id="h{gi}_{k}"', 1) for k, w in enumerate(gr)) + '</div>')
    for k, w in enumerate(gr):
        if 'class="hot"' in word_html(w):
            js.append(f'tl.fromTo("#h{gi}_{k}",{{color:"#FFF4DC"}},{{color:"#F2A541",duration:.35,ease:"power1.out",immediateRender:false}},{w["s"]:.2f});')
    s0 = gr[0]['s']
    nxt = groups[gi + 1][0]['s'] if gi + 1 < len(groups) else END
    e0 = min(max(gr[-1]['e'] + .12, s0 + .5), nxt)
    if e0 - s0 < .12: continue  # minutage incohérent : on ne montre pas ce sous-titre plutôt que de le laisser figé
    js.append(f'tl.fromTo("#c{gi}",{{opacity:0,y:16}},{{opacity:1,y:0,duration:.18,ease:"power2.out"}},{s0:.2f});tl.set("#c{gi}",{{opacity:0}},{e0:.2f});')

# mixage : voix + musique (bien présente, baissée automatiquement quand la voix parle) + effets sonores
music = job.get('music') or 'calme'
audio_src, audio_dur = 'voice_final.m4a', dur
ins, flt, lab = ['-i', f'{D}/assets/voice_final.m4a'], [f'[0:a]apad=whole_dur={END:.2f}[v0]'], ['[v]']
mf = f'{D}/assets/music_{music}.m4a'
if music != 'none' and os.path.exists(mf):
    ins += ['-stream_loop', '-1', '-i', mf]
    flt.append('[v0]asplit=2[v][vk]')
    flt.append(f'[1:a]volume=-12dB,atrim=0:{END:.2f},afade=t=in:d=1,afade=t=out:st={END - 2:.2f}:d=2[m0]')
    flt.append('[m0][vk]sidechaincompress=threshold=0.04:ratio=5:attack=20:release=400:makeup=1[m]'); lab.append('[m]')
else:
    flt[0] = flt[0].replace('[v0]', '[v]')
if sfx_on:
    last = {}
    for name, t, gain in sorted(SFX, key=lambda x: x[1]):
        f = f'{D}/assets/sfx_{name}.m4a'
        if not os.path.exists(f) or t > END - .3 or t - last.get(name, -9) < .35: continue
        last[name] = t
        idx = sum(1 for x in ins if x == '-i')
        ins += ['-i', f]
        ms = int(t * 1000)
        flt.append(f'[{idx}:a]volume={gain}dB,adelay={ms}|{ms}[s{idx}]'); lab.append(f'[s{idx}]')
if len(lab) > 1:
    flt.append(''.join(lab) + f'amix=inputs={len(lab)}:duration=first:normalize=0[out]')
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', ';'.join(flt), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{D}/assets/mix.m4a'], check=True)
        audio_src, audio_dur = 'mix.m4a', END
    except subprocess.CalledProcessError:
        pass
h[2] = f'<audio id="voice" data-start="0" data-duration="{audio_dur:.2f}" data-track-index="1" src="assets/{audio_src}"></audio>'

h.append('<div id="fade"></div>')
js.append(f'tl.to("#fade",{{opacity:1,duration:1.2,ease:"power1.in"}},{END - 1.3:.2f});')
js.append('window.__timelines["main"]=tl;')
h.append('</div><script>' + '\n'.join(js) + '</script></body></html>')
open(f'{D}/index.html', 'w').write('\n'.join(h))
json.dump({'starts': starts, 'dur': dur, 'cut_s': round(src_dur - dur, 2), 'words': words}, open(f'{D}/timing.json', 'w'), ensure_ascii=False)
print('plans', [round(s, 2) for s in starts], 'groups', len(groups), 'duree', round(END, 2), 'coupé', round(src_dur - dur, 2), 's')
