import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get('enabled', True)
    
    def notify(self, title: str, success: bool, error_msg: str = None):
        if not self.enabled:
            logger.info("Email notification disabled")
            return
        
        subject = f"[Video Monitor] {'✓' if success else '✗'} {title}"
        body = f"""
视频监控通知

视频标题：{title}
下载状态：{'成功' if success else '失败'}
时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{f"错误信息：{error_msg}" if error_msg else ""}
        """
        
        try:
            msg = MimeMultipart()
            msg["From"] = self.config.get('sender')
            msg["To"] = self.config.get('receiver')
            msg["Subject"] = subject
            msg.attach(MimeText(body.strip(), "plain"))
            
            with smtplib.SMTP(self.config.get('smtp_server'), self.config.get('smtp_port', 587)) as server:
                server.starttls()
                server.login(self.config.get('sender'), self.config.get('password'))
                server.send_message(msg)
            logger.info(f"Email sent for {title}")
        except Exception as e:
            logger.error(f"Email failed: {e}")
