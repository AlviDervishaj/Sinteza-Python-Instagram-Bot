import sys
import GramAddict.core.device_facade as device_facade
import GramAddict.core.utils as utils

deviceId = sys.argv[1]
device = device_facade.DeviceFacade(deviceId, "com.instagram.android")
utils.close_instagram(device)
utils.kill_atx_agent(device)
