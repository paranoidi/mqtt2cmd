from __future__ import annotations

import logging
import threading
import time

import paho.mqtt.client as mqtt

from mqtt2cmd.config import AppConfig, CommandConfig
from mqtt2cmd.executor import CommandExecutor

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT client that subscribes to topics and executes commands on messages."""

    def __init__(self, config: AppConfig, executor: CommandExecutor) -> None:
        """
        Initialize MQTT client.

        Args:
            config: Application configuration.
            executor: Command executor instance.
        """
        self.config = config
        self.executor = executor
        self.client: mqtt.Client | None = None
        self.topic_to_command: dict[str, CommandConfig] = {
            cmd.topic: cmd for cmd in config.commands
        }
        self._running = False
        self._lock = threading.Lock()
        self._connected_event = threading.Event()
        self._connection_successful = False

    def start(self) -> None:
        """Start the MQTT client and begin listening for messages."""
        self._running = True
        self._connect_and_subscribe()

    def stop(self) -> None:
        """Stop the MQTT client and disconnect."""
        with self._lock:
            self._running = False
            if self.client:
                self.client.disconnect()
                self.client.loop_stop()

    def _connect_and_subscribe(self) -> None:
        """Connect to broker and subscribe to all configured topics."""
        while self._running:
            try:
                if self.client:
                    self.client.loop_stop()
                    self.client = None

                self._connected_event.clear()
                self._connection_successful = False

                self.client = mqtt.Client()
                self.client.on_connect = self._on_connect
                self.client.on_message = self._on_message
                self.client.on_disconnect = self._on_disconnect

                broker = self.config.broker
                if broker.username and broker.password:
                    self.client.username_pw_set(broker.username, broker.password)

                logger.info(f"Connecting to MQTT broker at {broker.host}:{broker.port}")
                self.client.connect(broker.host, broker.port, 60)
                self.client.loop_start()

                # Wait for connection to be established (with timeout)
                if self._connected_event.wait(timeout=10):
                    # Check if connection was actually successful
                    if self._connection_successful and self.client:
                        # Connection successful, wait until disconnected
                        while self._running and self.client.is_connected():
                            time.sleep(1)
                    else:
                        # Connection failed, clean up and retry
                        if self.client:
                            self.client.loop_stop()
                            self.client = None
                else:
                    logger.warning("Connection timeout, will retry...")
                    if self.client:
                        self.client.loop_stop()
                        self.client = None

                if not self._running:
                    break

                logger.info("Connection lost, will retry...")

            except Exception as e:
                logger.error(f"Error connecting to MQTT broker: {e}")
                if self.client:
                    try:
                        self.client.loop_stop()
                    except Exception:
                        pass
                    self.client = None
                if self._running:
                    logger.info("Retrying connection in 5 seconds...")
                    time.sleep(5)

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        """
        Callback for when the client connects to the broker.

        Args:
            client: MQTT client instance.
            userdata: User data (unused).
            flags: Connection flags (unused).
            rc: Return code. 0 indicates success.
        """
        if rc == 0:
            logger.info("Connected to MQTT broker")
            for topic in self.topic_to_command.keys():
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
            self._connection_successful = True
            self._connected_event.set()
        else:
            logger.error(f"Failed to connect to MQTT broker with return code {rc}")
            self._connection_successful = False
            self._connected_event.set()  # Set anyway to unblock the wait

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        """
        Callback for when a message is received.

        Args:
            client: MQTT client instance.
            userdata: User data (unused).
            msg: Received MQTT message.
        """
        topic = msg.topic
        command_config = self.topic_to_command.get(topic)

        if not command_config:
            logger.warning(f"Received message on unconfigured topic: {topic}")
            return

        logger.info(f"Received message on topic: {topic}")
        thread = threading.Thread(
            target=self._execute_command_async,
            args=(command_config, msg.payload, topic),
            daemon=True,
        )
        thread.start()

    def _execute_command_async(
        self, command_config: CommandConfig, message_payload: bytes, topic: str
    ) -> None:
        """
        Execute a command asynchronously in a separate thread.

        Args:
            command_config: Configuration for the command to execute.
            message_payload: JSON array payload from MQTT message.
            topic: MQTT topic the message was received on.
        """
        execution_result = self.executor.execute(command_config, message_payload)

        with self._lock:
            client = self.client

        if client:
            if command_config.stdout:
                try:
                    result = client.publish(command_config.stdout, execution_result.stdout)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(
                            f"Published stdout to topic {command_config.stdout} "
                            f"for command on topic {topic}"
                        )
                    else:
                        logger.error(
                            f"Failed to publish stdout to topic {command_config.stdout}: "
                            f"MQTT error code {result.rc}"
                        )
                except Exception as e:
                    logger.error(
                        f"Error publishing stdout to topic {command_config.stdout}: {e}",
                        exc_info=True,
                    )

            if command_config.stderr:
                try:
                    result = client.publish(command_config.stderr, execution_result.stderr)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(
                            f"Published stderr to topic {command_config.stderr} "
                            f"for command on topic {topic}"
                        )
                    else:
                        logger.error(
                            f"Failed to publish stderr to topic {command_config.stderr}: "
                            f"MQTT error code {result.rc}"
                        )
                except Exception as e:
                    logger.error(
                        f"Error publishing stderr to topic {command_config.stderr}: {e}",
                        exc_info=True,
                    )

    def _on_disconnect(self, client: mqtt.Client, userdata: object, rc: int) -> None:
        """
        Callback for when the client disconnects from the broker.

        Args:
            client: MQTT client instance.
            userdata: User data (unused).
            rc: Disconnect reason code.
        """
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (rc={rc})")
        else:
            logger.info("Disconnected from MQTT broker")
