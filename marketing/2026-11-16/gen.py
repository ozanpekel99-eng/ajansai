"""ajansAI 16–22 Kasım 2026 haftası: tipografik gönderi/carousel (1080x1350) ve Reels kareleri (1080x1920).
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
# 1 Pzt 16 Kasım — İşletmeler — ajans ücreti yerine reklam bütçesi
S['g1'] = ('', '''<div class="pad" style="justify-content:center;gap:40px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">İşletme sahiplerine</span>
<h1 style="font-size:100px">Ajans ücretini değil,<br><span class="ind">reklamını büyüt.</span></h1>
<p style="font-size:38px;line-height:1.35" class="mut">İçeriği kendin üret, bütçeni reklama ayır.</p>
''' + ui('“Günlük 300 TL, İzmir, 25–45 yaş”', 'Reklam yayında') + '''
<div class="card" style="gap:20px">''' + chk('Günlük bütçeyi sen belirlersin') + chk('Bölgeyi ve yaş aralığını sen seçersin') + chk('İstediğin an durdurursun') + '''</div></div>''' + FOOT)

# 2 Sal 17 Kasım — İşletmeler — 4 yanlış inanış (carousel 6)
S['g2_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:108px">“Sosyal medyamı<br>kendim <span class="ind">yönetemem.</span>”</h1>
<p class="mut" style="font-size:42px">Bunu söyletenler 4 yanlış inanış.</p></div>''' + FOOT)
myths = [('Tasarımcı olmam lazım.', 'Ne istediğini Türkçe yazarsın, kampanya görselin hazır olur.', '“Kışlık botlarda %25 indirim görseli”', 'Görsel hazır'),
         ('Çok vaktimi alır.', 'Fikir, metin ve görsel dakikalar içinde. Haftanı tek oturumda planlarsın.', '“Bu haftanın 5 gönderi fikri ve metinleri”', 'Fikirler hazır'),
         ('Reklam vermek karmaşık.', 'Bütçeni ve bölgeni yazarsın, reklamın tek tıkla yayına girer.', '“Günlük 250 TL, Ankara”', 'Reklam yayında'),
         ('Ajanstan pahalıya gelir.', 'Aylık $10’dan başlayan paketler var. Önce ücretsiz paketle denersin.', '“Ücretsiz paketle başla”', 'Hesap açıldı')]
for i, (m, t, p, d) in enumerate(myths, start=2):
    S[f'g2_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:38px"><span class="mut" style="font-size:30px;font-weight:700">{i-1}/4 · YANLIŞ</span>
<div class="myth">“{m}”</div>
<div class="card on" style="gap:14px"><span class="lab">DOĞRUSU</span><p style="font-size:40px;line-height:1.3;font-weight:500">{t}</p></div>
{ui(p, d)}</div>''' + FOOT)
S['g2_6'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:108px">Kendin yönet,<br><span class="ind">kontrol sende.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Fikir, görsel, video ve Instagram reklamı tek yerde. Türkçe yazman yeterli.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 4 Per 19 Kasım — Freelance — müşteri görüşmesine hazır taslakla git (carousel 5)
S['g4_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Freelance sosyal medya yöneticilerine</span>
<h1 style="font-size:104px">Yeni müşteri<br>görüşmesine<br><span class="ind">boş gitme.</span></h1><p class="mut" style="font-size:42px">Teklifini somut göster. 3 adım →</p></div>''' + FOOT)
fl = [('Görüşmeden önce', 'Markayı anlat, ilk haftanın fikirleri hazır olsun.', '“Bir pastane için ilk haftanın 5 gönderi fikri”', 'Fikirler hazır'),
      ('Görüşmede', 'Beğendiği fikirden kampanya görselini birlikte üret.', '“2. fikirden kampanya görseli hazırla”', 'Görsel hazır'),
      ('Görüşmeden sonra', 'İstenen değişikliği tek cümleyle yap, teklifini gönder.', '“Arka planı açık yap, başlığı büyüt”', 'Düzenleme hazır')]
for i, (t, d, p, dn) in enumerate(fl, start=2):
    S[f'g4_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">{i-1} · {t}</span><h1 style="font-size:84px">{d}</h1>{ui(p, dn)}</div>''' + FOOT)
S['g4_5'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:100px">Teklifin<br>konuşmadan önce<br><span class="ind">ikna etsin.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Müşteri onaylayınca reklamını da aynı yerden tek tıkla yayına al.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 5 Cum 20 Kasım — İşletmeler — bir haftalık içerik kaç kredi?
S['g5'] = ('', '''<div class="pad" style="gap:34px"><img class="logo" src="logo-on-dark.png" style="align-self:flex-start">
<h1 style="font-size:92px;margin-top:6px">Bir haftalık içerik<br><span class="ind">kaç kredi?</span></h1>
<div class="card" style="gap:16px"><span class="lab">ÖRNEK HAFTA</span>
<div class="li"><span>10 mesajlık fikir sohbeti</span><b>10</b></div>
<div class="li"><span>5 kampanya görseli</span><b>25</b></div>
<div class="li"><span>1 Reels videosu (1080p, 6 sn)</span><b>36</b></div>
<div class="sep"></div>
<div class="li"><span style="font-weight:700">Toplam</span><b class="ind" style="font-size:52px">71 kredi</b></div></div>
<div class="card on" style="gap:10px;padding:30px 40px"><div class="li"><span style="font-family:SG;font-weight:700;font-size:44px">Başlangıç · 200 kredi</span><b style="font-size:48px">$10</b></div><span style="font-size:27px;color:#E3E3FF">aylık + KDV · ücretsiz paketle de deneyebilirsin</span></div>
<p class="mut" style="font-size:27px;line-height:1.4">Görsel 5, sohbet mesajı 1, 1080p 6 sn video 36 kredi. Reklam verme Pro ($20 · 500 kredi) ve Advanced ($35 · 1.000 kredi) paketlerinde.</p></div>''' + FOOT)

# 7 Paz 22 Kasım — İşletmeler — yılbaşı kampanyasını Kasım'da planla
S['g7'] = ('.wk{display:grid;grid-template-columns:200px 1fr;gap:20px;align-items:center;font-size:34px;font-weight:500}.wk span:first-child{font-family:SG;font-weight:700;color:var(--soft);font-size:32px}', '''<div class="pad" style="justify-content:center;gap:36px;padding-bottom:150px"><span class="tag" style="align-self:flex-start">Yılbaşına hazırlık</span>
<h1 style="font-size:96px">Yılbaşı telaşı<br>başlamadan<br><span class="ind">planın hazır.</span></h1>
''' + ui('“Butiğim için 4 haftalık yılbaşı kampanya planı çıkar”', 'Plan hazır') + '''
<div class="card" style="gap:22px"><div class="wk"><span>1. hafta</span><span>Fikirler ve gönderi metinleri</span></div><div class="sep"></div>
<div class="wk"><span>2. hafta</span><span>Kampanya görselleri ve Reels</span></div><div class="sep"></div>
<div class="wk"><span>3–4. hafta</span><span>Instagram reklamı yayında</span></div></div></div>''' + FOOT)


# Reels kareleri (1080x1920)
def rf(inner):
    return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')


def tg(t):
    return f'<span class="tag" style="align-self:flex-start;font-size:30px">{t}</span>'


R1 = [  # Çar 18 Kasım — İşletmeler — Kara Cuma reklamı
    rf(tg('Kara Cuma · 27 Kasım') + '<h1 style="font-size:116px">Kara Cuma<br>reklamın hâlâ<br><span class="ind">hazır değil mi?</span></h1>'),
    rf('<h1 style="font-size:112px">Bu akşam<br>5 dakikanı ayır. ↓</h1>'),
    rf(tg('1 · Görsel') + ui('“Kara Cuma’ya özel tüm ürünlerde %30 indirim görseli”', 'Görsel hazır')),
    rf(tg('2 · Reklam metni') + ui('“Bu görsel için kısa bir reklam metni yaz”', 'Metin hazır')),
    rf(tg('3 · Bütçe ve bölge') + ui('“Günlük 400 TL, Bursa, 25–45 yaş”', 'Reklam yayında')),
    rf('<h1 style="font-size:120px">Ajans takvimi<br>yok.<br><span class="ind">Kontrol sende.</span></h1>'),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Kara Cuma’ya<br><span class="ind">hazır ol.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
R2 = [  # Cmt 21 Kasım — Bireysel — Öğretmenler Günü
    rf(tg('24 Kasım · Öğretmenler Günü') + '<h1 style="font-size:112px">Öğretmenine<br>teşekkür etmenin<br><span class="ind">en kolay yolu?</span></h1>'),
    rf('<h1 style="font-size:116px">Tasarım<br>programı yok.<br><span class="ind">Sadece yaz. ↓</span></h1>'),
    rf(tg('Türkçe yaz') + ui('“İlkokul öğretmenime Öğretmenler Günü için teşekkür gönderisi hazırla”', 'Görsel ve metin hazır')),
    rf(tg('Bir dokunuş ekle') + ui('“Başlığa ‘İyi ki varsınız’ yaz”', 'Düzenleme hazır')),
    rf('<h1 style="font-size:116px">Salı sabahı<br><span class="ind">paylaşmaya<br>hazır.</span></h1>'),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Ücretsiz<br><span class="ind">başla.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
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
