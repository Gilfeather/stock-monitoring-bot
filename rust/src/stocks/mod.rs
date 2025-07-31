use anyhow::{Result, anyhow};
use chrono::Utc;
use reqwest::Client;
use serde_json::Value;
use crate::models::StockPrice;

pub struct StockClient {
    client: Client,
}

impl StockClient {
    pub fn new() -> Self {
        Self {
            client: Client::builder()
                .user_agent("Mozilla/5.0 (compatible; StockBot/1.0)")
                .build()
                .unwrap(),
        }
    }

    pub async fn validate_symbol(&self, symbol: &str) -> Result<bool> {
        // Yahoo Finance Quote APIで銘柄の存在確認
        let url = format!(
            "https://query1.finance.yahoo.com/v8/finance/chart/{}",
            symbol
        );

        let response = self.client
            .get(&url)
            .send()
            .await?;

        if !response.status().is_success() {
            return Ok(false);
        }

        let data: Value = response.json().await?;
        
        // エラーがある場合は無効な銘柄
        if let Some(error) = data.get("chart").and_then(|c| c.get("error")) {
            if !error.is_null() {
                return Ok(false);
            }
        }

        // 結果が空の場合も無効
        if let Some(result) = data.get("chart").and_then(|c| c.get("result")) {
            if result.as_array().map_or(true, |arr| arr.is_empty()) {
                return Ok(false);
            }
        } else {
            return Ok(false);
        }

        Ok(true)
    }

    pub async fn get_current_price(&self, symbol: &str) -> Result<StockPrice> {
        // Yahoo Finance Chart APIを使用
        let url = format!(
            "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=2d",
            symbol
        );

        let response = self.client
            .get(&url)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow!("Failed to fetch stock data: HTTP {}", response.status()));
        }

        let data: Value = response.json().await?;
        
        // エラーチェック
        if let Some(error) = data.get("chart").and_then(|c| c.get("error")) {
            if !error.is_null() {
                return Err(anyhow!("Yahoo Finance API error: {:?}", error));
            }
        }

        let result = data.get("chart")
            .and_then(|c| c.get("result"))
            .and_then(|r| r.as_array())
            .and_then(|arr| arr.first())
            .ok_or_else(|| anyhow!("No data found for symbol: {}", symbol))?;

        // メタデータから情報取得
        let meta = result.get("meta").ok_or_else(|| anyhow!("Missing metadata"))?;
        
        let current_price = meta.get("regularMarketPrice")
            .and_then(|p| p.as_f64())
            .ok_or_else(|| anyhow!("Missing current price"))?;

        let previous_close = meta.get("previousClose").and_then(|p| p.as_f64());
        
        // 価格履歴から追加情報を取得
        let indicators = result.get("indicators").and_then(|i| i.get("quote")).and_then(|q| q.as_array()).and_then(|arr| arr.first());
        
        let (open_price, high_price, low_price, volume) = if let Some(quote) = indicators {
            let opens = quote.get("open").and_then(|o| o.as_array());
            let highs = quote.get("high").and_then(|h| h.as_array());
            let lows = quote.get("low").and_then(|l| l.as_array());
            let volumes = quote.get("volume").and_then(|v| v.as_array());

            let open = opens.and_then(|arr| arr.last()).and_then(|v| v.as_f64());
            let high = highs.and_then(|arr| arr.iter().filter_map(|v| v.as_f64()).fold(None, |acc, x| Some(acc.map_or(x, |a| a.max(x)))));
            let low = lows.and_then(|arr| arr.iter().filter_map(|v| v.as_f64()).fold(None, |acc, x| Some(acc.map_or(x, |a| a.min(x)))));
            let vol = volumes.and_then(|arr| arr.last()).and_then(|v| v.as_u64());

            (open, high, low, vol)
        } else {
            (None, None, None, None)
        };

        // 変動額と変動率を計算
        let (change, change_percent) = if let Some(prev_close) = previous_close {
            let change_val = current_price - prev_close;
            let change_pct = (change_val / prev_close) * 100.0;
            (Some(change_val), Some(change_pct))
        } else {
            (None, None)
        };

        Ok(StockPrice {
            symbol: symbol.to_string(),
            timestamp: Utc::now(),
            price: current_price,
            open_price,
            high_price,
            low_price,
            volume,
            previous_close,
            change,
            change_percent,
        })
    }

    pub async fn get_historical_prices(&self, symbol: &str, period: &str) -> Result<Vec<StockPrice>> {
        let url = format!(
            "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range={}",
            symbol, period
        );

        let response = self.client
            .get(&url)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow!("Failed to fetch historical data: HTTP {}", response.status()));
        }

        let data: Value = response.json().await?;
        
        let result = data.get("chart")
            .and_then(|c| c.get("result"))
            .and_then(|r| r.as_array())
            .and_then(|arr| arr.first())
            .ok_or_else(|| anyhow!("No historical data found for symbol: {}", symbol))?;

        let timestamps = result.get("timestamp")
            .and_then(|t| t.as_array())
            .ok_or_else(|| anyhow!("Missing timestamps"))?;

        let quote = result.get("indicators")
            .and_then(|i| i.get("quote"))
            .and_then(|q| q.as_array())
            .and_then(|arr| arr.first())
            .ok_or_else(|| anyhow!("Missing quote data"))?;

        let opens = quote.get("open").and_then(|o| o.as_array()).unwrap_or(&vec![]);
        let highs = quote.get("high").and_then(|h| h.as_array()).unwrap_or(&vec![]);
        let lows = quote.get("low").and_then(|l| l.as_array()).unwrap_or(&vec![]);
        let closes = quote.get("close").and_then(|c| c.as_array()).unwrap_or(&vec![]);
        let volumes = quote.get("volume").and_then(|v| v.as_array()).unwrap_or(&vec![]);

        let mut prices = Vec::new();
        let mut previous_close: Option<f64> = None;

        for (i, timestamp) in timestamps.iter().enumerate() {
            if let Some(ts) = timestamp.as_i64() {
                let datetime = chrono::DateTime::from_timestamp(ts, 0)
                    .unwrap_or_else(|| Utc::now())
                    .with_timezone(&Utc);

                let close_price = closes.get(i).and_then(|v| v.as_f64());
                
                if let Some(price) = close_price {
                    let (change, change_percent) = if let Some(prev_close) = previous_close {
                        let change_val = price - prev_close;
                        let change_pct = (change_val / prev_close) * 100.0;
                        (Some(change_val), Some(change_pct))
                    } else {
                        (None, None)
                    };

                    prices.push(StockPrice {
                        symbol: symbol.to_string(),
                        timestamp: datetime,
                        price,
                        open_price: opens.get(i).and_then(|v| v.as_f64()),
                        high_price: highs.get(i).and_then(|v| v.as_f64()),
                        low_price: lows.get(i).and_then(|v| v.as_f64()),
                        volume: volumes.get(i).and_then(|v| v.as_u64()),
                        previous_close,
                        change,
                        change_percent,
                    });

                    previous_close = Some(price);
                }
            }
        }

        Ok(prices)
    }
}