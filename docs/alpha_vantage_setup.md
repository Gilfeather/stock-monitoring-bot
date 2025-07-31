# Alpha Vantage API セットアップガイド

## Alpha Vantageとは

Alpha Vantageは無料でリアルタイム株価データを提供するAPIサービスです。Yahoo Finance APIが利用できない場合のフォールバックとして使用されます。

## 特徴

- **リアルタイムデータ**: 株価、為替、暗号通貨の最新データを提供
- **無料プラン**: 1分間に5回、1日500回のAPI呼び出し制限
- **高い信頼性**: 金融機関でも使用される安定したサービス
- **グローバル対応**: 世界中の株式市場をカバー

## セットアップ手順

### 1. APIキーの取得

1. [Alpha Vantage公式サイト](https://www.alphavantage.co/support/#api-key)にアクセス
2. 無料アカウントを作成
3. APIキーを取得（即座に発行されます）

### 2. 環境変数の設定

`.env`ファイルにAPIキーを設定：

```bash
ALPHA_VANTAGE_API_KEY=your_actual_api_key_here
```

### 3. 設定の確認

`config/config.json`でフォールバック設定を確認：

```json
{
  "data_providers": {
    "primary": "yahoo_finance",
    "fallback": "alpha_vantage",
    "request_timeout_seconds": 30,
    "max_retries": 3
  }
}
```

## 使用方法

システムは自動的にYahoo Finance APIを最初に試行し、失敗した場合にAlpha Vantage APIにフォールバックします：

```python
from src.stock_monitoring_bot.services.data_provider import StockDataProvider

# Alpha Vantage APIキーを指定してプロバイダーを初期化
async with StockDataProvider(alpha_vantage_api_key="your_api_key") as provider:
    # 株価を取得（Yahoo Finance → Alpha Vantageの順で試行）
    stock_price = await provider.get_current_price("AAPL")
    print(f"価格: {stock_price.price}")
```

## API制限について

### 無料プランの制限

- **1分間**: 5回のAPI呼び出し
- **1日**: 500回のAPI呼び出し
- **同時接続**: 1接続

### 制限に達した場合

システムは以下のエラーメッセージを返します：

```
Alpha Vantage API呼び出し制限に達しました
```

この場合、Yahoo Finance APIのみが使用されます。

## 有料プランについて

より多くのAPI呼び出しが必要な場合は、Alpha Vantageの有料プランを検討してください：

- **Premium**: 月額$49.99（1分間に75回、1日7,500回）
- **Professional**: 月額$149.99（1分間に300回、1日30,000回）
- **Enterprise**: カスタム料金（無制限）

## トラブルシューティング

### よくあるエラー

1. **Invalid API call**: 無効なAPIキーまたは銘柄コード
2. **Rate limit exceeded**: API呼び出し制限に達した
3. **Network timeout**: ネットワーク接続の問題

### デバッグ方法

ログレベルをDEBUGに設定してAPI呼び出しの詳細を確認：

```python
import logging
logging.getLogger('src.stock_monitoring_bot.services.data_provider').setLevel(logging.DEBUG)
```

## 参考リンク

- [Alpha Vantage公式ドキュメント](https://www.alphavantage.co/documentation/)
- [API制限について](https://www.alphavantage.co/support/#support)
- [サポートされる銘柄コード](https://www.alphavantage.co/query?function=LISTING_STATUS&apikey=demo)