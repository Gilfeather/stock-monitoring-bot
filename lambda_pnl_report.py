"""
含み損益レポート定期実行Lambda関数
"""
from src.stock_monitoring_bot.handlers.scheduled_handler import lambda_handler

# Lambda関数のエントリーポイント
# AWS Lambdaから直接呼び出される
def handler(event, context):
    return lambda_handler(event, context)