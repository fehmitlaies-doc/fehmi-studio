# Format « Duo » (9:16), sans voix : petites scènes de comparaison en écran partagé (haut / bas),
# bonhomme en traits lumineux sur fond noir, deux étiquettes par scène, musique de fond + effets sonores.
# Scènes : pont, collines, feu, pente, vagues, iceberg, marches. Une carte finale : message + source.
# Usage : python3 duo_build.py <dossier>
#   <dossier>/job.json {format:"duo", lang, music, scenes:[{k, title, top, bot}], end, src, save, note}
# Sortie : index.html, assets/mix.m4a
import json, math, os, subprocess, sys, html as H

D = sys.argv[1]
W, HT = 1080, 1920
job = json.load(open(f'{D}/job.json'))
AR = job.get('lang') == 'ar'
KINDS = ('pont', 'collines', 'feu', 'pente', 'vagues', 'iceberg', 'marches')
scenes = [s for s in job.get('scenes', []) if s.get('k') in KINDS][:7]
esc = lambda s: H.escape(str(s or ''))
X = (lambda x: W - x) if AR else (lambda x: x)
GOLD, WHITE, DIM, BLUE = '#F2A541', '#EDE7DA', '#6E6878', '#5FB7D6'
LEN = {'pont': 8.5, 'collines': 8.5, 'feu': 8.0, 'pente': 8.5, 'vagues': 7.5, 'iceberg': 7.5, 'marches': 8.5}
TOPY, BOTY = 360, 1060  # haut de chaque panneau (600 px de haut)
FONT = '"Cairo-ar"' if AR else '"Archivo"'

SHORT = bool(job.get('short'))  # boucle courte : une accroche en haut dès la 1re image, pas de carte finale
starts, t = [], (0 if SHORT else .3)
for s in scenes: starts.append(t); t += LEN[s['k']]
END_A = t
END = END_A + (1.4 if SHORT else 5.2)

svg, js, SFX = [], ['window.__timelines=window.__timelines||{};var tl=gsap.timeline({paused:true});'], []
labels = []  # étiquettes HTML (non miroir)
n_id = [0]
def nid(p='e'):
    n_id[0] += 1; return f'{p}{n_id[0]}'

def tw(sel, vars_, at):
    js.append(f'tl.to("{sel}",{vars_},{at:.2f});')

def fig(x, y, col, sc=1.0):
    """bonhomme : groupe positionné en (x, y) = pieds ; renvoie l'id"""
    i = nid('f')
    svg.append(f'<g id="{i}" transform="translate({x},{y}) scale({sc})"><g stroke="{col}" stroke-width="7" stroke-linecap="round" fill="none" filter="url(#gl)">'
               f'<circle cx="0" cy="-118" r="17" fill="{col}" stroke="none"/><line x1="0" y1="-100" x2="0" y2="-48"/>'
               f'<line id="{i}a1" x1="0" y1="-90" x2="-20" y2="-62"/><line id="{i}a2" x1="0" y1="-90" x2="20" y2="-62"/>'
               f'<line id="{i}l1" x1="0" y1="-48" x2="-14" y2="0"/><line id="{i}l2" x1="0" y1="-48" x2="14" y2="0"/></g></g>')
    return i

def walk(i, at, dur, step=.28):
    n = max(1, int(dur / step))
    js.append(f'tl.to("#{i}l1",{{attr:{{x2:14}},duration:{step},yoyo:true,repeat:{n - 1},ease:"sine.inOut"}},{at:.2f});')
    js.append(f'tl.to("#{i}l2",{{attr:{{x2:-14}},duration:{step},yoyo:true,repeat:{n - 1},ease:"sine.inOut"}},{at:.2f});')
    js.append(f'tl.to("#{i}l1",{{attr:{{x2:-14}},duration:.15}},{at + n * step:.2f});tl.to("#{i}l2",{{attr:{{x2:14}},duration:.15}},{at + n * step:.2f});')

def push(i, at):  # bras tendus vers l'avant
    tw(f'#{i}a1', '{attr:{x2:26,y2:-80},duration:.25}', at); tw(f'#{i}a2', '{attr:{x2:30,y2:-74},duration:.25}', at)

def label(txt, x, y, col, size=34, at=0, out=0, sc=None):
    if SHORT and len(scenes) == 1: out = END + 1  # boucle : les étiquettes restent jusqu'à la fin
    i = nid('lb')
    labels.append(f'<div class="lb" id="{i}" style="left:{x - 300}px;top:{y}px;color:{col};font-size:{size}px;text-shadow:0 0 18px {col}55">{esc(txt)}</div>')
    if SHORT and at < .8: js.append(f'tl.set("#{i}",{{opacity:1}},0);')
    else: js.append(f'tl.fromTo("#{i}",{{opacity:0,y:10}},{{opacity:1,y:0,duration:.4,ease:"power2.out"}},{at:.2f});')
    js.append(f'tl.to("#{i}",{{opacity:0,duration:.3}},{out - .3:.2f});')

def path_pts(f, x0, x1, n=40):
    return [(x0 + (x1 - x0) * k / n, f(x0 + (x1 - x0) * k / n)) for k in range(n + 1)]

def keyframes(pts, dur, ang=True):
    out, step = [], dur / max(1, len(pts) - 1)
    for k, (x, y) in enumerate(pts):
        r = 0
        if ang and 0 < k < len(pts) - 1:
            r = math.degrees(math.atan2(pts[k + 1][1] - pts[k - 1][1], pts[k + 1][0] - pts[k - 1][0]))
        out.append(f'{{x:{x:.0f},y:{y:.0f},rotation:{r:.1f},duration:{step:.3f},ease:"none"}}')
    return '[' + ','.join(out) + ']'

# ---------------------------------------------------------------- scènes
def sc_pont(t0, s):
    for p, (y0, good) in enumerate([(TOPY, False), (BOTY, True)]):
        gy = y0 + 400
        svg.append(f'<rect x="0" y="{gy + 20}" width="1080" height="160" fill="url(#water)"/>')
        svg.append(f'<path d="M0,{gy - 10} L170,{gy - 10} Q200,{gy + 10} 190,{gy + 180} L0,{gy + 180}Z" fill="#2A2730"/><path d="M1080,{gy - 10} L910,{gy - 10} Q880,{gy + 10} 890,{gy + 180} L1080,{gy + 180}Z" fill="#2A2730"/>')
        col = GOLD if good else WHITE
        f = fig(150, gy - 10, col)
        if not good:  # pose un bloc, le réajuste sans fin
            b = nid('b'); svg.append(f'<rect id="{b}" x="-46" y="-14" width="92" height="28" rx="3" fill="#B9C3CC" transform="translate(150,{gy - 140})" opacity="0"/>')
            js.append(f'tl.set("#{b}",{{opacity:1}},{t0 + .6:.2f});tl.to("#{b}",{{x:245,y:{gy + 4},duration:.8,ease:"power2.in"}},{t0 + .8:.2f});')
            SFX.append(('pop', t0 + 1.6, -20))
            for k in range(5):
                tw(f'#{b}', f'{{rotation:{6 if k % 2 == 0 else -6},duration:.5,ease:"sine.inOut"}}', t0 + 2 + k * .9)
                tw(f'#{f}', f'{{x:{165 if k % 2 == 0 else 150},duration:.45}}', t0 + 2 + k * .9)
            tw(f'#{b}', '{rotation:0,duration:.4}', t0 + 6.6)
        else:  # lance des blocs imparfaits et traverse
            xs = [245, 400, 555, 710, 840]
            for k, x in enumerate(xs):
                b = nid('b'); rot = [-8, 5, -4, 9, -6][k]
                svg.append(f'<rect id="{b}" x="-48" y="-14" width="96" height="28" rx="3" fill="#C9A066" transform="translate(150,{gy - 140})" opacity="0"/>')
                a = t0 + .5 + k * .45
                js.append(f'tl.set("#{b}",{{opacity:1}},{a:.2f});tl.to("#{b}",{{x:{x},y:{gy + 4},rotation:{rot},duration:.45,ease:"power2.in"}},{a:.2f});')
                SFX.append(('pop', a + .45, -21))
            a = t0 + 3.0
            walk(f, a, 3.2); tw(f'#{f}', f'{{x:960,duration:3.2,ease:"none"}}', a)
            SFX.append(('ding', a + 3.3, -18))
    label(s.get('top'), 540, TOPY + 40, WHITE, 46, t0 + .2, t0 + LEN['pont'])
    label(s.get('bot'), 540, BOTY + 40, GOLD, 46, t0 + .2, t0 + LEN['pont'])

def sc_collines(t0, s):
    # haut : colline (difficile maintenant → facile ensuite) ; bas : vallée (facile maintenant → difficile ensuite)
    for p, (y0, hill) in enumerate([(TOPY, True), (BOTY, False)]):
        base = y0 + 470
        f_ = (lambda x, b=base: b - 260 * math.exp(-((x - 540) / 210) ** 2)) if hill else (lambda x, b=base: b - 300 + 260 * math.exp(-((x - 540) / 210) ** 2))
        pts = path_pts(f_, 60, 1020, 60)
        svg.append('<polyline points="' + ' '.join(f'{x:.0f},{y:.0f}' for x, y in pts) + f'" fill="none" stroke="{DIM}" stroke-width="5" filter="url(#gl)"/>')
        col = GOLD if hill else WHITE
        c = nid('c')
        svg.append(f'<g id="{c}" transform="translate(120,{f_(120):.0f})"><rect x="-38" y="-46" width="76" height="40" rx="6" fill="none" stroke="{col}" stroke-width="5"/><circle cx="-22" cy="-4" r="8" fill="{col}"/><circle cx="22" cy="-4" r="8" fill="{col}"/><path d="M-30,-46 Q0,-74 30,-46" fill="#B04A3A" opacity=".9"/></g>')
        fg = fig(70, f_(70), col)
        if hill:  # pousse lentement jusqu'au sommet, puis le chariot redescend tout seul
            up = path_pts(f_, 120, 540, 20); dn = path_pts(f_, 540, 960, 14)
            push(fg, t0 + .5)
            js.append(f'tl.to("#{c}",{{keyframes:{keyframes(up, 4.2)}}},{t0 + .6:.2f});')
            js.append(f'tl.to("#{fg}",{{keyframes:{keyframes(path_pts(f_, 70, 480, 20), 4.2, False)}}},{t0 + .6:.2f});')
            walk(fg, t0 + .6, 4.2, .4)
            js.append(f'tl.to("#{c}",{{keyframes:{keyframes(dn, 1.6)}}},{t0 + 4.9:.2f});')
            SFX.append(('whoosh', t0 + 4.9, -18)); SFX.append(('ding', t0 + 6.7, -18))
        else:  # descend facilement, puis bloqué en remontant
            dn = path_pts(f_, 120, 540, 14); up = path_pts(f_, 540, 700, 8)
            js.append(f'tl.to("#{c}",{{keyframes:{keyframes(dn, 1.6)}}},{t0 + .6:.2f});')
            js.append(f'tl.to("#{fg}",{{keyframes:{keyframes(path_pts(f_, 70, 480, 14), 1.8, False)}}},{t0 + .6:.2f});')
            walk(fg, t0 + .6, 1.8, .25); SFX.append(('whoosh', t0 + .6, -20))
            push(fg, t0 + 2.6)
            js.append(f'tl.to("#{c}",{{keyframes:{keyframes(up, 2.4)}}},{t0 + 2.7:.2f});')
            js.append(f'tl.to("#{c}",{{keyframes:{keyframes(list(reversed(up)), 1.0)}}},{t0 + 5.2:.2f});')
            js.append(f'tl.to("#{fg}",{{x:{f"{560}"},y:{f_(560):.0f},duration:2.4}},{t0 + 2.7:.2f});tl.to("#{fg}",{{x:470,y:{f_(470):.0f},rotation:-20,duration:.8}},{t0 + 5.2:.2f});')
            SFX.append(('impact', t0 + 6.1, -18))
    L = s.get('top', '').split('|'); B = s.get('bot', '').split('|')
    label(L[0], X(240), TOPY + 30, GOLD, 40, t0 + .2, t0 + LEN['collines'])
    if len(L) > 1: label(L[1], X(840), TOPY + 30, GOLD, 40, t0 + 4.6, t0 + LEN['collines'])
    label(B[0], X(240), BOTY + 430, WHITE, 40, t0 + .2, t0 + LEN['collines'])
    if len(B) > 1: label(B[1], X(840), BOTY + 430, WHITE, 40, t0 + 2.8, t0 + LEN['collines'])

def sc_feu(t0, s):
    # haut : réagit tout de suite (fonce au rouge, se cogne) ; bas : attend que le feu passe au vert
    for p, (y0, good) in enumerate([(TOPY, False), (BOTY, True)]):
        gy = y0 + 430
        svg.append(f'<line x1="40" y1="{gy}" x2="1040" y2="{gy}" stroke="{DIM}" stroke-width="4"/>')
        lx = 700
        svg.append(f'<rect x="{lx - 22}" y="{gy - 260}" width="44" height="120" rx="10" fill="#15131A" stroke="#3A3640" stroke-width="3"/><line x1="{lx}" y1="{gy - 140}" x2="{lx}" y2="{gy}" stroke="#3A3640" stroke-width="6"/>')
        r, o, g = nid('r'), nid('o'), nid('g')
        svg.append(f'<circle id="{r}" cx="{lx}" cy="{gy - 236}" r="14" fill="#E5484D" filter="url(#gl)"/><circle id="{o}" cx="{lx}" cy="{gy - 200}" r="14" fill="#3A2A12"/><circle id="{g}" cx="{lx}" cy="{gy - 164}" r="14" fill="#123A1E"/>')
        f = fig(180, gy, GOLD if good else WHITE)
        if not good:
            wall = nid('w'); svg.append(f'<rect id="{wall}" x="{lx + 20}" y="{gy - 150}" width="22" height="150" fill="#E5484D" opacity="0"/>')
            walk(f, t0 + .5, 1.3, .16); tw(f'#{f}', f'{{x:{lx},duration:1.3,ease:"power1.in"}}', t0 + .5)
            js.append(f'tl.to("#{wall}",{{opacity:.8,duration:.1}},{t0 + 1.8:.2f});tl.to("#{wall}",{{opacity:0,duration:.6}},{t0 + 2.0:.2f});')
            tw(f'#{f}', '{x:600,rotation:-75,y:"-=10",duration:.5,ease:"power2.out"}', t0 + 1.8)
            SFX.append(('impact', t0 + 1.8, -15))
        else:
            for k in range(3): SFX.append(('tick', t0 + 1 + k * .9, -22))
            js.append(f'tl.to("#{r}",{{fill:"#3A1416",duration:.2}},{t0 + 3.4:.2f});tl.to("#{o}",{{fill:"#F2A541",duration:.2}},{t0 + 3.4:.2f});')
            js.append(f'tl.to("#{o}",{{fill:"#3A2A12",duration:.2}},{t0 + 4.4:.2f});tl.to("#{g}",{{fill:"#3DD68C",duration:.2}},{t0 + 4.4:.2f});')
            walk(f, t0 + 4.7, 2.6); tw(f'#{f}', '{x:1000,duration:2.6,ease:"none"}', t0 + 4.7)
            SFX.append(('ding', t0 + 4.5, -18))
    label(s.get('top'), 540, TOPY + 40, WHITE, 46, t0 + .2, t0 + LEN['feu'])
    label(s.get('bot'), 540, BOTY + 40, GOLD, 46, t0 + .2, t0 + LEN['feu'])

def sc_pente(t0, s):
    # haut : ce qu'on imagine (ligne droite) ; bas : la réalité (marches irrégulières, reculs, mais on arrive)
    y0 = TOPY; gy = y0 + 470
    svg.append(f'<line x1="120" y1="{gy}" x2="960" y2="{gy - 300}" stroke="{DIM}" stroke-width="5"/>')
    svg.append(f'<path d="M960,{gy - 300} v-70 l46,16 l-46,16" fill="{WHITE}" stroke="{WHITE}" stroke-width="3"/>')
    f = fig(140, gy - 8, WHITE)
    walk(f, t0 + .6, 3, .3); tw(f'#{f}', f'{{x:930,y:{gy - 300},duration:3,ease:"none"}}', t0 + .6)
    y0 = BOTY; gy = y0 + 500
    pts = [(120, gy)]; x, y = 120, gy
    steps = [(90, -60), (90, -50), (70, 40), (90, -70), (60, 30), (100, -80), (90, -60), (90, -70)]
    d = f'M{x},{y}'
    for dx, dy in steps: x += dx; d += f' H{x}'; y += dy; d += f' V{y}'; pts.append((x, y))
    svg.append(f'<path d="{d} H{x + 80}" fill="none" stroke="{DIM}" stroke-width="5"/>')
    svg.append(f'<path d="M{x + 60},{y} v-70 l46,16 l-46,16" fill="{GOLD}" stroke="{GOLD}" stroke-width="3" filter="url(#gl)"/>')
    g = fig(100, gy, GOLD)
    a = t0 + .6
    for k, (px, py) in enumerate(pts[1:]):
        back = steps[k][1] > 0
        tw(f'#{g}', f'{{x:{px - 30},y:{py},duration:.55,ease:"{"bounce.out" if back else "power1.inOut"}"}}', a)
        if back: SFX.append(('impact', a + .3, -22))
        a += .7
    SFX.append(('ding', a + .2, -18))
    label(s.get('top'), 540, TOPY + 40, WHITE, 46, t0 + .2, t0 + LEN['pente'])
    label(s.get('bot'), 540, BOTY + 40, GOLD, 46, t0 + .2, t0 + LEN['pente'])

def sc_vagues(t0, s):
    # haut : motivation (un pic puis plus rien) ; bas : petites habitudes régulières qui avancent
    for y0, good in [(TOPY, False), (BOTY, True)]:
        gy = y0 + 440
        if not good:
            pts = [(80 + k * 9.2, gy - 300 * math.exp(-k / 18) * abs(math.sin(k / 7)) - (0 if k > 3 else 0)) for k in range(101)]
        else:
            pts = [(80 + k * 9.2, gy - 70 * abs(math.sin(k * math.pi / 16))) for k in range(101)]
        p = nid('p'); dpt = nid('d')
        col = GOLD if good else WHITE
        dd = 'M' + ' L'.join(f'{x:.0f},{y:.0f}' for x, y in pts)
        svg.append(f'<path id="{p}" d="{dd}" fill="none" stroke="{col}" stroke-width="6" stroke-linecap="round" filter="url(#gl)" stroke-dasharray="3000" stroke-dashoffset="3000"/>')
        svg.append(f'<circle id="{dpt}" cx="0" cy="0" r="13" fill="{BLUE if not good else GOLD}" filter="url(#gl)" transform="translate({pts[0][0]},{pts[0][1]})"/>')
        js.append(f'tl.to("#{p}",{{strokeDashoffset:{0 if good else 900},duration:5.6,ease:"none"}},{t0 + .6:.2f});')
        sub = pts[::5] if good else pts[:72:4]
        js.append(f'tl.to("#{dpt}",{{keyframes:{keyframes(sub, 5.6, False)}}},{t0 + .6:.2f});')
    SFX.append(('riser', t0 + .6, -24))
    label(s.get('top'), 540, TOPY + 40, '#3DD68C', 48, t0 + .2, t0 + LEN['vagues'])
    label(s.get('bot'), 540, BOTY + 40, GOLD, 48, t0 + .2, t0 + LEN['vagues'])

def sc_iceberg(t0, s):
    sea = 900
    svg.append(f'<rect x="0" y="{sea}" width="1080" height="820" fill="url(#deep)"/><line x1="0" y1="{sea}" x2="1080" y2="{sea}" stroke="{BLUE}" stroke-width="3" opacity=".7"/>')
    ice = nid('i')
    svg.append(f'<g id="{ice}"><polygon points="460,{sea} 540,{sea - 170} 610,{sea - 110} 650,{sea}" fill="#CFEFFA" filter="url(#gl)"/>'
               f'<polygon points="380,{sea} 650,{sea} 790,{sea + 250} 700,{sea + 560} 540,{sea + 700} 360,{sea + 520} 300,{sea + 230}" fill="#2B6F8C" opacity=".9"/>')
    f = fig(540, sea - 170, GOLD, .8)
    svg.append('</g>')
    if not SHORT: js.append(f'tl.fromTo("#{ice}",{{y:40,opacity:0}},{{y:0,opacity:1,duration:1,ease:"power2.out"}},{t0 + .2:.2f});')
    items = [x for x in (s.get('items') or []) if x][:4]
    for k, it in enumerate(items):
        yy = sea + 120 + k * 120
        label(it, 540, yy, WHITE, 42, t0 + 2.2 + k * .9, t0 + LEN['iceberg'])
        SFX.append(('pop', t0 + 2.2 + k * .9, -22))
    label(s.get('top'), 540, TOPY + 60, GOLD, 48, t0 + .4, t0 + LEN['iceberg'])
    label(s.get('bot'), 540, sea + 24, '#9FE3F7', 40, t0 + 1.6, t0 + LEN['iceberg'])

def sc_marches(t0, s):
    words = [x for x in (s.get('items') or []) if x][:6] or ['…']
    n = len(words) + 1
    x0, y0, sw, sh = 140, 1500, 120, 140
    for k in range(n):
        last = k == n - 1
        x, y = x0 + k * sw, y0 - k * sh
        sid = nid('st')
        svg.append(f'<g id="{sid}" opacity="0"><rect x="{x}" y="{y}" width="{sw}" height="{1600 - y}" fill="{"#2E2716" if last else "#1C1A22"}" stroke="{GOLD if last else DIM}" stroke-width="3"/></g>')
        js.append(f'tl.to("#{sid}",{{opacity:1,duration:.3}},{t0 + .2 + k * .12:.2f});')
    g = fig(x0 + 60, y0, GOLD)
    a = t0 + 1.2
    for k in range(1, n):
        x, y = x0 + k * sw + 60, y0 - k * sh
        tw(f'#{g}', f'{{keyframes:[{{y:{y + sh - 70},x:{x - 30},duration:.3,ease:"power2.out"}},{{y:{y},x:{x},duration:.25,ease:"power2.in"}}]}}', a)
        lab = words[k - 1] if k - 1 < len(words) else ''
        label(lab, X(x0 + (k - 1) * sw + 60), y0 - (k - 1) * sh + 24, "#C9C1D2", 27, a - .2, t0 + LEN['marches'])
        SFX.append(('pop', a + .5, -22)); a += .8
    label(s.get("bot") or "", X(x0 + (n - 1) * sw + 60), y0 - (n - 1) * sh - 210, GOLD, 42, a - .3, t0 + LEN['marches'])
    SFX.append(('ding', a, -16))
    label(s.get('top'), 540, TOPY + 20, WHITE, 48, t0 + .2, t0 + LEN['marches'])

FN = {'pont': sc_pont, 'collines': sc_collines, 'feu': sc_feu, 'pente': sc_pente, 'vagues': sc_vagues, 'iceberg': sc_iceberg, 'marches': sc_marches}

titles = []
for i, s in enumerate(scenes):
    t0 = starts[i]; t1 = t0 + LEN[s['k']]
    svg.append(f'<g id="sc{i}" opacity="0">')
    FN[s['k']](t0, s)
    svg.append('</g>')
    js.append(f'tl.set("#sc{i}",{{opacity:1}},{t0:.2f});' if i == 0 else f'tl.fromTo("#sc{i}",{{opacity:0}},{{opacity:1,duration:.35}},{t0:.2f});')
    if not (SHORT and i == len(scenes) - 1): js.append(f'tl.to("#sc{i}",{{opacity:0,duration:.35}},{t1 - .35:.2f});')
    if s.get('title') and not SHORT:
        titles.append(f'<div class="ti" id="ti{i}">{esc(s["title"])}</div>')
        js.append(f'tl.fromTo("#ti{i}",{{opacity:0,y:-10}},{{opacity:1,y:0,duration:.4}},{t0 + .05:.2f});tl.to("#ti{i}",{{opacity:0,duration:.3}},{t1 - .35:.2f});')
    if i: SFX.append(('whoosh', t0, -22))
    # séparation des deux panneaux (sauf iceberg / marches)
    if s['k'] not in ('iceberg', 'marches'):
        sep = nid('sp'); svg.append(f'<line id="{sep}" x1="140" y1="985" x2="940" y2="985" stroke="#2A2730" stroke-width="2" opacity="0"/>')
        js.append(f'tl.set("#{sep}",{{opacity:1}},{t0:.2f});tl.set("#{sep}",{{opacity:0}},{t1:.2f});')

if not SHORT: SFX.append(('riser', END_A - 1.2, -22)); SFX.append(('ding', END_A + .3, -17))
css = f'''
@font-face{{font-family:"Archivo";src:url(assets/Archivo.ttf)}}@font-face{{font-family:"Cairo-ar";src:url(assets/Cairo-ar.ttf)}}@font-face{{font-family:"Mono";src:url(assets/Mono.ttf)}}
html,body{{margin:0;background:#050407}}#root{{position:relative;width:{W}px;height:{HT}px;overflow:hidden;background:radial-gradient(ellipse at 50% 40%,#141118 0%,#060508 70%)}}
svg.sc{{position:absolute;left:0;top:0;width:{W}px;height:{HT}px}}
.lb{{position:absolute;width:600px;text-shadow:0 2px 10px #000;text-align:center;font-family:{FONT};font-weight:700;letter-spacing:{"0" if AR else ".02em"};direction:{"rtl" if AR else "ltr"};opacity:0;line-height:1.2}}
.ti{{position:absolute;left:60px;right:60px;top:180px;text-align:center;font-family:{FONT};font-weight:800;font-size:{66 if AR else 62}px;color:{WHITE};direction:{"rtl" if AR else "ltr"};opacity:0}}
.end{{position:absolute;left:90px;right:90px;top:640px;text-align:center;font-family:{FONT};font-weight:800;font-size:{70 if AR else 66}px;line-height:1.25;color:{WHITE};direction:{"rtl" if AR else "ltr"};opacity:0}}
.end b{{color:{GOLD}}}
.src{{position:absolute;left:90px;right:90px;top:1120px;text-align:center;font-family:"Mono";font-size:24px;letter-spacing:.08em;color:#8C8496;opacity:0}}
.save{{position:absolute;left:60px;right:60px;top:1260px;text-align:center;font-family:{FONT};font-weight:700;font-size:{40 if AR else 36}px;color:{GOLD};direction:{"rtl" if AR else "ltr"};opacity:0}}
.note{{position:absolute;left:90px;right:90px;top:1620px;text-align:center;font-family:{FONT};font-size:{26 if AR else 24}px;color:#8C8496;direction:{"rtl" if AR else "ltr"};opacity:0}}
.hk{{position:absolute;left:40px;right:40px;top:90px;padding:22px 26px;border-radius:22px;background:{GOLD};text-align:center;font-family:{FONT};font-weight:900;font-size:{78 if AR else 72}px;line-height:1.12;color:#120E16;direction:{"rtl" if AR else "ltr"};box-shadow:0 10px 40px rgba(0,0,0,.6)}}
.hk b{{color:#7A1E12}}
.sh{{position:absolute;left:60px;right:60px;top:1640px;text-align:center;font-family:{FONT};font-weight:800;font-size:{50 if AR else 46}px;color:{GOLD};direction:{"rtl" if AR else "ltr"};opacity:0;text-shadow:0 3px 14px #000}}
.wm{{position:absolute;left:0;right:0;top:1800px;text-align:center;font-family:"Mono";font-size:20px;letter-spacing:.5em;color:rgba(237,231,218,.28)}}
'''
defs = ('<defs><filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3E8FB0" stop-opacity=".75"/><stop offset="1" stop-color="#0B1A22" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="deep" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0E2A38"/><stop offset="1" stop-color="#050407"/></linearGradient></defs>')
mirror = f' transform="translate({W},0) scale(-1,1)"' if AR else ''
endtxt = esc(job.get('end'))
for w in (job.get('hot') or [])[:2]:
    if w and esc(w) in endtxt: endtxt = endtxt.replace(esc(w), f'<b>{esc(w)}</b>', 1)
h = [f'<!DOCTYPE html><html lang="{"ar" if AR else "fr"}"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>{css}</style></head><body>',
     f'<div id="root" data-composition-id="main" data-width="{W}" data-height="{HT}" data-start="0" data-duration="{END:.2f}">',
     f'<audio id="mix" data-start="0" data-duration="{END:.2f}" data-track-index="1" src="assets/mix.m4a"></audio>',
     f'<svg class="sc" viewBox="0 0 {W} {HT}">{defs}<g{mirror}>' + ''.join(svg) + '</g></svg>',
     *labels, *titles,
     f'<div class="end" id="end">{endtxt}</div><div class="src" id="src">{esc(job.get("src"))}</div>',
     f'<div class="save" id="save">{esc(job.get("save") or ("احفظ الفيديو وأرسله لمن يحتاجه." if AR else "Enregistre-la. Envoie-la à quelqu'un."))}</div>',
     f'<div class="note" id="note">{esc(job.get("note") or ("للتوعية فقط، لا يعوّض استشارة مختص." if AR else "Information générale : ne remplace pas une consultation."))}</div>',
     '<div class="wm">' + ('د. فهمي' if AR else 'DR FEHMI') + '</div>']
if SHORT:
    hk = esc(str(job.get('hook') or '').replace('« ', '«\u00a0').replace(' »', '\u00a0»'))
    for w in (job.get('hook_hot') or [])[:2]:
        w = esc(str(w).replace('« ', '«\u00a0').replace(' »', '\u00a0»'))
        if w and w in hk: hk = hk.replace(w, f'<b>{w}</b>', 1)
    h.append(f'<div class="hk" id="hk">{hk}</div><div class="sh" id="sh">{esc(job.get("end"))}</div>')
    js.append('tl.fromTo("svg.sc",{scale:1.18,transformOrigin:"50% 55%"},{scale:1,duration:.7,ease:"expo.out"},0);tl.fromTo("#hk",{scale:1.08},{scale:1,duration:.5,ease:"back.out(2)"},0);')
    SFX.append(('whoosh', 0, -16))
    js.append(f'tl.fromTo("#sh",{{opacity:0,y:12}},{{opacity:1,y:0,duration:.4}},{END_A - 1.4:.2f});')
    SFX.append(('ding', END_A - 1.3, -18))
else:
    js.append(f'tl.fromTo("#end",{{opacity:0,scale:.96}},{{opacity:1,scale:1,duration:.7,ease:"expo.out"}},{END_A + .2:.2f});')
    js.append(f'tl.fromTo("#src",{{opacity:0}},{{opacity:1,duration:.5}},{END_A + 1.2:.2f});tl.fromTo("#save",{{opacity:0,y:10}},{{opacity:1,y:0,duration:.5}},{END_A + 1.8:.2f});tl.fromTo("#note",{{opacity:0}},{{opacity:1,duration:.5}},{END_A + 2.2:.2f});')
    js.append(f'tl.to(["#end","#src","#save","#note"],{{opacity:0,duration:.6}},{END - .7:.2f});')
js.append('window.__timelines["main"]=tl;')
h.append('</div><script>' + '\n'.join(js) + '</script></body></html>')
open(f'{D}/index.html', 'w').write('\n'.join(h))

# mixage : musique de fond + effets sonores
A = f'{D}/assets'
music = job.get('music') or 'espoir'
inp, fc, lab = [], [], []
if music != 'none' and os.path.exists(f'{A}/music_{music}.m4a'):
    inp += ['-stream_loop', '-1', '-i', f'{A}/music_{music}.m4a']
    fc.append(f'[0:a]atrim=0:{END:.2f},volume=-12dB,afade=t=in:d=1,afade=t=out:st={END - 2:.2f}:d=2[m]'); lab.append('[m]')
for s, tt, g in SFX:
    if not os.path.exists(f'{A}/sfx_{s}.m4a') or tt >= END: continue
    i = len([x for x in inp if x == '-i']); inp += ['-i', f'{A}/sfx_{s}.m4a']
    fc.append(f'[{i}:a]adelay={int(tt * 1000)}|{int(tt * 1000)},volume={g + 4}dB[x{i}]'); lab.append(f'[x{i}]')
if not lab:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', f'{END:.2f}', '-c:a', 'aac', f'{A}/mix.m4a'], check=True)
else:
    fc.append(''.join(lab) + f'amix=inputs={len(lab)}:normalize=0,atrim=0:{END:.2f}[out]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{A}/mix.m4a'], check=True)
print('duo', len(scenes), 'scènes, durée', round(END, 2))
