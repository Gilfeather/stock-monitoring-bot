"""
Discordコマンド処理システム
"""
import logging
import re
import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, InvalidOperation

from ..models.stock import Command


class CommandParseError(Exception):
    """コマンド解析エラー"""
    pass


class CommandPermissionError(Exception):
    """コマンド権限エラー"""
    pass


class CommandExecutionError(Exception):
    """コマンド実行エラー"""
    pass


class CommandParser:
    """Discordコマンドパーサー"""
    
    # コマンドパターン定義
    COMMAND_PATTERNS = {
        'add': r'^!add\s+([A-Z0-9]+)(?:\s+(.+))?$',
        'remove': r'^!remove\s+([A-Z0-9]+)$',
        'list': r'^!list(?:\s+(\d+))?$',
        'alert': r'^!alert\s+([A-Z0-9]+)\s+([0-9.]+)(?:\s+([0-9.]+))?$',
        'chart': r'^!chart\s+([A-Z0-9]+)(?:\s+(\d+[hdwmy]))?$',
        'stats': r'^!stats\s+([A-Z0-9]+)$',
        'portfolio_add': r'^!portfolio\s+add\s+([A-Z0-9]+)\s+(\d+)\s+([0-9.]+)$',
        'portfolio_remove': r'^!portfolio\s+remove\s+([A-Z0-9]+)$',
        'portfolio_list': r'^!portfolio\s+list$',
        'portfolio_pnl': r'^!portfolio\s+pnl$',
        'help': r'^!help(?:\s+(\w+))?$'
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_command(self, message: str, user_id: str, channel_id: str) -> Command:
        """メッセージからコマンドを解析"""
        try:
            message = message.strip()
            
            # コマンドでない場合はNoneを返す
            if not message.startswith('!'):
                raise CommandParseError("コマンドではありません")
            
            # 各コマンドパターンをチェック
            for command_type, pattern in self.COMMAND_PATTERNS.items():
                match = re.match(pattern, message, re.IGNORECASE)
                if match:
                    parameters = self._extract_parameters(command_type, match.groups())
                    
                    return Command(
                        command_id=str(uuid.uuid4()),
                        user_id=user_id,
                        channel_id=channel_id,
                        command_type=command_type,
                        parameters=parameters,
                        executed_at=datetime.now(UTC),
                        status="pending"
                    )
            
            # マッチしない場合
            raise CommandParseError(f"不明なコマンドです: {message}")
            
        except Exception as e:
            self.logger.error(f"コマンド解析エラー: {e}")
            raise CommandParseError(str(e))
    
    def _extract_parameters(self, command_type: str, groups: Tuple) -> Dict[str, Any]:
        """コマンド種別に応じてパラメータを抽出"""
        parameters = {}
        
        if command_type == 'add':
            parameters['symbol'] = groups[0].upper()
            if groups[1]:  # オプションの銘柄名
                parameters['name'] = groups[1].strip()
        
        elif command_type == 'remove':
            parameters['symbol'] = groups[0].upper()
        
        elif command_type == 'list':
            if groups[0]:  # オプションの表示件数
                try:
                    parameters['limit'] = int(groups[0])
                    if parameters['limit'] <= 0 or parameters['limit'] > 50:
                        raise ValueError("表示件数は1-50の範囲で指定してください")
                except ValueError as e:
                    raise CommandParseError(f"無効な表示件数: {e}")
            else:
                parameters['limit'] = 10  # デフォルト
        
        elif command_type == 'alert':
            parameters['symbol'] = groups[0].upper()
            try:
                parameters['upper_limit'] = Decimal(groups[1])
                if parameters['upper_limit'] <= 0:
                    raise ValueError("上限閾値は正の値である必要があります")
                
                if groups[2]:  # 下限閾値（オプション）
                    parameters['lower_limit'] = Decimal(groups[2])
                    if parameters['lower_limit'] <= 0:
                        raise ValueError("下限閾値は正の値である必要があります")
                    if parameters['lower_limit'] >= parameters['upper_limit']:
                        raise ValueError("下限閾値は上限閾値より小さい値である必要があります")
            except (InvalidOperation, ValueError) as e:
                raise CommandParseError(f"無効な閾値: {e}")
        
        elif command_type == 'chart':
            parameters['symbol'] = groups[0].upper()
            if groups[1]:  # オプションの期間
                period = groups[1].lower()
                if not re.match(r'^\d+[hdwmy]$', period):
                    raise CommandParseError("期間は数値+単位（h/d/w/m/y）で指定してください")
                parameters['period'] = period
            else:
                parameters['period'] = '1d'  # デフォルト
        
        elif command_type == 'stats':
            parameters['symbol'] = groups[0].upper()
        
        elif command_type.startswith('portfolio_'):
            if command_type == 'portfolio_add':
                parameters['symbol'] = groups[0].upper()
                try:
                    parameters['quantity'] = int(groups[1])
                    parameters['purchase_price'] = Decimal(groups[2])
                    
                    if parameters['quantity'] <= 0:
                        raise ValueError("株数は正の値である必要があります")
                    if parameters['purchase_price'] <= 0:
                        raise ValueError("取得価格は正の値である必要があります")
                        
                except (ValueError, InvalidOperation) as e:
                    raise CommandParseError(f"無効なパラメータ: {e}")
            
            elif command_type == 'portfolio_remove':
                parameters['symbol'] = groups[0].upper()
        
        elif command_type == 'help':
            if groups[0]:  # 特定コマンドのヘルプ
                help_command = groups[0].lower()
                if help_command not in self.COMMAND_PATTERNS:
                    raise CommandParseError(f"不明なコマンド: {help_command}")
                parameters['command'] = help_command
        
        return parameters
    
    def validate_symbol(self, symbol: str) -> bool:
        """銘柄コードの基本的な検証"""
        if not symbol:
            return False
        
        # 基本的なフォーマットチェック
        if not re.match(r'^[A-Z0-9]{1,10}$', symbol):
            return False
        
        return True


class CommandPermissionManager:
    """コマンド権限管理"""
    
    def __init__(self, admin_users: Optional[List[str]] = None, allowed_channels: Optional[List[str]] = None):
        self.admin_users = set(admin_users or [])
        self.allowed_channels = set(allowed_channels or [])
        self.logger = logging.getLogger(__name__)
    
    def check_permission(self, command: Command) -> bool:
        """コマンド実行権限をチェック"""
        try:
            # チャンネル制限チェック
            if self.allowed_channels and command.channel_id not in self.allowed_channels:
                raise CommandPermissionError(f"このチャンネルではコマンドを実行できません: {command.channel_id}")
            
            # 管理者限定コマンドのチェック
            admin_only_commands = {'add', 'remove', 'alert'}
            if command.command_type in admin_only_commands:
                if self.admin_users and command.user_id not in self.admin_users:
                    raise CommandPermissionError(f"管理者権限が必要です: {command.command_type}")
            
            return True
            
        except CommandPermissionError:
            self.logger.warning(f"権限エラー: ユーザー {command.user_id} がコマンド {command.command_type} を実行しようとしました")
            raise
    
    def add_admin_user(self, user_id: str) -> None:
        """管理者ユーザーを追加"""
        self.admin_users.add(user_id)
    
    def remove_admin_user(self, user_id: str) -> None:
        """管理者ユーザーを削除"""
        self.admin_users.discard(user_id)
    
    def add_allowed_channel(self, channel_id: str) -> None:
        """許可チャンネルを追加"""
        self.allowed_channels.add(channel_id)
    
    def remove_allowed_channel(self, channel_id: str) -> None:
        """許可チャンネルを削除"""
        self.allowed_channels.discard(channel_id)


class CommandProcessor:
    """Discordコマンド処理システム"""
    
    def __init__(
        self,
        admin_users: Optional[List[str]] = None,
        allowed_channels: Optional[List[str]] = None
    ):
        self.parser = CommandParser()
        self.permission_manager = CommandPermissionManager(admin_users, allowed_channels)
        self.logger = logging.getLogger(__name__)
        
        # コマンド実行ハンドラー
        self.command_handlers = {
            'add': self._handle_add_command,
            'remove': self._handle_remove_command,
            'list': self._handle_list_command,
            'alert': self._handle_alert_command,
            'chart': self._handle_chart_command,
            'stats': self._handle_stats_command,
            'portfolio_add': self._handle_portfolio_add_command,
            'portfolio_remove': self._handle_portfolio_remove_command,
            'portfolio_list': self._handle_portfolio_list_command,
            'portfolio_pnl': self._handle_portfolio_pnl_command,
            'help': self._handle_help_command
        }
    
    async def process_message(self, message: str, user_id: str, channel_id: str) -> Optional[Command]:
        """メッセージを処理してコマンドを実行"""
        try:
            # コマンド解析
            command = self.parser.parse_command(message, user_id, channel_id)
            
            # 権限チェック
            self.permission_manager.check_permission(command)
            
            # コマンド実行
            command.status = "processing"
            await self._execute_command(command)
            
            return command
            
        except CommandParseError as e:
            self.logger.info(f"コマンド解析エラー: {e}")
            return None
        except CommandPermissionError as e:
            self.logger.warning(f"権限エラー: {e}")
            # 権限エラーの場合もCommandオブジェクトを返してエラーメッセージを送信
            command = Command(
                command_id=str(uuid.uuid4()),
                user_id=user_id,
                channel_id=channel_id,
                command_type="error",
                parameters={},
                status="failed",
                error_message=str(e)
            )
            return command
        except Exception as e:
            self.logger.error(f"コマンド処理エラー: {e}")
            command = Command(
                command_id=str(uuid.uuid4()),
                user_id=user_id,
                channel_id=channel_id,
                command_type="error",
                parameters={},
                status="failed",
                error_message=f"内部エラーが発生しました: {str(e)}"
            )
            return command
    
    async def _execute_command(self, command: Command) -> None:
        """コマンドを実行"""
        try:
            handler = self.command_handlers.get(command.command_type)
            if not handler:
                raise CommandExecutionError(f"未対応のコマンド: {command.command_type}")
            
            result = await handler(command)
            command.status = "completed"
            command.result = result
            
        except Exception as e:
            command.status = "failed"
            command.error_message = str(e)
            self.logger.error(f"コマンド実行エラー [{command.command_type}]: {e}")
            raise
    
    async def _handle_add_command(self, command: Command) -> str:
        """!add コマンドの処理"""
        symbol = command.parameters['symbol']
        name = command.parameters.get('name', symbol)
        
        # 銘柄コード検証
        if not self.parser.validate_symbol(symbol):
            raise CommandExecutionError(f"無効な銘柄コード: {symbol}")
        
        # TODO: 実際のデータベース操作とAPI連携
        # ここでは仮の実装
        self.logger.info(f"銘柄追加: {symbol} ({name})")
        
        return f"✅ 銘柄 {symbol} ({name}) を監視リストに追加しました"
    
    async def _handle_remove_command(self, command: Command) -> str:
        """!remove コマンドの処理"""
        symbol = command.parameters['symbol']
        
        # TODO: 実際のデータベース操作
        # ここでは仮の実装
        self.logger.info(f"銘柄削除: {symbol}")
        
        return f"✅ 銘柄 {symbol} を監視リストから削除しました"
    
    async def _handle_list_command(self, command: Command) -> str:
        """!list コマンドの処理"""
        limit = command.parameters['limit']
        
        # TODO: 実際のデータベースクエリ
        # ここでは仮の実装
        self.logger.info(f"監視リスト表示: 上限{limit}件")
        
        return f"📋 監視中の銘柄一覧（上位{limit}件）:\n（実装予定）"
    
    async def _handle_alert_command(self, command: Command) -> str:
        """!alert コマンドの処理"""
        symbol = command.parameters['symbol']
        upper_limit = command.parameters['upper_limit']
        lower_limit = command.parameters.get('lower_limit')
        
        # TODO: 実際のデータベース操作
        # ここでは仮の実装
        self.logger.info(f"アラート設定: {symbol} 上限={upper_limit} 下限={lower_limit}")
        
        result = f"🚨 {symbol} のアラート設定を更新しました\n"
        result += f"上限閾値: ¥{upper_limit:,.2f}"
        if lower_limit:
            result += f"\n下限閾値: ¥{lower_limit:,.2f}"
        
        return result
    
    async def _handle_chart_command(self, command: Command) -> str:
        """!chart コマンドの処理"""
        symbol = command.parameters['symbol']
        period = command.parameters['period']
        
        # TODO: 実際のチャート生成
        # ここでは仮の実装
        self.logger.info(f"チャート生成: {symbol} 期間={period}")
        
        return f"📈 {symbol} のチャート（{period}）を生成中..."
    
    async def _handle_stats_command(self, command: Command) -> str:
        """!stats コマンドの処理"""
        symbol = command.parameters['symbol']
        
        # TODO: 実際の統計情報取得
        # ここでは仮の実装
        self.logger.info(f"統計情報取得: {symbol}")
        
        return f"📊 {symbol} の統計情報:\n（実装予定）"
    
    async def _handle_portfolio_add_command(self, command: Command) -> str:
        """!portfolio add コマンドの処理"""
        symbol = command.parameters['symbol']
        quantity = command.parameters['quantity']
        purchase_price = command.parameters['purchase_price']
        
        # TODO: ポートフォリオサービスとの連携
        self.logger.info(f"ポートフォリオ追加: {symbol} x{quantity} @ ¥{purchase_price}")
        
        return f"✅ ポートフォリオに追加しました\n" \
               f"銘柄: {symbol}\n" \
               f"株数: {quantity:,}株\n" \
               f"取得価格: ¥{purchase_price:,.2f}"
    
    async def _handle_portfolio_remove_command(self, command: Command) -> str:
        """!portfolio remove コマンドの処理"""
        symbol = command.parameters['symbol']
        
        # TODO: ポートフォリオサービスとの連携
        self.logger.info(f"ポートフォリオ削除: {symbol}")
        
        return f"✅ {symbol} をポートフォリオから削除しました"
    
    async def _handle_portfolio_list_command(self, command: Command) -> str:
        """!portfolio list コマンドの処理"""
        # TODO: ポートフォリオサービスとの連携
        self.logger.info("ポートフォリオ一覧表示")
        
        return "📋 **ポートフォリオ一覧**\n（実装予定）"
    
    async def _handle_portfolio_pnl_command(self, command: Command) -> str:
        """!portfolio pnl コマンドの処理"""
        # TODO: ポートフォリオサービスとの連携
        self.logger.info("ポートフォリオ損益表示")
        
        return "📊 **含み損益レポート**\n（実装予定）"
    
    async def _handle_help_command(self, command: Command) -> str:
        """!help コマンドの処理"""
        help_command = command.parameters.get('command')
        
        if help_command:
            return self._get_command_help(help_command)
        else:
            return self._get_general_help()
    
    def _get_general_help(self) -> str:
        """一般的なヘルプメッセージ"""
        return """🤖 **株価監視ボット - コマンド一覧**

**基本コマンド:**
• `!add <銘柄コード> [銘柄名]` - 監視銘柄を追加
• `!remove <銘柄コード>` - 監視銘柄を削除
• `!list [件数]` - 監視銘柄一覧を表示
• `!alert <銘柄コード> <上限> [下限]` - アラート閾値を設定

**ポートフォリオ:**
• `!portfolio add <銘柄> <株数> <取得価格>` - 保有銘柄を追加
• `!portfolio remove <銘柄>` - 保有銘柄を削除
• `!portfolio list` - ポートフォリオ一覧を表示
• `!portfolio pnl` - 含み損益を表示

**情報表示:**
• `!chart <銘柄コード> [期間]` - 価格チャートを表示
• `!stats <銘柄コード>` - 統計情報を表示
• `!help [コマンド名]` - ヘルプを表示

詳細は `!help <コマンド名>` で確認できます。"""
    
    def _get_command_help(self, command_name: str) -> str:
        """特定コマンドのヘルプメッセージ"""
        help_texts = {
            'add': """**!add コマンド**
監視対象の銘柄を追加します。

**使用法:**
`!add <銘柄コード> [銘柄名]`

**例:**
• `!add 7203` - トヨタ自動車を追加
• `!add AAPL Apple Inc.` - Apple株を追加

**注意:** 管理者権限が必要です。""",
            
            'remove': """**!remove コマンド**
監視対象の銘柄を削除します。

**使用法:**
`!remove <銘柄コード>`

**例:**
• `!remove 7203` - トヨタ自動車を削除

**注意:** 管理者権限が必要です。""",
            
            'list': """**!list コマンド**
現在監視中の銘柄一覧を表示します。

**使用法:**
`!list [表示件数]`

**例:**
• `!list` - 上位10件を表示
• `!list 20` - 上位20件を表示

**注意:** 表示件数は1-50の範囲で指定してください。""",
            
            'alert': """**!alert コマンド**
指定銘柄のアラート閾値を設定します。

**使用法:**
`!alert <銘柄コード> <上限閾値> [下限閾値]`

**例:**
• `!alert 7203 3000` - 上限3000円でアラート
• `!alert 7203 3000 2500` - 上限3000円、下限2500円でアラート

**注意:** 管理者権限が必要です。""",
            
            'chart': """**!chart コマンド**
指定銘柄の価格チャートを表示します。

**使用法:**
`!chart <銘柄コード> [期間]`

**期間指定:**
• h: 時間 (例: 24h)
• d: 日 (例: 7d)
• w: 週 (例: 4w)
• m: 月 (例: 3m)
• y: 年 (例: 1y)

**例:**
• `!chart 7203` - 1日チャート
• `!chart 7203 7d` - 7日チャート""",
            
            'stats': """**!stats コマンド**
指定銘柄の統計情報を表示します。

**使用法:**
`!stats <銘柄コード>`

**表示内容:**
• 現在価格、変動額、変動率
• 当日の高値・安値
• 取引量
• その他統計データ

**例:**
• `!stats 7203` - トヨタ自動車の統計情報""",

            'portfolio': """**!portfolio コマンド**
ポートフォリオ管理機能です。

**使用法:**
• `!portfolio add <銘柄> <株数> <取得価格>` - 保有銘柄を追加
• `!portfolio remove <銘柄>` - 保有銘柄を削除
• `!portfolio list` - ポートフォリオ一覧を表示
• `!portfolio pnl` - 含み損益を表示

**例:**
• `!portfolio add 7203 100 2500` - トヨタ100株を2500円で追加
• `!portfolio remove 7203` - トヨタを削除
• `!portfolio list` - 保有銘柄一覧
• `!portfolio pnl` - 損益レポート"""
        }
        
        return help_texts.get(command_name, f"コマンド '{command_name}' のヘルプは見つかりませんでした。")