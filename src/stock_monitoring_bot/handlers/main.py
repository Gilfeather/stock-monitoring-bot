"""
Lambda function main handler
"""
import json
import logging
from typing import Dict, Any

from ..config import config
from .scheduled_handler import ScheduledHandler, ScheduledPnLReportHandler
from .interactions_handler import InteractionsHandler
# 重いライブラリは必要時のみインポート（遅延読み込み）
from .discord_handler import DiscordHandler

# ログ設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda関数のメインハンドラー"""
    try:
        logger.info(f"Lambda実行開始: {json.dumps(event, default=str)}")
        
        # EventBridge (CloudWatch Events) からの定期実行
        if event.get('source') == 'aws.events':
            import asyncio
            return asyncio.run(handle_scheduled_event(event, context))
        
        # API Gateway からのHTTPリクエスト（Discord Interactions）
        elif event.get('httpMethod') or event.get('requestContext'):
            import asyncio
            return asyncio.run(handle_http_request(event, context))
        
        # Discord非同期コマンド処理
        elif event.get('source') == 'discord.async_command':
            import asyncio
            return asyncio.run(handle_async_discord_command(event, context))
        
        # その他のイベント
        else:
            logger.warning(f"未対応のイベントタイプ: {event}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Unsupported event type'})
            }
            
    except Exception as e:
        logger.error(f"Lambda実行エラー: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }


async def handle_scheduled_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """定期実行イベントを処理"""
    try:
        # イベント種別を取得
        event_type = event.get('detail', {}).get('event_type', 'stock_monitoring')
        logger.info(f"定期実行開始: {event_type}")
        
        # Discord Webhook URLとAPI Keyを取得
        discord_webhook_url = config.discord_webhook_url
        alpha_vantage_api_key = config.alpha_vantage_api_key
        
        if not discord_webhook_url:
            raise ValueError("Discord Webhook URLが設定されていません")
        
        if not alpha_vantage_api_key:
            raise ValueError("Alpha Vantage API Keyが設定されていません")
        
        # 定期実行ハンドラーを実行
        handler = ScheduledHandler(
            discord_webhook_url=discord_webhook_url,
            alpha_vantage_api_key=alpha_vantage_api_key
        )
        
        # イベント種別に応じて処理を分岐
        if event_type == 'pnl_report':
            # P&L レポート専用ハンドラーを使用（遅延読み込み）
            from ..services.portfolio_service import PortfolioService
            from ..services.data_provider import StockDataProvider
            data_provider = StockDataProvider()
            portfolio_service = PortfolioService(data_provider)
            
            # 対象ユーザーIDを環境変数から取得（カンマ区切り）
            target_users_str = config.get_parameter(f"/{config.project_name}/{config.environment}/user-ids", default="")
            target_users = [user.strip() for user in target_users_str.split(',') if user.strip()]
            
            if not target_users:
                logger.warning("TARGET_USERS環境変数が設定されていません")
                return {
                    'statusCode': 200,
                    'body': json.dumps({"message": "対象ユーザーが設定されていません"})
                }
            
            async with DiscordHandler(discord_webhook_url) as discord_handler:
                pnl_handler = ScheduledPnLReportHandler(
                    portfolio_service, discord_handler, target_users
                )
                result = await pnl_handler.generate_and_send_pnl_reports()
        else:
            # 通常の株価監視
            result = await handler.execute()
        
        logger.info(f"定期実行完了: {event_type} - {result}")
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"定期実行エラー: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


async def handle_http_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """HTTPリクエストを処理（Discord Interactions）"""
    try:
        logger.info("Discord Interactions処理開始")
        
        # Discord Bot Public Keyを取得（環境変数から）
        discord_public_key = config.get_parameter(
            f"/{config.project_name}/{config.environment}/discord-public-key"
        )
        
        if not discord_public_key:
            logger.error("Discord Public Keyが設定されていません")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Discord Public Key not configured'})
            }
        
        # Interactions ハンドラーを実行
        handler = InteractionsHandler(
            public_key=discord_public_key,
            admin_users=[]  # TODO: 管理者ユーザーIDを設定
        )
        
        result = await handler.handle_interaction(event)
        
        logger.info("Discord Interactions処理完了")
        return result
        
    except Exception as e:
        logger.error(f"Discord Interactions処理エラー: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


async def handle_async_discord_command(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Discord非同期コマンドを処理してWebhookで結果を送信"""
    try:
        logger.info("Discord非同期コマンド処理開始")
        
        detail = event.get('detail', {})
        command_name = detail.get('command_name', '')
        options = detail.get('options', [])
        user_id = detail.get('user_id', '')
        interaction_token = detail.get('interaction_token', '')
        application_id = detail.get('application_id', '')
        
        # Discord Public Keyを取得
        discord_public_key = config.get_parameter(
            f"/{config.project_name}/{config.environment}/discord-public-key"
        )
        
        if not discord_public_key:
            logger.error("Discord Public Keyが設定されていません")
            return {'statusCode': 500, 'body': 'Discord Public Key not configured'}
        
        # コマンドプロセッサで処理
        from .interactions_handler import InteractionsHandler
        handler = InteractionsHandler(
            public_key=discord_public_key,
            admin_users=[]
        )
        
        # コマンド実行（時間がかかるもの）
        response_content = await handler._process_slash_command(
            command_name, options, user_id
        )
        
        # Discord Webhook URLを構築（follow-upメッセージ用）
        webhook_url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}"
        
        # 結果をWebhookで送信（PATCHで元のメッセージを更新）
        import aiohttp
        async with aiohttp.ClientSession() as session:
            webhook_payload = {
                "content": response_content,
                "flags": 64 if response_content.startswith('❌') else 0  # EPHEMERAL if error
            }
            
            # 元のメッセージを更新（PATCH）
            patch_url = f"{webhook_url}/messages/@original"
            async with session.patch(patch_url, json=webhook_payload) as response:
                if response.status == 200:
                    logger.info(f"Webhook送信成功: {command_name}")
                else:
                    error_text = await response.text()
                    logger.error(f"Webhook送信失敗: {response.status} - {error_text}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Async command processed'})
        }
        
    except Exception as e:
        logger.error(f"Discord非同期コマンド処理エラー: {e}", exc_info=True)
        
        # エラー時もWebhookで通知
        try:
            if application_id and interaction_token:
                import aiohttp
                webhook_url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}"
                patch_url = f"{webhook_url}/messages/@original"
                async with aiohttp.ClientSession() as session:
                    error_payload = {
                        "content": "❌ コマンドの処理中にエラーが発生しました",
                        "flags": 64  # EPHEMERAL
                    }
                    await session.patch(patch_url, json=error_payload)
        except Exception as webhook_error:
            logger.error(f"エラー通知Webhook送信失敗: {webhook_error}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }