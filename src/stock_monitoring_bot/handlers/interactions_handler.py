"""
Discord Interactions API handler for slash commands
"""
import json
import logging
from typing import Dict, Any, Optional
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from .command_processor import CommandProcessor


class InteractionsHandler:
    """Discord Interactions API handler"""
    
    def __init__(self, public_key: str, admin_users: Optional[list] = None):
        self.public_key = public_key.strip()
        self.logger = logging.getLogger(__name__)
        
        # Discord公開鍵の長さを確認（64文字 = 32バイト）
        if len(self.public_key) != 64:
            self.logger.error(f"Discord公開鍵の長さが無効: {len(self.public_key)}, 期待値: 64")
            raise ValueError(f"Invalid public key length: {len(self.public_key)}")
        
        try:
            self.verify_key = VerifyKey(bytes.fromhex(self.public_key))
            self.logger.debug(f"Discord公開鍵を正常に初期化: {self.public_key[:16]}...")
        except ValueError as e:
            self.logger.error(f"Discord公開鍵の初期化エラー: {e}")
            raise ValueError(f"Invalid public key format: {e}")
            
        self.command_processor = CommandProcessor(admin_users)
    
    def verify_signature(self, signature: str, timestamp: str, body: str) -> bool:
        """Discord署名を検証"""
        try:
            # 署名の形式をログ出力してデバッグ
            self.logger.debug(f"署名検証開始 - signature長: {len(signature)}, timestamp: {timestamp}")
            
            # 署名が128文字（64バイト * 2）でない場合はエラー
            if len(signature) != 128:
                self.logger.error(f"署名長が無効: {len(signature)}, 期待値: 128")
                return False
            
            # 16進数文字列を検証
            try:
                signature_bytes = bytes.fromhex(signature)
            except ValueError as e:
                self.logger.error(f"署名の16進数変換エラー: {e}")
                return False
            
            # 署名検証実行 - PyNaClのverifyメソッドは引数の順序が重要
            message = f'{timestamp}{body}'.encode()
            self.logger.debug(f"検証メッセージ: {message[:50]}...")
            
            # PyNaCl.signing.VerifyKey.verify(message, signature) の順序
            self.verify_key.verify(message, signature_bytes)
            self.logger.debug("署名検証成功")
            return True
            
        except BadSignatureError as e:
            self.logger.error(f"署名検証失敗: {e}")
            return False
        except Exception as e:
            self.logger.error(f"署名検証で予期しないエラー: {e}")
            return False
    
    async def handle_interaction(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Discord Interactionを処理"""
        try:
            # 署名検証
            headers = event.get('headers', {})
            body = event.get('body', '')
            
            # ヘッダー名の大文字小文字を考慮して取得（API Gatewayでは小文字に変換される）
            signature = ''
            timestamp = ''
            
            for key, value in headers.items():
                key_lower = key.lower()
                if key_lower == 'x-signature-ed25519':
                    signature = value
                elif key_lower == 'x-signature-timestamp':
                    timestamp = value
            
            # 署名検証を実行
            if not self.verify_signature(signature, timestamp, body):
                return {
                    'statusCode': 401,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Invalid signature'})
                }
            
            # リクエストボディをパース
            interaction_data = json.loads(body)
            interaction_type = interaction_data.get('type')
            
            # PING応答
            if interaction_type == 1:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'type': 1})
                }
            
            # アプリケーションコマンド
            if interaction_type == 2:
                return await self._handle_application_command(interaction_data)
            
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Unknown interaction type'})
            }
            
        except Exception as e:
            self.logger.error(f"Interaction処理エラー: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Internal server error'})
            }
    
    async def _handle_application_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """アプリケーションコマンドを処理"""
        try:
            data = interaction.get('data', {})
            command_name = data.get('name', '')
            options = data.get('options', [])
            user = interaction.get('member', {}).get('user', {}) or interaction.get('user', {})
            user_id = user.get('id', '')
            
            # 軽量なコマンドは即座に処理（DynamoDBアクセスなし、3秒以内確実）
            if command_name in ['status', 'help']:
                response_content = await self._process_slash_command(
                    command_name, options, user_id
                )
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'type': 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                        'data': {
                            'content': response_content,
                            'flags': 64 if response_content.startswith('❌') else 0  # EPHEMERAL if error
                        }
                    })
                }
            
            # DynamoDBアクセスが必要なコマンドや重いコマンドは非同期処理
            else:
                # まず「処理中...」を返す
                import boto3
                lambda_client = boto3.client('lambda')
                
                # 非同期でコマンド処理を実行
                payload = {
                    'command_name': command_name,
                    'options': options,
                    'user_id': user_id,
                    'interaction_token': interaction.get('token', ''),
                    'application_id': interaction.get('application_id', '')
                }
                
                try:
                    # 現在のLambda関数名を取得
                    import os
                    function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'stock-monitoring-bot-dev')
                    
                    lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType='Event',  # 非同期
                        Payload=json.dumps({
                            'source': 'discord.async_command',
                            'detail': payload
                        })
                    )
                except Exception as e:
                    self.logger.error(f"非同期Lambda呼び出しエラー: {e}")
                
                # 即座に「処理中...」レスポンス
                processing_messages = {
                    'list': '📋 監視リストを取得中...',
                    'add': '🔄 銘柄を追加中...',
                    'remove': '🔄 銘柄を削除中...',
                    'price': '📈 株価を取得中...',
                    'alert': '🔔 アラートを設定中...',
                    'chart': '📊 チャートを生成中...'
                }
                
                processing_msg = processing_messages.get(command_name, '🔄 処理中...')
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'type': 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                        'data': {
                            'content': processing_msg,
                            'flags': 0  # 公開メッセージ
                        }
                    })
                }
            
        except Exception as e:
            self.logger.error(f"アプリケーションコマンド処理エラー: {e}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'type': 4,
                    'data': {
                        'content': '❌ コマンドの処理中にエラーが発生しました',
                        'flags': 64  # EPHEMERAL
                    }
                })
            }
    
    async def _process_slash_command(self, command_name: str, options: list, user_id: str) -> str:
        """スラッシュコマンドを処理"""
        try:
            if command_name == 'status':
                return await self._handle_status_command()
            
            elif command_name == 'add':
                symbol = self._get_option_value(options, 'symbol')
                if not symbol:
                    return '❌ 銘柄コードを指定してください'
                return await self._handle_add_command(symbol, user_id)
            
            elif command_name == 'remove':
                symbol = self._get_option_value(options, 'symbol')
                if not symbol:
                    return '❌ 銘柄コードを指定してください'
                return await self._handle_remove_command(symbol, user_id)
            
            elif command_name == 'list':
                return await self._handle_list_command()
            
            elif command_name == 'price':
                symbol = self._get_option_value(options, 'symbol')
                if not symbol:
                    return '❌ 銘柄コードを指定してください'
                return await self._handle_price_command(symbol)
            
            elif command_name == 'alert':
                symbol = self._get_option_value(options, 'symbol')
                threshold = self._get_option_value(options, 'threshold')
                if not symbol:
                    return '❌ 銘柄コードを指定してください'
                return await self._handle_alert_command(symbol, threshold, user_id)
            
            elif command_name == 'chart':
                symbol = self._get_option_value(options, 'symbol')
                if not symbol:
                    return '❌ 銘柄コードを指定してください'
                period = self._get_option_value(options, 'period') or '1mo'
                return await self._handle_chart_command(symbol, period)
            
            elif command_name == 'help':
                return await self._handle_help_command()
            
            else:
                return f'❌ 不明なコマンド: {command_name}'
                
        except Exception as e:
            self.logger.error(f"スラッシュコマンド処理エラー: {e}")
            return '❌ コマンドの処理中にエラーが発生しました'
    
    def _get_option_value(self, options: list, name: str) -> Optional[str]:
        """オプション値を取得"""
        for option in options:
            if option.get('name') == name:
                return option.get('value')
        return None
    
    async def _handle_status_command(self) -> str:
        """ステータスコマンドを処理（軽量版 - 外部サービスアクセスなし）"""
        try:
            from datetime import datetime, UTC
            import os
            
            # 環境情報を取得
            environment = os.environ.get('ENVIRONMENT', 'unknown')
            function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
            region = os.environ.get('AWS_REGION', 'unknown')
            
            result = "🔍 **システムステータス**\n\n"
            result += f"⚙️ **Lambda関数**: ✅ 正常動作中\n"
            result += f"🌍 **環境**: {environment}\n"
            result += f"📍 **リージョン**: {region}\n"
            result += f"🔧 **関数名**: {function_name}\n"
            result += f"🕐 **応答時刻**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            result += "✅ **株価監視システムは正常に動作しています**\n"
            result += "📋 詳細な監視状況は `/list` コマンドで確認できます"
            
            return result
            
        except Exception as e:
            self.logger.error(f"ステータスコマンドエラー: {e}")
            return "❌ システムステータスの取得に失敗しました"
    
    async def _handle_add_command(self, symbol: str, user_id: str) -> str:
        """銘柄追加コマンドを処理"""
        try:
            from ..repositories.stock_repository import StockRepository
            from ..models.stock import MonitoredStock
            from datetime import datetime, UTC
            from decimal import Decimal
            
            symbol = symbol.upper().strip()
            if not symbol:
                return "❌ 有効な銘柄コードを入力してください"
            
            # DynamoDBに銘柄追加
            stock_repo = StockRepository()
            
            # 既存チェック
            existing = await stock_repo.get_monitored_stock(symbol)
            if existing:
                return f"⚠️ 銘柄 {symbol} は既に監視リストに登録されています"
            
            # 新規作成
            monitored_stock = MonitoredStock(
                symbol=symbol,
                name=f"{symbol} Stock",  # 後でyfinanceから取得して更新
                market="US",  # デフォルト
                volume_threshold_multiplier=Decimal('1.5'),
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            
            success = await stock_repo.create_monitored_stock(monitored_stock)
            if success:
                return f"✅ 銘柄 {symbol} を監視リストに追加しました\n👤 ユーザー: {user_id}"
            else:
                return f"❌ 銘柄 {symbol} の追加に失敗しました"
                
        except Exception as e:
            self.logger.error(f"追加コマンドエラー: {e}")
            return f"❌ 銘柄 {symbol} の追加に失敗しました"
    
    async def _handle_remove_command(self, symbol: str, user_id: str) -> str:
        """銘柄削除コマンドを処理"""
        try:
            from ..repositories.stock_repository import StockRepository
            
            symbol = symbol.upper().strip()
            if not symbol:
                return "❌ 有効な銘柄コードを入力してください"
            
            # DynamoDBから銘柄削除
            stock_repo = StockRepository()
            
            # 存在チェック
            existing = await stock_repo.get_monitored_stock(symbol)
            if not existing:
                return f"❌ 銘柄 {symbol} は監視リストに登録されていません"
            
            success = await stock_repo.delete_monitored_stock(symbol)
            if success:
                return f"✅ 銘柄 {symbol} を監視リストから削除しました"
            else:
                return f"❌ 銘柄 {symbol} の削除に失敗しました"
                
        except Exception as e:
            self.logger.error(f"削除コマンドエラー: {e}")
            return f"❌ 銘柄 {symbol} の削除に失敗しました"
    
    async def _handle_list_command(self) -> str:
        """監視リスト表示コマンドを処理"""
        try:
            from ..repositories.stock_repository import StockRepository
            import os
            
            # デバッグ情報をログ出力
            self.logger.error(f"=== DEBUG LIST COMMAND START ===")
            self.logger.error(f"Environment: {os.getenv('ENVIRONMENT', 'NOT_SET')}")
            self.logger.error(f"DynamoDB Table Stocks: {os.getenv('DYNAMODB_TABLE_STOCKS', 'NOT_SET')}")
            self.logger.error(f"AWS Region: {os.getenv('AWS_REGION', 'NOT_SET')}")
            self.logger.error(f"=== DEBUG LIST COMMAND ABOUT TO CALL REPO ===")
            
            # DynamoDBから監視リスト取得
            stock_repo = StockRepository()
            stocks = await stock_repo.list_monitored_stocks(active_only=True)
            
            if not stocks:
                return "📊 **現在の監視銘柄**\n\n監視中の銘柄はありません。\n`/add <銘柄コード>` で銘柄を追加してください。"
            
            result = "📊 **現在の監視銘柄**\n\n"
            for stock in stocks:
                result += f"• **{stock.symbol}** ({stock.name})\n"
                if stock.price_threshold_upper:
                    result += f"  - 上限アラート: ¥{stock.price_threshold_upper:,.2f}\n"
                if stock.price_threshold_lower:
                    result += f"  - 下限アラート: ¥{stock.price_threshold_lower:,.2f}\n"
                result += f"  - 出来高倍率: {stock.volume_threshold_multiplier}倍\n\n"
            
            result += f"**合計: {len(stocks)}銘柄** ✅ システムは正常に動作しています"
            return result
            
        except Exception as e:
            self.logger.error(f"リストコマンドエラー詳細: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.error(f"スタックトレース: {traceback.format_exc()}")
            return f"❌ 監視リストの取得に失敗しました\nエラー: {type(e).__name__}: {str(e)}"
    
    async def _handle_price_command(self, symbol: str) -> str:
        """価格取得コマンドを処理"""
        try:
            from ..services.data_provider import StockDataProvider
            
            symbol = symbol.upper().strip()
            if not symbol:
                return "❌ 有効な銘柄コードを入力してください"
            
            # yfinanceから最新価格取得
            data_provider = StockDataProvider()
            async with data_provider:
                stock_price = await data_provider.get_current_price(symbol)
                
                # 価格データをフォーマット
                price_str = f"¥{stock_price.price:,.2f}" if stock_price.price < 1000 else f"${stock_price.price:,.2f}"
                
                result = f"📈 **{symbol}** の現在価格\n\n"
                result += f"**価格**: {price_str}\n"
                
                if stock_price.change_amount and stock_price.change_percent:
                    change_emoji = "📈" if stock_price.change_amount > 0 else "📉" if stock_price.change_amount < 0 else "➡️"
                    change_sign = "+" if stock_price.change_amount > 0 else ""
                    result += f"**変動**: {change_emoji} {change_sign}{stock_price.change_amount:,.2f} ({change_sign}{stock_price.change_percent:.2f}%)\n"
                
                if stock_price.high_price and stock_price.low_price:
                    high_str = f"¥{stock_price.high_price:,.2f}" if stock_price.high_price < 1000 else f"${stock_price.high_price:,.2f}"
                    low_str = f"¥{stock_price.low_price:,.2f}" if stock_price.low_price < 1000 else f"${stock_price.low_price:,.2f}"
                    result += f"**日中高値**: {high_str}\n**日中安値**: {low_str}\n"
                
                if stock_price.volume:
                    result += f"**出来高**: {stock_price.volume:,}\n"
                
                result += f"\n🕐 {stock_price.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                return result
                
        except Exception as e:
            self.logger.error(f"価格取得コマンドエラー: {e}")
            return f"❌ 銘柄 {symbol} の価格取得に失敗しました\n詳細: {str(e)}"
    
    async def _handle_alert_command(self, symbol: str, threshold: str, user_id: str) -> str:
        """アラート設定コマンドを処理"""
        try:
            from ..repositories.stock_repository import StockRepository
            from decimal import Decimal
            
            symbol = symbol.upper().strip()
            if not symbol:
                return "❌ 有効な銘柄コードを入力してください"
            
            if not threshold:
                return "❌ アラート閾値を指定してください"
            
            try:
                threshold_value = Decimal(str(threshold))
            except:
                return "❌ 有効な閾値を入力してください"
            
            # 監視対象の銘柄を取得または作成
            stock_repo = StockRepository()
            stock = await stock_repo.get_monitored_stock(symbol)
            
            if not stock:
                # 銘柄が監視対象にない場合は追加
                from ..models.stock import MonitoredStock
                from datetime import datetime, UTC
                
                stock = MonitoredStock(
                    symbol=symbol,
                    name=f"{symbol} Stock",
                    market="US",
                    price_threshold_upper=threshold_value,
                    volume_threshold_multiplier=Decimal('1.5'),
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                await stock_repo.create_monitored_stock(stock)
                return f"✅ 銘柄 {symbol} を監視リストに追加し、アラート閾値を {threshold_value} に設定しました"
            else:
                # 既存の銘柄のアラート閾値を更新
                stock.price_threshold_upper = threshold_value
                await stock_repo.update_monitored_stock(stock)
                return f"✅ 銘柄 {symbol} のアラート閾値を {threshold_value} に更新しました"
                
        except Exception as e:
            self.logger.error(f"アラートコマンドエラー: {e}")
            return f"❌ アラートの設定に失敗しました\n詳細: {str(e)}"
    
    async def _handle_chart_command(self, symbol: str, period: str = '1mo') -> str:
        """チャート生成コマンドを処理"""
        try:
            from ..services.data_provider import StockDataProvider
            
            symbol = symbol.upper().strip()
            if not symbol:
                return "❌ 有効な銘柄コードを入力してください"
            
            # 過去データを取得
            data_provider = StockDataProvider()
            async with data_provider:
                historical_data = await data_provider.get_historical_data(symbol, period)
                
                if not historical_data:
                    return f"❌ 銘柄 {symbol} の過去データが見つかりません"
                
                # チャート情報をテキストで返す（Discord制約のため）
                latest_price = historical_data[0] if historical_data else None
                oldest_price = historical_data[-1] if historical_data else None
                
                if latest_price and oldest_price:
                    price_change = float(latest_price.price - oldest_price.price)
                    price_change_percent = (price_change / float(oldest_price.price)) * 100
                    change_emoji = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
                    
                    result = f"📊 **{symbol} チャート情報** ({period})\n\n"
                    result += f"📅 **期間**: {oldest_price.timestamp.strftime('%Y-%m-%d')} ~ {latest_price.timestamp.strftime('%Y-%m-%d')}\n"
                    result += f"🔢 **データポイント**: {len(historical_data)}件\n"
                    result += f"💰 **期間開始価格**: ${oldest_price.price:.2f}\n"
                    result += f"💰 **期間終了価格**: ${latest_price.price:.2f}\n"
                    result += f"📊 **期間変動**: {change_emoji} ${price_change:+.2f} ({price_change_percent:+.2f}%)\n\n"
                    result += f"📋 **最高価格**: ${max(float(d.price) for d in historical_data):.2f}\n"
                    result += f"📋 **最安価格**: ${min(float(d.price) for d in historical_data):.2f}\n\n"
                    result += "*チャート画像はDiscordの制約により表示できませんが、上記のデータで価格動向を確認できます*"
                    
                    return result
                else:
                    return f"❌ チャートデータの処理に失敗しました"
                
        except Exception as e:
            self.logger.error(f"チャートコマンドエラー: {e}")
            return f"❌ チャートの生成に失敗しました\n詳細: {str(e)}"
    
    async def _handle_help_command(self) -> str:
        """ヘルプコマンドを処理"""
        try:
            help_text = """📚 **株価監視Bot - コマンド一覧**

**基本コマンド**
• `/status` - システムの動作状況を確認
• `/help` - このヘルプを表示

**監視リスト管理**
• `/list` - 監視中の銘柄一覧を表示
• `/add <銘柄コード>` - 銘柄を監視リストに追加
• `/remove <銘柄コード>` - 銘柄を監視リストから削除

**株価情報**
• `/price <銘柄コード>` - 現在の株価を取得
• `/chart <銘柄コード> [期間]` - チャート情報を表示
• `/alert <銘柄コード> [閾値]` - 価格アラートを設定

**使用例**
```
/add AAPL          # Apple株を監視リストに追加
/price TSLA        # Tesla株の現在価格を取得
/chart MSFT 1mo    # Microsoft株の1ヶ月チャート
/alert GOOGL 150   # Google株の150ドルアラート設定
```

**対応銘柄コード**
• 米国株: AAPL, TSLA, MSFT, GOOGL など
• 日本株: 7203.T, 6758.T など（.T付き）

**注意事項**
• 株価データはリアルタイムではありません
• 市場時間外は前日終値が表示されます
• アラートは定期監視で通知されます

💡 **ヒント**: コマンドは大文字小文字を区別しません"""
            
            return help_text
            
        except Exception as e:
            self.logger.error(f"ヘルプコマンドエラー: {e}")
            return "❌ ヘルプの表示に失敗しました"