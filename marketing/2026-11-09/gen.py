"""ajansAI 9–15 Kasım 2026 haftası: tipografik gönderi/carousel (1080x1350) ve Reels kareleri (1080x1920).
Çalıştırma: npm i @fontsource/space-grotesk @fontsource/inter && cp ../../web/public/logo-on-dark.png . && python3 gen.py && bash reels.sh
"""
import pathlib
from playwright.sync_api import sync_playwright

HEAD = '<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>.chk{{display:flex;gap:22px;align-items:center;font-size:38px;font-weight:500;line-height:1.3}}.chk i{{font-style:normal;width:54px;height:54px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center;font-size:30px;flex:none}}.card{{background:#15152A;border:1px solid #2E2E4C;border-radius:28px;padding:36px 40px;display:flex;flex-direction:column;gap:26px}}.st{{display:flex;justify-content:space-between;align-items:center;font-size:32px;font-weight:500}}.pill{{font-size:24px;font-weight:700;padding:8px 18px;border-radius:999px;background:rgba(65,63,245,.22);color:var(--soft)}}.pill.live{{background:var(--indigo);color:#fff}}{css}</style></head><body class="{cls}"><div class="glow"></div><div class="grid"></div>{body}</body></html>'
FOOT = '<div class="foot"><img class="logo" src="logo-on-dark.png" style="height:36px"><span><b>ajansai.tr</b></span></div>'


def ui(prompt, done):
    return (f'<div class="bubble" style="align-self:flex-end;max-width:880px">{prompt}</div>'
            f'<div style="display:flex;gap:16px;align-items:center;font-size:32px;color:var(--soft);font-weight:700">'
            f'<span style="width:46px;height:46px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center">✓</span>{done}</div>')


def chk(t):
    return f'<div class="chk"><i>✓</i><span>{t}</span></div>'


S = {}
# 1 Pzt 9 Kasım — İşletmeler — zaman tasarrufu
S['g1'] = ('', '''<div class="pad" style="justify-content:center;gap:34px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">İşletme sahiplerine</span>
<h1 style="font-size:96px">Kahven soğumadan<br><span class="ind">kampanyan hazır.</span></h1>
''' + ui('“Yeni gelen kışlık ürünler için bu haftanın kampanyasını hazırla”', 'Kampanya hazır') + '''
<div class="card" style="gap:22px">''' + chk('Gönderi fikri ve metni') + chk('Kampanya görseli') + chk('Reels videosu') + chk('Tek tıkla Instagram reklamı') + '''</div>
<p class="mut" style="font-size:32px">Brief, toplantı, bekleme yok. Sadece Türkçe yaz.</p></div>''' + FOOT)

# 2 Sal 10 Kasım — Freelance carousel (5)
S['g2_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Freelance sosyal medya yöneticilerine</span>
<h1 style="font-size:108px">Teklifine bir<br>satır ekle:<br><span class="ind">reklam yönetimi.</span></h1>
<p class="mut" style="font-size:40px">İçeriği hazırladığın yerde reklamı da ver. →</p></div>''' + FOOT)
S['g2_2'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">1 · İçerik</span>
<h1 style="font-size:84px">Müşterinin kampanyasını Türkçe yaz.</h1>''' + ui('“Kuaför müşterim için kasım kampanyası görseli ve metni”', 'Görsel ve metin hazır') + '</div>' + FOOT)
S['g2_3'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">2 · Reklam</span>
<h1 style="font-size:84px">Amacı seç: profil ziyareti, site tıklaması ya da mesaj.</h1>''' + ui('“Günlük 200 TL, İzmir, 20-40 yaş”', 'Reklam hazır') + '</div>' + FOOT)
S['g2_4'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">3 · Yayın</span>
<h1 style="font-size:84px">Tek tıkla yayına al, durumunu tek ekranda gör.</h1>
<div class="card"><div class="st"><span>Kuaför · Kasım kampanyası</span><span class="pill live">Yayında</span></div>
<div class="st"><span>Kafe · Kış menüsü</span><span class="pill live">Yayında</span></div>
<div class="st"><span>Butik · Yeni sezon</span><span class="pill">Duraklatıldı</span></div></div></div>''' + FOOT)
S['g2_5'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:104px">Aynı mesai,<br><span class="ind">daha geniş hizmet.</span></h1>
<p class="mut" style="font-size:40px;line-height:1.4">Fikir, görsel, video ve Instagram reklamı tek yerde. Ücretsiz paketle dene.</p>
<span class="cta" style="align-self:flex-start">ajansai.tr</span></div>''' + FOOT)

# 4 Per 12 Kasım — Kara Cuma hazırlık carousel (6)
S['g4_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kara Cuma · 27 Kasım</span>
<h1 style="font-size:116px">15 gün kaldı.<br><span class="ind">Hazırlığı<br>kendin yap.</span></h1>
<p class="mut" style="font-size:40px">Ajans takvimine sıkışmadan, 4 adımda. →</p></div>''' + FOOT)
kc = [('1 · Fikir', 'Kampanya fikrini ve metinlerini çıkar.', '“Kara Cuma için 3 kampanya fikri ve gönderi metni”', 'Fikirler hazır'),
      ('2 · Görsel', 'Ürün fotoğrafını yükle, indirimini yaz.', '“Bu ürün fotoğrafıyla Kara Cuma indirim görseli”', 'Görsel hazır'),
      ('3 · Video', 'Aynı görselden Reels videosu üret.', '“Bu görselden Reels videosu yap”', 'Video hazır'),
      ('4 · Reklam', 'Bütçeni ve bölgeni seç, tek tıkla yayına al.', '“Günlük 400 TL, Türkiye geneli”', 'Reklam yayında')]
for i, (t, h, p, d) in enumerate(kc, start=2):
    S[f'g4_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">{t}</span>
<h1 style="font-size:88px">{h}</h1>{ui(p, d)}</div>''' + FOOT)
S['g4_6'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:112px">Kara Cuma'ya<br><span class="ind">hazırsın.</span></h1>
<p class="mut" style="font-size:40px;line-height:1.4">Kaydet, hazırlık günü geldiğinde aç. Ücretsiz paketle bugünden dene.</p>
<span class="cta" style="align-self:flex-start">ajansai.tr</span></div>''' + FOOT)

# 5 Cum 13 Kasım — Bireysel
S['g5'] = ('', '''<div class="pad" style="justify-content:center;gap:48px"><span class="tag" style="align-self:flex-start">Yan işin varsa</span>
<h1 style="font-size:108px">Yan işin var,<br><span class="ind">tasarımcın<br>yok mu?</span></h1>
<p style="font-size:38px;line-height:1.4" class="mut">Takı, örgü, ev yapımı reçel, özel ders… Ne yapıyorsan Türkçe yaz.</p>
''' + ui('“Elde ördüğüm bereler için tanıtım gönderisi hazırla”', 'Görsel ve metin hazır') + '''
<span class="cta" style="align-self:flex-start">Ücretsiz başla → ajansai.tr</span></div>''')

# 7 Paz 15 Kasım — İşletmeler — mesaj amaçlı reklam
S['g7'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><span class="tag" style="align-self:flex-start">Instagram reklamı</span>
<h1 style="font-size:104px">Reklamın<br>müşteriyi<br><span class="ind">mesaja getirsin.</span></h1>
<div class="card">''' + chk('Amaç: Mesaj — WhatsApp ya da Instagram DM') + chk('Buton: “WhatsApp\'tan mesaj gönder”') + chk('Bütçeni ve bölgeni sen seç') + '''</div>
<p class="mut" style="font-size:30px">Reklam verme Pro ve Advanced paketlerinde.</p></div>''' + FOOT)


def rf(inner):
    return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')


def tg(t):
    return f'<span class="tag" style="align-self:flex-start;font-size:30px">{t}</span>'


END = lambda h: rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start">' + h +
                   '<span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr · ücretsiz dene</span>')

R1 = [  # Çar 11 Kasım — 11.11 son dakika
    rf(tg('İşletme sahibiysen') + '<h1 style="font-size:150px">Bugün<br><span class="ind">11.11.</span></h1><h1 style="font-size:96px">Kampanyan<br>hazır mı?</h1>'),
    rf('<h1 style="font-size:112px">Ajansa brief<br>yazacak vaktin<br><span class="ind">yok mu?</span></h1><p class="mut" style="font-size:52px">Gerek de yok. ↓</p>'),
    rf(tg('1 · Fikir') + ui('“Bugüne özel 11.11 indirimimiz için gönderi fikri ve metni”', 'Fikir ve metin hazır')),
    rf(tg('2 · Görsel') + ui('“Tüm ayakkabılarda 11.11 indirimi görseli”', 'Görsel hazır')),
    rf(tg('3 · Reklam') + ui('“Günlük 300 TL, Bursa, Instagram”', 'Reklam yayında')),
    END('<h1 style="font-size:112px">5 dakikada<br><span class="ind">reklamın<br>yayında.</span></h1>'),
]
R2 = [  # Cmt 14 Kasım — sektörler
    rf(tg('Her işletme için') + '<h1 style="font-size:116px">Sektörün<br>ne olursa olsun.<br><span class="ind">Bir cümle yeter.</span></h1>'),
    rf(tg('Kafe') + ui('“Yeni kış menümüz için gönderi görseli”', 'Görsel hazır')),
    rf(tg('Kuaför') + ui('“Hafta içi fön kampanyası için Reels videosu”', 'Video hazır')),
    rf(tg('Emlak') + ui('“Satılık 3+1 daire için Instagram reklamı, Antalya”', 'Reklam yayında')),
    rf(tg('Butik') + ui('“Yeni sezon kabanlar için bu haftanın gönderi fikirleri”', 'Fikirler hazır')),
    END('<h1 style="font-size:112px">Ajans masrafı yok.<br><span class="ind">Kontrol sende.</span></h1>'),
]
for k, frames in (('r1', R1), ('r2', R2)):
    for i, f in enumerate(frames):
        S[f'{k}_{i}'] = f

out = pathlib.Path('.')
frames = pathlib.Path('frames'); frames.mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, (css, body) in S.items():
        story = name.startswith('r')
        pg = b.new_page(viewport={'width': 1080, 'height': 1920 if story else 1350})
        f = pathlib.Path(f'_{name}.html'); f.write_text(HEAD.format(css=css, cls='story' if story else '', body=body))
        pg.goto('file://' + str(f.resolve())); pg.wait_for_timeout(400)
        # taşma kontrolü
        ov = pg.evaluate('''()=>{const H=document.body.clientHeight,W=document.body.clientWidth;let bad=[];
          document.querySelectorAll('.pad > *, .foot').forEach(e=>{const r=e.getBoundingClientRect();if(r.bottom>H-4||r.right>W-4||r.top<0)bad.push(e.className||e.tagName)});
          const pad=document.querySelector('.pad');if(pad&&pad.scrollHeight>pad.clientHeight+2)bad.push('pad-scroll');
          const foot=document.querySelector('.foot');if(foot){const fr=foot.getBoundingClientRect();document.querySelectorAll('.pad > *').forEach(e=>{if(e.getBoundingClientRect().bottom>fr.top-10)bad.push('foot-overlap:'+(e.className||e.tagName))})}
          return bad}''')
        if ov: print('OVERFLOW', name, ov)
        pg.screenshot(path=str((frames if story else out) / f'{name}.png')); pg.close()
        f.unlink()
    b.close()
print(len(S))
