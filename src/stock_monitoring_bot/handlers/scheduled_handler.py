"""
定期実行ハンドラー（Lambda用）
"""
import asyncio
import json
import logging
import os
from datetime import datetime, UTC
from typing import Dict, Any, List

from ..services.portfolio_service import PortfolioService
from ..services.data_provider import StockDataProvider
from ..handlers.discord_handler import DiscordHandler
from ..models.stock import PortfolioProfitLossReport


class ScheduledHandler:
    """定期実行ハンドラー（株価監視用）"""
    
    def __init__(self, discord_webhook_url: str, alpha_vantage_api_key: str):
        self.discord_webhook_url = discord_webhook_url
        self.alpha_vantage_api_key = alpha_vantage_api_key
        self.logger = logging.getLogger(__name__)
    
    async def execute(self) -> Dict[str, Any]:
        """定期株価監視を実行"""
        try:
            self.logger.info("定期株価監視開始")
            
            # TODO: 実際の株価監視ロジックを実装
            # 現在はプレースホルダー
            result = {
                "status": "success",
                "message": "株価監視が正常に完了しました",
                "processed_stocks": 0,
                "alerts_sent": 0
            }
            
            self.logger.info(f"定期株価監視完了: {result}")
            return result
            
        except Exception as e:
            error_msg = f"定期株価監視エラー: {str(e)}"
            self.logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "processed_stocks": 0,
                "alerts_sent": 0
            }


class ScheduledPnLReportHandler:
    """定期損益レポートハンドラー"""
    
    def __init__(
        self,
        portfolio_service: PortfolioService,
        discord_handler: DiscordHandler,
        target_users: List[str] = None
    ):
        self.portfolio_service = portfolio_service
        self.discord_handler = discord_handler
        self.target_users = target_users or []
        self.logger = logging.getLogger(__name__)
    
    async def generate_and_send_pnl_reports(self) -> Dict[str, Any]:
        """全ユーザーの損益レポートを生成・送信"""
        results = {
            "processed_users": 0,
            "successful_reports": 0,
            "failed_reports": 0,
            "errors": []
        }
        
        try:
            # 対象ユーザーの損益レポートを生成
            for user_id in self.target_users:
                try:
                    await self._process_user_pnl_report(user_id)
                    results["successful_reports"] += 1
                    
                except Exception as e:
                    error_msg = f"ユーザー {user_id} の処理エラー: {str(e)}"
                    self.logger.error(error_msg)
                    results["errors"].append(error_msg)
                    results["failed_reports"] += 1
                
                results["processed_users"] += 1
            
            self.logger.info(f"定期レポート完了: 成功={results['successful_reports']}, 失敗={results['failed_reports']}")
            
        except Exception as e:
            error_msg = f"定期レポート処理エラー: {str(e)}"
            self.logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results
    
    async def _process_user_pnl_report(self, user_id: str) -> None:
        """個別ユーザーの損益レポート処理"""
        try:
            # ユーザーの全ポートフォリオの損益を計算
            reports = await self.portfolio_service.calculate_all_user_portfolios_pnl(user_id)
            
            if not reports:
                self.logger.info(f"ユーザー {user_id} のポートフォリオが見つかりません")
                return
            
            # Discord通知を送信
            await self._send_pnl_notification(user_id, reports)
            
        except Exception as e:
            self.logger.error(f"ユーザー {user_id} のレポート処理エラー: {e}")
            raise
    
    async def _send_pnl_notification(self, user_id: str, reports: List[PortfolioProfitLossReport]) -> None:
        """損益レポートのDiscord通知を送信"""
        try:
            # 通知メッセージを作成
            embed = self._create_pnl_report_embed(user_id, reports)
            
            # Discord Webhookで送信
            message_data = {
                "embeds": [embed],
                "content": f"<@{user_id}> 定期損益レポートです"
            }
            
            success = await self.discord_handler._send_webhook(
                self.discord_handler.DiscordMessage(**message_data)
            )
            
            if success:
                self.logger.info(f"ユーザー {user_id} への損益レポート送信成功")
            else:
                self.logger.error(f"ユーザー {user_id} への損益レポート送信失敗")
                
        except Exception as e:
            self.logger.error(f"Discord通知送信エラー: {e}")
            raise
    
    def _create_pnl_report_embed(self, user_id: str, reports: List[PortfolioProfitLossReport]) -> Dict[str, Any]:
        """損益レポート用Embed作成"""
        # 全ポートフォリオの合計を計算
        total_purchase_value = sum(r.total_purchase_value for r in reports)
        total_current_value = sum(r.total_current_value for r in reports)
        total_unrealized_pnl = total_current_value - total_purchase_value
        total_unrealized_pnl_percent = (total_unrealized_pnl / total_purchase_value * 100) if total_purchase_value > 0 else 0
        
        # 色を決定（利益=緑、損失=赤）
        color = 0x00FF00 if total_unrealized_pnl >= 0 else 0xFF0000
        
        # 符号付きフォーマット
        pnl_sign = "+" if total_unrealized_pnl >= 0 else ""
        pnl_emoji = "📈" if total_unrealized_pnl >= 0 else "📉"
        
        embed = {
            "title": f"{pnl_emoji} 定期損益レポート",
            "color": color,
            "timestamp": datetime.now(UTC).isoformat(),
            "fields": [
                {
                    "name": "💰 総取得金額",
                    "value": f"¥{total_purchase_value:,.0f}",
                    "inline": True
                },
                {
                    "name": "💎 現在評価額",
                    "value": f"¥{total_current_value:,.0f}",
                    "inline": True
                },
                {
                    "name": "📊 含み損益",
                    "value": f"{pnl_sign}¥{total_unrealized_pnl:,.0f}\n({pnl_sign}{total_unrealized_pnl_percent:.2f}%)",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"ユーザー: {user_id} | 更新時刻: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            }
        }
        
        # ポートフォリオ別詳細を追加
        if len(reports) > 1:
            portfolio_details = ""
            for report in reports:
                p_pnl_sign = "+" if report.total_unrealized_pnl >= 0 else ""
                p_pnl_emoji = "🟢" if report.total_unrealized_pnl >= 0 else "🔴"
                
                portfolio_details += f"{p_pnl_emoji} **{report.portfolio_name}**\n"
                portfolio_details += f"  {p_pnl_sign}¥{report.total_unrealized_pnl:,.0f} ({p_pnl_sign}{report.total_unrealized_pnl_percent:.2f}%)\n"
            
            embed["fields"].append({
                "name": "📁 ポートフォリオ別",
                "value": portfolio_details,
                "inline": False
            })
        
        # 主要銘柄の損益を表示（上位5銘柄）
        all_holdings = []
        for report in reports:
            all_holdings.extend(report.holdings)
        
        # 損益額でソート
        all_holdings.sort(key=lambda x: abs(x.unrealized_pnl), reverse=True)
        top_holdings = all_holdings[:5]
        
        if top_holdings:
            holdings_details = ""
            for holding in top_holdings:
                h_pnl_sign = "+" if holding.unrealized_pnl >= 0 else ""
                h_pnl_emoji = "🟢" if holding.unrealized_pnl >= 0 else "🔴"
                
                holdings_details += f"{h_pnl_emoji} **{holding.symbol}**: {h_pnl_sign}¥{holding.unrealized_pnl:,.0f} "
                holdings_details += f"({h_pnl_sign}{holding.unrealized_pnl_percent:.1f}%)\n"
            
            embed["fields"].append({
                "name": "🏆 主要銘柄（損益額順）",
                "value": holdings_details,
                "inline": False
            })
        
        return embed


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda エントリーポイント"""
    
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # 環境変数から設定を取得
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        if not webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL環境変数が設定されていません")
        
        # 対象ユーザーIDを環境変数から取得（カンマ区切り）
        target_users_str = os.environ.get('TARGET_USERS', '')
        target_users = [user.strip() for user in target_users_str.split(',') if user.strip()]
        
        if not target_users:
            logger.warning("TARGET_USERS環境変数が設定されていません")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "対象ユーザーが設定されていません"})
            }
        
        # 非同期処理を実行
        result = asyncio.run(_async_lambda_handler(webhook_url, target_users))
        
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Lambda実行エラー: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


async def _async_lambda_handler(webhook_url: str, target_users: List[str]) -> Dict[str, Any]:
    """非同期Lambda処理"""
    
    # サービス初期化
    data_provider = StockDataProvider()
    portfolio_service = PortfolioService(data_provider)
    
    async with DiscordHandler(webhook_url) as discord_handler:
        # 定期レポートハンドラー初期化
        scheduled_handler = ScheduledPnLReportHandler(
            portfolio_service, discord_handler, target_users
        )
        
        # 損益レポート生成・送信
        result = await scheduled_handler.generate_and_send_pnl_reports()
        
        return result


# ローカル実行用
if __name__ == "__main__":
    
    # 環境変数設定例
    os.environ['DISCORD_WEBHOOK_URL'] = 'your_webhook_url_here'
    os.environ['TARGET_USERS'] = 'user1,user2,user3'
    
    # テスト実行
    test_event = {}
    test_context = None
    
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2, ensure_ascii=False))