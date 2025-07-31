"""
コマンド処理システムのテスト
"""
import pytest
import uuid
from decimal import Decimal

from src.stock_monitoring_bot.handlers.command_processor import (
    CommandParser,
    CommandPermissionManager,
    CommandProcessor,
    CommandParseError,
    CommandPermissionError,
    CommandExecutionError
)
from src.stock_monitoring_bot.models.stock import Command


class TestCommandParser:
    """CommandParserのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.parser = CommandParser()
        self.user_id = "test_user_123"
        self.channel_id = "test_channel_456"
    
    def test_parse_add_command_basic(self):
        """基本的な!addコマンドの解析テスト"""
        message = "!add 7203"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "add"
        assert command.parameters["symbol"] == "7203"
        assert command.user_id == self.user_id
        assert command.channel_id == self.channel_id
        assert command.status == "pending"
    
    def test_parse_add_command_with_name(self):
        """銘柄名付き!addコマンドの解析テスト"""
        message = "!add AAPL Apple Inc."
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "add"
        assert command.parameters["symbol"] == "AAPL"
        assert command.parameters["name"] == "Apple Inc."
    
    def test_parse_remove_command(self):
        """!removeコマンドの解析テスト"""
        message = "!remove 7203"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "remove"
        assert command.parameters["symbol"] == "7203"
    
    def test_parse_list_command_default(self):
        """デフォルト!listコマンドの解析テスト"""
        message = "!list"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "list"
        assert command.parameters["limit"] == 10
    
    def test_parse_list_command_with_limit(self):
        """制限付き!listコマンドの解析テスト"""
        message = "!list 20"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "list"
        assert command.parameters["limit"] == 20
    
    def test_parse_list_command_invalid_limit(self):
        """無効な制限値の!listコマンドテスト"""
        with pytest.raises(CommandParseError, match="無効な表示件数"):
            self.parser.parse_command("!list 0", self.user_id, self.channel_id)
        
        with pytest.raises(CommandParseError, match="無効な表示件数"):
            self.parser.parse_command("!list 100", self.user_id, self.channel_id)
    
    def test_parse_alert_command_upper_only(self):
        """上限のみの!alertコマンドの解析テスト"""
        message = "!alert 7203 3000.50"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "alert"
        assert command.parameters["symbol"] == "7203"
        assert command.parameters["upper_limit"] == Decimal("3000.50")
        assert "lower_limit" not in command.parameters
    
    def test_parse_alert_command_both_limits(self):
        """上下限両方の!alertコマンドの解析テスト"""
        message = "!alert 7203 3000 2500"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "alert"
        assert command.parameters["symbol"] == "7203"
        assert command.parameters["upper_limit"] == Decimal("3000")
        assert command.parameters["lower_limit"] == Decimal("2500")
    
    def test_parse_alert_command_invalid_limits(self):
        """無効な閾値の!alertコマンドテスト"""
        # 負の値 - 現在は正規表現で除外されているため不明なコマンドとして扱われる
        with pytest.raises(CommandParseError, match="不明なコマンドです"):
            self.parser.parse_command("!alert 7203 -100", self.user_id, self.channel_id)
        
        # 下限が上限より大きい
        with pytest.raises(CommandParseError, match="下限閾値は上限閾値より小さい値である必要があります"):
            self.parser.parse_command("!alert 7203 2000 3000", self.user_id, self.channel_id)
        
        # 無効な数値形式
        with pytest.raises(CommandParseError, match="不明なコマンドです"):
            self.parser.parse_command("!alert 7203 abc", self.user_id, self.channel_id)
    
    def test_parse_chart_command_default(self):
        """デフォルト!chartコマンドの解析テスト"""
        message = "!chart 7203"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "chart"
        assert command.parameters["symbol"] == "7203"
        assert command.parameters["period"] == "1d"
    
    def test_parse_chart_command_with_period(self):
        """期間指定!chartコマンドの解析テスト"""
        message = "!chart 7203 7d"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "chart"
        assert command.parameters["symbol"] == "7203"
        assert command.parameters["period"] == "7d"
    
    def test_parse_chart_command_invalid_period(self):
        """無効な期間の!chartコマンドテスト"""
        with pytest.raises(CommandParseError, match="不明なコマンドです"):
            self.parser.parse_command("!chart 7203 invalid", self.user_id, self.channel_id)
    
    def test_parse_stats_command(self):
        """!statsコマンドの解析テスト"""
        message = "!stats 7203"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "stats"
        assert command.parameters["symbol"] == "7203"
    
    def test_parse_help_command_general(self):
        """一般!helpコマンドの解析テスト"""
        message = "!help"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "help"
        assert "command" not in command.parameters
    
    def test_parse_help_command_specific(self):
        """特定コマンドの!helpコマンドの解析テスト"""
        message = "!help add"
        command = self.parser.parse_command(message, self.user_id, self.channel_id)
        
        assert command.command_type == "help"
        assert command.parameters["command"] == "add"
    
    def test_parse_help_command_invalid(self):
        """無効なコマンドの!helpテスト"""
        with pytest.raises(CommandParseError, match="不明なコマンド"):
            self.parser.parse_command("!help invalid", self.user_id, self.channel_id)
    
    def test_parse_non_command_message(self):
        """コマンドでないメッセージのテスト"""
        with pytest.raises(CommandParseError, match="コマンドではありません"):
            self.parser.parse_command("Hello world", self.user_id, self.channel_id)
    
    def test_parse_unknown_command(self):
        """不明なコマンドのテスト"""
        with pytest.raises(CommandParseError, match="不明なコマンドです"):
            self.parser.parse_command("!unknown", self.user_id, self.channel_id)
    
    def test_validate_symbol_valid(self):
        """有効な銘柄コードの検証テスト"""
        assert self.parser.validate_symbol("7203") is True
        assert self.parser.validate_symbol("AAPL") is True
        assert self.parser.validate_symbol("MSFT") is True
    
    def test_validate_symbol_invalid(self):
        """無効な銘柄コードの検証テスト"""
        assert self.parser.validate_symbol("") is False
        assert self.parser.validate_symbol("abc-def") is False
        assert self.parser.validate_symbol("12345678901") is False  # 長すぎる
        assert self.parser.validate_symbol("abc@def") is False  # 特殊文字


class TestCommandPermissionManager:
    """CommandPermissionManagerのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.admin_users = ["admin1", "admin2"]
        self.allowed_channels = ["channel1", "channel2"]
        self.permission_manager = CommandPermissionManager(
            self.admin_users, self.allowed_channels
        )
    
    def test_check_permission_allowed_channel_and_admin(self):
        """許可チャンネル・管理者ユーザーの権限チェック"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id="admin1",
            channel_id="channel1",
            command_type="add",
            parameters={}
        )
        
        assert self.permission_manager.check_permission(command) is True
    
    def test_check_permission_disallowed_channel(self):
        """許可されていないチャンネルの権限チェック"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id="admin1",
            channel_id="forbidden_channel",
            command_type="add",
            parameters={}
        )
        
        with pytest.raises(CommandPermissionError, match="このチャンネルではコマンドを実行できません"):
            self.permission_manager.check_permission(command)
    
    def test_check_permission_non_admin_user(self):
        """非管理者ユーザーの管理者限定コマンド実行テスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id="regular_user",
            channel_id="channel1",
            command_type="add",
            parameters={}
        )
        
        with pytest.raises(CommandPermissionError, match="管理者権限が必要です"):
            self.permission_manager.check_permission(command)
    
    def test_check_permission_public_command(self):
        """一般ユーザーでも実行可能なコマンドのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id="regular_user",
            channel_id="channel1",
            command_type="list",
            parameters={}
        )
        
        assert self.permission_manager.check_permission(command) is True
    
    def test_add_remove_admin_user(self):
        """管理者ユーザーの追加・削除テスト"""
        new_admin = "new_admin"
        
        # 追加
        self.permission_manager.add_admin_user(new_admin)
        assert new_admin in self.permission_manager.admin_users
        
        # 削除
        self.permission_manager.remove_admin_user(new_admin)
        assert new_admin not in self.permission_manager.admin_users
    
    def test_add_remove_allowed_channel(self):
        """許可チャンネルの追加・削除テスト"""
        new_channel = "new_channel"
        
        # 追加
        self.permission_manager.add_allowed_channel(new_channel)
        assert new_channel in self.permission_manager.allowed_channels
        
        # 削除
        self.permission_manager.remove_allowed_channel(new_channel)
        assert new_channel not in self.permission_manager.allowed_channels
    
    def test_no_restrictions(self):
        """制限なしの権限マネージャーテスト"""
        unrestricted_manager = CommandPermissionManager()
        
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id="any_user",
            channel_id="any_channel",
            command_type="add",
            parameters={}
        )
        
        # 制限がない場合は全て許可
        assert unrestricted_manager.check_permission(command) is True


class TestCommandProcessor:
    """CommandProcessorのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.admin_users = ["admin1"]
        self.allowed_channels = ["channel1"]
        self.processor = CommandProcessor(self.admin_users, self.allowed_channels)
        self.user_id = "admin1"
        self.channel_id = "channel1"
    
    @pytest.mark.asyncio
    async def test_process_message_valid_command(self):
        """有効なコマンドメッセージの処理テスト"""
        message = "!add 7203 Toyota"
        
        command = await self.processor.process_message(message, self.user_id, self.channel_id)
        
        assert command is not None
        assert command.command_type == "add"
        assert command.status == "completed"
        assert "追加しました" in command.result
    
    @pytest.mark.asyncio
    async def test_process_message_invalid_command(self):
        """無効なコマンドメッセージの処理テスト"""
        message = "Hello world"
        
        command = await self.processor.process_message(message, self.user_id, self.channel_id)
        
        assert command is None
    
    @pytest.mark.asyncio
    async def test_process_message_permission_error(self):
        """権限エラーのコマンド処理テスト"""
        message = "!add 7203"
        regular_user = "regular_user"
        
        command = await self.processor.process_message(message, regular_user, self.channel_id)
        
        assert command is not None
        assert command.command_type == "error"
        assert command.status == "failed"
        assert "管理者権限が必要です" in command.error_message
    
    @pytest.mark.asyncio
    async def test_handle_add_command(self):
        """!addコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="add",
            parameters={"symbol": "7203", "name": "Toyota"}
        )
        
        result = await self.processor._handle_add_command(command)
        
        assert "追加しました" in result
        assert "7203" in result
        assert "Toyota" in result
    
    @pytest.mark.asyncio
    async def test_handle_add_command_invalid_symbol(self):
        """無効な銘柄コードの!addコマンドテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="add",
            parameters={"symbol": "invalid@symbol"}
        )
        
        with pytest.raises(CommandExecutionError, match="無効な銘柄コード"):
            await self.processor._handle_add_command(command)
    
    @pytest.mark.asyncio
    async def test_handle_remove_command(self):
        """!removeコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="remove",
            parameters={"symbol": "7203"}
        )
        
        result = await self.processor._handle_remove_command(command)
        
        assert "削除しました" in result
        assert "7203" in result
    
    @pytest.mark.asyncio
    async def test_handle_list_command(self):
        """!listコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="list",
            parameters={"limit": 10}
        )
        
        result = await self.processor._handle_list_command(command)
        
        assert "監視中の銘柄一覧" in result
        assert "10件" in result
    
    @pytest.mark.asyncio
    async def test_handle_alert_command(self):
        """!alertコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="alert",
            parameters={
                "symbol": "7203",
                "upper_limit": Decimal("3000"),
                "lower_limit": Decimal("2500")
            }
        )
        
        result = await self.processor._handle_alert_command(command)
        
        assert "アラート設定を更新しました" in result
        assert "7203" in result
        assert "3,000.00" in result
        assert "2,500.00" in result
    
    @pytest.mark.asyncio
    async def test_handle_chart_command(self):
        """!chartコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="chart",
            parameters={"symbol": "7203", "period": "7d"}
        )
        
        result = await self.processor._handle_chart_command(command)
        
        assert "チャート" in result
        assert "7203" in result
        assert "7d" in result
    
    @pytest.mark.asyncio
    async def test_handle_stats_command(self):
        """!statsコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="stats",
            parameters={"symbol": "7203"}
        )
        
        result = await self.processor._handle_stats_command(command)
        
        assert "統計情報" in result
        assert "7203" in result
    
    @pytest.mark.asyncio
    async def test_handle_help_command_general(self):
        """一般!helpコマンドハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="help",
            parameters={}
        )
        
        result = await self.processor._handle_help_command(command)
        
        assert "コマンド一覧" in result
        assert "!add" in result
        assert "!remove" in result
        assert "!list" in result
    
    @pytest.mark.asyncio
    async def test_handle_help_command_specific(self):
        """特定コマンドの!helpハンドラーのテスト"""
        command = Command(
            command_id=str(uuid.uuid4()),
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_type="help",
            parameters={"command": "add"}
        )
        
        result = await self.processor._handle_help_command(command)
        
        assert "!add コマンド" in result
        assert "使用法" in result
        assert "管理者権限が必要" in result
    
    def test_get_command_help_all_commands(self):
        """全コマンドのヘルプテキスト存在確認"""
        commands = ["add", "remove", "list", "alert", "chart", "stats"]
        
        for cmd in commands:
            help_text = self.processor._get_command_help(cmd)
            assert f"!{cmd} コマンド" in help_text
            assert "使用法" in help_text
    
    def test_get_command_help_unknown(self):
        """不明なコマンドのヘルプテスト"""
        help_text = self.processor._get_command_help("unknown")
        assert "見つかりませんでした" in help_text


@pytest.mark.asyncio
async def test_integration_command_processing():
    """コマンド処理の統合テスト"""
    processor = CommandProcessor(["admin1"], ["channel1"])
    
    # 正常なコマンド処理フロー
    message = "!add 7203 Toyota Motor"
    command = await processor.process_message(message, "admin1", "channel1")
    
    assert command is not None
    assert command.command_type == "add"
    assert command.status == "completed"
    assert command.parameters["symbol"] == "7203"
    assert command.parameters["name"] == "Toyota Motor"
    assert "追加しました" in command.result
    
    # 権限エラーフロー
    command = await processor.process_message(message, "regular_user", "channel1")
    
    assert command is not None
    assert command.command_type == "error"
    assert command.status == "failed"
    assert "管理者権限が必要です" in command.error_message