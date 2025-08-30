from pydantic import BaseModel
from typing import Optional
from datetime import datetime



class TradingSignalApproval(BaseModel):
    """Standardized signal format for Discord approval"""
    signal_id: str
    action: str  # "SHORT" or "LONG"
    pair: str    # "BTCUSDT/ETHUSDT"
    confidence: float  # 0.0-1.0
    spread: float
    threshold: float
    beta: float #hedge ratio
    mu: float #mean reversion param
    btc_price: float
    eth_price: float
    timestamp: datetime
    expires_minutes: int = 60

    def to_discord_message(self) -> str:
        """Convert to Discord approval message format"""
        confidence_pct = self.confidence * 100
        
        message = f"""🚨 **TRADING SIGNAL APPROVAL NEEDED** 🚨
⏰ SIGNAL APPROVAL REQUIRED
🔴 {self.action} signal for {self.pair}

📊 Signal Details        🛠️ Parameters
Type: {self.action}             Beta: {self.beta:.4f}
Spread: {self.spread:.6f}        Mu: {self.mu:.6f}
Threshold: ±{self.threshold:.6f}    Pair: {self.pair}
Confidence: {confidence_pct:.1f}%

💰 Entry Prices
BTCUSDT: ${self.btc_price:.2f}
ETHUSDT: ${self.eth_price:.2f}

⚡ Action Required
React with ✅ to APPROVE this signal
React with ❌ to REJECT this signal
⏰ Expires in {self.expires_minutes} minutes

Signal ID: {self.signal_id} • Awaiting Approval • {self.timestamp.strftime('%d/%m/%Y %H:%M')}

```json
{self.model_dump_json()}
```"""
        return message

    @classmethod
    def from_discord_message(cls, content: str) -> Optional["TradingSignalApproval"]:
        """Parse signal from Discord message with JSON block"""
        try:
            start = content.find('```json\n') + 8
            end = content.find('\n```', start)
            
            if start > 7 and end > start:
                json_str = content[start:end]
                return cls.model_validate_json(json_str)
        except Exception:
            pass
        return None
    

class PairsTradingSignal(TradingSignalApproval):
    beta: float  # hedge ratio
    mu: float    # mean reversion parameter
    # Inherits all other fields
    
    def calculate_position_sizes(self, total_capital: float) -> dict:
        """Calculate position sizes based on beta and capital allocation"""
        allocation = total_capital * 0.10  # 10% allocation
        # Placeholder for position sizing logic
        return {
            "btc_size": ...,
            "eth_size": ...
        }