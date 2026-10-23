import pathlib
from playwright.sync_api import sync_playwright
HEAD='<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>{css}</style></head><body class="{cls}"><div class="glow"></div><div class="grid"></div>{body}</body></html>'
FOOT='<div class="foot"><img class="logo" src="logo-on-dark.png" style="height:36px"><span><b>ajansai.tr</b></span></div>'
S={}
# P1 tanıtım
S['p1_tanitim']=('',  '''<div class="pad" style="justify-content:center;gap:60px">
<img class="logo" src="logo-on-dark.png" style="height:58px;align-self:flex-start">
<h1 style="font-size:132px"><span class="ind">5 dakikada</span><br>reklamın<br>yayında.</h1>
<div style="display:flex;flex-direction:column;gap:18px">
<div class="bubble" style="border-radius:24px;display:flex;gap:24px;align-items:center"><span class="tag">1</span>Fikrini üret</div>
<div class="bubble" style="border-radius:24px;display:flex;gap:24px;align-items:center"><span class="tag">2</span>Görselini ya da videonu üret</div>
<div class="bubble" style="border-radius:24px;display:flex;gap:24px;align-items:center;background:var(--indigo);border-color:var(--indigo)"><span class="tag" style="background:#fff;color:var(--indigo)">3</span>Tek tıkla reklamını ver<span style="margin-left:auto;font-size:22px;font-weight:700;background:rgba(255,255,255,.2);padding:8px 16px;border-radius:999px">Çok yakında</span></div>
</div></div><div class="foot" style="justify-content:flex-end"><span><b>ajansai.tr</b> · ücretsiz dene</span></div>''')
# P2 carousel tek cümle
S['p2_1']=('', '''<div class="pad" style="gap:48px;justify-content:center">
<span class="tag" style="align-self:flex-start">ajansAI'a yazdığımız tek cümle</span>
<div class="bubble" style="font-size:52px;align-self:flex-end;max-width:900px">“Mobilya mağazası için kampanya görseli: Tüm ürünlerde %40 indirim, ücretsiz teslimat ve montaj”</div>
<h1 style="font-size:96px">Ajans yok.<br>Tasarımcı yok.<br><span class="ind">Sonuç →</span></h1></div>'''+FOOT)
S['p2_2']=('.img{position:absolute;inset:0;background:url(src/qa_mobilya.png) center/cover}', '<div class="img"></div>')
S['p2_3']=('', '''<div class="pad" style="justify-content:center;gap:46px">
<h1 style="font-size:104px">Sıra senin<br><span class="ind">işletmende.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Ürün fotoğrafını yükle, kampanyanı Türkçe yaz. Fiyatlar, indirim ve yazılar birebir doğru çıkar.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>'''+FOOT)
# P4 sektör carousel
S['p4_1']=('', '''<div class="pad" style="justify-content:center;gap:50px">
<span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:118px">Her sektöre<br>tek cümleyle<br><span class="ind">kampanya.</span></h1>
<p style="font-size:40px" class="mut">Mobilya · Beyaz eşya · Kafe · Güzellik merkezi<br>Hepsi ajansAI'da, Türkçe tek cümleyle üretildi.</p></div>'''+FOOT)
for i,(n,f,prompt) in enumerate([('mobilya','qa_mobilya.png','Tüm ürünlerde %40 indirim, ücretsiz teslimat ve montaj'),('beyaz','qa_beyaz.png','Çamaşır + kurutma makinesi ikili alımda 10.000 TL indirim, peşin fiyatına 9 taksit'),('kafe','qa_kafe.png','Yeni sezon kabak baharatlı latte, 120 TL'),('guzellik','qa_guzellik.png','Lazer epilasyonda 6 seans alana 2 seans hediye')],start=2):
    S[f'p4_{i}']=('.wrap{position:absolute;left:0;right:0;top:0;height:1110px;background:#111 url(src/'+f+') center/contain no-repeat}.cap{position:absolute;left:0;right:0;bottom:0;height:240px;padding:34px 60px;display:flex;flex-direction:column;gap:12px;background:var(--ink)}',
     f'<div class="wrap"></div><div class="cap"><span class="mut" style="font-size:24px;font-weight:700">YAZILAN</span><div style="font-size:36px;font-weight:500;line-height:1.3">“{prompt}”</div></div>')
# P5 fiyat
S['p5_fiyat']=('.row{display:flex;justify-content:space-between;align-items:center;background:#15152A;border:1px solid #2E2E4C;border-radius:26px;padding:34px 40px}.row.on{background:var(--indigo);border-color:var(--indigo)}.n{font-family:SG;font-weight:700;font-size:48px}.p{font-family:SG;font-weight:700;font-size:56px;text-align:right}.d{font-size:27px;color:var(--mut);margin-top:6px}.on .d{color:#E3E3FF}.k{font-size:24px;color:var(--mut);text-align:right}.on .k{color:#E3E3FF}',
'''<div class="pad" style="gap:34px">
<img class="logo" src="logo-on-dark.png" style="align-self:flex-start">
<h1 style="font-size:84px;margin-top:10px">Ajans faturası yerine<br><span class="ind">aylık $10'dan</span> başlayan paketler</h1>
<div class="row"><div><div class="n">Başlangıç</div><div class="d">200 kredi · ~40 görsel ya da 5 video</div></div><div><div class="p">$10</div><div class="k">+ KDV / ay</div></div></div>
<div class="row on"><div><div class="n">Pro</div><div class="d">500 kredi · ~100 görsel ya da 13 video</div></div><div><div class="p">$20</div><div class="k">+ KDV / ay</div></div></div>
<div class="row"><div><div class="n">Advanced</div><div class="d">1.000 kredi · ~200 görsel ya da 27 video</div></div><div><div class="p">$35</div><div class="k">+ KDV / ay</div></div></div>
<p class="mut" style="font-size:28px">Video: 1080p, 6 saniye. Ödeme TL olarak iyzico ile. Ücretsiz paketle dene, beğenirsen geç.</p>
</div>'''+FOOT)
# P7 nasıl çalışır
S['p7_1']=('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Nasıl çalışır?</span>
<h1 style="font-size:120px">3 adım.<br><span class="ind">5 dakika.</span></h1><p class="mut" style="font-size:40px">Teknik bilgi gerekmez. Türkçe yazman yeterli.</p></div>'''+FOOT)
steps=[('1','Fikrini üret','Sohbete işletmeni anlat: “Bu hafta ne paylaşayım?” ajansAI gönderi fikirlerini ve metinlerini hazırlasın.',''),
       ('2','Görselini ya da videonu üret','Ürün fotoğrafını yükle, kampanyanı yaz. Ürünün bozulmadan, fiyatların doğru yazıldığı görsel ve Reels videosu hazır.',''),
       ('3','Tek tıkla reklamını ver','Bütçeni ve bölgeni seç, reklamın Instagram\'da yayına girsin.','Çok yakında')]
for i,(n,t,d,soon) in enumerate(steps,start=2):
    S[f'p7_{i}']=('', f'''<div class="pad" style="justify-content:center;gap:44px"><div style="font-family:SG;font-weight:700;font-size:220px;color:var(--indigo);line-height:.9">{n}</div>
<h1 style="font-size:92px">{t}</h1><p style="font-size:40px;line-height:1.45" class="mut">{d}</p>{f'<span class="tag" style="align-self:flex-start">{soon}</span>' if soon else ''}</div>'''+FOOT)
S['p7_5']=S['p2_3']
# Reels intro/outro cards (1080x1920)
def card(top, bubble, bottom):
    return ('', f'''<div class="pad" style="justify-content:center;gap:70px;padding:200px 84px"><span class="tag" style="align-self:flex-start;font-size:30px">{top}</span>
<div class="bubble" style="font-size:58px;align-self:flex-end">“{bubble}”</div><h1 style="font-size:110px">{bottom}</h1></div>''')
S['r1_intro']=card("ajansAI'a yazdık","Bu kampanya görselinden Instagram reklam videosu yap","Ve video<br><span class='ind'>hazır ↓</span>")
S['r2_intro']=card("Tatlının fotoğrafını yükledik","Bir kadın bu tatlıdan bir çatal alıp keyifle yesin","Çekim yok.<br><span class='ind'>Sonuç ↓</span>")
S['r_outro']=('', '''<div class="pad" style="justify-content:center;gap:60px;padding:200px 84px"><img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start">
<h1 style="font-size:130px"><span class="ind">5 dakikada</span><br>reklamın<br>yayında.</h1><span class="cta" style="align-self:flex-start;font-size:54px">ajansai.tr · ücretsiz dene</span></div>''')
with sync_playwright() as p:
    b=p.chromium.launch()
    for name,(css,body) in S.items():
        story=name.startswith('r')
        pg=b.new_page(viewport={'width':1080,'height':1920 if story else 1350})
        f=pathlib.Path(f'_{name}.html'); f.write_text(HEAD.format(css=css,cls='story' if story else '',body=body))
        pg.goto('file://'+str(f.resolve())); pg.wait_for_timeout(500)
        pg.screenshot(path=f'out/{name}.png'); pg.close()
    b.close()
print(len(S))
