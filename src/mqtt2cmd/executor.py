from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Sequence

from mqtt2cmd.config import CommandConfig

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Executes shell commands with argument substitution from MQTT messages."""

    def execute(self, command_config: CommandConfig, message_payload: bytes) -> None:
        """
        Execute a command with arguments substituted from the message payload.

        Args:
            command_config: Configuration for the command to execute.
            message_payload: JSON array payload from MQTT message.
        """
        try:
            payload_str = message_payload.decode("utf-8")
            args_array = json.loads(payload_str)

            if not isinstance(args_array, list):
                logger.error(
                    f"Invalid payload format for topic {command_config.topic}: "
                    f"expected JSON array, got {type(args_array).__name__}"
                )
                return

            substituted_args = self._substitute_args(command_config.args, args_array)
            full_command = [command_config.cmd] + substituted_args

            logger.info(
                f"Executing command for topic {command_config.topic}: {' '.join(full_command)}"
            )

            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                logger.info(
                    f"Command succeeded for topic {command_config.topic}. "
                    f"Output: {result.stdout[:200]}"
                )
            else:
                logger.warning(
                    f"Command failed for topic {command_config.topic} "
                    f"(exit code {result.returncode}). "
                    f"Stderr: {result.stderr[:200]}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON payload for topic {command_config.topic}: {e}")
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode message payload for topic {command_config.topic}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error executing command for topic {command_config.topic}: {e}",
                exc_info=True,
            )

    def _substitute_args(self, args: Sequence[str], payload_args: Sequence[str]) -> list[str]:
        """
        Substitute placeholders in args with values from payload_args.

        Args:
            args: Command arguments with placeholders like "$1", "$2", etc.
            payload_args: Array of values from the message payload.

        Returns:
            List of arguments with placeholders substituted.
        """
        substituted = []
        for arg in args:
            if arg.startswith("$") and arg[1:].isdigit():
                index = int(arg[1:]) - 1
                if 0 <= index < len(payload_args):
                    substituted.append(str(payload_args[index]))
                else:
                    logger.warning(
                        f"Placeholder {arg} references index {index + 1}, "
                        f"but payload only has {len(payload_args)} element(s). Ignoring."
                    )
            else:
                substituted.append(arg)
        return substituted
