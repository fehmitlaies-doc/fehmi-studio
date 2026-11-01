# Format « Métaphore » (9:16) : personnage en traits lumineux sur fond noir, une métaphore visuelle par vidéo
# (cartons, portes, attaches), texte court en capitales, compteurs, lumière dorée au retournement.
# Usage : python3 metaphor_build.py <dossier>
#   <dossier>/job.json  {kind, lang, beats:[{say, txt, act}], labels:[], paper, source:{b,i}, end, save, note, music, sfx}
#   <dossier>/assets/voice.m4a + transcript.json   facultatifs : sans voix, la vidéo suit le temps de lecture
# Sortie : index.html, assets/mix.m4a (voix + musique + effets)
import json, os, re, sys, subprocess, unicodedata, difflib, html as H

D = sys.argv[1]
W, HT, FLOOR = 1080, 1920, 1300
job = json.load(open(f'{D}/job.json'))
AR = job.get('lang') == 'ar'
KIND = job.get('kind') if job.get('kind') in ('cartons', 'portes', 'attaches') else 'cartons'
beats = [b for b in job.get('beats', []) if str(b.get('txt') or b.get('say') or '').strip() or b.get('act') in ('rise', 'card', 'end')]
LABELS = [str(x)[:22] for x in (job.get('labels') or [])][:6] or ['…']
VOICE = os.path.exists(f'{D}/assets/voice.m4a')
AMB = 'nuit' if job.get('ambiance') == 'nuit' else 'aube'  # aube : ciel de crépuscule, montagnes, particules, rayons ; nuit : noir sobre
probe = lambda f: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode())
esc = lambda s: H.escape(str(s or ''))
X = (lambda x: W - x) if AR else (lambda x: x)  # en arabe, la scène est en miroir (lecture de droite à gauche)

def norm(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\W_]+', '', s)

# 1. minutage : la voix réelle (mots horodatés) ou le temps de lecture
MIN = {'drop': .8, 'unload': .75, 'close': .9, 'open': .6, 'cut': .9, 'relink': .8}
def need(b):  # durée minimale d'un temps fort, selon le texte et l'animation
    n = len(str(b.get('txt', '')).split())
    base = max(2.0, 1.1 + n * (.42 if AR else .36))
    per = MIN.get(b.get('act'))
    if per: base = max(base, per * max(1, b.get('_n', 1)) + .6)
    if b.get('act') == 'card': base = max(base, 4.6)
    if b.get('act') == 'end': base = max(base, 4.8)
    return base

acts = [b.get('act') for b in beats]
def spread(act):  # répartit les éléments (cartons, portes, attaches) sur les temps forts de ce type
    idx = [i for i, a in enumerate(acts) if a == act]
    for j, i in enumerate(idx):
        beats[i]['_n'] = len(LABELS) // len(idx) + (1 if j < len(LABELS) % len(idx) else 0)
for a in ('drop', 'unload', 'close', 'open', 'cut', 'relink'): spread(a)

words = []
for bi, b in enumerate(beats):
    for w in str(b.get('say') or '').split(): words.append({'t': w, 'b': bi})
if VOICE and words:
    dur = probe(f'{D}/assets/voice.m4a')
    try: asr = [w for w in json.load(open(f'{D}/assets/transcript.json')) if str(w.get('text', '')).strip()]
    except Exception: asr = []
    A, B = [norm(w['t']) for w in words], [norm(x['text']) for x in asr]
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            for k in range(i2 - i1): words[i1 + k]['s'], words[i1 + k]['e'] = asr[j1 + k]['start'], asr[j1 + k]['end']
    if not any('s' in w for w in words):  # rien de reconnu : répartition proportionnelle
        for k, w in enumerate(words): w['s'], w['e'] = .2 + (dur - .4) * k / len(words), .2 + (dur - .4) * (k + 1) / len(words)
    for i, w in enumerate(words):
        if 's' not in w:
            prev = next((words[j]['e'] for j in range(i - 1, -1, -1) if 'e' in words[j]), .1)
            w['s'], w['e'] = prev, prev + .25
    for a, b in zip(words, words[1:]):  # toujours croissant
        if b['s'] < a['s']: b['s'] = a['s']
        if b['e'] < b['s'] + .05: b['e'] = b['s'] + .05
    o = []  # début de chaque temps fort dans la voix d'origine
    for bi in range(len(beats)):
        ws = [w for w in words if w['b'] == bi]
        o.append(max(0, ws[0]['s'] - .15) if ws else (o[-1] + .01 if o else 0))
    o[0] = 0
    # chaque temps fort garde au moins le temps de son animation : on insère du silence dans la voix si besoin
    def hold(b):
        a, n = b.get('act'), b.get('_n', 1)
        return {'card': 4.4, 'end': 4.2, 'drop': .7 * n + .5, 'unload': .65 * n + .5, 'close': .75 * n + .5, 'open': .55 * n + .5, 'cut': .8 * n + .5, 'relink': .7 * n + .6, 'small': 2.4, 'rise': 2.0}.get(a, 1.6)
    seg = [(o[i], o[i + 1] if i + 1 < len(o) else dur) for i in range(len(o))]
    starts, t = [], 0.0
    for i, (a, b) in enumerate(seg): starts.append(t); t += max(b - a, hold(beats[i]))
    shift = lambda x: next(starts[i] + x - seg[i][0] for i in range(len(seg) - 1, -1, -1) if x >= seg[i][0])
    for w in words: w['s'], w['e'] = shift(w['s']), shift(w['e'])
    fc = ''.join(f'[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,adelay={int(starts[i] * 1000)}|{int(starts[i] * 1000)}[g{i}];' for i, (a, b) in enumerate(seg))
    fc += ''.join(f'[g{i}]' for i in range(len(seg))) + f'amix=inputs={len(seg)}:normalize=0[out]'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{D}/assets/voice.m4a', '-filter_complex', fc, '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{D}/assets/voice_paced.m4a'], check=True)
    END = t + .8
else:
    words, starts, t = [], [], 0.0
    for b in beats: starts.append(t); t += need(b)
    END = t + .4
ends = starts[1:] + [END - .3]

# 2. personnage : squelette (articulations) et poses
POSES = {
    'stand': dict(head=(540, 900), neck=(540, 942), sh=(540, 960), hip=(540, 1112), le=(514, 1025), lh=(503, 1100), re=(566, 1025), rh=(577, 1100), lk=(523, 1206), lf=(510, 1300), rk=(557, 1206), rf=(570, 1300)),
    'carry': dict(head=(540, 900), neck=(540, 942), sh=(540, 960), hip=(540, 1112), le=(494, 902), lh=(506, 838), re=(586, 902), rh=(574, 838), lk=(523, 1206), lf=(510, 1300), rk=(557, 1206), rf=(570, 1300)),
    'bend': dict(head=(560, 998), neck=(552, 1038), sh=(549, 1055), hip=(520, 1170), le=(512, 975), lh=(528, 910), re=(608, 972), rh=(594, 910), lk=(468, 1228), lf=(470, 1300), rk=(582, 1232), rf=(602, 1300)),
    'kneel': dict(head=(566, 1076), neck=(556, 1114), sh=(552, 1130), hip=(505, 1214), le=(518, 1050), lh=(534, 988), re=(612, 1046), rh=(600, 988), lk=(482, 1298), lf=(410, 1300), rk=(560, 1298), rf=(490, 1300)),
    'sad': dict(head=(548, 935), neck=(543, 975), sh=(542, 990), hip=(534, 1135), le=(522, 1050), lh=(518, 1122), re=(560, 1052), rh=(566, 1124), lk=(522, 1215), lf=(512, 1300), rk=(552, 1215), rf=(566, 1300)),
    'reach': dict(head=(548, 900), neck=(546, 942), sh=(546, 960), hip=(538, 1112), le=(600, 960), lh=(650, 930), re=(590, 1000), rh=(640, 1010), lk=(523, 1206), lf=(505, 1300), rk=(560, 1206), rf=(585, 1300)),
    'open': dict(head=(540, 895), neck=(540, 937), sh=(540, 955), hip=(540, 1110), le=(470, 900), lh=(430, 850), re=(610, 900), rh=(650, 850), lk=(520, 1206), lf=(500, 1300), rk=(560, 1206), rf=(580, 1300)),
}
SEGS = [('neck', 'sh'), ('sh', 'hip'), ('sh', 'le'), ('le', 'lh'), ('sh', 're'), ('re', 'rh'), ('hip', 'lk'), ('lk', 'lf'), ('hip', 'rk'), ('rk', 'rf')]
for P in POSES.values():
    for k, (x, y) in P.items(): P[k] = (X(x), y)
HANDS = {k: ((v['lh'][0] + v['rh'][0]) / 2, min(v['lh'][1], v['rh'][1])) for k, v in POSES.items()}

# 3. styles
MONO = '"Cairo"' if AR else '"Mono"'
SER = '"Cairo"' if AR else '"Fraunces"'
LS = '0' if AR else '.16em'
css = f'''
@font-face{{font-family:"Fraunces";src:url("assets/Fraunces.ttf") format("truetype")}}
@font-face{{font-family:"Mono";src:url("assets/Mono.ttf") format("truetype")}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-ar.ttf") format("truetype");unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-la.ttf") format("truetype");unicode-range:U+0000-024F,U+2000-206F,U+20AC}}
#root{{position:relative;width:{W}px;height:{HT}px;overflow:hidden;background:#07060A}}
#cam{{position:absolute;inset:0;transform-origin:50% 62%}}
.sky{{position:absolute;inset:0;background:linear-gradient(180deg,#140F1C 0%,#2A2138 30%,#5A4766 54%,#A27C86 64%,#E2B08E 68.6%,#2A2030 68.8%,#120E17 100%)}}
.mt{{position:absolute;left:-60px;width:1200px;top:{FLOOR - 420}px;height:420px}}
.sun{{position:absolute;left:{X(540) - 260}px;top:{FLOOR - 260}px;width:520px;height:520px;border-radius:50%;background:radial-gradient(rgba(255,214,160,.55),rgba(255,190,130,.18) 40%,rgba(255,190,130,0) 70%)}}
.rays{{position:absolute;left:{X(540) - 900}px;top:{FLOOR - 1300}px;width:1800px;height:1800px;border-radius:50%;background:repeating-conic-gradient(from 0deg,rgba(255,222,170,.2) 0deg 5deg,rgba(255,222,170,0) 5deg 15deg);-webkit-mask:radial-gradient(circle,#000 8%,rgba(0,0,0,.6) 30%,transparent 62%);mask:radial-gradient(circle,#000 8%,rgba(0,0,0,.6) 30%,transparent 62%);opacity:0}}
.pt{{position:absolute;width:5px;height:5px;border-radius:50%;background:#FFE6C2;box-shadow:0 0 8px rgba(255,220,170,.9)}}
.dust{{position:absolute;left:{X(540) - 220}px;top:{FLOOR - 70}px;width:440px;height:120px;border-radius:50%;background:radial-gradient(rgba(230,210,200,.55),rgba(230,210,200,0) 70%);filter:blur(10px);opacity:0}}
.vig{{position:absolute;inset:0;background:radial-gradient(ellipse 70% 52% at 50% 60%,rgba(44,36,54,.6),rgba(7,6,10,0) 72%)}}
.floor{{position:absolute;left:80px;right:80px;top:{FLOOR}px;height:2px;background:linear-gradient(90deg,rgba(242,165,65,0),rgba(246,242,234,.4),rgba(242,165,65,0))}}
.shadow{{position:absolute;left:{X(540) - 90}px;top:{FLOOR - 10}px;width:180px;height:22px;border-radius:50%;background:radial-gradient(rgba(246,242,234,.22),rgba(246,242,234,0) 70%)}}
.light{{position:absolute;left:190px;top:0;width:700px;height:{FLOOR}px;background:radial-gradient(ellipse 45% 80% at 50% 100%,rgba(242,165,65,.34),rgba(242,165,65,0) 70%);opacity:0}}
.beam{{position:absolute;left:{X(540) - 8}px;top:0;width:16px;height:{FLOOR - 60}px;background:linear-gradient(180deg,rgba(255,214,150,0),rgba(255,214,150,.55));filter:blur(6px);opacity:0}}
svg.fig{{position:absolute;left:0;top:0;width:{W}px;height:{HT}px;overflow:visible}}
.dots{{position:absolute;left:0;right:0;top:205px;text-align:center;font-size:0}}
.dots i{{display:inline-block;width:9px;height:9px;margin:0 6px;border-radius:50%;background:rgba(237,231,218,.22)}}
.t{{position:absolute;left:70px;right:70px;top:280px;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{MONO};font-weight:{700 if AR else 500};font-size:{46 if AR else 35}px;letter-spacing:{'0' if AR else '.11em'};line-height:{1.5 if AR else 1.42};color:#F1EBDF;opacity:0;text-shadow:0 2px 18px rgba(0,0,0,.8)}}
.t b{{color:#F2A541;font-weight:inherit}}
.cnt{{position:absolute;left:0;right:0;top:470px;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{MONO};font-size:{32 if AR else 30}px;letter-spacing:{".2em" if not AR else "0"};opacity:0;white-space:nowrap}}
.cnt b{{color:#E5484D;font-weight:600}} .cnt i{{color:#F2A541;font-style:normal;font-weight:600}}
.lab{{position:absolute;height:58px;line-height:54px;padding:0 22px;border:3px solid #F6F2EA;border-radius:6px;background:#0D0B11;font-family:{MONO};font-size:{30 if AR else 25}px;letter-spacing:{".12em" if not AR else "0"};color:#F6F2EA;white-space:nowrap;box-shadow:0 0 18px rgba(246,242,234,.35);opacity:0;direction:{"rtl" if AR else "ltr"}}}
.lab.red{{border-color:#E5484D;color:#FF8A8D;box-shadow:0 0 22px rgba(229,72,77,.55)}}
#stack{{position:absolute;left:0;top:0;width:0;height:0}}
.paper{{position:absolute;left:{X(675) - (340 if AR else 0)}px;top:1005px;width:340px;height:295px;border:2px solid #F2A541;border-radius:6px;background:rgba(242,165,65,.08);box-shadow:0 0 40px rgba(242,165,65,.25);opacity:0;direction:{"rtl" if AR else "ltr"}}}
.paper h4{{margin:16px 0 4px;text-align:center;font-family:{MONO};font-weight:600;font-size:{28 if AR else 24}px;letter-spacing:{".3em" if not AR else "0"};color:#F2A541}}
.pl{{position:absolute;{"right" if AR else "left"}:24px;font-family:{MONO};font-size:{24 if AR else 21}px;color:#FFE2B3;opacity:0;white-space:nowrap}}
.door{{position:absolute;perspective:700px;top:{FLOOR - 300}px;width:150px;height:300px;border:4px solid #F6F2EA;border-bottom:0;border-radius:6px 6px 0 0;background:#0B0A0F;box-shadow:0 0 16px rgba(246,242,234,.3)}}
.door .lt{{position:absolute;inset:0;background:linear-gradient(180deg,#FFE7BF,#F2A541);opacity:0}}
.door .lf{{position:absolute;inset:0;background:#141119;border-right:3px solid rgba(246,242,234,.6);transform-origin:0 50%}}
.door .tag{{position:absolute;left:-30px;right:-30px;top:-52px;text-align:center;font-family:{MONO};font-size:{24 if AR else 19}px;letter-spacing:{".1em" if not AR else "0"};color:#F6F2EA;white-space:nowrap}}
.door .st{{position:absolute;left:8px;right:8px;top:118px;text-align:center;border:3px solid #E5484D;border-radius:4px;color:#E5484D;font-family:{MONO};font-weight:700;font-size:{24 if AR else 20}px;letter-spacing:{".12em" if not AR else "0"};transform:rotate(-12deg);opacity:0;background:rgba(7,6,10,.7)}}
.anc{{position:absolute;width:0;height:0}}
.anc i{{position:absolute;left:-14px;top:-14px;width:28px;height:28px;border-radius:50%;border:3px solid #F6F2EA;box-shadow:0 0 18px rgba(246,242,234,.5)}}
.anc span{{position:absolute;top:24px;left:-160px;width:320px;text-align:center;font-family:{MONO};font-size:{26 if AR else 21}px;letter-spacing:{".12em" if not AR else "0"};color:#F6F2EA;white-space:nowrap}}
.card{{position:absolute;left:90px;right:90px;top:250px;text-align:center;opacity:0;direction:{"rtl" if AR else "ltr"}}}
.card p{{margin:0;font-family:{SER};font-style:{"normal" if AR else "italic"};font-weight:{600 if AR else 400};font-size:{48 if AR else 46}px;line-height:{1.5 if AR else 1.3};color:#F6F2EA}}
.card small{{display:block;margin-top:26px;font-family:"Mono";font-size:22px;letter-spacing:.16em;color:#F2A541;direction:ltr}}
.end{{position:absolute;left:60px;right:60px;top:320px;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{SER};font-weight:700;font-size:{76 if AR else 78}px;line-height:{1.35 if AR else 1.1};color:#F6F2EA;opacity:0}}
.save{{position:absolute;left:40px;right:40px;top:{600 if AR else 570}px;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{MONO};font-size:{34 if AR else 30}px;letter-spacing:{".22em" if not AR else "0"};color:#F2A541;opacity:0}}
.note{{position:absolute;left:90px;right:90px;top:1560px;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{MONO};font-size:{26 if AR else 22}px;line-height:1.5;color:#A39AAB;opacity:0}}
.cap{{position:absolute;left:70px;right:70px;top:1440px;text-align:center;direction:{"rtl" if AR else "ltr"};font-family:{SER};font-weight:{700 if AR else 600};font-size:{52 if AR else 50}px;line-height:1.3;opacity:0}}
.cap span{{color:rgba(237,231,218,.32)}}
.wm{{position:absolute;left:0;right:0;top:1790px;text-align:center;font-family:"Mono";font-size:20px;letter-spacing:.5em;color:rgba(237,231,218,.28)}}
'''
js = ['window.__timelines=window.__timelines||{};var tl=gsap.timeline({paused:true});']
h = [f'<!DOCTYPE html><html lang="{"ar" if AR else "fr"}"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>{css}</style></head><body>',
     f'<div id="root" data-composition-id="main" data-width="{W}" data-height="{HT}" data-start="0" data-duration="{END:.2f}">',
     f'<audio id="mix" data-start="0" data-duration="{END:.2f}" data-track-index="1" src="assets/mix.m4a"></audio>',
     '<div id="cam">']
if AMB == 'aube':
    import random
    rnd = random.Random(7)
    h.append('<div class="sky"></div><div class="sun" id="sun"></div><div class="rays" id="rays"></div>')
    def ridge(seed, base, amp, col, op):
        r = random.Random(seed); pts, x = [], 0
        while x <= 1200: pts.append(f'{x},{base - r.uniform(.25, 1) * amp:.0f}'); x += r.uniform(70, 160)
        return f'<svg class="mt" viewBox="0 0 1200 420" preserveAspectRatio="none" style="opacity:{op}"><polygon fill="{col}" points="0,420 {" ".join(pts)} 1200,420"/></svg>'
    h.append(ridge(3, 420, 330, '#4A3A57', .9)); h.append(ridge(11, 420, 190, '#2E2439', 1))
    for k in range(34):
        x, y, d = rnd.uniform(40, 1040), rnd.uniform(500, FLOOR - 20), rnd.uniform(6, 14)
        h.append(f'<div class="pt" id="pt{k}" style="left:{x:.0f}px;top:{y:.0f}px;opacity:{rnd.uniform(.2, .7):.2f};transform:scale({rnd.uniform(.5, 1.2):.2f})"></div>')
        js.append(f'tl.to("#pt{k}",{{y:-{rnd.uniform(120, 320):.0f},x:{rnd.uniform(-40, 40):.0f},duration:{END:.2f},ease:"none"}},0);tl.to("#pt{k}",{{opacity:.1,duration:{d / 2:.1f},yoyo:true,repeat:{max(1, int(END / d) * 2 - 1)}}},{rnd.uniform(0, 2):.2f});')
    js.append(f'tl.to("#rays",{{rotation:25,duration:{END:.2f},ease:"none"}},0);')
h.append('<div class="vig"></div><div class="light" id="light"></div><div class="beam" id="beam"></div><div class="floor"></div><div class="shadow" id="shadow"></div><div class="dust" id="dust"></div>')
SFX = []
cur = {'pose': 'stand'}

def pose(t, name, dur=.7, ease='power2.inOut'):
    P = POSES[name]
    for a, b in SEGS:
        js.append(f'tl.to("#s_{a}_{b}",{{attr:{{x1:{P[a][0]},y1:{P[a][1]},x2:{P[b][0]},y2:{P[b][1]}}},duration:{dur},ease:"{ease}"}},{t:.2f});')
    js.append(f'tl.to("#head",{{attr:{{cx:{P["head"][0]},cy:{P["head"][1]}}},duration:{dur},ease:"{ease}"}},{t:.2f});')
    if KIND == 'cartons':
        hx, hy = HANDS[name]
        js.append(f'tl.to("#stack",{{x:{hx},y:{hy - 2},duration:{dur},ease:"{ease}"}},{t:.2f});')
    cur['pose'] = name

def fig_svg(P0):
    s = ['<svg class="fig" viewBox="0 0 1080 1920"><defs><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>']
    if KIND == 'attaches':
        s.append('<g id="teth" stroke="#F6F2EA" stroke-width="3" stroke-linecap="round" opacity=".85" filter="url(#glow)">' + ''.join(f'<line id="tl{k}" x1="0" y1="0" x2="0" y2="0"/>' for k in range(len(LABELS))) + '</g>')
    s.append('<g id="fig" filter="url(#glow)" stroke="#F6F2EA" stroke-width="9" stroke-linecap="round" fill="none">')
    for a, b in SEGS:
        s.append(f'<line id="s_{a}_{b}" x1="{P0[a][0]}" y1="{P0[a][1]}" x2="{P0[b][0]}" y2="{P0[b][1]}"/>')
    s.append(f'<circle id="head" cx="{P0["head"][0]}" cy="{P0["head"][1]}" r="34" fill="{'#241C30' if AMB == 'aube' else '#07060A'}"/></g></svg>')
    return ''.join(s)

def B(act):  # temps forts d'un type : [(début, fin, n)]
    return [(starts[i], ends[i], beats[i].get('_n', 1)) for i, a in enumerate(acts) if a == act]

# 4. scène selon la métaphore
n = len(LABELS)
if KIND == 'cartons':
    h.append(fig_svg(POSES['stand']))
    hx, hy = HANDS['carry']
    js.append(f'tl.set("#stack",{{x:{hx},y:{hy - 2}}},0);')
    h.append('<div id="stack">')
    widths, OFF = [], [0, -14, 10, -8, 12, -4]
    for k, lab in enumerate(LABELS):
        w = int(len(lab) * (27 if AR else 19) + 50); widths.append(w)
        top = -(60 * (k + 1) + 4 * k)
        h.append(f'<div class="lab{" red" if k == n - 1 else ""}" id="b{k}" style="left:{-w / 2 + OFF[k % 6]:.0f}px;top:{top}px">{esc(lab)}</div>')
    h.append('</div>')
    h.append(f'<div class="paper" id="paper"><h4>{esc(job.get("paper") or ("غدا" if AR else "DEMAIN"))}</h4>' + ''.join(f'<div class="pl" id="pl{k}" style="top:{66 + 36 * k}px">— {esc(lab.strip("« »"))}</div>' for k, lab in enumerate(LABELS)) + '</div>')
    cn = 'العبء الذهني' if AR else 'CHARGE MENTALE'
    for k in range(1, n + 1): h.append(f'<div class="cnt" id="cn{k}"><b>{cn} ×{k}</b></div>')
    inhead, onpaper = ('في رأسك', 'على الورقة') if AR else ('DANS TA TÊTE', 'SUR LE PAPIER')
    for k in range(n): h.append(f'<div class="cnt" id="cu{k}"><b>{inhead} ×{k}</b> · <i>{onpaper} ×{n - k}</i></div>')
    k = 0; carried = False
    for a, b, m in B('drop'):
        if not carried: pose(max(0, a - .1), 'carry', .5); carried = True
        step = max(.55, (b - a - .3) / max(1, m))
        for j in range(m):
            if k >= n: break
            t = a + .15 + j * step
            js.append(f'tl.fromTo("#b{k}",{{opacity:0,y:-150}},{{opacity:1,y:0,duration:.4,ease:"power3.in"}},{t:.2f});tl.fromTo("#b{k}",{{scaleY:.8,scaleX:1.07}},{{scaleY:1,scaleX:1,duration:.25,ease:"back.out(3)"}},{t + .45:.2f});')
            js.append(f'tl.set("#cn{k + 1}",{{opacity:1}},{t + .45:.2f});' + (f'tl.set("#cn{k}",{{opacity:0}},{t + .45:.2f});' if k else ''))
            js.append(f'tl.fromTo("#shadow",{{scaleX:1.25}},{{scaleX:1,duration:.3}},{t + .45:.2f});')
            SFX.append(('impact', t + .42, -16 if k < n - 1 else -12))
            js.append(f'tl.fromTo("#dust",{{opacity:.9,scale:.5}},{{opacity:0,scale:1.4,duration:.9,ease:"power2.out"}},{t + .42:.2f});')
            k += 1
            if k == max(2, n // 2): pose(t + .5, 'bend', .7)
            if k == n: pose(t + .55, 'kneel', .7)
    for a, b, m in B('shake'):
        r = max(1, int((b - a) / .2))
        js.append(f'tl.to("#stack",{{rotation:-1.8,duration:.1,yoyo:true,repeat:{r * 2 - 1},ease:"sine.inOut"}},{a + .1:.2f});')
        js.append(f'tl.to("#b{n - 1}",{{boxShadow:"0 0 46px rgba(229,72,77,.9)",duration:.5,yoyo:true,repeat:{max(1, int((b - a) / .5)) | 1}}},{a + .1:.2f});')
        SFX.append(('heartbeat', a + .2, -18))
    for a, b, m in B('paper'):
        js.append(f'tl.fromTo("#paper",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.6,ease:"power2.out"}},{a + .2:.2f});'); SFX.append(('ding', a + .3, -20))
    done = 0; ub = B('unload')
    if ub and not B('paper'): js.append(f'tl.fromTo("#paper",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.6}},{ub[0][0]:.2f});')
    if ub: js.append(f'tl.to("#cn{n}",{{opacity:0,duration:.3}},{ub[0][0]:.2f});')
    kx, ky = HANDS['kneel']
    for a, b, m in ub:
        step = max(.5, (b - a - .4) / max(1, m))
        for j in range(m):
            if done >= n: break
            k = n - 1 - done; t = a + .2 + j * step
            px = (X(675) - 340 if AR else 675) + 170; py = 1005 + 66 + 36 * k
            top = -(60 * (k + 1) + 4 * k)
            js.append(f'tl.to("#b{k}",{{x:{px - kx - (-widths[k] / 2 + OFF[k % 6]) - widths[k] / 2:.0f},y:{py - ky - top - 30:.0f},scale:.3,opacity:0,duration:.55,ease:"power2.inOut"}},{t:.2f});')
            js.append(f'tl.fromTo("#pl{k}",{{opacity:0,x:{12 if AR else -12}}},{{opacity:1,x:0,duration:.35,ease:"power2.out"}},{t + .45:.2f});')
            c = n - 1 - done
            js.append(f'tl.set("#cu{c}",{{opacity:1}},{t + .45:.2f});' + (f'tl.set("#cu{c + 1}",{{opacity:0}},{t + .45:.2f});' if done else ''))
            SFX.append(('whoosh', t, -22)); SFX.append(('scribble', t + .42, -24))
            done += 1
            if done == n // 2: pose(t + .5, 'bend', .7)
        last_unload = b
    if ub: js.append(f'tl.to("#cu0",{{opacity:0,duration:.35}},{ub[-1][1] - .2:.2f});')
elif KIND == 'portes':
    nd = n; gap = 18; dw = 150; total = nd * dw + (nd - 1) * gap
    x0 = (W - total) / 2
    for P in POSES.values():  # personnage devant la porte du milieu, plus petit et plus bas
        pass
    for k, lab in enumerate(LABELS):
        x = x0 + k * (dw + gap) if not AR else W - (x0 + k * (dw + gap)) - dw
        h.append(f'<div class="door" id="d{k}" style="left:{x:.0f}px"><div class="lt" id="dl{k}"></div><div class="lf" id="df{k}"></div><div class="tag">{esc(lab)}</div><div class="st" id="ds{k}">{"مغلق" if AR else "FERMÉE"}</div></div>')
    h.append(fig_svg(POSES['stand']))
    js.append('tl.set("#fig",{transformOrigin:"50% 100%",y:120,scale:.72},0);')
    cl, op = ('مغلق', 'مفتوح') if AR else ('FERMÉE', 'OUVERTE')
    for k in range(1, nd + 1): h.append(f'<div class="cnt" id="cc{k}"><b>{cl} ×{k}</b></div>')
    for k in range(1, nd + 1): h.append(f'<div class="cnt" id="co{k}"><b>{cl} ×{nd - k}</b> · <i>{op} ×{k}</i></div>')
    # au début, les portes sont entrouvertes (lumière dedans)
    for k in range(nd): js.append(f'tl.set("#dl{k}",{{opacity:.55}},0);tl.set("#df{k}",{{rotationY:-55}},0);')
    k = 0
    for a, b, m in B('close'):
        step = max(.7, (b - a - .3) / max(1, m))
        for j in range(m):
            if k >= nd: break
            t = a + .2 + j * step
            js.append(f'tl.to("#df{k}",{{rotationY:0,duration:.35,ease:"power3.in"}},{t:.2f});tl.to("#dl{k}",{{opacity:0,duration:.3}},{t + .1:.2f});')
            js.append(f'tl.fromTo("#ds{k}",{{opacity:0,scale:1.8}},{{opacity:1,scale:1,duration:.25,ease:"back.out(2)"}},{t + .4:.2f});')
            js.append(f'tl.set("#cc{k + 1}",{{opacity:1}},{t + .4:.2f});' + (f'tl.set("#cc{k}",{{opacity:0}},{t + .4:.2f});' if k else ''))
            SFX.append(('impact', t + .33, -15))
            k += 1
            if k == max(2, nd // 2): pose(t + .5, 'sad', .7)
            if k == nd: pose(t + .55, 'kneel', .8)
    for a, b, m in B('shake'):
        js.append(f'tl.to(".door",{{x:"+=4",duration:.08,yoyo:true,repeat:{max(3, int((b - a) / .16)) | 1}}},{a + .1:.2f});'); SFX.append(('heartbeat', a + .2, -18))
    sm = B('small')
    for a, b, m in sm:
        pose(a + .1, 'stand', .7); pose(a + .9, 'reach', .6)
        js.append(f'tl.to("#fig",{{x:{(x0 + dw / 2 if not AR else W - x0 - dw / 2) - 540:.0f},duration:{max(.8, b - a - 1.2):.2f},ease:"power1.inOut"}},{a + .3:.2f});')
        js.append(f'tl.to("#ds0",{{opacity:0,duration:.3}},{b - .6:.2f});tl.to("#df0",{{rotationY:-70,duration:.6,ease:"power2.out"}},{b - .5:.2f});tl.to("#dl0",{{opacity:1,duration:.5}},{b - .5:.2f});')
        SFX.append(('riser', a + .2, -22))
    opened = 1 if sm else 0
    if sm: js.append(f'tl.set("#co1",{{opacity:1}},{sm[0][1] - .3:.2f});tl.set("#cc{nd}",{{opacity:0}},{sm[0][1] - .3:.2f});')
    for a, b, m in B('open'):
        step = max(.45, (b - a - .3) / max(1, m))
        for j in range(m):
            if opened >= nd: break
            k = opened; t = a + .15 + j * step
            js.append(f'tl.to("#ds{k}",{{opacity:0,duration:.2}},{t:.2f});tl.to("#df{k}",{{rotationY:-70,duration:.5,ease:"power2.out"}},{t:.2f});tl.to("#dl{k}",{{opacity:1,duration:.45}},{t:.2f});')
            js.append(f'tl.set("#co{k + 1}",{{opacity:1}},{t + .3:.2f});' + (f'tl.set("#co{k}",{{opacity:0}},{t + .3:.2f});' if k else f'tl.set("#cc{nd}",{{opacity:0}},{t + .3:.2f});'))
            SFX.append(('pop', t + .1, -20)); opened += 1
    ob = B('open')
    if ob: js.append(f'tl.to("#co{nd}",{{opacity:0,duration:.35}},{ob[-1][1] - .2:.2f});')
else:  # attaches
    AN = [(170, 1230), (910, 1230), (250, 760), (830, 760), (540, 1290), (540, 640)][:n]
    AN = [(X(x), y) for x, y in AN]
    for k, (x, y) in enumerate(AN):
        h.append(f'<div class="anc" id="a{k}" style="left:{x}px;top:{y}px"><i></i><span>{esc(LABELS[k])}</span></div>')
    h.append(fig_svg(POSES['open']))
    js.append('tl.set("#fig",{transformOrigin:"50% 60%",y:-160},0);')
    waist = lambda: (540, 1040 - 160)
    wx, wy = waist()
    for k, (x, y) in enumerate(AN): js.append(f'tl.set("#tl{k}",{{attr:{{x1:{wx},y1:{wy},x2:{x},y2:{y}}}}},0);')
    js.append(f'tl.to("#fig",{{y:-175,duration:1.6,yoyo:true,repeat:{int(END / 1.6)},ease:"sine.inOut"}},0);')  # flotte doucement
    lk, rl = ('مقطوع', 'مربوط') if AR else ('LÂCHÉ', 'RELIÉ')
    for k in range(1, n + 1): h.append(f'<div class="cnt" id="cx{k}"><b>{lk} ×{k}</b></div>')
    for k in range(1, n + 1): h.append(f'<div class="cnt" id="cr{k}"><i>{rl} ×{k}</i></div>')
    k = 0; drift = 0
    for a, b, m in B('cut'):
        step = max(.7, (b - a - .3) / max(1, m))
        for j in range(m):
            if k >= n: break
            t = a + .2 + j * step
            js.append(f'tl.to("#tl{k}",{{attr:{{x1:"{AN[k][0]}",y1:"{AN[k][1]}"}},opacity:0,duration:.35,ease:"power3.in"}},{t:.2f});tl.to("#a{k}",{{opacity:.3,duration:.4}},{t + .2:.2f});')
            js.append(f'tl.set("#cx{k + 1}",{{opacity:1}},{t + .3:.2f});' + (f'tl.set("#cx{k}",{{opacity:0}},{t + .3:.2f});' if k else ''))
            drift += 1
            js.append(f'tl.to("#fig",{{rotation:{(-1 if AR else 1) * 6 * drift},opacity:{1 - .13 * drift:.2f},duration:.7}},{t + .2:.2f});')
            SFX.append(('whoosh', t + .1, -18)); k += 1
            if k == n: pose(t + .5, 'sad', .9)
    for a, b, m in B('drift'):
        js.append(f'tl.to("#fig",{{scale:.7,duration:{b - a:.2f},ease:"sine.inOut"}},{a:.2f});'); SFX.append(('riser', a, -24))
    cb = B('cut')
    if cb: js.append(f'tl.to("#cx{n}",{{opacity:0,duration:.3}},{cb[-1][1]:.2f});')
    k = 0
    for a, b, m in B('relink'):
        step = max(.6, (b - a - .3) / max(1, m))
        if k == 0: pose(a + .1, 'open', .8); js.append(f'tl.to("#fig",{{scale:1,rotation:0,opacity:1,duration:1}},{a + .1:.2f});')
        for j in range(m):
            if k >= n: break
            t = a + .4 + j * step
            js.append(f'tl.to("#a{k}",{{opacity:1,duration:.3}},{t:.2f});tl.fromTo("#tl{k}",{{attr:{{x1:{AN[k][0]},y1:{AN[k][1]}}},opacity:1}},{{attr:{{x1:{wx},y1:{wy}}},duration:.5,ease:"power2.out"}},{t:.2f});tl.to("#tl{k}",{{stroke:"#F2A541",duration:.4}},{t + .4:.2f});')
            js.append(f'tl.set("#cr{k + 1}",{{opacity:1}},{t + .4:.2f});' + (f'tl.set("#cr{k}",{{opacity:0}},{t + .4:.2f});' if k else ''))
            SFX.append(('pop', t + .4, -20)); k += 1
    rb = B('relink')
    if rb: js.append(f'tl.to("#cr{n}",{{opacity:0,duration:.35}},{rb[-1][1] - .2:.2f});')

# lumière et fin (communs)
rise = B('rise')
if rise:
    a, b, m = rise[0]
    if KIND != 'attaches': pose(a + .1, 'stand', .9, 'power2.out')
    js.append(f'tl.to("#light",{{opacity:1,duration:1.6,ease:"power1.out"}},{a:.2f});tl.to("#beam",{{opacity:1,duration:1.2}},{a + .3:.2f});')
    if AMB == 'aube': js.append(f'tl.fromTo("#rays",{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:1.4,ease:"expo.out"}},{a + .2:.2f});tl.to("#sun",{{scale:1.5,duration:1.6}},{a + .2:.2f});')
    if KIND == 'portes': js.append(f'tl.to("#fig",{{x:0,duration:1}},{a:.2f});')
    SFX.append(('ding', a + .6, -16))
h.append('</div>')  # fin #cam
for i, b in enumerate(beats):
    txt = esc(b.get('txt') or '')
    for w in (b.get('hot') or [])[:2]:
        if w and esc(w) in txt: txt = txt.replace(esc(w), f'<b>{esc(w)}</b>', 1)
    h.append(f'<div class="t" id="t{i}">{txt}</div>')
    a, e = starts[i], ends[i]
    if b.get('act') in ('card', 'end'): continue
    js.append(f'tl.set("#t{i}",{{opacity:1}},0);' if i == 0 else f'tl.fromTo("#t{i}",{{opacity:0,y:14}},{{opacity:1,y:0,duration:.4,ease:"power2.out"}},{a:.2f});')
    js.append(f'tl.to("#t{i}",{{opacity:0,duration:.3}},{e - .3:.2f});')
src = job.get('source') or {}
h.append(f'<div class="card" id="card"><p>« {esc(src.get("b"))} »</p><small>{esc(src.get("i"))}</small></div>' if not AR else f'<div class="card" id="card"><p>{esc(src.get("b"))}</p><small>{esc(src.get("i"))}</small></div>')
h.append(f'<div class="end" id="end">{esc(job.get("end"))}</div><div class="save" id="save">{esc(job.get("save") or ("احفظها للأيام الصعبة." if AR else "À GARDER POUR LES JOURS LOURDS."))}</div>')
h.append(f'<div class="note" id="note">{esc(job.get("note"))}</div>')
for a, b, m in B('card'):
    js.append(f'tl.fromTo("#card",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.6,ease:"power2.out"}},{a + .1:.2f});tl.to("#card",{{opacity:0,duration:.35}},{b - .35:.2f});')
    js.append(f'tl.to(".paper",{{opacity:.3,duration:.5}},{a:.2f});')
for a, b, m in B('end'):
    js.append(f'tl.fromTo("#end",{{opacity:0,scale:.96}},{{opacity:1,scale:1,duration:.6,ease:"expo.out"}},{a + .1:.2f});tl.fromTo("#save",{{opacity:0}},{{opacity:1,duration:.5}},{a + 1.3:.2f});tl.fromTo("#note",{{opacity:0}},{{opacity:1,duration:.5}},{a + 1.8:.2f});')
    SFX.append(('ding', a + .2, -19))
# progression (points) : un point par temps fort, l'actuel s'allume
h.append('<div class="dots">' + ''.join(f'<i id="p{i}"></i>' for i in range(len(beats))) + '</div>')
for i in range(len(beats)):
    js.append(f'tl.to("#p{i}",{{backgroundColor:"#F2A541",duration:.2}},{starts[i]:.2f});')
# sous-titres mot à mot (seulement avec voix)
if words:
    groups, g = [], []
    for w in words:
        if g and (g[-1]['b'] != w['b'] or len(g) >= 5): groups.append(g); g = []
        g.append(w)
        if re.search(r'[.?!؟:]$', w['t']): groups.append(g); g = []
    if g: groups.append(g)
    for gi, g in enumerate(groups):
        h.append(f'<div class="cap" id="c{gi}">' + ' '.join(f'<span id="w{gi}_{k}">{esc(w["t"])}</span>' for k, w in enumerate(g)) + '</div>')
        s0 = g[0]['s']; nxt = min([x[0]['s'] for x in groups[gi + 1:]] + [END])
        e0 = min(max(g[-1]['e'] + .15, s0 + .5), nxt)
        if e0 - s0 < .12: continue
        js.append(f'tl.set("#c{gi}",{{opacity:1}},{s0:.2f});tl.set("#c{gi}",{{opacity:0}},{e0:.2f});')
        for k, w in enumerate(g): js.append(f'tl.to("#w{gi}_{k}",{{color:"#F6F2EA",duration:.12}},{w["s"]:.2f});')
h.append('<div class="wm">' + ('د. فهمي' if AR else 'DR FEHMI') + '</div>')
js.append('tl.set("#fig",{opacity:1},0);')
js.append(f'tl.fromTo("#cam",{{scale:1}},{{scale:1.06,duration:{END:.2f},ease:"none"}},0);' if KIND != 'attaches' else '')
js.append(f'tl.to(["#end","#save","#note","#light","#beam",".paper"],{{opacity:0,duration:.6}},{END - .7:.2f});')
js.append('window.__timelines["main"]=tl;')
h.append('</div><script>' + '\n'.join(js) + '</script></body></html>')
open(f'{D}/index.html', 'w').write('\n'.join(h))

# 5. mixage : voix (si présente) + musique (baissée sous la voix) + effets
A = f'{D}/assets'
music = job.get('music') or 'calme'
inp, fc, lab = [], [], []
if VOICE: inp += ['-i', f'{A}/voice_paced.m4a']; fc.append('[0:a]apad[v]'); lab.append('[v]')
if music != 'none' and os.path.exists(f'{A}/music_{music}.m4a'):
    i = len([x for x in inp if x == '-i']); inp += ['-stream_loop', '-1', '-i', f'{A}/music_{music}.m4a']
    fc.append(f'[{i}:a]atrim=0:{END:.2f},volume={-21 if VOICE else -14}dB,afade=t=in:d=1,afade=t=out:st={END - 2:.2f}:d=2[m]'); lab.append('[m]')
if job.get('sfx', True) is not False:
    for s, t, g in SFX:
        if not os.path.exists(f'{A}/sfx_{s}.m4a') or t >= END: continue
        i = len([x for x in inp if x == '-i']); inp += ['-i', f'{A}/sfx_{s}.m4a']
        fc.append(f'[{i}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={g}dB[x{i}]'); lab.append(f'[x{i}]')
if not lab:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo', '-t', f'{END:.2f}', '-c:a', 'aac', f'{A}/mix.m4a'], check=True)
else:
    fc.append(''.join(lab) + f'amix=inputs={len(lab)}:normalize=0,atrim=0:{END:.2f}[out]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{A}/mix.m4a'], check=True)
json.dump({'starts': [round(s, 2) for s in starts], 'end': round(END, 2)}, open(f'{D}/timing.json', 'w'))
print('métaphore', KIND, 'temps forts', len(beats), 'durée', round(END, 2), 'voix' if VOICE else 'texte seul')
