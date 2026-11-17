# Vidéo longue YouTube (16:9, chapitres) — même moteur que les Shorts Radar : style R7 calé sur la voix réelle.
# Usage : python3 long_build.py <dossier>
#   <dossier>/job.json              {format:"long", lang, chapters:[titre], plans:[{ch, say, title, _file, gfx, hot, …}]}
#   <dossier>/assets/voice.m4a      voix (la tienne ou la voix clonée)
#   <dossier>/assets/transcript.json  mots horodatés (hyperframes transcribe)
# Animation (v3, 17 nov. 2026) : titres et phrases animés par mot (jamais par lettre), entrées variées et échelonnées,
#   sorties courtes, chiffres qui comptent, trait dessiné sous le mot clé, carte de chapitre qui glisse, caméra continue.
#   Le minutage (starts, durée, timing.json) ne dépend pas de l'animation.
# Sortie : index.html, assets/voice_final.m4a (prises ratées et longs silences coupés), timing.json
import json, os, re, sys, subprocess, unicodedata, difflib, html as H

D = sys.argv[1]
W, HT = 1920, 1080
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
for a, b in zip(words, words[1:]):  # minutage toujours croissant : deux sous-titres ne peuvent jamais s'afficher ensemble
    if b['s'] < a['s']: b['s'] = a['s']
    if b['e'] < b['s'] + 0.05: b['e'] = b['s'] + 0.05

# format long : rythme posé, silences de plus de 0,8 s ramenés à 0,45 s (0,9 s entre deux chapitres)
for a, b in zip(words, words[1:]):
    gap = 0.9 if plans[b['p']].get('ch') != plans[a['p']].get('ch') else 0.45
    if b['s'] - a['e'] > gap + 0.35 and not any(c0 <= a['e'] < c1 for c0, c1 in cuts):
        cuts.append((a['e'] + gap / 2, b['s'] - gap / 2))
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
    if len(cur) == 6 or re.search(r'[.:?!؟]$', w['t']) or (len(cur) >= 3 and re.search(r'[,،]$', w['t'])): groups.append(cur); cur = []
if cur: groups.append(cur)
HOT = [{norm(x) for h in p.get('hot', []) for x in str(h).split() if len(norm(x)) > 2} for p in plans]  # expressions → mots
def word_html(w):
    k = norm(w['t'])
    hot = k and any(k == h or (len(h) > 3 and k.startswith(h)) for h in HOT[w['p']])
    return f'<span{" class=\"hot\"" if hot else ""}>{H.escape(w["t"])}</span>'

# --- moteur d'animation v3 (17 nov. 2026) : textes animés par mot, sorties, chiffres qui comptent, trait dessiné sur le mot clé ---
# Garde-fous de forme : avertissements seulement, la construction continue.
from collections import Counter
_img, _k = Counter(p['_file'] for p in plans).most_common(1)[0]
if len(plans) > 3 and _k > len(plans) / 2:
    print(f'ATTENTION : {_k} plans sur {len(plans)} ont la même image ({_img}) : choisir une image du pack par plan (champ img)')
_long = [i for i, p in enumerate(plans) if len(str(p.get('title', '')).replace('·', ' ').split()) > 6]
if _long: print(f'ATTENTION : titre de plus de 6 mots aux plans {_long} : à raccourcir dans la fiche')

ARAB = re.compile(r'[؀-ۿݐ-ݿࢠ-ࣿ]')
def toks(t):
    """Mots d'un texte à l'écran. Jamais de découpe par lettre (ligatures arabes). En arabe, une suite sans lettre
    arabe qui contient du latin (« GTA 6 », « Drake et al. ») reste en un seul bloc : sinon l'ordre d'affichage s'inverse."""
    out = []
    for w in re.split(r'[ \t\n]+', nb(t).strip()):
        if not w: continue
        if AR and out and not ARAB.search(w) and not ARAB.search(out[-1]) and re.search(r'[A-Za-z]', out[-1] + w): out[-1] += ' ' + w
        else: out.append(w)
    return out
def spans(t, cls):
    return ' '.join(f'<span class="{cls}">{H.escape(w)}</span>' for w in toks(t))
def swoosh(sid):  # trait doré qui se dessine sous un mot (départ à droite en arabe)
    d = 'M98,7 Q52,1 2,8' if AR else 'M2,7 Q48,1 98,8'
    return f'<svg class="sw" viewBox="0 0 100 12" preserveAspectRatio="none" data-layout-ignore><path id="{sid}" d="{d}" pathLength="1" fill="none" stroke="#F2A541" stroke-width="5" stroke-linecap="round" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/></svg>'
def title_html(i, p, mark):
    """Titre découpé en mots ; mot clé (mot « hot », sinon 1er nombre qui n'est pas un numéro de liste) en doré, souligné,
    et compté s'il s'agit d'une quantité (≥ 10, pas une année). Rend (html, nombre de mots, mot clé ?, (départ, valeur) du compteur)."""
    tk = toks(p.get('title', ''))
    ki = None
    if mark:
        ki = next((k for k, w in enumerate(tk) if norm(w) and any(norm(w) == x or (len(x) > 3 and norm(w).startswith(x)) for x in HOT[i])), None)
        if ki is None: ki = next((k for k, w in enumerate(tk) if re.search(r'\d', w) and not re.fullmatch(r'\d+[.)]', w)), None)
    out, cnt = [], None
    for k, w in enumerate(tk):
        if k != ki:
            out.append(f'<span class="w">{H.escape(w)}</span>'); continue
        m = re.fullmatch(r'(\D*)(\d+)(\D*)', w)
        if m and p.get('countup', True) is not False and int(m[2]) >= 10 and str(int(m[2])) == m[2] and not 1900 <= int(m[2]) <= 2100:
            cnt = (10 ** (len(m[2]) - 1), int(m[2]))  # même nombre de chiffres du début à la fin : le texte ne bouge pas
            body = f'{H.escape(m[1])}<b id="n{i}">{m[2]}</b>{H.escape(m[3])}'
        else:
            body = H.escape(w)
        out.append(f'<span class="w k">{body}{swoosh(f"ks{i}")}</span>')
    return ' '.join(out), len(tk), ki is not None, cnt
def out(sel, t, hard):  # sortie plus courte que l'entrée (.in) ; coupe franche si la carte de chapitre recouvre déjà le plan
    return f'tl.set({sel},{{opacity:0}},{t:.2f});' if hard else f'tl.to({sel},{{opacity:0,duration:.2,ease:"power2.in"}},{max(0, t - .2):.2f});'

TF, CF = ('Cairo', 'Cairo') if AR else ('Fraunces', 'Archivo')
DIR = 'rtl' if AR else 'ltr'
ST = 'right' if AR else 'left'  # côté où commence la lecture
# palette : chaîne arabe = ops/state/anim/DESIGN.md (fond #120E16, panneau #1C1622, texte blanc) ; français inchangé
BG, BGR, FG, MUT, PAN = ('#120E16', '18,14,22', '#FFFFFF', 'rgba(255,255,255,.72)', '#1C1622') if AR else ('#17121C', '23,18,28', '#F6EEE3', '#A89AA6', '#3A2E40')
# colonnes : illustration à gauche et texte à droite (inversé en arabe)
IL, TL, TWID = (1040, 120, 820) if AR else (120, 980, 820)
css = f'''
@font-face{{font-family:"Fraunces";src:url("assets/Fraunces.ttf") format("truetype")}}
@font-face{{font-family:"Archivo";src:url("assets/Archivo.ttf") format("truetype")}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-ar.ttf") format("truetype");unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F}}
@font-face{{font-family:"Cairo";src:url("assets/Cairo-la.ttf") format("truetype");unicode-range:U+0000-024F,U+2000-206F,U+20AC}}
body{{margin:0;width:{W}px;height:{HT}px;overflow:hidden;background:{BG}}}
#root{{position:relative;width:{W}px;height:{HT}px;background:{BG};overflow:hidden;font-family:"{CF}",sans-serif}}
.dust{{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(242,165,65,.55),rgba(242,165,65,.12) 45%,rgba(242,165,65,0) 70%)}}
.vign{{position:absolute;inset:0;background:radial-gradient(ellipse 70% 75% at 50% 50%,rgba({BGR},0) 55%,rgba(10,7,12,.75) 100%)}}
.halo{{position:absolute;left:{IL - 40}px;top:120px;width:840px;height:840px;border-radius:50%;background:radial-gradient(circle,rgba(242,165,65,.30),rgba(242,165,65,.10) 40%,rgba(242,165,65,0) 68%)}}
.ttl{{position:absolute;top:190px;left:{TL}px;width:{TWID}px;text-align:start;direction:{DIR};font-family:"{TF}";font-weight:800;font-size:{60 if AR else 64}px;line-height:{1.25 if AR else 1.08};color:{FG};opacity:0}}
.ttl.solo{{top:0;height:{HT - 160}px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;font-size:{70 if AR else 78}px}}
.w,.qw,.cw{{display:inline-block}}
.k{{position:relative;display:inline-block}}
.ttl .k{{color:#F2A541}}
.k b{{font-weight:inherit;font-variant-numeric:tabular-nums}}
.sw{{position:absolute;left:-3%;width:106%;bottom:-.04em;height:.2em;overflow:visible}}
.sw path{{opacity:0}}
.rl{{display:block;text-decoration:none;width:150px;height:6px;border-radius:3px;background:#F2A541;margin-top:28px;transform-origin:{ST} center}}
.ill{{position:absolute;left:{IL}px;top:160px;width:760px;height:760px;opacity:0}}
.ill img{{width:100%;height:100%;object-fit:cover;display:block;-webkit-mask-image:radial-gradient(circle,#000 52%,transparent 71%);mask-image:radial-gradient(circle,#000 52%,transparent 71%)}}
.cap{{position:absolute;z-index:50;top:952px;left:220px;right:220px;text-align:center;direction:{DIR};font-family:"{CF}";font-weight:800;font-size:44px;line-height:{1.3 if AR else 1.12};color:{FG};opacity:0;text-shadow:0 2px 12px rgba(10,7,12,.9)}}
.cap span{{display:inline-block;margin:0 7px}}
.hot{{color:#F2A541}}
.g{{position:absolute;opacity:0}}
.col{{left:{TL}px;width:{TWID}px}}
.lbl{{font-family:"{CF}";font-weight:800;font-size:36px;letter-spacing:{0 if AR else 3}px;color:#F2A541;text-align:start;direction:{DIR}}}
.card{{position:absolute;left:{TL}px;width:{TWID}px;box-sizing:border-box;top:470px;background:rgba({BGR},.9);border:2px solid rgba(242,165,65,.45);border-radius:26px;padding:28px 36px;text-align:start;direction:{DIR};opacity:0}}
.card b{{display:block;font-family:"{TF}";font-weight:800;font-size:{52 if AR else 44}px;line-height:1.15;color:{FG}}}
.card u{{display:block;text-decoration:none;width:96px;height:4px;border-radius:2px;background:#F2A541;margin-top:16px;transform-origin:{ST} center}}
.card i{{display:block;font-style:normal;font-family:"Archivo","Cairo";font-weight:{600 if AR else 800};font-size:{34 if AR else 26}px;color:{MUT};margin-top:12px}}
#fade{{position:absolute;inset:0;z-index:60;background:{BG};opacity:0}}
#prog{{position:absolute;z-index:45;left:0;bottom:0;height:8px;width:{W}px;background:#F2A541;transform-origin:{ST} center;opacity:.9}}
.tick{{position:absolute;z-index:46;bottom:0;width:4px;height:16px;background:{FG};opacity:.55}}
.panel{{position:absolute;left:{TL}px;width:{TWID}px;box-sizing:border-box;top:440px;direction:{DIR};opacity:0}}
.it{{display:flex;align-items:center;gap:22px;box-sizing:border-box;margin-bottom:14px;padding:12px 24px;border-radius:22px;background:rgba({BGR},.82);border:2px solid rgba(242,165,65,.35);font-family:"{CF}";font-weight:800;font-size:{44 if AR else 38}px;color:{FG}}}
.it b{{flex:none;width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:32px;color:{BG};background:#F2A541}}
.it.no{{border-color:rgba(255,255,255,.16)}}
.it.no b{{background:{PAN};color:{MUT};box-shadow:inset 0 0 0 2px rgba(255,255,255,.22)}}
.split{{position:absolute;left:{TL}px;width:{TWID}px;top:450px;display:flex;gap:22px;direction:{DIR}}}
.split div{{flex:1;border-radius:24px;padding:22px 22px;text-align:center;opacity:0}}
.split.st{{flex-direction:column;gap:18px}}
.split.st div{{flex:none;text-align:start;padding:22px 32px}}
.split small{{display:block;font-family:"Archivo","Cairo";font-weight:800;font-size:{34 if AR else 24}px;letter-spacing:{0 if AR else 2}px;text-transform:uppercase;margin-bottom:8px}}
.split p{{margin:0;font-family:"{TF}";font-weight:800;font-size:36px;line-height:1.2;color:{FG}}}
.split.st p{{font-size:{46 if AR else 42}px}}
.sl{{background:{"#1C1622" if AR else "rgba(58,46,64,.92)"};border:2px solid rgba(255,255,255,.14)}} .sl small{{color:{MUT}}}
.sr{{background:rgba(242,165,65,.16);border:2px solid #F2A541}} .sr small{{color:#F2A541}}
.quote{{position:absolute;left:{TL}px;width:{TWID}px;box-sizing:border-box;top:440px;background:rgba({BGR},.85);border-radius:24px;padding:10px 30px 26px;text-align:start;direction:{DIR};font-family:"{TF}";font-weight:800;font-style:{"normal" if AR else "italic"};font-size:{56 if AR else 46}px;line-height:1.22;color:{FG};opacity:0}}
.qm{{display:block;font-style:normal;font-size:100px;line-height:.6;color:#F2A541;transform-origin:{ST} center}}
.bigw{{position:absolute;left:{TL}px;width:{TWID}px;top:470px;text-align:start;direction:{DIR};font-family:"{TF}";font-weight:800;font-size:{140 if AR else 160}px;line-height:1;color:#F2A541;text-shadow:0 10px 40px rgba({BGR},.9),0 0 4px {BG};opacity:0}}
.stamp{{position:absolute;left:{IL + (40 if AR else 440)}px;top:150px;font-family:"{TF}";font-weight:800;font-size:96px;color:#F2A541;border:9px solid #F2A541;border-radius:16px;padding:0 26px;background:rgba({BGR},.85);opacity:0}}
.timer{{position:absolute;left:{TL + TWID // 2 - 100}px;top:480px;width:200px;height:200px;opacity:0}}
.timer span{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:"{TF if AR else "Fraunces"}";font-weight:800;font-size:96px;color:{FG}}}
.chap{{position:absolute;top:0;bottom:0;left:-8px;right:-8px;z-index:40;background:{"#1C1622" if AR else "#211A28"};border-left:8px solid #F2A541;border-right:8px solid #F2A541;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;opacity:0;direction:{DIR}}}
.chap small{{font-family:"Archivo","Cairo";font-weight:800;font-size:{38 if AR else 34}px;letter-spacing:{0 if AR else 8}px;color:#F2A541;text-transform:uppercase}}
.chap b{{max-width:1400px;text-align:center;font-family:"{TF}";font-weight:{900 if AR else 800};font-size:{92 if AR else 88}px;line-height:1.15;color:{FG}}}
.chap i{{width:140px;height:6px;border-radius:3px;background:#F2A541;transform-origin:{ST} center}}
.chl{{position:absolute;top:40px;{ST}:60px;max-width:900px;font-family:"Archivo","Cairo";font-weight:800;font-size:{34 if AR else 26}px;letter-spacing:{0 if AR else 2}px;color:{MUT};text-transform:uppercase;direction:{DIR};opacity:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
'''
# fond : poussières de lumière ambrée qui montent lentement (positions fixes, pas de hasard au rendu)
import random
RND = random.Random(7)
dust = []
for k in range(22):
    size = RND.choice([10, 14, 18, 26, 40, 60])
    dust.append((k, RND.randint(40, W - 60), RND.randint(200, HT - 60), size, RND.uniform(.25, .7), RND.randint(120, 320), RND.uniform(6, 11)))
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

# chapitres : carte plein écran au début de chacun (sauf l'intro), titre discret en haut, repères sur la barre.
# La carte est la transition entre deux chapitres : elle glisse par-dessus le plan qui finit (resté entier), tient, puis
# repart en découvrant le plan suivant. 1,65 s en tout, et rien ne bouge avant le début du chapitre.
CHT = job.get('chapters') or []
chs = []  # (n° de chapitre, 1er plan, début)
for i, p in enumerate(plans):
    c = int(p.get('ch', 0))
    if not chs or chs[-1][0] != c: chs.append((c, i, 0.0 if not chs else starts[i]))
cards = {i0 for n, (c, i0, t0) in enumerate(chs) if n and c < len(CHT) and CHT[c]}  # plans précédés d'une carte
CX = -100 if AR else 100  # la carte arrive du côté où va la lecture
for n, (c, i0, t0) in enumerate(chs):
    t1 = chs[n + 1][2] if n + 1 < len(chs) else END
    title = CHT[c] if c < len(CHT) else ''
    if not title: continue
    h.append(f'<div class="chl" id="chl{n}">{H.escape(nb(title))}</div>')
    nxt_card = n + 1 < len(chs) and chs[n + 1][1] in cards
    js.append(f'tl.fromTo("#chl{n}",{{opacity:0,y:-12}},{{opacity:.9,y:0,duration:.5,ease:"power1.out"}},{t0 + (1.75 if n else .5):.2f});tl.set("#chl{n}",{{opacity:0}},{t1 + (.42 if nxt_card else 0):.2f});')
    if n:
        h.append(f'<div class="tick" style="{ST}:{W * t0 / END:.0f}px"></div>')
        h.append(f'<div class="chap" id="chap{n}"><small>{"الفصل" if AR else "Chapitre"} {n}</small><b>{spans(title, "cw")}</b><i></i></div>')
        nw = max(1, len(toks(title)))
        js.append(f'tl.set("#chap{n}",{{opacity:1}},{t0:.2f});tl.fromTo("#chap{n}",{{xPercent:{CX}}},{{xPercent:0,duration:.4,ease:"power3.inOut"}},{t0:.2f});'
                  f'tl.fromTo("#chap{n} small",{{opacity:0,y:-18}},{{opacity:1,y:0,duration:.35,ease:"power2.out"}},{t0 + .14:.2f});'
                  f'tl.fromTo("#chap{n} .cw",{{opacity:0,y:40}},{{opacity:1,y:0,duration:.45,ease:"expo.out",stagger:{min(.07, .24 / nw):.3f}}},{t0 + .2:.2f});'
                  f'tl.fromTo("#chap{n} i",{{scaleX:0}},{{scaleX:1,duration:.5,ease:"power4.out"}},{t0 + .5:.2f});'
                  f'tl.to("#chap{n}",{{xPercent:{-CX},duration:.4,ease:"power3.in"}},{t0 + 1.25:.2f});tl.set("#chap{n}",{{opacity:0}},{t0 + 1.66:.2f});')
        SFX.append(('whoosh', max(0, t0 - .25), -16)); SFX.append(('ding', t0 + .2, -18))

# minutage de chaque plan : TA = entrée du texte, TI = arrivée de l'image, TB = sortie du texte (starts / END ne changent jamais)
run0 = []  # 1er plan de la suite d'images identiques : une seule image dans la page par suite, caméra continue
for i, p in enumerate(plans):
    run0.append(run0[-1] if i and plans[i - 1]['_file'] == p['_file'] else i)
TA, TI, TB = [], [], []
for i in range(len(plans)):
    a, b = starts[i], ends[i]
    TA.append(max(a, min(a + 1.35, b - 1.0)) if i in cards else a)  # le plan se construit pendant que la carte repart
    TI.append(min(a + .6, TA[-1]) if i in cards else a)             # l'image change sous la carte
    TB.append(b + .42 if i + 1 in cards else b)                     # le plan reste entier jusqu'à ce que la carte le recouvre
IN_I = ['{opacity:0,y:40},{opacity:1,y:0,duration:.45,ease:"power2.out"}', '{opacity:0,x:%d},{opacity:1,x:0,duration:.55,ease:"expo.out"}' % (60 if AR else -60),
        '{opacity:0,scale:.9},{opacity:1,scale:1,duration:.6,ease:"back.out(1.4)"}', '{opacity:0},{opacity:1,duration:.35,ease:"power1.out"}']
IN_T = [('{opacity:0,y:30}', 'opacity:1,y:0,duration:.45,ease:"power3.out"'), ('{opacity:0,x:%d}' % (-40 if AR else 40), 'opacity:1,x:0,duration:.5,ease:"expo.out"'),
        ('{opacity:0,scale:1.14}', 'opacity:1,scale:1,duration:.35,ease:"power4.out"'), ('{opacity:0,y:-24}', 'opacity:1,y:0,duration:.5,ease:"circ.out"')]
cam = (1.0, 0)  # (zoom, glissement) de la caméra à la fin du plan précédent

for i, p in enumerate(plans):
    a, b, ai, fu = TA[i], TB[i], TI[i], 0.45
    last = i == len(plans) - 1
    hard = last or i + 1 in cards
    r0 = run0[i]; ie = f'#i{r0}'
    new_img = r0 == i
    run_end = last or run0[i + 1] != r0
    g = p.get('gfx') or 'none'
    pw = [w for w in words if w['p'] == i]
    solo = g in ('none', 'pulse', 'ring', 'stamp')  # rien dans la colonne : titre centré, plus grand, filet doré dessous
    th, ntok, key, cnt = title_html(i, p, g != 'bigword')
    nch = len(str(p.get('title', '')))
    fsz = f' style="font-size:{(84 if nch <= 22 else 70) if solo else (76 if nch <= 18 else 68 if nch <= 26 else 60)}px"' if AR else ''  # titre court = plus gros (hiérarchie)
    h.append(f'<div class="ttl{" solo" if solo else ""}" id="t{i}"{fsz}><span>{th}</span>{"<u class=rl></u>" if solo else ""}</div>')
    if new_img: h.append(f'<div class="ill" id="i{i}"><img src="assets/{p["_file"]}"></div>')
    if i == 0:  # accroche : image et titre visibles dès la 1re image, coup de zoom (pas de fondu depuis le noir)
        tt = 0.0
        js.append('tl.fromTo("#i0",{opacity:1,scale:1.18},{opacity:1,scale:1,duration:.5,ease:"expo.out"},0);')
        js.append('tl.fromTo("#t0",{opacity:1,scale:1.12},{opacity:1,scale:1,duration:.45,ease:"expo.out"},0);')
        SFX.append(('impact', 0.0, -9))
    else:
        tt = a + (.1 if i in cards else .22 if i % 2 else .3)  # l'image d'abord, le titre ensuite ; jamais à 0
        if new_img:
            if i in cards: js.append(f'tl.set("{ie}",{{opacity:1}},{ai:.2f});')  # découverte par la carte qui repart
            else: js.append(f'tl.fromTo("{ie}",{IN_I[0 if g in ("bigword", "pulse") else i % 4]},{a + .1:.2f});')
            if i % 3 == 0: SFX.append(('whoosh', max(0, a - 0.25), -21))  # discret : la vidéo dure plusieurs minutes
        f0, f1 = IN_T[(i + 1) % 4]
        js.append(f'tl.set("#t{i}",{{opacity:1}},{tt:.2f});tl.fromTo("#t{i} .w",{f0},{{{f1},stagger:{min(.09, .42 / max(1, ntok)):.3f}}},{tt:.2f});')
    if solo: js.append(f'tl.fromTo("#t{i} .rl",{{scaleX:0}},{{scaleX:1,duration:.6,ease:"power4.out"}},{tt + .4:.2f});')
    if cnt:  # chiffre qui compte (valeur finale écrite dans la page : c'est elle qu'on lit hors animation)
        js.append(f'tl.fromTo("#n{i}",{{textContent:{cnt[0]}}},{{textContent:{cnt[1]},snap:{{textContent:1}},duration:{min(1.4, max(.7, (b - a) / 3)):.2f},ease:"power2.out"}},{tt + .1:.2f});')
    if key:  # trait dessiné sous le mot clé, au milieu du plan (2e temps fort)
        tk = max(tt + .5, min(max(tt + .8, a + (b - a) * .5), b - .9))
        js.append(f'tl.set("#ks{i}",{{opacity:1}},{tk:.2f});tl.fromTo("#ks{i}",{{strokeDashoffset:1.1}},{{strokeDashoffset:0,duration:.55,ease:"power2.inOut"}},{tk:.2f});')
    # caméra : un mouvement d'ambiance par plan, différent du précédent (zoom avant, zoom arrière, immobile, glissement),
    # qui repart de là où le plan d'avant s'est arrêté quand l'image est la même
    tgt = [(1.08, 0), (1.0, 0), None, (1.06, 22 if (i // 4) % 2 else -22)][i % 4]
    if new_img:
        cam = (1.04, 0) if tgt is None else (1.1, 0) if tgt == (1.0, 0) else (1.0, 0) if tgt[1] == 0 else (1.06, -tgt[1])
        if tgt is None: js.append(f'tl.set("{ie} img",{{scale:{cam[0]},x:{cam[1]}}},0);')
    c0, c1 = round(ai, 2), round((TB[i] + .7) if run_end else TI[i + 1], 2)
    if tgt is not None and c1 - c0 > .3:
        js.append(f'tl.fromTo("{ie} img",{{scale:{cam[0]},x:{cam[1]}}},{{scale:{tgt[0]},x:{tgt[1]},duration:{c1 - c0 - .01:.2f},ease:"{["power1.inOut", "sine.inOut", "", "none"][i % 4]}",immediateRender:{"true" if new_img else "false"}}},{c0:.2f});')
        cam = tgt
    img = p.get('img', '')
    if img in ('scroll_bed', 'phone_night', 'screens'): SFX.append(('phone', a + 0.3, -16))
    if img in ('journal',): SFX.append(('scribble', a + 0.4, -18))
    if img in ('clock_night',): SFX.append(('tick', a + 0.3, -14)); SFX.append(('tick', a + 1.3, -14))
    if not last:
        js.append(f'tl.set("#t{i}",{{opacity:0}},{b:.2f});' if hard else f'tl.to("#t{i}",{{opacity:0,y:-14,duration:.2,ease:"power2.in"}},{b - .2:.2f});')
        if run_end: js.append(f'tl.set("{ie}",{{opacity:0}},{TI[i + 1] if i + 1 in cards else b + .7:.2f});')  # fondu enchaîné sous la nouvelle image
    if g == 'ring':  # anneau ambre qui se dessine pendant le plan
        h.append(f'<svg class="g" id="ring{i}" style="top:140px;left:{IL - 20}px;width:800px;height:800px" viewBox="0 0 800 800"><circle cx="400" cy="400" r="380" fill="none" stroke="#F2A541" stroke-width="6" stroke-linecap="round" stroke-dasharray="2388" stroke-dashoffset="2388" transform="rotate(-90 400 400)"/></svg>')
        SFX.append(('riser', max(0, b - 2.2), -20))
        js.append(f'tl.set("#ring{i}",{{opacity:1}},{a + .1:.2f});tl.to("#ring{i} circle",{{strokeDashoffset:0,duration:{b - a - .1:.2f},ease:"none"}},{a + .1:.2f});' + out(f'"#ring{i}"', b, hard))
    elif g == 'pulse':  # le personnage tremble : tension
        SFX.append(('heartbeat', a + 0.2, -12))
        js.append(f'tl.fromTo("{ie}",{{x:0}},{{x:6,duration:.07,ease:"none",yoyo:true,repeat:{max(1, int((b - a - .9) / .39)) * 2 - 1},repeatDelay:.25,immediateRender:false}},{a + 0.75:.2f});')
    elif g == 'breath':  # cercle qui gonfle / se vide, étiquettes sur les mots-clés
        steps = (p.get('steps') or ['INSPIRE', 'EXPIRE'])[:3]
        at = []
        for k, s in enumerate(steps):
            kw = norm(s.split()[-1]) if s.split() else ''
            hit = next((w['s'] for w in pw if kw and norm(w['t']).startswith(kw[:5])), None)
            at.append(hit if hit is not None and (not at or hit > at[-1]) else a + 0.3 + (b - a - 0.6) * k / len(steps))
        scales = [1.2, 1.38, .7] if len(steps) == 3 else [1.25, .7] if len(steps) == 2 else [1.2]
        h.append(f'<div class="g" id="br{i}" style="top:190px;left:{IL + 30}px;width:700px;height:700px"><div id="brc{i}" style="position:absolute;left:150px;top:150px;width:400px;height:400px;border-radius:50%;border:8px solid #F2A541;box-sizing:border-box"></div></div>')
        js.append(f'tl.set("#br{i}",{{opacity:1}},{at[0] - .1:.2f});tl.set("#brc{i}",{{scale:.7}},{at[0] - .1:.2f});')
        for k, s in enumerate(steps):
            nxt = at[k + 1] if k + 1 < len(steps) else b
            lastk = k == len(steps) - 1
            js.append(f'tl.to("#brc{i}",{{scale:{scales[k]},duration:{max(.4, (nxt - at[k] - .1) if lastk else min(1.1, nxt - at[k])):.2f},ease:"sine.inOut"}},{at[k]:.2f});')
            h.append(f'<div class="g col lbl" id="bl{i}_{k}" style="top:520px;font-size:60px">{H.escape(nb(s))}</div>')
            js.append(f'tl.fromTo("#bl{i}_{k}",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,ease:"power2.out"}},{at[k]:.2f});tl.set("#bl{i}_{k}",{{opacity:0}},{nxt:.2f});')
        js.append(f'tl.set("#br{i}",{{opacity:0}},{b:.2f});')
        SFX.append(('breath', at[-1], -16))
    elif g == 'cta' and (p.get('cta') or p.get('word')):  # mot à écrire en commentaire (champ cta, sinon word)
        h.append(f'<div class="g col" id="cta{i}" style="top:470px;text-align:center"><span style="display:inline-block;font-family:{TF};font-weight:800;font-size:96px;color:{BG};background:#F2A541;border-radius:999px;padding:6px 60px 18px">{H.escape(str(p.get("cta") or p.get("word")))}</span></div>')
        SFX.append(('pop', a + .5, -10))
        js.append(f'tl.fromTo("#cta{i}",{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:.5,ease:"back.out(2)"}},{a + .5:.2f});' + out(f'"#cta{i}"', b, hard))
    elif g == 'ecg':  # rythme cardiaque qui ralentit
        path = 'M0 70 H120 L140 70 L155 15 L172 125 L188 70 H330 L350 70 L365 15 L382 125 L398 70 H600 L620 70 L635 15 L652 125 L668 70 H860'
        h.append(f'<svg class="g" id="ecg{i}" style="top:520px;left:{TL - 20}px;width:860px;height:140px" viewBox="0 0 860 140"><path d="{path}" fill="none" stroke="#F2A541" stroke-width="7" stroke-linejoin="round" stroke-dasharray="1400" stroke-dashoffset="1400"/></svg>')
        SFX.append(('heartbeat', a + .2, -13))
        js.append(f'tl.set("#ecg{i}",{{opacity:1}},{a + .2:.2f});tl.to("#ecg{i} path",{{strokeDashoffset:0,duration:{max(1, b - a - .4):.2f},ease:"power1.out"}},{a + .2:.2f});' + out(f'"#ecg{i}"', b, hard))
    elif g == 'card' and p.get('card'):  # source, chiffre ou conseil : la carte glisse, le filet se dessine, la référence suit
        c = p['card']
        sub = f'<u></u><i><bdi>{H.escape(c["i"])}</bdi></i>' if c.get('i') else ''  # <bdi> : une source en lettres latines garde son point final à droite
        h.append(f'<div class="card" id="card{i}"><b><bdi>{H.escape(nb(c.get("b", "")))}</bdi></b>{sub}</div>')
        tc = a + min(1.2, (b - a) / 3)
        SFX.append(('pop', tc, -14))
        js.append(f'tl.fromTo("#card{i}",{{opacity:0,x:{-50 if AR else 50}}},{{opacity:1,x:0,duration:.5,ease:"power3.out"}},{tc:.2f});')
        if sub: js.append(f'tl.fromTo("#card{i} u",{{scaleX:0}},{{scaleX:1,duration:.45,ease:"expo.out"}},{tc + .25:.2f});tl.fromTo("#card{i} i",{{opacity:0,y:12}},{{opacity:1,y:0,duration:.4,ease:"power1.out"}},{tc + .38:.2f});')
        js.append(out(f'"#card{i}"', b, hard))
    elif g == 'count':  # 1 · 2 · 3
        n = max(2, min(5, int(p.get('count') or 3)))
        h.append(f'<div class="g col" id="x{i}" style="top:520px;display:flex;justify-content:flex-start;gap:36px;direction:{DIR}">' + ''.join(f'<div id="d{i}_{k}" style="width:84px;height:84px;border-radius:50%;border:6px solid #F2A541;box-sizing:border-box;font-family:{TF if AR else "Fraunces"};font-weight:800;font-size:46px;color:{BG};display:flex;align-items:center;justify-content:center">{k + 1}</div>' for k in range(n)) + '</div>')
        js.append(f'tl.set("#x{i}",{{opacity:1}},{a + .3:.2f});')
        for k in range(n):
            js.append(f'tl.fromTo("#d{i}_{k}",{{scale:0,backgroundColor:"rgba(242,165,65,0)"}},{{scale:1,backgroundColor:"#F2A541",duration:.4,ease:"back.out(2.4)"}},{a + .5 + k * min(.45, (b - a - 1) / n):.2f});')
            SFX.append(('ding', a + .5 + k * min(.45, (b - a - 1) / n), -17))
        js.append(out(f'"#x{i}"', b, hard))
    elif g == 'check' and p.get('items'):  # liste ✓ / ✗ : une ligne par élément, jamais de cadre vide ; chaque ligne arrive quand on la dit
        items = p['items'][:3]
        h.append(f'<div class="panel" id="ck{i}">' + ''.join(f'<div class="it{"" if it.get("ok", True) else " no"}" id="ck{i}_{k}"><b>{"✓" if it.get("ok", True) else "✗"}</b><span>{H.escape(str(it.get("t", "")))}</span></div>' for k, it in enumerate(items)) + '</div>')
        js.append(f'tl.set("#ck{i}",{{opacity:1}},{a + .3:.2f});' + out(f'"#ck{i}"', b, hard))
        step = min(1.1, max(.5, (b - a - 1) / max(1, len(items))))
        tp = a
        for k, it in enumerate(items):
            kw = norm(str(it.get('t', '')).split()[-1]) if str(it.get('t', '')).split() else ''
            hit = next((w['s'] for w in pw if len(kw) > 2 and w['s'] > tp + .3 and kw in norm(w['t'])), None)
            t0 = a + .45 if k == 0 else max(tp + .3, min(hit - .1 if hit is not None else tp + step, b - 1.5 - .4 * (len(items) - 1 - k)))  # la dernière ligne reste lisible au moins 1,5 s
            tp = t0
            js.append(f'tl.fromTo("#ck{i}_{k}",{{opacity:0,x:{36 if AR else -36}}},{{opacity:1,x:0,duration:.4,ease:"power3.out"}},{t0:.2f});tl.fromTo("#ck{i}_{k} b",{{scale:0}},{{scale:1,duration:.4,ease:"back.out(2.4)"}},{t0 + .12:.2f});')
            SFX.append(('pop', t0, -15))
    elif g == 'split' and p.get('left') and p.get('right'):  # avant / après, mythe / vérité : les deux côtés arrivent de bords opposés
        L, Rr = [x if isinstance(x, dict) else {'t': x} for x in (p['left'], p['right'])]
        stack = max(len(str(L.get('t', ''))), len(str(Rr.get('t', '')))) > 16  # textes longs : l'un sous l'autre, plus gros
        box = lambda cls, d: f'<div class="{cls}" id="{cls}{i}">' + (f'<small>{H.escape(str(d["label"]))}</small>' if d.get('label') else '') + f'<p>{H.escape(nb(d.get("t", "")))}</p></div>'
        h.append(f'<div class="split{" st" if stack else ""}">{box("sl", L)}{box("sr", Rr)}</div>')
        t1 = a + .3; t2 = a + max(.9, (b - a) * .45); x1 = 50 if AR else -50
        js.append(f'tl.fromTo("#sl{i}",{{opacity:0,x:{x1}}},{{opacity:1,x:0,duration:.4,ease:"power3.out"}},{t1:.2f});tl.fromTo("#sr{i}",{{opacity:0,x:{-x1}}},{{opacity:1,x:0,duration:.5,ease:"expo.out"}},{t2:.2f});')
        if L.get('label') and Rr.get('label'): js.append(f'tl.to("#sl{i}",{{opacity:.6,duration:.3,ease:"power1.out"}},{t2:.2f});')  # mythe / vérité : l'œil va sur la réponse
        js.append(out(f'["#sl{i}","#sr{i}"]', b, hard))
        SFX.append(('whoosh', t1, -20)); SFX.append(('pop', t2, -12))
    elif g == 'quote' and p.get('quote'):  # phrase à retenir : le guillemet saute, puis la phrase arrive mot à mot
        h.append(f'<div class="quote" id="q{i}"><em class="qm" data-layout-ignore>“</em>{spans(p["quote"], "qw")}</div>')
        nq = max(1, len(toks(p['quote'])))
        js.append(f'tl.fromTo("#q{i}",{{opacity:0,y:24}},{{opacity:1,y:0,duration:.4,ease:"power2.out"}},{a + .3:.2f});tl.fromTo("#q{i} .qm",{{scale:0}},{{scale:1,duration:.45,ease:"back.out(2)"}},{a + .4:.2f});'
                  f'tl.fromTo("#q{i} .qw",{{opacity:0,y:18}},{{opacity:1,y:0,duration:.4,ease:"expo.out",stagger:{min(.1, .45 / nq):.3f}}},{a + .55:.2f});' + out(f'"#q{i}"', b, hard))
    elif g == 'bigword' and p.get('word'):  # mot-choc géant qui claque quand on le dit, puis reste (la colonne n'est jamais vide)
        kw = norm(str(p['word']).split()[0])
        t0 = max(a + .25, next((w['s'] for w in pw if kw and norm(w['t']).startswith(kw[:5])), a + .4))
        fs = min(150, int(TWID / (0.62 * max(1, len(str(p['word']))))))  # tient dans la colonne de texte, sous le titre
        wd = str(p['word']).strip()
        num = re.fullmatch(r'[1-9]\d+', wd) and not 1900 <= int(wd) <= 2100 and p.get('countup', True) is not False  # quantité : elle compte en claquant
        h.append(f'<div class="bigw" id="bw{i}" style="font-size:{fs}px"><span class="k">{f"<b id=n{i}>{wd}</b>" if num else H.escape(wd)}{swoosh(f"bs{i}")}</span></div>')
        if num: js.append(f'tl.fromTo("#n{i}",{{textContent:{10 ** (len(wd) - 1)}}},{{textContent:{int(wd)},snap:{{textContent:1}},duration:.9,ease:"power2.out"}},{t0:.2f});')
        if t0 - a > 1.5:  # dit tard : le mot entre tôt (la colonne n'est jamais vide) et claque quand on le dit
            js.append(f'tl.fromTo("#bw{i}",{{opacity:0,y:36}},{{opacity:1,y:0,duration:.5,ease:"power3.out"}},{a + .5:.2f});tl.fromTo("#bw{i} .k",{{scale:1}},{{scale:1.16,duration:.16,ease:"power2.out",yoyo:true,repeat:1,immediateRender:false}},{t0:.2f});')
        else:
            js.append(f'tl.fromTo("#bw{i}",{{opacity:0,scale:2.2}},{{opacity:1,scale:1,duration:.3,ease:"expo.out"}},{t0:.2f});')
        js.append(f'tl.set("#bs{i}",{{opacity:1}},{t0 + .4:.2f});tl.fromTo("#bs{i}",{{strokeDashoffset:1.1}},{{strokeDashoffset:0,duration:.5,ease:"power2.inOut"}},{t0 + .4:.2f});' + out(f'"#bw{i}"', b, hard))
        js.append(f'tl.fromTo("{ie}",{{x:0}},{{x:10,duration:.05,yoyo:true,repeat:5,ease:"none",immediateRender:false}},{t0:.2f});')
        SFX.append(('impact', t0, -10))
    elif g == 'stamp' and p.get('stamp'):  # tampon FAUX / VRAI / MYTHE
        kw = norm(str(p['stamp']).split()[0])
        t0 = next((w['s'] for w in pw if kw and norm(w['t']).startswith(kw[:4])), a + .5)
        ns = len(str(p['stamp']))  # tampon long : plus petit et plus bas, pour ne pas toucher le titre de chapitre en haut
        h.append(f'<div class="stamp" id="st{i}" style="font-size:{min(96, int(700 / (.6 * max(1, ns))))}px;top:{150 if ns <= 6 else 200}px">{H.escape(str(p["stamp"]))}</div>')
        js.append(f'tl.fromTo("#st{i}",{{opacity:0,scale:2.4,rotation:-26}},{{opacity:1,scale:1,rotation:-10,duration:.32,ease:"back.out(2.2)"}},{t0:.2f});' + out(f'"#st{i}"', b, hard))
        SFX.append(('impact', t0, -11))
    elif g == 'timer':  # compte à rebours (ex. « 5 secondes »)
        n = max(3, min(10, int(p.get('seconds') or 5)))
        circ = 565
        h.append(f'<div class="timer" id="tm{i}"><svg viewBox="0 0 200 200" width="200" height="200"><circle cx="100" cy="100" r="90" fill="none" stroke="{PAN}" stroke-width="10"/><circle id="tmc{i}" cx="100" cy="100" r="90" fill="none" stroke="#F2A541" stroke-width="10" stroke-linecap="round" stroke-dasharray="{circ}" stroke-dashoffset="0" transform="rotate(-90 100 100)"/></svg>' + ''.join(f'<span id="tn{i}_{k}" style="opacity:0">{n - k}</span>' for k in range(n)) + '</div>')
        t0 = a + .3; span = min(n, max(2.0, b - a - .6))
        js.append(f'tl.set("#tm{i}",{{opacity:1}},{t0:.2f});tl.to("#tmc{i}",{{strokeDashoffset:{circ},duration:{span:.2f},ease:"none"}},{t0:.2f});' + out(f'"#tm{i}"', b, hard))
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
    nxt = min([g[0]['s'] for g in groups[gi + 1:]] + [END])  # caché dès qu'un sous-titre suivant apparaît
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
    flt.append(f'[1:a]volume=-17dB,atrim=0:{END:.2f},afade=t=in:d=1,afade=t=out:st={END - 2:.2f}:d=2[m0]')
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
# chapitres YouTube (le 1er à 0:00), lus par le Studio pour la description
fmt = lambda t: f'{int(t // 60):02d}:{int(t % 60):02d}'
json.dump([{'t': fmt(t0), 'title': CHT[c] if c < len(CHT) else ''} for c, i0, t0 in chs], open(f'{D}/chapters.json', 'w'), ensure_ascii=False)
print('plans', [round(s, 2) for s in starts], 'groups', len(groups), 'duree', round(END, 2), 'coupé', round(src_dur - dur, 2), 's')
