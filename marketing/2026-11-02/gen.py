# ajansAI haftalık plan görselleri — 2026-11-02 haftası (2–8 Kasım)
# Kurulum (bu klasörde): npm i @fontsource/space-grotesk @fontsource/inter ; cp ../../web/public/logo-on-dark.png .
# Çalıştır: python3 gen.py  → PNG'ler bu klasöre, Reels kareleri frames/ altına; ardından reels.sh
import pathlib
from playwright.sync_api import sync_playwright
HEAD='<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>.vs{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.col{{background:#15152A;border:1px solid #2E2E4C;border-radius:26px;padding:30px;display:flex;flex-direction:column;gap:14px}}.col.on{{background:var(--indigo);border-color:var(--indigo)}}.col p{{font-size:30px;line-height:1.3}}.lab{{font-size:24px;font-weight:700;color:var(--mut);letter-spacing:.04em}}.on .lab{{color:#DCDCFF}}.qa{{background:#15152A;border:1px solid #2E2E4C;border-radius:26px;padding:28px 34px;display:flex;flex-direction:column;gap:10px}}.qa b{{font-family:SG;font-size:38px;font-weight:700}}.qa span{{font-size:29px;color:var(--mut);line-height:1.35}}.qa span em{{font-style:normal;color:var(--soft);font-weight:700}}.day{{display:flex;justify-content:space-between;align-items:center;background:#15152A;border:1px solid #2E2E4C;border-radius:20px;padding:18px 28px;font-size:30px}}.day b{{font-family:SG;font-size:32px;width:190px}}.day span{{flex:1;color:var(--mut)}}.day i{{font-style:normal;color:var(--soft);font-weight:700;font-size:26px}}.client{{font-size:28px;font-weight:700;color:var(--mut);letter-spacing:.04em}}.strike{{text-decoration:line-through;text-decoration-color:var(--indigo);text-decoration-thickness:6px;color:#6E6E86}}{css}</style></head><body class="{cls}"><div class="glow"></div><div class="grid"></div>{body}</body></html>'
FOOT='<div class="foot"><img class="logo" src="logo-on-dark.png" style="height:36px"><span><b>ajansai.tr</b></span></div>'
def ui(prompt, done, size=38):
    return f'<div class="bubble" style="align-self:flex-end;max-width:880px;font-size:{size}px">{prompt}</div><div style="display:flex;gap:16px;align-items:center;font-size:32px;color:var(--soft);font-weight:700"><span style="width:46px;height:46px;border-radius:50%;background:var(--indigo);color:#fff;display:grid;place-items:center">✓</span>{done}</div>'
S={}
# 1 Pzt 2 Kasım — Kasım indirim dönemi (hedef 1: işletmeler)
S['g1']=('', '''<div class="pad" style="justify-content:center;gap:54px"><span class="tag" style="align-self:flex-start">Kasım indirimleri kapıda</span>
<h1 style="font-size:104px">Kampanya görselin<br>için ajans takvimini<br><span class="ind">bekleme.</span></h1>
'''+ui('“11.11 için tüm ürünlerde %25 indirim görseli hazırla”','Görsel hazır')+'''
<p style="font-size:38px;line-height:1.4" class="mut">İndirimini Türkçe yaz, görselin ve videon dakikalar içinde hazır. Reklamını da tek tıkla kendin ver.</p></div>'''+FOOT)
# 2 Sal 3 Kasım — Revize derdi carousel (hedef 1)
S['g2_1']=('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Kaydır →</span>
<h1 style="font-size:116px">“Bir revize<br>daha rica<br>edeceğim…”</h1><p class="mut" style="font-size:42px;line-height:1.35">Her değişiklik için yeniden yazışmaya son.<br>ajansAI'da revize <b style="color:var(--fg)">tek cümle.</b></p></div>'''+FOOT)
rv=[('Renk mi değişecek?','“Arka planı lacivert yap”','Görsel güncellendi'),
    ('Fiyat mı değişti?','“Fiyatı 499 TL olarak düzelt”','Görsel güncellendi'),
    ('Metin uzun mu geldi?','“Açıklamayı kısalt, daha samimi olsun”','Metin güncellendi'),
    ('Video da mı lazım?','“Bu görselden Reels videosu yap”','Video hazır')]
for i,(q,p,d) in enumerate(rv,start=2):
    S[f'g2_{i}']=('', f'''<div class="pad" style="justify-content:center;gap:48px"><span class="mut" style="font-size:30px;font-weight:700">{i-1}/4</span><h1 style="font-size:96px">{q}</h1>{ui(p,d)}
<p class="mut" style="font-size:32px">Toplantı yok, e-posta zinciri yok. Yaz, bitsin.</p></div>'''+FOOT)
S['g2_6']=('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:100px">Revizeyi<br><span class="ind">sen yönet.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">İstediğin kadar dene, beğendiğinde paylaş. Kontrol sende, ajans masrafı yok.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>'''+FOOT)
# 4 Per 5 Kasım — Freelancer: her müşteriye ayrı kampanya (hedef 2)
S['g4_1']=('', '''<div class="pad" style="justify-content:center;gap:50px"><span class="tag" style="align-self:flex-start">Freelance sosyal medya yöneticilerine</span>
<h1 style="font-size:104px">Kasım yoğunluğu:<br>her müşteriye<br><span class="ind">ayrı kampanya.</span></h1><p class="mut" style="font-size:42px">Aynı gün, hepsi hazır. →</p></div>'''+FOOT)
cl=[('MÜŞTERİ 1 · KAFE','“Kasım boyunca 2. kahve yarı fiyatına görseli”','Görsel hazır'),
    ('MÜŞTERİ 2 · BUTİK','“Kış koleksiyonunda %30 indirim Reels videosu”','Video hazır'),
    ('MÜŞTERİ 3 · KUAFÖR','“Günlük 200 TL, Kadıköy, Instagram reklamı”','Reklam yayında')]
for i,(c,p,d) in enumerate(cl,start=2):
    S[f'g4_{i}']=('', f'''<div class="pad" style="justify-content:center;gap:46px"><span class="client">{c}</span><h1 style="font-size:84px">Yaz, onayla,<br>sıradakine geç.</h1>{ui(p,d)}</div>'''+FOOT)
S['g4_5']=('', '''<div class="pad" style="justify-content:center;gap:46px"><h1 style="font-size:100px">Aynı mesaiyle<br><span class="ind">daha çok müşteri.</span></h1>
<p style="font-size:40px;line-height:1.4" class="mut">Fikir, görsel, Reels ve Instagram reklamı tek yerde. Türkçe yaz, dakikalar içinde hazır.</p>
<span class="cta" style="align-self:flex-start">Ücretsiz dene → ajansai.tr</span></div>'''+FOOT)
# 5 Cum 6 Kasım — Sık sorulan sorular (hedef 1)
S['g5']=('', '''<div class="pad" style="gap:24px"><img class="logo" src="logo-on-dark.png" style="align-self:flex-start">
<h1 style="font-size:88px;margin:14px 0 10px">En çok<br><span class="ind">sorulanlar</span></h1>
<div class="qa"><b>Teknik bilgi gerekir mi?</b><span><em>Hayır.</em> Türkçe yazman yeterli; tasarım programı yok.</span></div>
<div class="qa"><b>Ücretsiz deneyebilir miyim?</b><span><em>Evet.</em> Ücretsiz paketle başla, beğenirsen geç.</span></div>
<div class="qa"><b>Bir görsel kaç kredi?</b><span><em>5 kredi.</em> 1080p, 6 saniyelik video 36 kredi.</span></div>
<div class="qa"><b>Ödeme nasıl?</b><span><em>TL ile, iyzico üzerinden.</em> Paketler aylık $10'dan başlar (+KDV).</span></div></div>'''+FOOT)
# 7 Paz 8 Kasım — Haftanın içeriği bir oturumda (hedef 1)
days=[('Pazartesi','Yeni ürün gönderisi'),('Salı','İndirim görseli'),('Çarşamba','Reels videosu'),('Perşembe','Müşteri sorusu'),
      ('Cuma','Hafta sonu kampanyası'),('Cumartesi','Instagram reklamı'),('Pazar','Haftaya teaser')]
S['g7']=('', '''<div class="pad" style="gap:18px"><span class="tag" style="align-self:flex-start">Pazar planı</span>
<h1 style="font-size:84px;margin:16px 0 20px">Haftanın içeriği<br><span class="ind">tek oturumda.</span></h1>'''+
''.join(f'<div class="day"><b>{d}</b><span>{t}</span><i>✓ Hazır</i></div>' for d,t in days)+
'''<p class="mut" style="font-size:30px;margin-top:12px">Bu akşam yaz, hafta boyu rahat et.</p></div>'''+FOOT)
# Reels kareleri (1080x1920)
def rf(inner): return ('', f'<div class="pad" style="justify-content:center;gap:64px;padding:220px 84px">{inner}</div>')
R1=[ # Çar: reklam bütçeni kendin yönet (hedef 1)
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">İşletme sahibiysen</span><h1 style="font-size:120px">Reklam<br>bütçeni kim<br><span class="ind">yönetiyor?</span></h1>'),
 rf('<h1 style="font-size:116px">Bütçe de,<br>karar da<br><span class="ind">senin olsun.</span></h1>'),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">1 · Görselini seç</span>'+ui('“Kasım indirimi görselimle reklam ver”','Görsel seçildi',42)),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">2 · Bütçeni ve bölgeni yaz</span>'+ui('“Günlük 250 TL, İzmir, 25-45 yaş”','Hedefleme hazır',42)),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">3 · Tek tık</span><h1 style="font-size:120px">Reklamın<br><span class="ind">yayında.</span></h1>'),
 rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Reklamını<br><span class="ind">kendin ver.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr · ücretsiz dene</span>'),
]
R2=[ # Cmt: hafta sonu içerik derdi (hedef 3: bireysel)
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">Cumartesi akşamı</span><h1 style="font-size:120px">Paylaşacak<br>bir şey<br><span class="ind">yok mu?</span></h1>'),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">Kitap hesabın için</span>'+ui('“Bu hafta okuduğum kitap için öneri gönderisi hazırla”','Görsel ve metin hazır',42)),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">Bir kutlama için</span>'+ui('“Annemin doğum günü için kutlama görseli”','Görsel hazır',42)),
 rf('<span class="tag" style="align-self:flex-start;font-size:30px">İstersen videoya çevir</span>'+ui('“Bunu Reels videosu yap”','Reels hazır',42)),
 rf('<h1 style="font-size:120px">Hafta sonu<br>derdi yok.<br><span class="ind">Sadece yaz.</span></h1>'),
 rf('<img class="logo" src="logo-on-dark.png" style="height:70px;align-self:flex-start"><h1 style="font-size:110px">Ücretsiz<br><span class="ind">başla.</span></h1><span class="cta" style="align-self:flex-start;font-size:52px">ajansai.tr</span>'),
]
for k,frames in (('r1',R1),('r2',R2)):
    for i,f in enumerate(frames): S[f'{k}_{i}']=f
pathlib.Path('frames').mkdir(exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch()
    for name,(css,body) in S.items():
        story=name.startswith('r')
        pg=b.new_page(viewport={'width':1080,'height':1920 if story else 1350})
        f=pathlib.Path(f'_{name}.html'); f.write_text(HEAD.format(css=css,cls='story' if story else '',body=body))
        pg.goto('file://'+str(f.resolve())); pg.wait_for_timeout(400)
        # taşma kontrolü: içerik kutusu sayfadan taşıyorsa uyar
        over=pg.evaluate('()=>{const p=document.querySelector(".pad");return p.scrollHeight>p.clientHeight||p.scrollWidth>p.clientWidth}')
        if over: print('TAŞMA:',name)
        pg.screenshot(path=(f'frames/{name}.png' if story else f'{name}.png')); pg.close(); f.unlink()
    b.close()
print(len(S))
