# Prépare un dossier de rendu : voix normalisée, images (pack ou URL), polices.
# Usage : python3 prepare.py <dossier contenant job.json>
import json, os, sys, shutil, subprocess, urllib.request
D = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, '..', 'pack')
os.makedirs(f'{D}/assets', exist_ok=True)
job = json.load(open(f'{D}/job.json'))

def get(url, dest):
    req = urllib.request.Request(url, headers={'User-Agent': 'fehmi-studio-render'})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f)

# voix : mono 48 kHz, volume harmonisé (la voix elle-même n'est pas modifiée)
get(job['voice'], f'{D}/assets/voice.src')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{D}/assets/voice.src', '-vn', '-ac', '1', '-ar', '48000',
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', f'{D}/assets/voice.m4a'], check=True)

names = {f[:-4] for f in os.listdir(PACK) if f.endswith('.jpg')}
for i, p in enumerate(job['plans']):
    if p.get('img_url'):
        get(p['img_url'], f'{D}/assets/n{i}.src')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{D}/assets/n{i}.src', '-q:v', '2', f'{D}/assets/n{i}.jpg'], check=True)
        p['_file'] = f'n{i}.jpg'
    else:
        n = p.get('img') if p.get('img') in names else 'standing'
        shutil.copy(f'{PACK}/{n}.jpg', f'{D}/assets/{n}.jpg')
        p['_file'] = f'{n}.jpg'
for f in ('Fraunces.ttf', 'Archivo.ttf', 'Cairo-ar.ttf', 'Cairo-la.ttf'):
    shutil.copy(f'{PACK}/{f}', f'{D}/assets/{f}')
for f in os.listdir(f'{PACK}/music'):
    shutil.copy(f'{PACK}/music/{f}', f'{D}/assets/music_{f}')
for f in os.listdir(f'{PACK}/sfx'):
    shutil.copy(f'{PACK}/sfx/{f}', f'{D}/assets/sfx_{f}')
json.dump(job, open(f'{D}/job.json', 'w'), ensure_ascii=False)
print('préparé :', len(job['plans']), 'plans, langue', job.get('lang'))
