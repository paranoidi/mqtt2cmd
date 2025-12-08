from __future__ import annotations

import argparse
import logging
import shutil
import signal
import sys
import time
from pathlib import Path
from textwrap import dedent

from mqtt2cmd.config import load_config
from mqtt2cmd.executor import CommandExecutor
from mqtt2cmd.mqtt_client import MQTTClient


def setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def generate_service_file(config_path: Path, service_name: str = "mqtt2cmd") -> None:
    """
    Generate a systemd user service file and write it to the correct location.

    Args:
        config_path: Path to the configuration file to use.
        service_name: Name of the service (default: mqtt2cmd).
    """
    mqtt2cmd_path = shutil.which("mqtt2cmd")
    if mqtt2cmd_path is None:
        print("Error: mqtt2cmd command not found in PATH")
        print("Make sure mqtt2cmd is installed or use 'uv run mqtt2cmd' in the service file")
        sys.exit(1)

    config_abs_path = config_path.resolve()
    if not config_abs_path.exists():
        print(f"Error: Configuration file not found: {config_abs_path}")
        sys.exit(1)

    home = Path.home()
    systemd_user_dir = home / ".config" / "systemd" / "user"
    systemd_user_dir.mkdir(parents=True, exist_ok=True)

    service_file = systemd_user_dir / f"{service_name}.service"

    service_content = dedent(f"""
        [Unit]
        Description=MQTT to Command Executor
        After=network.target

        [Service]
        Type=simple
        ExecStart={mqtt2cmd_path} run --config {config_abs_path}
        Restart=on-failure
        RestartSec=5

        [Install]
        WantedBy=default.target
        """).strip()

    service_file.write_text(service_content)
    print(f"Service file created: {service_file}")
    print()
    print("To enable and start the service, run:")
    print(f"  systemctl --user enable {service_name}.service")
    print(f"  systemctl --user start {service_name}.service")
    print()
    print("To check the service status:")
    print(f"  systemctl --user status {service_name}.service")


def run_service(config_path: Path) -> None:
    """Run the MQTT command executor service."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)

        logger.info(f"Loaded {len(config.commands)} command configuration(s)")

        executor = CommandExecutor()
        mqtt_client = MQTTClient(config, executor)

        def signal_handler(signum: int, frame: object) -> None:
            """Handle shutdown signals."""
            logger.info("Received shutdown signal, stopping...")
            mqtt_client.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Starting MQTT client...")
        mqtt_client.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping...")
            mqtt_client.stop()

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the MQTT command executor."""
    parser = argparse.ArgumentParser(description="Execute commands based on MQTT messages")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    run_parser = subparsers.add_parser("run", help="Run the MQTT command executor")
    run_parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path to configuration file (default: config.yml)",
    )

    install_parser = subparsers.add_parser(
        "install-service", help="Generate systemd user service file"
    )
    install_parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path to configuration file (default: config.yml)",
    )
    install_parser.add_argument(
        "--service-name",
        type=str,
        default="mqtt2cmd",
        help="Name of the systemd service (default: mqtt2cmd)",
    )

    args = parser.parse_args()

    if args.command == "install-service":
        config_path = Path(args.config)
        service_name = getattr(args, "service_name", "mqtt2cmd")
        generate_service_file(config_path, service_name)
    elif args.command == "run":
        config_path = Path(args.config)
        run_service(config_path)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
