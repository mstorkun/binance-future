# Walk-Forward Analiz

Amaç: Parametrelerin geçmiş veriye fazla uyup uymadığını ölçmek.

Yöntem:

- Train: 3000 adet 4H bar, yaklaşık 16-18 ay.
- Test: 500 adet 4H bar, yaklaşık 3 ay.
- Roll: 500 adet 4H bar.
- Her dönemde parametreler sadece train üzerinde seçilir, sonra test döneminde denenir.

## Güncel BTC Sonucu

`walk_forward_results.csv` son çalıştırmada 7 test penceresi içeriyor.

| Dönem | Train PnL | Test PnL | Test WR | Test Trade | Test DD |
|---|---:|---:|---:|---:|---:|
| 1 | +167.45 | +20.09 | %61.5 | 13 | 37.35 |
| 2 | +192.30 | -7.11 | %50.0 | 6 | 49.11 |
| 3 | +241.57 | -69.37 | %33.3 | 9 | 78.39 |
| 4 | +237.77 | +20.79 | %66.7 | 6 | 6.95 |
| 5 | +223.36 | -71.76 | %18.2 | 11 | 69.09 |
| 6 | +59.05 | +16.48 | %75.0 | 4 | 23.35 |
| 7 | +116.88 | -1.71 | %50.0 | 4 | 3.81 |

## Özet

| Metrik | Değer |
|---|---:|
| Test dönemi | 7 |
| Pozitif test dönemi | 3/7 |
| Ortalama test PnL | -13.23 USDT |
| Toplam test PnL | -92.59 USDT |
| Ortalama train PnL | +176.91 USDT |
| Ortalama train-test farkı | +190.14 USDT |

## Yorum

BTC tek başına hâlâ güvenilir görünmüyor. Train dönemleri güçlü, test dönemleri zayıf. Bu tablo overfitting riskinin devam ettiğini gösteriyor.

Bu sonuç, stratejinin tamamen çöpe atılması gerektiği anlamına gelmez; ancak BTC üzerinde seçilen parametrelerin geleceğe taşınmadığını gösterir. Bu yüzden çoklu sembol testine bakmak daha doğru: `docs/MULTI_SYMBOL.md`.

## Sonuç

BTC/USDT tek sembol ile canlıya geçilmemeli.

Öncelik:

1. Çoklu sembol portföy testi.
2. Parametre stabilite haritası.
3. Monte Carlo trade-shuffle.
4. Testnet/paper trading.

## Yeniden Üretim

```bash
python walk_forward.py
```

Çıktı: `walk_forward_results.csv`
