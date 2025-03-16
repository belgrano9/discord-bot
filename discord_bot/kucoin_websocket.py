import json
import threading
import time
import uuid
import websocket
from typing import Dict, List, Any, Callable, Optional
from loguru import logger
from kucoin_handler import KucoinAPI    


class KucoinWebsocketClient:
    """
    WebSocket client for KuCoin API that handles connection management,
    authentication, subscription, and message handling.
    """
    
    def __init__(self, 
                kucoin_api,
                on_message: Optional[Callable] = None,
                on_error: Optional[Callable] = None,
                on_close: Optional[Callable] = None,
                is_private: bool = False):
        """
        Initialize the KuCoin WebSocket client.
        
        Args:
            kucoin_api: KucoinAPI instance for authentication and token retrieval
            on_message: Callback function for message handling
            on_error: Callback function for error handling
            on_close: Callback function for connection close events
            is_private: Whether to use private channels (requires authentication)
        """
        self.kucoin_api = kucoin_api
        self.is_private = is_private
        self.ws = None
        self.ws_thread = None
        self.keep_running = False
        self.ping_interval = 30  # seconds
        self.ping_thread = None
        self.subscriptions = set()
        
        # Set up callbacks
        self.on_message_callback = on_message
        self.on_error_callback = on_error
        self.on_close_callback = on_close
        
        # Store connection info
        self.token = None
        self.server_url = None
        self.connect_id = str(uuid.uuid4())
        
    def connect(self):
        """
        Establish a WebSocket connection to KuCoin.
        
        This method retrieves a token, establishes the WebSocket connection,
        and starts the background threads for ping and message handling.
        """
        try:
            # Get WebSocket token
            if self.is_private:
                response = self.kucoin_api._make_request(
                    method="POST", 
                    endpoint="/api/v1/bullet-private"
                )
            else:
                response = self.kucoin_api._make_request(
                    method="POST", 
                    endpoint="/api/v1/bullet-public"
                )
            
            if not response or "data" not in response:
                raise ValueError(f"Failed to get WebSocket token: {response}")
            
            # Extract connection details
            data = response["data"]
            self.token = data["token"]
            
            # Use the first server in the instanceServers list
            if "instanceServers" in data and len(data["instanceServers"]) > 0:
                server = data["instanceServers"][0]
                self.server_url = f"{server['endpoint']}?token={self.token}&connectId={self.connect_id}"
                self.ping_interval = server.get("pingInterval", 30000) / 1000  # Convert to seconds
            else:
                raise ValueError("No WebSocket server instances available")
            
            # Create WebSocket connection
            logger.info(f"Connecting to WebSocket: {self.server_url}")
            self.ws = websocket.WebSocketApp(
                self.server_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start WebSocket in a separate thread
            self.keep_running = True
            self.ws_thread = threading.Thread(target=self._ws_thread)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {str(e)}")
            return False
            
    def disconnect(self):
        """
        Disconnect from the WebSocket and clean up resources.
        """
        self.keep_running = False
        if self.ws:
            self.ws.close()
        
        # Wait for threads to finish
        if self.ping_thread and self.ping_thread.is_alive():
            self.ping_thread.join(timeout=1)
            
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=1)
            
        logger.info("WebSocket disconnected")
        
    def subscribe(self, topic: str, private_channel: bool = False, response: bool = True):
        """
        Subscribe to a WebSocket topic.
        
        Args:
            topic: The topic to subscribe to (e.g., "/market/ticker:BTC-USDT")
            private_channel: Whether to use private channel
            response: Whether to request an acknowledgment
            
        Returns:
            The message ID of the subscription request
        """
        message_id = int(time.time() * 1000)
        message = {
            "id": message_id,
            "type": "subscribe",
            "topic": topic,
            "privateChannel": private_channel,
            "response": response
        }
        
        # Send subscription request
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(message))
            self.subscriptions.add(topic)
            logger.info(f"Subscribed to topic: {topic}")
            return message_id
        else:
            logger.error("WebSocket not connected, cannot subscribe")
            return None
            
    def unsubscribe(self, topic: str, private_channel: bool = False, response: bool = True):
        """
        Unsubscribe from a WebSocket topic.
        
        Args:
            topic: The topic to unsubscribe from
            private_channel: Whether it's a private channel
            response: Whether to request an acknowledgment
            
        Returns:
            The message ID of the unsubscription request
        """
        message_id = int(time.time() * 1000)
        message = {
            "id": message_id,
            "type": "unsubscribe",
            "topic": topic,
            "privateChannel": private_channel,
            "response": response
        }
        
        # Send unsubscription request
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(message))
            if topic in self.subscriptions:
                self.subscriptions.remove(topic)
            logger.info(f"Unsubscribed from topic: {topic}")
            return message_id
        else:
            logger.error("WebSocket not connected, cannot unsubscribe")
            return None
    
    def _ws_thread(self):
        """
        Background thread for the WebSocket connection.
        """
        while self.keep_running:
            try:
                self.ws.run_forever()
                
                # If we get here, the connection was closed
                if self.keep_running:
                    logger.warning("WebSocket connection lost, attempting to reconnect...")
                    time.sleep(3)  # Wait before reconnecting
                    self.connect()
                    
            except Exception as e:
                logger.error(f"Error in WebSocket thread: {str(e)}")
                time.sleep(3)
                
        logger.info("WebSocket thread terminated")
                
    def _start_ping_thread(self):
        """
        Start a background thread to send ping messages.
        """
        if self.ping_thread and self.ping_thread.is_alive():
            return
            
        self.ping_thread = threading.Thread(target=self._ping_loop)
        self.ping_thread.daemon = True
        self.ping_thread.start()
        
    def _ping_loop(self):
        """
        Loop to send ping messages at regular intervals.
        """
        while self.keep_running and self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                message = {
                    "id": int(time.time() * 1000),
                    "type": "ping"
                }
                self.ws.send(json.dumps(message))
                time.sleep(self.ping_interval)
            except Exception as e:
                logger.error(f"Error sending ping: {str(e)}")
                break
                
        logger.info("Ping thread terminated")
                
    def _on_open(self, ws):
        """
        Callback for WebSocket open event.
        """
        logger.info("WebSocket connection established")
        self._start_ping_thread()
        
        # Resubscribe to previous topics
        for topic in list(self.subscriptions):
            self.subscribe(topic)
            
    def _on_message(self, ws, message):
        """
        Callback for WebSocket message event.
        """
        try:
            data = json.loads(message)
            
            # Handle welcome message
            if data.get("type") == "welcome":
                logger.info("Received welcome message")
                
            # Handle pong message
            elif data.get("type") == "pong":
                pass  # Silent handling of pong
                
            # Handle ack message
            elif data.get("type") == "ack":
                logger.debug(f"Received ack for message {data.get('id')}")
                
            # Handle regular data messages
            else:
                # Pass to user callback if defined
                if self.on_message_callback:
                    self.on_message_callback(data)
                else:
                    logger.debug(f"Received message: {data}")
                    
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            
    def _on_error(self, ws, error):
        """
        Callback for WebSocket error event.
        """
        logger.error(f"WebSocket error: {str(error)}")
        if self.on_error_callback:
            self.on_error_callback(error)
            
    def _on_close(self, ws, close_status_code, close_msg):
        """
        Callback for WebSocket close event.
        """
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        if self.on_close_callback:
            self.on_close_callback(close_status_code, close_msg)


if __name__ == "__main__":

    import os
    
    key = os.getenv("KUCOIN_API_KEY", "")
    secret = os.getenv("KUCOIN_API_SECRET", "")
    passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "")

    # Initialize KuCoin API
    kucoin_api = KucoinAPI(key, secret, passphrase)

    # Define a message handler
    def handle_message(message):
        print(f"Received message: {message}")

    # Create WebSocket client
    ws_client = KucoinWebsocketClient(
        kucoin_api=kucoin_api,
        on_message=handle_message,
        is_private=False  # For public channels
    )

    # Connect and subscribe to topics
    if ws_client.connect():
        # Subscribe to ticker for BTC-USDT
        ws_client.subscribe("/market/ticker:BTC-USDT")
        
        try:
            # Keep the main thread running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Clean disconnect on exit
            ws_client.disconnect()
