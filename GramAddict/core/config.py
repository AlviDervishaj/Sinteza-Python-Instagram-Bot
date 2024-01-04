import logging
import os
import sys
from typing import Optional, Union

import configargparse
import yaml

from GramAddict.core.plugin_loader import PluginLoader

logger = logging.getLogger(__name__)


class Config:
    def __init__(self, first_run=False, **kwargs):
        if kwargs:
            self.args = kwargs
            self.module = True
        else:
            self.args = sys.argv
            self.module = False
        self.config = None
        self.config_list = None
        self.plugins = None
        self.actions = None
        self.special = None
        self.analytics = None
        self.actions_enabled = []
        self.special_enabled = []
        self.analytics_enabled = []
        self.unknown_args = []
        self.debug = False
        self.device_id: Optional[str] = None
        self.app_id: Optional[str] = None
        self.first_run = first_run
        self.username = False

        # Pre-Load Variables Needed for Script Init
        self.load_config()

        if self.module:
            self.debug = self.args.get("debug", False)
            self.username = self.args.get("username", None)
            self.app_id = self.args.get("app_id", "com.instagram.android")
            self.device_id = self.args.get("device_id", None)
        # else:
        #     self.debug = "--debug" in self.args
        #     if "--username" in self.args:
        #         try:
        #             self.username = self.args[self.args.index("--username") + 1]
        #         except IndexError:
        #             logger.warning(
        #                 "Please provide a username with your --username argument. Example: '--username yourusername'"
        #             )
        #             exit(2)
        #     if "--app-id" in self.args:
        #         self.app_id = self.args[self.args.index("--app-id") + 1]
        #     else:
        #         self.app_id = "com.instagram.android"

        # Configure ArgParse
        self.parser = configargparse.ArgumentParser(
            config_file_open_func=lambda filename: open(
                filename, "r", encoding="utf-8"
            ),
            description="GramAddict Instagram Bot",
        )
        self.parser.add_argument(
            "--config",
            required=False,
            is_config_file=True,
            help="config file path",
        )

        # on first run, we must wait to proceed with loading
        if not self.first_run:
            self.load_plugins()
            self.parse_args()

    def load_config(self):
        if self.module:
            if not self.args.get("config", False):
                return
        elif "--config" not in self.args:
            return
        try:
            if self.module:
                file_name = self.args.get("config")
            else:
                file_name = self.args[self.args.index("--config") + 1]
            if not file_name.endswith((".yml", ".yaml")):
                logger.error(
                    f"You have to specify a *.yml / *.yaml config file path (For example 'accounts/your_account_name/config.yml')! \nYou entered: {file_name}, abort."
                )

                sys.exit(1)
            with open(file_name, encoding="utf-8") as fin:
                self.config_list = [line.strip() for line in fin]
                fin.seek(0)
                self.config = yaml.safe_load(fin)
        except IndexError:
            logger.warning(
                "Please provide a filename with your --config argument. Example: '--config accounts/yourusername/config.yml'"
            )

            exit(2)
        except FileNotFoundError:
            logger.error(
                f"I can't see the file '{file_name}'! Double check the spelling or if you're calling the bot from the right folder. (You're there: '{os.getcwd()}')"
            )

            exit(2)
        self.debug = self.config.get("debug", False)
        self.username = self.config.get("username", None)
        self.app_id = self.config.get("app_id", "com.instagram.android")
        self.device_id = self.config.get("device", None)

    def load_plugins(self):
        self.plugins = PluginLoader("GramAddict.plugins", self.first_run).plugins
        self.special = {}
        self.actions = {}
        self.analytics = {}
        for plugin in self.plugins:
            if plugin.arguments:
                for arg in plugin.arguments:
                    try:
                        action = arg.get("action", None)
                        if action:
                            self.parser.add_argument(
                                arg["arg"],
                                help=arg["help"],
                                action=arg.get("action", None),
                            )
                        else:
                            self.parser.add_argument(
                                arg["arg"],
                                nargs=arg["nargs"],
                                help=arg["help"],
                                metavar=arg["metavar"],
                                default=arg["default"],
                            )
                        if arg.get("operation", False):
                            self.actions[arg["arg"][2:]] = plugin
                        if arg.get("special", False):
                            self.special[arg["arg"][2:]] = plugin
                        if arg.get("analytics", False):
                            self.analytics[arg["arg"][2:]] = plugin
                    except Exception as e:
                        logger.error(
                            f"Error while importing arguments of plugin {plugin.__class__.__name__}. Error: Missing key from arguments dictionary - {e}"
                        )

    def parse_args(self):
        def _is_legacy_arg(arg):
            if arg in ["interact", "hashtag-likers"]:
                if self.first_run:
                    logger.warning(
                        f"You are using a legacy argument {arg} that is no longer supported. It will not be used. Please refer to https://docs.gramaddict.org/#/configuration?id=arguments."
                    )
                return True
            return False

        if self.module:
            if self.first_run:
                logger.debug("Arguments used:")
                if self.config:
                    logger.debug(f"Config used: {self.config}")
                if not len(self.args) > 0:
                    self.parser.print_help()
                    exit(0)
        else:
            if self.first_run:
                logger.debug(f"Arguments used: {' '.join(sys.argv[1:])}")
                if self.config:
                    logger.debug(f"Config used: {self.config}")
                if not len(sys.argv) > 1:
                    self.parser.print_help()
                    exit(0)
        if self.module:
            arg_str = ""
            for k, v in self.args.items():
                arg_str += f" --{k.replace('_', '-')} {v}"
            self.args, self.unknown_args = self.parser.parse_known_args(args=arg_str)
        else:
            self.args, self.unknown_args = self.parser.parse_known_args()
        if "run" in self.unknown_args:
            self.unknown_args.remove("run")
        if self.unknown_args and self.first_run:
            logger.error(
                "Unknown arguments: " + ", ".join(str(arg) for arg in self.unknown_args)
            )
            self.parser.print_help()
            for arg in self.unknown_args:
                if "detect-block" in arg:
                    logger.error(
                        "Please replace the line 'detect-block: true/false' in your config file *.yml with 'disable-block-detection: true/false'"
                    )
                    break
            exit(0)
        # We need to maintain the order of plugins as defined
        # in config or sys.argv
        if self.config_list is not None:
            config_list = [
                item for item in self.config_list if item and not item.startswith("#")
            ]
        else:
            config_list = None
        for item in config_list or sys.argv:
            item = item.split(":")[0].replace("--", "")
            if (
                item in self.actions
                and getattr(self.args, item.replace("-", "_"))
                and not _is_legacy_arg(item)
            ):
                self.actions_enabled.append(item)
            elif (
                item in self.special
                and getattr(self.args, item.replace("-", "_"))
                and not _is_legacy_arg(item)
            ):
                self.special_enabled.append(item)
            elif (
                item in self.analytics
                and getattr(self.args, item.replace("-", "_"))
                and not _is_legacy_arg(item)
            ):
                self.analytics_enabled.append(item)
