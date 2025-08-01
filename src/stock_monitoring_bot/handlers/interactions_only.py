"""
軽量Discord Interactions専用ハンドラー
pandas/numpy等の重いライブラリを使わない
"""
import json
import logging
from typing import Dict, Any
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import boto3

# 軽量ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SSMクライアント（グローバル）
ssm_client = boto3.client('ssm', region_name='ap-northeast-1')

def get_discord_public_key():
    """Discord公開鍵を取得"""
    try:
        response = ssm_client.get_parameter(
            Name='/stock-monitoring-bot/dev/discord-public-key'
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"公開鍵取得エラー: {e}")
        raise

def verify_discord_signature(signature: str, timestamp: str, body: str, public_key: str) -> bool:
    """Discord署名を検証"""
    try:
        if len(signature) != 128:
            return False
        
        verify_key = VerifyKey(bytes.fromhex(public_key))
        message = f'{timestamp}{body}'.encode()
        signature_bytes = bytes.fromhex(signature)
        
        verify_key.verify(message, signature_bytes)
        return True
    except (BadSignatureError, ValueError, Exception):
        return False

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """軽量Discord Interactions専用ハンドラー"""
    try:
        logger.info("Discord Interactions処理開始")
        
        # ヘッダーと署名取得
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        signature = ''
        timestamp = ''
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower == 'x-signature-ed25519':
                signature = value
            elif key_lower == 'x-signature-timestamp':
                timestamp = value
        
        # 署名検証
        public_key = get_discord_public_key()
        if not verify_discord_signature(signature, timestamp, body, public_key):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        # リクエストパース
        interaction_data = json.loads(body)
        interaction_type = interaction_data.get('type')
        
        # PING応答
        if interaction_type == 1:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'type': 1})
            }
        
        # スラッシュコマンド
        if interaction_type == 2:
            data = interaction_data.get('data', {})
            command_name = data.get('name', '')
            
            # 簡単なレスポンス
            responses = {
                'list': '📊 監視銘柄:\n• AAPL\n• TSLA\n• MSFT',
                'add': '✅ 銘柄を追加しました',
                'remove': '✅ 銘柄を削除しました',
                'alert': '🔔 アラートを設定しました',
                'chart': '📈 チャート機能は準備中です'
            }
            
            content = responses.get(command_name, f'❌ 未対応コマンド: {command_name}')
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'type': 4,
                    'data': {'content': content}
                })
            }
        
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Unknown interaction type'})
        }
        
    except Exception as e:
        logger.error(f"エラー: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }