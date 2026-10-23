import pathlib
from playwright.sync_api import sync_playwright
HEAD='<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>.chk{{display:flex;gap:22px;align-items:center;font-size:40px;font-weight:500}}.chk i{{font-style:normal;width:54px;height:54px;border-radius:50%;background:var(--indigo);display:grid;place-items:center;font-size:30px;flex:none}}.x i{{background:#2A2A3A;color:#8A8AA0}}.vs{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.col{{background:#15152A;border:1px solid #2E2E4C;border-radius:26px;padding:30px;display:flex;flex-direction:column;gap:14px}}.col.on{{background:var(--indigo);border-color:var(--indigo)}}.col h3{{font-family:SG;font-size:34px}}.col p{{font-size:30px;line-height:1.3}}.lab{{font-size:24px;font-weight:700;color:var(--mut);letter-spacing:.04em}}.on .lab{{color:#DCDCFF}}{css}</style></head><body class="{cls}"><div class="glow"></div><div class="grid"></div>{body}</body></html>'
FOOT='<div class="foot"><img class="logo" src="logo-on-dark.png" style="height:36px"><span><b>ajansai.tr</b></span></div>'
def ui(prompt, done):
    return f'<div class="bubble" style="align-self:flex-end;max-width:880px">{prompt}</div><div style="display:flex;gap:16px;align-items:center;font-size:32px;color:var(--soft);font-weight:700"><span style="width:46px;height:46px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center">✓</span>{done}</div>'
S={}
# 1 Pzt: ajans masrafı (hedef 1)
S['g1']=('', '''<div class="pad" style="justify-content:center;gap:56px"><img class="logo" src="logo-on-dark.png" style="height:56px;align-self:flex-start">
<h1 style="font-size:116px">Ajansa her ay<br>para ödemeyi<br><span class="ind">bırak.</span></h1>
<p style="font-size:44px;line-height:1.35">İşletmenin sosyal medyasını<br><b>kendin yönet.</b> Fikir, görsel, video<br>ve reklam tek yerde.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz başla → ajansai.tr</span></div>''')
# 2 Sal: Ajans vs ajansAI carousel
S['g2_1']=('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:124px">Ajans mı,<br><span class="ind">ajansAI mı?</span></h1><p class="mut" style="font-size:42px">4 soruda karşılaştırdık.</p></div>'''+FOOT)
rows=[('Ne kadar beklersin?','Brief, toplantı, onay… günler sürebilir.','Yaz, dakikalar içinde hazır.'),
      ('Ne kadar ödersin?','Her ay sabit ajans ücreti.','Aylık $10\'dan başlayan paketler.'),
      ('Değişiklik istersen?','Her revize için yeniden yazışma.','Tek cümleyle düzenle.'),
      ('Reklamı kim verir?','Ajans yönetir, sen raporu beklersin.','Tek tıkla kendin yayına alırsın.')]
for i,(q,a,b) in enumerate(rows,start=2):
    S[f'g2_{i}']=('', f'''<div class="pad" style="justify-content:center;gap:44px"><span class="mut" style="font-size:30px;font-weight:700">{i-1}/4</span><h1 style="font-size:88px">{q}</h1>
<div class="vs"><div class="col"><span class="lab">AJANS</span><p>{a}</p></div><div class="col on"><span class="lab">AJANSAI</span><p>{b}</p></div></div></div>'''+FOOT)
S['g2_6']=('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:104px">Kontrol sende,<br><span class="ind">masraf yok.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Ücretsiz paketle dene. Beğenirsen aylık $10'dan başlayan paketlerle devam et.</p>
<span class="cta" style="align-self:flex-start">ajansai.tr</span></div>'''+FOOT)
# 4 Per: freelancer carousel (hedef 2)
S['g4_1']=('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Freelance sosyal medya yöneticilerine</span>
<h1 style="font-size:112px">Daha çok müşteri,<br><span class="ind">daha az mesai.</span></h1><p class="mut" style="font-size:42px">Haftalık içerik işini dakikalara indir. →</p></div>'''+FOOT)
fl=[('Fikir','Her müşterin için haftalık gönderi ve Reels fikirleri, metinleri ve hashtag\'leriyle.','“Kafe müşterim için bu haftanın 5 gönderi fikri”'),
    ('Görsel','Ürün fotoğrafını yükle, kampanyayı yaz. Yazılar ve fiyatlar doğru, tasarım hazır.','“Hafta sonu tüm menüde %20 indirim görseli”'),
    ('Video','Görselden ya da tek cümleden 1080p Reels videosu.','“Bu ürün fotoğrafından Reels videosu yap”'),
    ('Reklam','Bütçeyi ve bölgeyi seç, Instagram reklamını tek tıkla yayına al.','“Günlük 300 TL, İstanbul, 25-45 yaş”')]
for i,(t,d,p) in enumerate(fl,start=2):
    S[f'g4_{i}']=('', f'''<div class="pad" style="justify-content:center;gap:40px"><span class="tag" style="align-self:flex-start">{t}</span><h1 style="font-size:84px">{d}</h1>{ui(p, t+" hazır")}</div>'''+FOOT)
# 5 Cum fiyat
S['g5']=('.row{display:flex;justify-content:space-between;align-items:center;background:#15152A;border:1px solid #2E2E4C;border-radius:26px;padding:34px 40px}.row.on{background:var(--indigo);border-color:var(--indigo)}.n{font-family:SG;font-weight:700;font-size:48px}.p{font-family:SG;font-weight:700;font-size:56px;text-align:right}.d{font-size:27px;color:var(--mut);margin-top:6px}.on .d{color:#E3E3FF}.k{font-size:24px;color:var(--mut);text-align:right}.on .k{color:#E3E3FF}',
'''<div class="pad" style="gap:34px"><img class="logo" src="logo-on-dark.png" style="align-self:flex-start">
<h1 style="font-size:84px;margin-top:10px">Ajans faturası yerine<br><span class="ind">aylık $10'dan</span> başlayan paketler</h1>
<div class="row"><div><div class="n">Başlangıç</div><div class="d">200 kredi · ~40 görsel ya da 5 video</div></div><div><div class="p">$10</div><div class="k">+ KDV / ay</div></div></div>
<div class="row on"><div><div class="n">Pro</div><div class="d">500 kredi · ~100 görsel ya da 13 video</div></div><div><div class="p">$20</div><div class="k">+ KDV / ay</div></div></div>
<div class="row"><div><div class="n">Advanced</div><div class="d">1.000 kredi · ~200 görsel ya da 27 video</div></div><div><div class="p">$35</div><div class="k">+ KDV / ay</div></div></div>
<p class="mut" style="font-size:28px">Video: 1080p, 6 saniye. Ödeme TL olarak iyzico ile. Ücretsiz paketle dene, beğenirsen geç.</p></div>'''+FOOT)
# 7 Paz nasıl çalışır
S['g7_1']=('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Nasıl çalışır?</span>
<h1 style="font-size:120px">3 adım.<br><span class="ind">5 dakika.</span></h1><p class="mut" style="font-size:40px">Teknik bilgi gerekmez. Türkçe yazman yeterli.</p></div>'''+FOOT)
st=[('1','Fikrini üret','Sohbete işletmeni anlat. Gönderi fikirleri, metinler ve hashtag\'ler hazır.','“Butiğim için bu haftanın gönderi fikirleri”','Fikirler hazır'),
    ('2','Görselini ya da videonu üret','Ürün fotoğrafını yükle, kampanyanı yaz. Görsel ve Reels hazır.','“Yeni sezon montlarda %30 indirim görseli”','Görsel hazır'),
    ('3','Tek tıkla reklamını ver','Bütçeni ve bölgeni seç, reklamın Instagram\'da yayında.','“Günlük 250 TL, Ankara”','Reklam yayında')]
for i,(n,t,d,p,dn) in enumerate(st,start=2):
    S[f'g7_{i}']=('', f'''<div class="pad" style="justify-content:center;gap:36px"><div style="font-family:SG;font-weight:700;font-size:180px;color:var(--indigo);line-height:.9">{n}</div>
<h1 style="font-size:84px">{t}</h1><p style="font-size:38px;line-height:1.4" class="mut">{d}</p>{ui(p,dn)}</div>'''+FOOT)
S['g7_5']=('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:112px"><span class="ind">5 dakikada</span><br>reklamın<br>yayında.</h1>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>'''+FOOT)
# Reels frames (1080x1920)
def rf(inner): return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')
R1=[ # hedef 1: işletme sahibi
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">İşletme sahibiysen</span><h1 style="font-size:120px">Sosyal medya<br>için ajans mı<br><span class="ind">arıyorsun?</span></h1>'),
 rf('<h1 style="font-size:110px">Önce şunu<br>bir dene. ↓</h1>'),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">1 · Fikir</span>'+ui('“Mobilya mağazam için bu haftanın gönderi fikirleri”','Fikirler hazır')),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">2 · Görsel & video</span>'+ui('“Tüm ürünlerde %40 indirim görseli ve Reels videosu”','Görsel ve video hazır')),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">3 · Reklam</span>'+ui('“Günlük 300 TL, İstanbul, Instagram”','Reklam yayında')),
 rf('<h1 style="font-size:120px">Ajans yok.<br>Bekleme yok.<br><span class="ind">5 dakika.</span></h1>'),
 rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Sosyal medyanı<br><span class="ind">kendin yönet.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr · ücretsiz dene</span>'),
]
R2=[ # hedef 3: bireysel
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">Tasarım bilmiyorum diyenlere</span><h1 style="font-size:120px">Paylaşacak<br>şey bulamıyor<br><span class="ind">musun?</span></h1>'),
 rf('<h1 style="font-size:104px">El yapımı ürünlerin,<br>küçük işin,<br>kendi hesabın…</h1>'),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">Türkçe yaz</span>'+ui('“El yapımı mumlarım için yılbaşı gönderisi hazırla”','Görsel ve metin hazır')),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">İstersen videoya çevir</span>'+ui('“Bunu Reels videosu yap”','Reels hazır')),
 rf('<h1 style="font-size:120px">Tasarım<br>programı yok.<br><span class="ind">Sadece yaz.</span></h1>'),
 rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Ücretsiz<br><span class="ind">başla.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
for k,frames in (('r1',R1),('r2',R2)):
    for i,f in enumerate(frames): S[f'{k}_{i}']=f
with sync_playwright() as p:
    b=p.chromium.launch()
    for name,(css,body) in S.items():
        story=name.startswith('r')
        pg=b.new_page(viewport={'width':1080,'height':1920 if story else 1350})
        f=pathlib.Path(f'_{name}.html'); f.write_text(HEAD.format(css=css,cls='story' if story else '',body=body))
        pg.goto('file://'+str(f.resolve())); pg.wait_for_timeout(400)
        pg.screenshot(path=f'out2/{name}.png'); pg.close()
    b.close()
print(len(S))
