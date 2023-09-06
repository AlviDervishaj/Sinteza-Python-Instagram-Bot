import logging
import re
import time
from subprocess import PIPE, run

from GramAddict.core.plugin_loader import Plugin
from GramAddict.core.resources import AndroidElements

logger = logging.getLogger(__name__)


class RotateIp(Plugin):
    """Rotate IP by switching to airplane mode and back"""

    def __init__(self):
        super().__init__()
        self.description = "Rotate IP by switching to airplane mode and back"
        self.arguments = [
            {
                "arg": "--rotate-ip",
                "help": "rotate the ip by switching to airplane mode and back. Note that this is device specific and may not work!",
                "action": "store_true",
                "operation": False,
                "special": True,
            }
        ]

    def get_ip(self):
        ip = None
        time.sleep(5)
        output = self._execute_cmd(self.rmnet0)
        if output:
            regex = r"inet (?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            try:
                ip = re.search(regex, output).group("ip")
            except AttributeError:
                logger.error("Could not find ip!")
        return ip

    def rotate_ip(self):
        logger.debug("Open settings")
        self._execute_cmd(self.airplane_mode)
        switcher = self.device.find(resourceIdMatches=AndroidElements.SWITCH_WIDGET)
        if switcher.get_checked():
            logger.debug("Already in airplane mode! Switch off as starting point")
            switcher.click()
        old_ip = self.get_ip()
        logger.debug("Switch to airplane mode")
        switcher.click()
        logger.debug("Wait for 5 seconds...")
        time.sleep(5)
        logger.debug("Switch back")
        switcher.click()
        new_ip = self.get_ip()
        logger.debug("Back")
        self.device.back()
        logger.debug("Done!")
        return old_ip, new_ip

    def _execute_cmd(self, cmd):
        proc = run(cmd, shell=True, stdout=PIPE)
        return proc.stdout.decode("utf-8")

    def run(self, device):
        self.device = device
        self._adb = (
            f"adb -s {self.device.device_id}" if self.device.device_id else "adb"
        )
        self.airplane_mode = (
            f"{self._adb} shell am start -a android.settings.AIRPLANE_MODE_SETTINGS"
        )
        self.rmnet0 = f"{self._adb} shell ip addr show rmnet0"

        logger.info("Rotating IP...")
        old_ip, new_ip = self.rotate_ip()
        if old_ip != new_ip:
            logger.info(f"IP changed from {old_ip} to {new_ip}")
        else:
            logger.error("IP did not change! (Are you on WIFI?)")
