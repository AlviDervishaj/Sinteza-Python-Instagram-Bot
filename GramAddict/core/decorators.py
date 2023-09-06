import functools
import logging
import sys
import traceback
from datetime import datetime
from enum import Enum, auto
from http.client import HTTPException
from socket import timeout

from colorama import Fore, Style
from uiautomator2.exceptions import UiObjectNotFoundError

from GramAddict.core.device_facade import DeviceFacade
from GramAddict.core.report import print_full_report
from GramAddict.core.utils import (
    EmptyList,
    check_if_crash_popup_is_there,
    close_instagram,
    open_instagram,
    random_sleep,
    save_crash,
    stop_bot,
)
from GramAddict.core.views import TabBarView

logger = logging.getLogger(__name__)


class Restart(Enum):
    LOCAL_CRASH = auto()
    APP_CRASH = auto()
    CTRL_C = auto()
    BLOCK_DIALOG = auto()


def run_safely(device, sessions, configs):
    def actual_decorator(func):
        def wrapper(*args, **kwargs):
            session_state = sessions[-1]
            try:
                func(*args, **kwargs)
            except KeyboardInterrupt:
                try:
                    # Catch Ctrl-C and ask if user wants to pause execution
                    logger.info(
                        "CTRL-C detected . . .",
                        extra={"color": f"{Style.BRIGHT}{Fore.YELLOW}"},
                    )
                    logger.info(
                        f"-------- PAUSED: {datetime.now().strftime('%H:%M:%S')} --------",
                        extra={"color": f"{Style.BRIGHT}{Fore.YELLOW}"},
                    )
                    logger.info(
                        "NOTE: This is a rudimentary pause. It will restart the action, while retaining session data.",
                        extra={"color": Style.BRIGHT},
                    )
                    logger.info(
                        "Press RETURN to resume or CTRL-C again to Quit: ",
                        extra={"color": Style.BRIGHT},
                    )

                    input("")

                    logger.info(
                        f"-------- RESUMING: {datetime.now().strftime('%H:%M:%S')} --------",
                        extra={"color": f"{Style.BRIGHT}{Fore.YELLOW}"},
                    )
                    TabBarView(device).navigate_to_profile()
                except KeyboardInterrupt:
                    stop_bot(device, sessions, session_state)
                    return Restart.CTRL_C

            except DeviceFacade.AppHasCrashed:
                logger.warning("App has crashed / has been closed!")
                restart(
                    device,
                    sessions,
                    session_state,
                    configs,
                    normal_crash=False,
                    print_traceback=False,
                )
                return Restart.APP_CRASH

            except DeviceFacade.RelogAfterBlock:
                logger.info("Restarting activities...")
                return Restart.BLOCK_DIALOG

            except (
                DeviceFacade.JsonRpcError,
                IndexError,
                HTTPException,
                timeout,
                UiObjectNotFoundError,
                EmptyList,
            ):
                restart(
                    device,
                    sessions,
                    session_state,
                    configs,
                )
                return Restart.LOCAL_CRASH

            except Exception as e:
                logger.error(traceback.format_exc())
                for exception_line in traceback.format_exception_only(type(e), e):
                    logger.critical(
                        f"'{exception_line}' -> This kind of exception will stop the bot (no restart)."
                    )
                logger.info(
                    f"List of running apps: {', '.join(device.deviceV2.app_list_running())}"
                )
                save_crash(device)
                close_instagram(device)
                print_full_report(sessions, configs.args.scrape_to_file)
                sessions.persist(directory=session_state.my_username)
                raise e from e

        return wrapper

    return actual_decorator


def restart(
    device: DeviceFacade,
    sessions,
    session_state,
    configs,
    normal_crash: bool = True,
    print_traceback: bool = True,
):
    if print_traceback:
        logger.error(traceback.format_exc())
        save_crash(device)
    logger.info(
        f"List of running apps: {', '.join(device.deviceV2.app_list_running())}."
    )
    if configs.args.count_app_crashes or normal_crash:
        session_state.totalCrashes += 1
        if session_state.check_limit(
            limit_type=session_state.Limit.CRASHES, output=True
        ):
            logger.error(
                "Reached crashes limit. Bot has crashed too much! Please check what's going on."
            )
            stop_bot(device, sessions, session_state)
        logger.info("Something unexpected happened. Let's try again.")
    close_instagram(device)
    check_if_crash_popup_is_there(device)
    random_sleep()
    if not open_instagram(device):
        print_full_report(sessions, configs.args.scrape_to_file)
        sessions.persist(directory=session_state.my_username)
        sys.exit(2)
    TabBarView(device).navigate_to_profile()


def retry(max_reties, exceptions):
    """
    Retries the wrapped function n times if the listed exception is thrown
    """

    def decorator(func):
        @functools.wraps(func)
        def fn(*args, **kwargs):
            n_reties = 1
            while n_reties < max_reties + 1:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    logger.warning(
                        f"{func.__name__} failed due to {exceptions[0].__name__}. Attempt {n_reties}/{max_reties}"
                    )
                    n_reties += 1
            return None

        return fn

    return decorator
