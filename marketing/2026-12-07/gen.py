"""ajansAI 7 – 13 Aralık 2026 haftası: tipografik gönderi/carousel (1080x1350) ve Reels kareleri (1080x1920).
Çalıştırma: npm i @fontsource/space-grotesk @fontsource/inter && cp ../../web/public/logo-on-dark.png . && python3 gen.py && bash reels.sh
Şablon: 2026-10-27/gen.py + base.css (aynı görsel dil). Üretilmiş örnek görsel/video kullanılmaz; yalnızca tipografi ve arayüz anlatımı.
"""
import pathlib
from playwright.sync_api import sync_playwright

HEAD = '<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>.chk{{display:flex;gap:22px;align-items:center;font-size:36px;font-weight:500;line-height:1.3}}.chk i{{font-style:normal;width:52px;height:52px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center;font-size:28px;flex:none}}.card{{background:#15152A;border:1px solid #2E2E4C;border-radius:28px;padding:36px 40px;display:flex;flex-direction:column;gap:24px}}.card.on{{background:var(--indigo);border-color:var(--indigo)}}.lab{{font-size:24px;font-weight:700;color:var(--mut);letter-spacing:.06em}}.on .lab{{color:#DCDCFF}}.li{{display:flex;justify-content:space-between;align-items:center;gap:24px;font-size:36px;font-weight:500;padding:4px 0}}.li b{{font-family:SG;font-size:38px;white-space:nowrap}}.sep{{height:1px;background:#33335A}}.strike{{color:var(--mut);text-decoration:line-through;text-decoration-color:var(--indigo);text-decoration-thickness:5px}}.chip{{display:inline-block;border:1px solid #3A3A62;color:var(--fg);font-size:28px;font-weight:500;padding:12px 22px;border-radius:999px}}.btn{{font-family:SG;font-weight:700;font-size:30px;padding:16px 30px;border-radius:16px;border:2px solid #3A3A62;color:var(--fg)}}.btn.pri{{background:var(--indigo);border-color:var(--indigo);color:#fff}}.dot{{display:inline-flex;align-items:center;gap:12px;font-size:28px;font-weight:700;color:#7CF2B0}}.dot:before{{content:"";width:16px;height:16px;border-radius:50%;background:#3DDC84}}.story .bubble{{font-size:48px;padding:36px 42px}}.story .tag{{font-size:34px!important}}{css}</style></head><body class="{cls}"><div class="glow"></div><div class="grid"></div>{body}</body></html>'
FOOT = '<div class="foot"><img class="logo" src="logo-on-dark.png" style="height:36px"><span><b>ajansai.tr</b></span></div>'


def ui(prompt, done):
    return (f'<div class="bubble" style="align-self:flex-end;max-width:880px">{prompt}</div>'
            f'<div style="display:flex;gap:16px;align-items:center;font-size:32px;color:var(--soft);font-weight:700">'
            f'<span style="width:46px;height:46px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center">✓</span>{done}</div>')


def chk(t):
    return f'<div class="chk"><i>✓</i><span>{t}</span></div>'


S = {}

# 1 Pzt 7 Ara — 2027 bütçesi: ajans satırına gerek yok (işletmeler)
S['g1'] = ('', '''<div class="pad" style="justify-content:center;gap:48px"><span class="tag" style="align-self:flex-start">Yıl sonu bütçe hesabı</span>
<h1 style="font-size:100px">2027 bütçende<br>bu satıra<br><span class="ind">gerek yok.</span></h1>
<div class="card"><span class="lab">SOSYAL MEDYA · 2027</span>
<div class="li"><span class="strike">Aylık ajans ücreti</span><b class="strike">—</b></div><div class="sep"></div>
<div class="li"><span>İçerik: fikir, görsel, video</span><b class="ind" style="color:var(--soft)">ajansAI</b></div><div class="sep"></div>
<div class="li"><span>Reklam bütçesi</span><b>Senin kararın</b></div></div>
<p class="mut" style="font-size:36px;line-height:1.4">Sosyal medyanı kendin yönet. Paketler aylık <b style="color:var(--fg)">$10</b>'dan başlar (+KDV).</p></div>''' + FOOT)

# 2 Sal 8 Ara — Yılbaşı sezonunun 4 gönderisi, 4 cümle (carousel 6, işletmeler)
S['g2_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:116px">Yılbaşı<br>sezonunun<br><span class="ind">4 gönderisi.</span></h1><p class="mut" style="font-size:42px;line-height:1.35">Her biri için tek bir Türkçe cümle yeter.</p></div>''' + FOOT)
yb = [('Hediye rehberi', 'Ne alacağını bilemeyenlere yol göster.', '“Butiğim için yılbaşı hediye önerileri gönderisi hazırla”', 'Görsel ve metin hazır'),
      ('Yılbaşı indirimi', 'Kampanyanı tek görselde duyur.', '“Yılbaşına özel tüm ürünlerde %20 indirim görseli”', 'Görsel hazır'),
      ('Son sipariş günü', 'Hediyesi zamanında gelsin isteyenlere hatırlat.', '“Yılbaşına yetişmesi için son sipariş günü duyurusu”', 'Görsel hazır'),
      ('Teşekkür', 'Yılı müşterilerine teşekkür ederek kapat.', '“Bu yıl bizi seçen müşterilerimize teşekkür Reels\'i”', 'Reels hazır')]
for i, (t, d, p, dn) in enumerate(yb, start=2):
    S[f'g2_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="mut" style="font-size:30px;font-weight:700">{i-1}/4</span>
<h1 style="font-size:96px">{t}</h1><p class="mut" style="font-size:40px;line-height:1.35">{d}</p>{ui(p, dn)}</div>''' + FOOT)
S['g2_6'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:104px">4 cümle,<br>sezon <span class="ind">hazır.</span></h1>
<p class="mut" style="font-size:40px;line-height:1.4">Beğendiğini tek tıkla Instagram reklamına çevir. Ajans takvimi bekleme, kontrol sende.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 4 Per 10 Ara — Freelancer: tatile çıkmadan müşterilerinin Ocak'ını hazırla (carousel 5)
S['g4_1'] = ('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Freelance sosyal medya yöneticilerine</span>
<h1 style="font-size:104px">Tatile çıkmadan<br>müşterilerinin<br><span class="ind">Ocak'ı hazır.</span></h1><p class="mut" style="font-size:38px">Yılbaşı haftan bilgisayar başında geçmesin. →</p></div>''' + FOOT)
fr = [('1 · Fikir', 'Her müşterin için Ocak ayının gönderi ve Reels fikirleri.', '“Pilates stüdyosu müşterim için Ocak ayı gönderi planı”', 'Fikirler ve metinler hazır'),
      ('2 · Görsel & video', 'Planı tek oturumda görsele ve 1080p Reels videosuna çevir.', '“Yeni yıl, yeni hedef: Ocak üyelik kampanyası görseli”', 'Görsel ve video hazır'),
      ('3 · Reklam', 'Başlangıç ve bitiş tarihini seç; reklam Ocak\'ta kendiliğinden başlasın.', '“Başlangıç 2 Ocak, bitiş 31 Ocak, toplam bütçe”', 'Reklam kuruldu')]
for i, (t, d, p, dn) in enumerate(fr, start=2):
    S[f'g4_{i}'] = ('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">{t}</span>
<h1 style="font-size:80px">{d}</h1>{ui(p, dn)}</div>''' + FOOT)
S['g4_5'] = ('', '''<div class="pad" style="justify-content:center;gap:44px"><h1 style="font-size:100px">Müşterilerin<br>hazır,<br><span class="ind">sen tatilde.</span></h1>
''' + chk('Her müşteri için ayrı fikir ve metin') + chk('Görseller ve Reels tek oturumda') + chk('Tarihli reklam, tek tıkla') + '''
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>''' + FOOT)

# 5 Cum 11 Ara — "Bugün ne paylaşsam?" (işletmeler)
S['g5'] = ('', '''<div class="pad" style="justify-content:center;gap:46px"><span class="tag" style="align-self:flex-start">Fikir tükendiyse</span>
<h1 style="font-size:96px">“Bugün ne<br>paylaşsam?”<br><span class="ind">Bunu da sor.</span></h1>
''' + ui('“Kuaför salonum için bu hafta ne paylaşsam? Aralık\'a uygun olsun.”', 'Fikirler hazır') + '''
<div style="display:flex;flex-wrap:wrap;gap:14px"><span class="chip">Gönderi fikirleri</span><span class="chip">Açıklama metni</span><span class="chip">Hashtag'ler</span><span class="chip">Reels fikri</span></div>
<p class="mut" style="font-size:34px;line-height:1.4">Beğendiğin fikri aynı yerde görsele, videoya ve reklama çevir.</p></div>''' + FOOT)

# 7 Paz 13 Ara — Reklamını sen başlat, sen durdur (işletmeler)
S['g7'] = ('', '''<div class="pad" style="justify-content:center;gap:42px"><span class="tag" style="align-self:flex-start">Kontrol sende</span>
<h1 style="font-size:100px">Reklamını<br>sen başlat,<br><span class="ind">sen durdur.</span></h1>
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><span class="lab">REKLAMLARIM</span><span class="dot">Yayında</span></div>
<div style="font-family:SG;font-weight:700;font-size:44px">Yılbaşı indirimi</div>
<div style="display:flex;gap:16px"><span class="btn">Durdur</span><span class="btn pri">Sonuçları izle</span></div></div>
''' + chk('Sen “Yayına al” demeden yayına girmez') + chk('Bütçe kendi reklam hesabından harcanır') + chk('İstediğin an tek tıkla durdur') + '''</div>''' + FOOT)


# Reels kareleri (1080x1920)
def rf(inner):
    return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')


R1 = [  # Çar 9 Ara — işletme: dükkânı kapattıktan sonra 5 dakika
    rf('<span class="tag" style="align-self:flex-start">Esnafa, işletme sahibine</span><h1 style="font-size:118px">Dükkânı<br>kapattın.<br><span class="ind">Yorgunsun.</span></h1>'),
    rf('<h1 style="font-size:108px">Yarının<br>reklamı için<br>5 dakikan<br><span class="ind">var mı?</span></h1>'),
    rf('<span class="tag" style="align-self:flex-start">1 · Fikir</span>' + ui('“Pastanem için yılbaşı pastası siparişi gönderisi”', 'Fikir ve metin hazır')),
    rf('<span class="tag" style="align-self:flex-start">2 · Görsel</span>' + ui('“Yılbaşı pastası siparişleri başladı görseli”', 'Görsel hazır')),
    rf('<span class="tag" style="align-self:flex-start">3 · Reklam</span>' + ui('“Yarın sabah başlasın, günlük bütçe, semtim”', 'Reklam kuruldu')),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:104px">Ajansa<br>gerek yok.<br><span class="ind">Yarın sabah<br>reklamın yayında.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
R2 = [  # Cmt 12 Ara — bireysel: yeni yıl hedefi kendi işin
    rf('<span class="tag" style="align-self:flex-start">2027 hedefin</span><h1 style="font-size:120px">Kendi işini<br>kurmak<br><span class="ind">mı?</span></h1>'),
    rf('<h1 style="font-size:104px">Tasarımcın yok.<br>Ajans bütçen yok.<br><span class="ind">Sorun değil.</span></h1>'),
    rf('<span class="tag" style="align-self:flex-start">İlk gönderin</span>' + ui('“Ev yapımı reçellerimi satmaya başlıyorum, ilk duyuru gönderisi”', 'Görsel ve metin hazır')),
    rf('<span class="tag" style="align-self:flex-start">İlk Reels\'in</span>' + ui('“Bunu kısa bir Reels videosu yap”', 'Reels hazır')),
    rf('<h1 style="font-size:116px">Teknik bilgi<br>gerekmez.<br><span class="ind">Türkçe yaz.</span></h1>'),
    rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">İlk adımı<br><span class="ind">bugün at.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr · ücretsiz başla</span>'),
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
            over = pg.evaluate('''()=>{const p=document.querySelector('.pad');return p.scrollHeight>p.clientHeight||p.scrollWidth>p.clientWidth}''')
            if over:
                print('TAŞMA:', name)
            pg.screenshot(path=(f'frames/{name}.png' if story else f'{name}.png'))
            pg.close()
            f.unlink()
        b.close()
    print(len(S), 'kare')
