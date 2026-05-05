# Araştırma & Mimari Taslak: Funding-Rate Carry (Delta-Neutral) Stratejisi

**Tarih:** 2026-05-05  
**Durum:** POC (Proof of Concept) Tasarım Aşamasında  
**AI Sahibi:** Gemini  

> Guvenlik notu: Bu dosya research-only mimari taslaktir. Paper/live davranisa
> baglanmaz; once veri toplama, backtest, walk-forward, maliyet stresi ve
> testnet/preflight kaniti gerekir.

## 1. Strateji Teorisi (Neden Delta-Neutral?)
Binance Futures üzerinde sürekli sözleşmelerde (Perpetual), fiyatı Spot piyasaya yakın tutmak için bir **Fonlama Oranı (Funding Rate)** ödenir. Çoğu zaman piyasa "Long" eğilimlidir ve Long açanlar, Short açanlara her 8 saatte bir ücret öder.

**Mantık:** 
Aynı varlık için (örneğin ETH) Binance Spot'tan 1 ETH **alır** ve Binance Futures'tan 1 ETH'lik **Short (Açığa Satış)** açarsak, fiyat değişimlerinden etkilenmeyiz (Delta-Neutral). Ancak Short pozisyonumuz olduğu için her 8 saatte bir fonlama oranı tahsil etmeyi hedefler. Bu strateji, kaldıraç kullanımıyla yüksek yıllık getiri potansiyeli sunar, ancak piyasa risklerinden (örn. ani fonlama oranı değişimleri, likidasyon riskleri) tamamen arınmış değildir.

## 2. API ve Altyapı Limitasyonları (Rate Limit Koruması)
Binance REST API üzerinden saniyede onlarca kez fiyat sorgulamak ban (429/418) sebebidir.

- **REST Kullanımı SADECE Şunlar İçin Olmalı:**
  - İşleme girme (Spot Buy / Futures Sell emirleri).
  - Likidasyon yastığı transferleri (`/sapi/v1/asset/transfer` ile Spot cüzdanından Futures cüzdanına teminat kaydırma).
- **WebSocket Kullanımı SÜREKLİ Olmalı:**
  - Fiyat takibi ve anlık spread farkları için `!markPrice@arr@1s` ve `!ticker@arr` stream'leri asenkron (asyncio) dinlenmelidir.

## 3. Mimari Bileşenler (Codex İçin Uygulama Planı)
Yeni sistem 3 ana Python modülünden oluşmalıdır:

### A. `funding_scanner.py` (Fırsat Avcısı)
Periyodik (örneğin saatte bir) çalışır. Binance `fapi/v1/premiumIndex` endpoint'ini kullanarak fonlama oranlarını çeker. 
- **Filtreler:** Sadece likiditesi yüksek (ilk 50), fonlama oranı son 7 gündür stabil pozitif olan koinleri seçer.

### B. `delta_neutral_executor.py` (Market Yapıcı)
Fırsat bulunduğunda atomik olarak işlem açar.
- Spot'ta Market/Limit Buy atar.
- Asenkron bir gecikme yaşamadan anında USDT-M Futures tarafında eşdeğer hacimde Market/Limit Sell (Short) açar.
- Slippage (kayma) kontrolü yapar.

### C. `margin_rebalancer.py` (Likidasyon Koruyucu - ÇOK KRİTİK)
Koin fiyatı %20 aniden fırlarsa, spot değerimiz artsa bile Futures'taki Short pozisyonumuz likidasyon riskiyle karşı karşıya kalır.
- Sürekli WebSocket dinler.
- Futures Margin Buffer'ı (Kaldıraç tamponu) %15'in altına düşerse, Spot'taki varlığın küçük bir kısmını satar, gelen USDT'yi Futures cüzdanına transfer ederek likidasyon fiyatını yukarı iter (Rebalancing).

## 4. Sonraki Adımlar
- [ ] Codex'in Binance Spot ve Futures hesapları arasında para transferini sağlayan Universal API Client metodlarını yazması (`binance-bot` içerisine).
- [ ] Hurst-MTF modelindeki başarısızlıklar sonrası doğrudan bu modülün `live_state.py` ile (async biçimde) test edilmesi.
