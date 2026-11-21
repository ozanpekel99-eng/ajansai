"""ajansAI 30 Kasım – 6 Aralık 2026 haftası: tipografik gönderi/carousel (1080x1350) ve Reels kareleri (1080x1920).
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


# 1 Pzt 30 Kasım — İşletmeler — zaman tasarrufu: brief/toplantı/revize zinciri yerine tek cümle
steps = ''.join(f'<div class="li" style="padding:2px 0"><span class="myth" style="font-size:50px;letter-spacing:-1px">{s}</span></div>'
                for s in ['Brief yaz', 'Toplantı ayarla', 'Taslak bekle', 'Revize iste'])
S['g1'] = ('', '''<div class="pad" style="justify-content:center;gap:38px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">Yeni haftaya başlarken</span>
<h1 style="font-size:92px">Brief, toplantı,<br>revize, onay…<br><span class="ind">ya da 5 dakika.</span></h1>
<div class="card" style="gap:10px;padding:28px 40px">''' + steps + '''</div>
''' + ui('“Çiçekçim için bu haftanın kampanya görselini hazırla”', 'Görsel hazır') + '''</div>''' + FOOT)

# 2 Sal 1 Aralık — İşletmeler — öğrenmen gerekmeyen 4 şey (carousel 6)
S['g2_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:104px">Sosyal medyanı<br>yönetmek için<br><span class="ind">öğrenmen<br>gerekmeyen<br>4 şey.</span></h1>
<p class="mut" style="font-size:42px;line-height:1.35">Teknik bilgi yok. Sadece Türkçe yaz.</p></div>''' + FOOT)
learn = [('Tasarım programı', 'Katman, yazı tipi, ölçü derdi yok. Ne istediğini anlat, görselin hazır gelsin.', '“Yeni sezon botlarımız için şık bir kampanya görseli”', 'Görsel hazır'),
         ('Video kurgusu', 'Zaman çizelgesi, geçiş, dışa aktarma yok. 1080p Reels videon hazır gelir.', '“Bu görselden 6 saniyelik Reels videosu yap”', 'Video hazır'),
         ('Metin yazarlığı', 'Boş sayfaya bakmak yok. Açıklama metni ve hashtag’ler birlikte gelir.', '“Bu gönderi için samimi bir açıklama ve hashtag’ler yaz”', 'Metin hazır'),
         ('Reklam paneli', 'Onlarca menü yok. Bütçeni, bölgeni ve kitleni seç; tek tıkla yayına al.', '“Bu videoyla Bursa’da Instagram reklamı ver”', 'Reklam yayında')]
for i, (h, t, p, d) in enumerate(learn, start=2):
    S[f'g2_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="mut" style="font-size:30px;font-weight:700">{i-1}/4 · Öğrenmen gerekmez</span>
<h1 class="myth" style="font-size:96px">{h}</h1>
<p style="font-size:40px;line-height:1.35" class="mut">{t}</p>
{ui(p, d)}</div>''' + FOOT)
S['g2_6'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:96px">Ajans masrafından kurtul.<br><span class="ind">Sosyal medyanı kendin yönet.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Fikir, görsel, video ve Instagram reklamı tek yerde.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 4 Per 3 Aralık — Freelance — müşterine tek taslak değil, seçenekler götür (carousel 5)
S['g4_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Freelance sosyal medya yöneticilerine</span>
<h1 style="font-size:100px">Müşterine<br>tek taslak değil,<br><span class="ind">seçenekler götür.</span></h1><p class="mut" style="font-size:42px">Müşterin seçsin, sen yayına al. 3 adım →</p></div>''' + FOOT)
tones = ''.join(f'<div class="card{" on" if j == 1 else ""}" style="padding:22px 32px;gap:6px"><span class="lab">{a}</span><span style="font-size:32px;line-height:1.3;font-weight:500">{b}</span></div>'
                for j, (a, b) in enumerate([('SAMİMİ', 'Kışın en sıcak köşesi seni bekliyor.'), ('ŞIK', 'Kış koleksiyonu, zamansız bir dokunuşla.'), ('ESPRİLİ', 'Üşümek mi? Bizim vitrinde öyle bir şey yok.')]))
S['g4_2'] = ('', '''<div class="pad" style="justify-content:center;gap:30px"><span class="tag" style="align-self:flex-start">1 · Metin seçenekleri</span>''' +
             ui('“Butik müşterim için kış kampanyası metnini 3 farklı tonda yaz”', '3 metin hazır') + tones + '''</div>''' + FOOT)
S['g4_3'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">2 · Görsel seçenekleri</span><h1 style="font-size:84px">Seçilen metinle<br>iki farklı görsel.</h1>''' +
             ui('“Şık tondaki metinle 2 görsel: biri açık, biri koyu tonlarda”', '2 görsel hazır') + '''
<p style="font-size:36px;line-height:1.35" class="mut">Görsel başına 5 kredi: iki seçenek 10 kredi.</p></div>''' + FOOT)
S['g4_4'] = ('', '''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">3 · Seçileni yayına al</span><h1 style="font-size:84px">Müşterin seçti,<br>reklamı sen ver.</h1>''' + form([('Görsel', 'Koyu ton'), ('Günlük bütçe', '300 TL'), ('Bölge', 'Ankara'), ('Yaş', '22–45')], 'Reklam yayında') + '''</div>''' + FOOT)
S['g4_5'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:96px">Daha az yazışma,<br><span class="ind">daha hızlı onay.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Seçenekleri dakikalar içinde hazırla, müşterin karar versin, sen bir sonraki işe geç.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 5 Cum 4 Aralık — İşletmeler — artık kimseye sormana gerek yok
qs = ''.join(f'<div class="li" style="padding:2px 0"><span class="myth" style="font-size:46px;letter-spacing:-1px">{q}</span></div>'
             for q in ['“Görsel ne zaman hazır?”', '“Şu yazıyı değiştirir misiniz?”', '“Reklam yayına girdi mi?”', '“Bütçenin ne kadarı harcandı?”'])
S['g5'] = ('', '''<div class="pad" style="justify-content:center;gap:40px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">İşletme sahiplerine</span>
<h1 style="font-size:96px">Artık kimseye<br><span class="ind">sormana gerek yok.</span></h1>
<div class="card" style="gap:14px;padding:32px 40px">''' + qs + '''</div>
<div class="card on" style="flex-direction:row;justify-content:space-between;align-items:center;padding:30px 40px"><span style="font-size:38px;font-weight:700">Hepsinin cevabı ekranında.</span><span style="font-size:44px">✓</span></div>
</div>''' + FOOT)

# 7 Paz 6 Aralık — İşletmeler — önce dene, sonra karar ver
plans = ''.join(f'<div class="card{" on" if j == 1 else ""}" style="padding:26px 28px;gap:6px;flex:1"><span class="lab">{a}</span><span style="font-family:SG;font-weight:700;font-size:52px">{b}</span><span class="{"" if j == 1 else "mut"}" style="font-size:26px">{c}</span></div>'
                for j, (a, b, c) in enumerate([('BAŞLANGIÇ', '$10', '200 kredi'), ('PRO', '$20', '500 kredi'), ('ADVANCED', '$35', '1.000 kredi')]))
S['g7'] = ('', '''<div class="pad" style="justify-content:center;gap:36px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">Pazar planı</span>
<h1 style="font-size:100px">Önce dene,<br><span class="ind">sonra karar ver.</span></h1>
<div class="card" style="gap:18px">''' + chk('Ücretsiz paketle başla') + chk('İlk görselini Türkçe yazarak üret') + chk('Beğenirsen sana uyan paketi seç') + '''</div>
<div style="display:flex;gap:16px">''' + plans + '''</div>
<p class="mut" style="font-size:26px">Fiyatlara KDV eklenir · Ödeme TL, iyzico ile</p></div>''' + FOOT)

# Reels kareleri (1080x1920)
def rf(inner):
    return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')


def tg(t):
    return f'<span class="tag" style="align-self:flex-start;font-size:30px">{t}</span>'




R1 = [  # Çar 2 Aralık — İşletmeler — Aralık geldi, vitrinin hâlâ Kasım'da mı?
    rf(tg('Aralık geldi') + '<h1 style="font-size:116px">Vitrinin<br>hâlâ<br><span class="ind">Kasım’da mı?</span></h1>'),
    rf('<h1 style="font-size:116px">Ajansı<br>bekleme.<br><span class="ind">Kendin<br>değiştir. ↓</span></h1>'),
    rf(tg('1 · Fikir') + ui('“Kafem için yılbaşı menüsü kampanya fikirleri”', 'Fikirler hazır')),
    rf(tg('2 · Görsel') + ui('“Yılbaşı menüsü için sıcak bir kampanya görseli”', 'Görsel hazır')),
    rf(tg('3 · Video') + ui('“Bu görselden 6 saniyelik Reels videosu yap”', 'Video hazır')),
    rf(tg('4 · Reklam') + ui('“İzmir’de 25–45 yaş, günlük 200 TL reklam ver”', 'Reklam yayında')),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:108px">5 dakikada<br><span class="ind">reklamın<br>yayında.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
R2 = [  # Cmt 5 Aralık — Bireysel — Dünya Kadın Hakları Günü: kendi işini kuran kadınlara
    rf(tg('5 Aralık · Dünya Kadın Hakları Günü') + '<h1 style="font-size:112px">Kendi işini<br>kuran tüm<br><span class="ind">kadınlara.</span></h1>'),
    rf('<h1 style="font-size:108px">Emeğini<br>anlatmak için<br><span class="ind">tasarımcı<br>beklemene<br>gerek yok. ↓</span></h1>'),
    rf(tg('Ev yapımı reçeller') + ui('“Ev yapımı reçellerim için samimi bir tanıtım gönderisi”', 'Gönderi hazır')),
    rf(tg('El örgüsü atkılar') + ui('“Yeni örgü koleksiyonum için 6 saniyelik Reels videosu”', 'Video hazır')),
    rf(tg('Özel ders') + ui('“Kendi şehrimde ders ilanım için Instagram reklamı ver”', 'Reklam yayında')),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Emeğin,<br><span class="ind">senin sesinle.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
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
