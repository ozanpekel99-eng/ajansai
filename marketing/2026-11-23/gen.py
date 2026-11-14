"""ajansAI 23–29 Kasım 2026 haftası: tipografik gönderi/carousel (1080x1350) ve Reels kareleri (1080x1920).
Çalıştırma: npm i @fontsource/space-grotesk @fontsource/inter && cp ../../web/public/logo-on-dark.png . && python3 gen.py && bash reels.sh
"""
import pathlib
from playwright.sync_api import sync_playwright

HEAD = '<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>.chk{{display:flex;gap:22px;align-items:center;font-size:36px;font-weight:500;line-height:1.3}}.chk i{{font-style:normal;width:52px;height:52px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center;font-size:28px;flex:none}}.card{{background:#15152A;border:1px solid #2E2E4C;border-radius:28px;padding:36px 40px;display:flex;flex-direction:column;gap:24px}}.card.on{{background:var(--indigo);border-color:var(--indigo)}}.lab{{font-size:24px;font-weight:700;color:var(--mut);letter-spacing:.06em}}.on .lab{{color:#DCDCFF}}.myth{{font-family:SG;font-weight:700;font-size:76px;line-height:1.05;letter-spacing:-2px;color:var(--mut);text-decoration:line-through;text-decoration-color:var(--indigo);text-decoration-thickness:6px}}.li{{display:flex;justify-content:space-between;align-items:center;font-size:34px;font-weight:500;padding:6px 0}}.li b{{font-family:SG;font-size:40px}}.sep{{height:1px;background:#33335A}}.story .bubble{{font-size:48px;padding:36px 42px}}.story .tag{{font-size:34px!important}}{css}</style></head><body class="{cls}"><div class="glow"></div><div class="grid"></div>{body}</body></html>'
FOOT = '<div class="foot"><img class="logo" src="logo-on-dark.png" style="height:36px"><span><b>ajansai.tr</b></span></div>'


def ui(prompt, done):
    return (f'<div class="bubble" style="align-self:flex-end;max-width:880px">{prompt}</div>'
            f'<div style="display:flex;gap:16px;align-items:center;font-size:32px;color:var(--soft);font-weight:700">'
            f'<span style="width:46px;height:46px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center">✓</span>{done}</div>')


def chk(t):
    return f'<div class="chk"><i>✓</i><span>{t}</span></div>'


S = {}


def form(rows, done):
    """Reklam formu görünümü: alan adı / değer satırları + onay."""
    r = '<div class="sep"></div>'.join(f'<div class="li"><span class="mut">{a}</span><b>{b}</b></div>' for a, b in rows)
    return (f'<div class="card" style="gap:14px"><span class="lab">REKLAM AYARLARI</span>{r}</div>'
            f'<div style="display:flex;gap:16px;align-items:center;font-size:32px;color:var(--soft);font-weight:700">'
            f'<span style="width:46px;height:46px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center">✓</span>{done}</div>')


# 1 Pzt 23 Kasım — İşletmeler — Kara Cuma reklamı tarihli: kendiliğinden başlar, kendiliğinden biter
S['g1'] = ('', '''<div class="pad" style="justify-content:center;gap:40px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">Kara Cuma haftası</span>
<h1 style="font-size:96px">Reklamın Cuma<br>başlasın, indirim<br><span class="ind">bitince dursun.</span></h1>
<p style="font-size:38px;line-height:1.35" class="mut">Tarihini ve toplam bütçeni bugünden sen belirle.</p>
''' + form([('Toplam bütçe', '2.000 TL'), ('Başlangıç', '27 Kasım'), ('Bitiş', '30 Kasım'), ('Bölge', 'İstanbul')], 'Reklam planlandı') + '''</div>''' + FOOT)

# 2 Sal 24 Kasım — İşletmeler — Markanı en iyi sen anlatırsın (carousel 6)
S['g2_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:112px">Markanı<br>en iyi<br><span class="ind">sen anlatırsın.</span></h1>
<p class="mut" style="font-size:42px;line-height:1.35">Sosyal medyanı kendin yönetmek için<br>4 neden.</p></div>''' + FOOT)
why = [('Müşterini sen tanırsın.', 'Kime seslendiğini anlatman yeter; fikir ve metin ona göre hazırlanır.', '“Mahallemizin müdavimleri için samimi bir kış menüsü gönderisi”', 'Fikir ve metin hazır'),
       ('Kendi dilinle konuşursun.', 'Markanın sesi değişmez. Tonu tek cümleyle sen ayarlarsın.', '“Daha sıcak yaz, ‘siz’ yerine ‘sen’ de”', 'Metin güncellendi'),
       ('Stoğu sen bilirsin.', 'Değişiklik olduğunda kimseye haber vermeden görselini güncellersin.', '“Görsele ‘Son 20 adet’ ekle”', 'Görsel güncellendi'),
       ('Zamanlamaya sen karar verirsin.', 'Hazır olduğunda reklamını tek tıkla yayına alırsın.', '“Bu görselle Instagram reklamı ver”', 'Reklam yayında')]
for i, (h, t, p, d) in enumerate(why, start=2):
    S[f'g2_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="mut" style="font-size:30px;font-weight:700">{i-1}/4</span>
<h1 style="font-size:84px">{h}</h1>
<p style="font-size:40px;line-height:1.35" class="mut">{t}</p>
{ui(p, d)}</div>''' + FOOT)
S['g2_6'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:104px">Ajans masrafı yok.<br><span class="ind">Kontrol sende.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Fikir, görsel, video ve Instagram reklamı tek yerde. Türkçe yazman yeterli.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 4 Per 26 Kasım — İşletmeler — En çok beğenilen gönderini reklama çevir (carousel 5)
S['g4_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">İşletme sahiplerine</span>
<h1 style="font-size:104px">En çok beğenilen<br>gönderini<br><span class="ind">reklama çevir.</span></h1><p class="mut" style="font-size:42px">Yeni görsel bile gerekmez. 3 adım →</p></div>''' + FOOT)
opts = ''.join(f'<div class="card{" on" if j == 3 else ""}" style="padding:22px 32px;gap:4px;flex-direction:row;justify-content:space-between;align-items:center"><span style="font-size:34px;font-weight:700">{a}</span><span style="font-size:26px" class="{"" if j == 3 else "mut"}">{b}</span></div>'
               for j, (a, b) in enumerate([('Profil ziyareti', 'Instagram profiline'), ('Web sitesi', 'Sitene tıklama'), ('WhatsApp', 'Sana yazarlar'), ('Instagram DM', 'DM’den mesaj'), ('Bilinirlik', 'Daha çok kişiye')]))
S['g4_2'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">1 · Gönderini seç</span><h1 style="font-size:84px">Reklam türünde<br>“Mevcut gönderi”yi seç.</h1>
<div class="card" style="gap:18px"><span class="lab">REKLAM İÇERİĞİ</span><div style="display:flex;gap:14px;font-size:30px;font-weight:700"><span class="mut" style="padding:16px 22px;border:1px solid #33335A;border-radius:16px">Görsel / video</span><span class="mut" style="padding:16px 22px;border:1px solid #33335A;border-radius:16px">Karusel</span><span style="padding:16px 22px;background:var(--indigo);border-radius:16px">Mevcut gönderi</span></div></div>
<p style="font-size:38px;line-height:1.35" class="mut">Instagram’da zaten beğenilen gönderin, olduğu gibi reklama dönüşür.</p></div>''' + FOOT)
S['g4_3'] = ('', '''<div class="pad" style="justify-content:center;gap:30px"><span class="tag" style="align-self:flex-start">2 · Amacını seç</span><h1 style="font-size:80px">Reklamın ne getirsin?</h1>''' + opts + '''</div>''' + FOOT)
S['g4_4'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">3 · Bütçe ve kitle</span><h1 style="font-size:84px">Bütçeni ve kitleni<br>sen belirle.</h1>''' + form([('Günlük bütçe', '250 TL'), ('Bölge', 'Eskişehir'), ('Yaş', '20–40')], 'Reklam yayında') + '''</div>''' + FOOT)
S['g4_5'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:100px">Beğenilen gönderi,<br><span class="ind">daha çok kişiye.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Ajansa brief yok, bekleme yok. Reklamını kendin ver, kendin durdur.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 5 Cum 27 Kasım — İşletmeler — Bugün Kara Cuma: rapor bekleme, reklamını kendin izle
kpi = ''.join(f'<div class="card" style="padding:26px 30px;gap:8px;flex:1"><span style="font-family:SG;font-weight:700;font-size:40px">{a}</span><span class="mut" style="font-size:26px;line-height:1.3">{b}</span></div>'
              for a, b in [('Sonuç', 'Ziyaret ya da mesaj'), ('Erişim', 'Kaç kişiye ulaştı'), ('Gösterim', 'Kaç kez görüldü')])
S['g5'] = ('', '''<div class="pad" style="justify-content:center;gap:40px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">Bugün Kara Cuma</span>
<h1 style="font-size:96px">Rapor bekleme.<br><span class="ind">Reklamını kendin izle.</span></h1>
<p style="font-size:38px;line-height:1.35" class="mut">Reklamın yayındayken sonuçları panelinde gör, kararı sen ver.</p>
<div style="display:flex;gap:18px">''' + kpi + '''</div>
<div class="card on" style="flex-direction:row;justify-content:space-between;align-items:center;padding:30px 40px"><span style="font-size:36px;font-weight:700">Kara Cuma reklamı · Yayında</span><span style="background:#fff;color:var(--indigo);font-family:SG;font-weight:700;font-size:30px;padding:14px 26px;border-radius:14px">Durdur</span></div>
</div>''' + FOOT)

# 7 Paz 29 Kasım — Bireysel — yeni yıl kartını kendin hazırla
S['g7'] = ('', '''<div class="pad" style="justify-content:center;gap:42px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">Aralık geliyor</span>
<h1 style="font-size:100px">Yeni yıl kartını<br><span class="ind">kendin hazırla.</span></h1>
''' + ui('“Arkadaş grubum için sıcak ve eğlenceli bir 2027 yılbaşı kartı”', 'Görsel ve metin hazır') + '''
<div class="card" style="gap:20px">''' + chk('Tasarım programı gerekmez') + chk('Değişiklik için tek cümle yeter') + chk('İstersen Reels videosuna çevir') + '''</div></div>''' + FOOT)

# Reels kareleri (1080x1920)
def rf(inner):
    return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')


def tg(t):
    return f'<span class="tag" style="align-self:flex-start;font-size:30px">{t}</span>'




R1 = [  # Çar 25 Kasım — Freelance — Kara Cuma haftası: 4 müşteri, tek akşam
    rf(tg('Freelance sosyal medya yöneticilerine') + '<h1 style="font-size:116px">Kara Cuma<br>haftası.<br><span class="ind">4 müşteri.</span></h1>'),
    rf('<h1 style="font-size:120px">Hepsi<br><span class="ind">tek akşamda.</span> ↓</h1>'),
    rf(tg('Müşteri 1 · Ayakkabı mağazası') + ui('“Tüm spor ayakkabılarda Kara Cuma indirimi görseli”', 'Görsel hazır')),
    rf(tg('Müşteri 2 · Kitabevi') + ui('“Kara Cuma kitap kampanyası için 6 saniyelik Reels videosu”', 'Video hazır')),
    rf(tg('Müşteri 3 · Spor salonu') + ui('“Kara Cuma üyelik kampanyası, WhatsApp’tan mesaj alan reklam”', 'Reklam yayında')),
    rf(tg('Müşteri 4 · Çiçekçi') + ui('“Hafta sonu teslimat kampanyası için 3 gönderi fikri”', 'Fikirler hazır')),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:104px">Daha çok müşteri,<br><span class="ind">daha az mesai.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
R2 = [  # Cmt 28 Kasım — İşletmeler — indirim uzadı mı? tek cümleyle güncelle
    rf(tg('Kara Cuma hafta sonu') + '<h1 style="font-size:112px">İndirimin<br>hafta sonu da<br><span class="ind">devam mı?</span></h1>'),
    rf('<h1 style="font-size:116px">Görselini<br>baştan yaptırma.<br><span class="ind">Tek cümle yaz. ↓</span></h1>'),
    rf(tg('1 · Görseli güncelle') + ui('“Görseldeki tarihi ‘Pazar gecesine kadar’ yap”', 'Görsel güncellendi')),
    rf(tg('2 · Videoya çevir') + ui('“Bu görselden 6 saniyelik Reels videosu yap”', 'Video hazır')),
    rf(tg('3 · Reklamı ver') + ui('“Yeni videoyla hafta sonu reklamı, günlük 300 TL, Antalya”', 'Reklam yayında')),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Ajansa yeni<br>brief yok.<br><span class="ind">Kontrol sende.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
for k, frames in (('r1', R1), ('r2', R2)):
    for i, f in enumerate(frames):
        S[f'{k}_{i}'] = f

if __name__ == '__main__':
    pathlib.Path('frames').mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, (css, body) in S.items():
            story = name.startswith('r')
            pg = b.new_page(viewport={'width': 1080, 'height': 1920 if story else 1350})
            f = pathlib.Path(f'_{name}.html')
            f.write_text(HEAD.format(css=css, cls='story' if story else '', body=body))
            pg.goto('file://' + str(f.resolve()))
            pg.wait_for_timeout(400)
            # taşma kontrolü: .pad içeriği sayfadan taşıyor mu?
            over = pg.evaluate('''()=>{const p=document.querySelector('.pad');return p.scrollHeight>p.clientHeight||p.scrollWidth>p.clientWidth}''')
            if over:
                print('TAŞMA:', name)
            pg.screenshot(path=(f'frames/{name}.png' if story else f'{name}.png'))
            pg.close()
            f.unlink()
        b.close()
    print(len(S), 'kare')
