"""
Discord Webhook Processor Lambda Function
SQSからDiscord Webhookメッセージを受信して処理
"""
import json
import logging
import os
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# 既存のハンドラーをインポート
from stock_monitoring_bot.handlers.interactions_handler import InteractionsHandler
from stock_monitoring_bot.config import config

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    SQSトリガーでDiscord Webhookを処理するLambda関数
    
    Args:
        event: SQSイベント
        context: Lambda context
        
    Returns:
        Dict: 処理結果
    """
    logger.info(f"Discord processor started with {len(event.get('Records', []))} messages")
    
    failed_messages = []
    
    for record in event.get('Records', []):
        try:
            # SQSメッセージからDiscord webhookデータを取得
            message_body = record['body']
            receipt_handle = record['receiptHandle']
            
            logger.info(f"Processing message: {record.get('messageId', 'unknown')}")
            
            # Discord webhookデータを解析
            webhook_data = json.loads(message_body)
            
            # Discord Interactionを処理
            result = process_discord_interaction(webhook_data)
            
            if result.get('success'):
                logger.info(f"Successfully processed Discord interaction: {webhook_data.get('id', 'unknown')}")
            else:
                logger.error(f"Failed to process Discord interaction: {result.get('error', 'Unknown error')}")
                failed_messages.append({
                    'itemIdentifier': record.get('messageId', 'unknown')
                })
                
        except Exception as e:
            logger.error(f"Error processing SQS message: {e}", exc_info=True)
            failed_messages.append({
                'itemIdentifier': record.get('messageId', 'unknown')
            })
    
    # SQSバッチ処理の結果を返す
    if failed_messages:
        return {
            'batchItemFailures': failed_messages
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Successfully processed {len(event.get("Records", []))} messages'
        })
    }

def process_discord_interaction(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Discord Interactionを処理
    
    Args:
        webhook_data: Discord webhookデータ
        
    Returns:
        Dict: 処理結果
    """
    try:
        interaction_type = webhook_data.get('type')
        
        # PING (type 1) は既にCloudflare Workerで処理済み
        if interaction_type == 1:
            logger.info("Received PING interaction (already handled by Cloudflare Worker)")
            return {'success': True, 'message': 'PING handled'}
        
        # APPLICATION_COMMAND (type 2)
        if interaction_type == 2:
            return process_application_command(webhook_data)
        
        # その他のタイプ
        logger.warning(f"Unsupported interaction type: {interaction_type}")
        return {'success': False, 'error': f'Unsupported interaction type: {interaction_type}'}
        
    except Exception as e:
        logger.error(f"Error processing Discord interaction: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def process_application_command(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Discord Application Commandを処理
    
    Args:
        webhook_data: Discord webhookデータ
        
    Returns:
        Dict: 処理結果
    """
    try:
        # Discord Public Keyを取得
        discord_public_key = config.get_parameter(
            f"/{config.project_name}/{config.environment}/discord-public-key"
        )
        
        if not discord_public_key:
            raise ValueError("Discord Public Key not configured")
        
        # InteractionsHandlerを使用して処理
        handler = InteractionsHandler(
            public_key=discord_public_key,
            admin_users=[]
        )
        
        # コマンドデータを抽出
        data = webhook_data.get('data', {})
        command_name = data.get('name', '')
        options = data.get('options', [])
        
        # ユーザー情報を取得
        user = webhook_data.get('member', {}).get('user', {}) or webhook_data.get('user', {})
        user_id = user.get('id', '')
        
        # インタラクショントークンとアプリケーションID
        interaction_token = webhook_data.get('token', '')
        application_id = webhook_data.get('application_id', '')
        
        if not interaction_token or not application_id:
            raise ValueError("Missing interaction token or application ID")
        
        # コマンドを非同期で処理
        import asyncio
        response_content = asyncio.run(
            handler._process_slash_command(command_name, options, user_id)
        )
        
        # Discord Webhook URLを構築してレスポンスを送信
        webhook_url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}"
        
        # レスポンスを送信
        send_discord_response(webhook_url, response_content)
        
        return {
            'success': True, 
            'message': f'Command {command_name} processed successfully'
        }
        
    except Exception as e:
        logger.error(f"Error processing application command: {e}", exc_info=True)
        
        # エラー時もDiscordに通知を試行
        try:
            interaction_token = webhook_data.get('token', '')
            application_id = webhook_data.get('application_id', '')
            
            if interaction_token and application_id:
                webhook_url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}"
                send_discord_response(webhook_url, "❌ コマンドの処理中にエラーが発生しました")
        except Exception as webhook_error:
            logger.error(f"Failed to send error response to Discord: {webhook_error}")
        
        return {'success': False, 'error': str(e)}

def send_discord_response(webhook_url: str, content: str) -> None:
    """
    DiscordのWebhook URLにレスポンスを送信
    
    Args:
        webhook_url: Discord Webhook URL
        content: 送信するコンテンツ
    """
    import requests
    
    try:
        # follow-upメッセージとして送信
        payload = {
            "content": content,
            "flags": 64 if content.startswith('❌') else 0  # EPHEMERAL if error
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("Successfully sent response to Discord")
        else:
            logger.error(f"Failed to send response to Discord: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending response to Discord: {e}")
        raise