# Format « App » (9:16) : promotion d'une appli à partir de ses vraies captures et vidéos d'écran.
# Accroche en gros dès l'image 0, iPhone animé (zoom, toucher), une légende par temps fort, carte finale.
# Usage : python3 app_build.py <dossier>
#   <dossier>/job.json {format:"app", lang, music, hook, hook_hot:[], theme:{bg, accent, ink},
#                       beats:[{media:"x.mp4"|"x.png", from:s, dur:s, caption, zoom:{x,y,s}, tap:{x,y,t}}],
#                       end:{title, sub, cta, note}}
#   <dossier>/assets/<media> (captures 1206×2622 ou vidéos du simulateur)
# Sortie : index.html, assets/mix.m4a
import json, os, subprocess, sys, html as H

D = sys.argv[1]
W, HT = 1080, 1920
job = json.load(open(f'{D}/job.json'))
AR = job.get('lang') == 'ar'
esc = lambda s: H.escape(str(s or ''))
th = {'bg': '#071A2E', 'bg2': '#0E3556', 'accent': '#7FD3F7', 'ink': '#06223A', 'text': '#EAF6FF', **(job.get('theme') or {})}
FONT = '"Cairo-ar"' if AR else '"Archivo"'
SW, SH = 1206, 2622                      # taille native des captures
PW, PX, PY, BZ = 540, 270, 440, 12       # iPhone : largeur, position, bordure
IW = PW - 2 * BZ; IH = round(IW * SH / SW); PH = IH + 2 * BZ
K = IW / SW                              # échelle capture → écran

beats = job.get('beats') or []
t, starts = 0.0, []
for b in beats: starts.append(t); t += float(b.get('dur') or 3)
END_A = t
end = job.get('end') or {}
END = END_A + (2.8 if end else 0.4)

js = ['window.__timelines=window.__timelines||{};var tl=gsap.timeline({paused:true});']
media, caps, taps, SFX = [], [], [], []
for i, b in enumerate(beats):
    a, d = starts[i], float(b.get('dur') or 3)
    m = b.get('media', '')
    if m.endswith('.mp4'):
        media.append(f'<video id="m{i}" src="assets/{esc(m)}" data-start="{a:.2f}" data-duration="{d:.2f}" data-track-index="{2 + i}" data-media-start="{float(b.get("from") or 0):.2f}" muted playsinline></video>')
    else:
        media.append(f'<img id="m{i}" class="shot" src="assets/{esc(m)}" data-start="{a:.2f}" data-duration="{d:.2f}" data-track-index="{2 + i}">')
    z = b.get('zoom')
    if z:  # zoom doux vers un point de la capture (coordonnées natives)
        ox, oy = z.get('x', SW / 2) / SW * 100, z.get('y', SH / 2) / SH * 100
        js.append(f'tl.fromTo("#m{i}",{{scale:1}},{{scale:{z.get("s", 1.35)},transformOrigin:"{ox:.1f}% {oy:.1f}%",duration:{d * .8:.2f},ease:"power2.inOut"}},{a + .15:.2f});')
    tp = b.get('tap')
    if tp:
        x, y, tt = tp['x'] * K, tp['y'] * K, a + float(tp.get('t', .6))
        taps.append(f'<div class="tap" id="tp{i}" style="left:{x - 45:.0f}px;top:{y - 45:.0f}px"></div>')
        js.append(f'tl.fromTo("#tp{i}",{{opacity:.9,scale:.3}},{{opacity:0,scale:1.6,duration:.55,ease:"power2.out"}},{tt:.2f});')
        SFX.append(('pop', tt, -18))
    if b.get('caption'):
        caps.append(f'<div class="cap" id="c{i}">{esc(b["caption"])}</div>')
        js.append(f'tl.set("#c{i}",{{opacity:1}},0);' if i == 0 else f'tl.fromTo("#c{i}",{{opacity:0,y:16}},{{opacity:1,y:0,duration:.35,ease:"power2.out"}},{a:.2f});')
        js.append(f'tl.to("#c{i}",{{opacity:0,duration:.25}},{a + d - .25:.2f});')
    if i: SFX.append(('whoosh', a, -24))

hk = esc(job.get('hook'))
for w in (job.get('hook_hot') or [])[:2]:
    if w and esc(w) in hk: hk = hk.replace(esc(w), f'<b>{esc(w)}</b>', 1)
css = f'''
@font-face{{font-family:"Archivo";src:url(assets/Archivo.ttf)}}@font-face{{font-family:"Cairo-ar";src:url(assets/Cairo-ar.ttf)}}@font-face{{font-family:"Mono";src:url(assets/Mono.ttf)}}
html,body{{margin:0;background:{th["bg"]}}}
#root{{position:relative;width:{W}px;height:{HT}px;overflow:hidden;background:radial-gradient(ellipse at 50% 38%,{th["bg2"]} 0%,{th["bg"]} 68%)}}
.wave{{position:absolute;left:-60px;width:1200px;height:420px;bottom:-40px;opacity:.55}}
.hk{{position:absolute;left:44px;right:44px;top:86px;padding:22px 28px;border-radius:24px;background:{th["accent"]};color:{th["ink"]};text-align:center;font-family:{FONT};font-weight:900;font-size:{70 if AR else 64}px;line-height:1.12;direction:{"rtl" if AR else "ltr"};box-shadow:0 12px 40px rgba(0,0,0,.45)}}
.hk b{{color:#FFFFFF;text-shadow:0 2px 0 {th["ink"]}}}
.phone{{position:absolute;left:{PX}px;top:{PY}px;width:{IW}px;height:{IH}px;border:{BZ}px solid #0B1220;border-radius:70px;overflow:hidden;background:#000;box-shadow:0 0 0 2px #2B4766,0 40px 100px rgba(0,0,0,.6),0 0 120px rgba(127,211,247,.18)}}
.phone video,.phone img{{position:absolute;left:0;top:0;width:{IW}px;height:{IH}px;object-fit:cover}}
.tap{{position:absolute;width:90px;height:90px;border-radius:50%;background:rgba(255,255,255,.55);border:4px solid #fff;opacity:0;z-index:5}}
.cap{{position:absolute;left:60px;right:60px;top:{PY + PH + 34}px;text-align:center;font-family:{FONT};font-weight:800;font-size:{52 if AR else 48}px;line-height:1.2;color:{th["text"]};direction:{"rtl" if AR else "ltr"};opacity:0;text-shadow:0 3px 16px rgba(0,0,0,.7)}}
.endc{{position:absolute;inset:0;background:rgba(4,14,26,.9);opacity:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;text-align:center;padding:0 80px;box-sizing:border-box}}
.endc h1{{margin:0;font-family:{FONT};font-weight:900;font-size:120px;color:{th["accent"]};letter-spacing:.02em}}
.endc h2{{margin:0;font-family:{FONT};font-weight:700;font-size:50px;color:{th["text"]};direction:{"rtl" if AR else "ltr"}}}
.endc .cta{{margin-top:20px;padding:22px 40px;border-radius:999px;background:{th["accent"]};color:{th["ink"]};font-family:{FONT};font-weight:900;font-size:46px}}
.endc small{{font-family:{FONT};font-size:28px;color:#8FB3CC;direction:{"rtl" if AR else "ltr"}}}
.note{{position:absolute;left:0;right:0;top:{PY + PH - 4}px;text-align:center;font-family:"Mono";font-size:20px;letter-spacing:.12em;color:rgba(234,246,255,.45)}}
'''
wave = ('<svg class="wave" viewBox="0 0 1200 420" preserveAspectRatio="none"><path id="wv" fill="#1C5A86" d="M0,220 C200,140 400,300 600,220 C800,140 1000,300 1200,220 L1200,420 L0,420Z"/>'
        '<path fill="#123F63" d="M0,280 C200,220 400,340 600,280 C800,220 1000,340 1200,280 L1200,420 L0,420Z"/></svg>')
h = [f'<!DOCTYPE html><html lang="{"ar" if AR else "fr"}"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>{css}</style></head><body>',
     f'<div id="root" data-composition-id="main" data-width="{W}" data-height="{HT}" data-start="0" data-duration="{END:.2f}">',
     f'<audio id="mix" data-start="0" data-duration="{END:.2f}" data-track-index="1" src="assets/mix.m4a"></audio>',
     wave, '<div class="phone" id="phone">', *media, *taps, '</div>',
     *([f'<div class="note">{esc(job["note"])}</div>'] if job.get('note') else []),
     f'<div class="hk" id="hk">{hk}</div>', *caps]
if end:
    h.append(f'<div class="endc" id="endc"><h1>{esc(end.get("title"))}</h1><h2>{esc(end.get("sub"))}</h2>'
             + (f'<div class="cta">{esc(end.get("cta"))}</div>' if end.get('cta') else '') + (f'<small>{esc(end.get("note"))}</small>' if end.get('note') else '') + '</div>')
    js.append(f'tl.fromTo("#endc",{{opacity:0}},{{opacity:1,duration:.45}},{END_A:.2f});tl.fromTo("#endc h1",{{scale:.85}},{{scale:1,duration:.6,ease:"back.out(2)"}},{END_A:.2f});')
    SFX.append(('ding', END_A + .1, -16))
js.append('tl.fromTo("#phone",{y:60,scale:.94},{y:0,scale:1,duration:.7,ease:"expo.out"},0);tl.fromTo("#hk",{scale:1.08},{scale:1,duration:.5,ease:"back.out(2)"},0);')
js.append(f'tl.to("#wv",{{x:-120,duration:{END:.2f},ease:"sine.inOut"}},0);')
SFX.append(('whoosh', 0, -18))
js.append('window.__timelines["main"]=tl;')
h.append('</div><script>' + '\n'.join(js) + '</script></body></html>')
open(f'{D}/index.html', 'w').write('\n'.join(h))

# mixage : musique + effets (les vidéos d'écran sont muettes)
A = f'{D}/assets'
music = job.get('music') or 'calme'
inp, fc, lab = [], [], []
if music != 'none' and os.path.exists(f'{A}/music_{music}.m4a'):
    inp += ['-stream_loop', '-1', '-i', f'{A}/music_{music}.m4a']
    fc.append(f'[0:a]atrim=0:{END:.2f},volume=-12dB,afade=t=in:d=0.6,afade=t=out:st={max(0, END - 1.5):.2f}:d=1.5[m]'); lab.append('[m]')
for s, tt, g in SFX:
    if not os.path.exists(f'{A}/sfx_{s}.m4a') or tt >= END: continue
    i = len([x for x in inp if x == '-i']); inp += ['-i', f'{A}/sfx_{s}.m4a']
    fc.append(f'[{i}:a]adelay={int(tt * 1000)}|{int(tt * 1000)},volume={g + 4}dB[x{i}]'); lab.append(f'[x{i}]')
if not lab:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', f'{END:.2f}', '-c:a', 'aac', f'{A}/mix.m4a'], check=True)
else:
    fc.append(''.join(lab) + f'amix=inputs={len(lab)}:normalize=0,atrim=0:{END:.2f}[out]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', f'{A}/mix.m4a'], check=True)
print('app', len(beats), 'temps forts, durée', round(END, 2))
