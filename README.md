# Binance Futures Trading Bot

Binance Futures için 4 saatlik Donchian breakout trend takip botu.

> Durum: Araştırma ve test aşamasında. Backtest altyapısı ilerledi, ancak canlı para ile kullanılmaya hazır değil. En güncel karar için `docs/MULTI_SYMBOL.md` ve `docs/WALK_FORWARD.md` dosyalarından başlayın.

## Hızlı Bakış

| Başlık | Değer |
|---|---|
| Sermaye varsayımı | 1000 USDT |
| Ana timeframe | 4 saat |
| Yüksek timeframe filtresi | 1D EMA50 |
| Kaldıraç | 3x |
| İşlem başı risk | %2 |
| Ana sinyal | Donchian breakout |
| Filtreler | Hacim, ADX, RSI, 1D trend |
| Çıkış | ATR initial SL, trailing SL, Donchian exit |

## Strateji

Giriş mantığı:

1. 4H kapanış fiyatı önceki Donchian kanalını kırar.
2. Hacim, 20 bar ortalamasının belirlenen katının üstündedir.
3. ADX trend gücü eşiğinin üstündedir.
4. RSI aşırı alım/satım bölgesinde değildir.
5. 1D trend filtresi aynı yönü onaylar.

Çıkış mantığı:

- İlk stop-loss: ATR tabanlı.
- Trailing stop: kazancın bir bölümünü kilitler.
- Erken çıkış: ters yönde daha kısa Donchian kanal kırılımı.

## Güncel Bulgular

- Tek BTC backtest sonucu zayıf ve walk-forward tarafında negatif.
- Çoklu sembol testinde ETH, SOL ve BNB sonuçları BTC'den daha iyi görünüyor.
- 4 sembol walk-forward özeti: 3/4 sembolde test ortalaması pozitif, fakat train-test farkı hâlâ yüksek.
- Sonuç: Strateji umut verici olabilir, ama overfitting riski devam ediyor. Testnet/paper aşamasına geçmeden önce ek sağlamlık testleri gerekli.

## Dosyalar

```text
config.py                    Parametreler
data.py                      Canlı veri ve borsa sorguları
indicators.py                ATR, RSI, ADX, Donchian, günlük trend
strategy.py                  Sinyal ve çıkış kuralları
risk.py                      Pozisyon boyutu ve SL/TP hesabı
order_manager.py             Emir açma, SL güncelleme, pozisyon kapama
bot.py                       Tek sembollü testnet/canlı bot döngüsü
backtest.py                  Tek sembol backtest
optimize.py                  Parametre tarama
walk_forward.py              Tek sembol walk-forward
multi_symbol_backtest.py     Çoklu sembol düz backtest
multi_symbol_walk_forward.py Çoklu sembol walk-forward
monte_carlo.py               Trade-shuffle drawdown testi
docs/                        İnceleme ve sonuç raporları
```

## Kurulum

```bash
pip install -r requirements.txt
copy .env.example .env
python backtest.py
python walk_forward.py
python multi_symbol_backtest.py
python multi_symbol_walk_forward.py
python monte_carlo.py --trades backtest_results.csv
```

Canlı/testnet bot için API anahtarlarını `.env` veya ortam değişkenlerine girin. `config.TESTNET = True` kalmadan gerçek para moduna geçmeyin.

## Güvenlik Notu

Bu repo yatırım tavsiyesi değildir. Vadeli işlemler kaldıraç, likidasyon, funding, slippage ve API/bağlantı riski taşır. Canlıya geçmeden önce testnet, paper trading, alarm/monitoring ve küçük sermaye aşaması zorunlu kabul edilmelidir.
