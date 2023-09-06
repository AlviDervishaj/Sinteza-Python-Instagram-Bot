import logging
import time
from random import seed

from colorama import Fore, Style

from GramAddict.core.decorators import run_safely
from GramAddict.core.device_facade import Direction
from GramAddict.core.interaction import _send_PM
from GramAddict.core.navigation import nav_to_blogger
from GramAddict.core.plugin_loader import Plugin
from GramAddict.core.resources import ResourceID as resources
from GramAddict.core.scroll_end_detector import ScrollEndDetector
from GramAddict.core.utils import get_value, inspect_current_view

logger = logging.getLogger(__name__)

# Script Initialization
seed()


class WelcomeDmNewFollowers(Plugin):
    """Handles the functionality of welcoming new followers"""

    def __init__(self):
        super().__init__()
        self.description = "Handles the functionality of welcoming new followers"
        self.arguments = [
            {
                "arg": "--welcoming",
                "nargs": None,
                "help": "send a welcome message to new followers to the number of user provided",
                "metavar": "5-10",
                "default": "5-10",
                "operation": True,
            },
            {
                "arg": "--max-welcoming-skips",
                "nargs": None,
                "help": "how many skips before ending job",
                "metavar": "5-10",
                "default": None,
            },
            {
                "arg": "--check-chat-before-welcoming",
                "help": "check if the chat is empty before welcoming",
                "action": "store_true",
            },
        ]

    def run(self, device, configs, storage, sessions, profile_filter, plugin):
        class State:
            def __init__(self):
                pass

            is_job_completed = False

        self.device_id = configs.args.device
        self.state = None
        self.sessions = sessions
        self.session_state = sessions[-1]
        self.args = configs.args
        self.ResourceID = resources(self.args.app_id)
        self.current_mode = plugin
        self.profile_filter = profile_filter

        # IMPORTANT: in each job we assume being on the top of the Profile tab already
        users_to_welcoming = get_value(count=self.args.welcoming, name=None, default=5)
        max_skips = get_value(
            count=self.args.max_welcoming_skips, name=None, default=None
        )

        # Start

        (
            active_limits_reached,
            _,
            actions_limit_reached,
        ) = self.session_state.check_limit(limit_type=self.session_state.Limit.ALL)
        limit_reached = active_limits_reached or actions_limit_reached

        self.state = State()
        my_username = self.session_state.my_username
        logger.info(
            f"Welcoming {users_to_welcoming} users of {my_username}.",
            extra={"color": f"{Style.BRIGHT}"},
        )
        scroll_end_detector = ScrollEndDetector()

        @run_safely(
            device=device,
            sessions=self.sessions,
            configs=configs,
        )
        def job():
            self.welcoming_followers(
                device=device,
                current_job="followers",
                my_username=my_username,
                session_state=self.session_state,
                users_to_welcoming=users_to_welcoming,
                max_skips=max_skips,
                scroll_end_detector=scroll_end_detector,
                storage=storage,
                profile_filter=profile_filter,
            )
            self.state.is_job_completed = True

        while not self.state.is_job_completed and not limit_reached:
            job()

        if limit_reached:
            logger.info("Ending session.")
            self.session_state.check_limit(
                limit_type=self.session_state.Limit.ALL, output=True
            )

    def welcoming_followers(
        self,
        device,
        current_job,
        my_username: str,
        session_state,
        users_to_welcoming: int,
        max_skips: int,
        scroll_end_detector,
        storage,
        profile_filter,
    ):
        # navigate to user profile
        nav_to_blogger(device, None, current_job)
        skipped_list_limit = get_value(self.args.skipped_list_limit, None, 5)
        skipped_fling_limit = get_value(self.args.fling_when_skipped, None, 0)
        can_continue = True
        skip_counter = 0
        users_welcomed = 0
        user_list = device.find(
            resourceIdMatches=self.ResourceID.USER_LIST_CONTAINER,
        )
        std_height = user_list.get_height()
        while can_continue:
            start = time.time()
            posts_end_detector = ScrollEndDetector(
                repeats_to_end=2,
                skipped_list_limit=skipped_list_limit,
                skipped_fling_limit=skipped_fling_limit,
            )
            logger.info("Iterate over visible followers.")
            screen_iterated_followers = []
            scroll_end_detector.notify_new_page()

            skip, n_users = inspect_current_view(user_list, std_height)
            posts_end_detector.notify_new_page()
            try:
                for idx, item in enumerate(user_list):
                    if idx in skip:
                        continue
                    user_info_view = item.child(index=1)
                    user_name_view = user_info_view.child(index=0).child()
                    if not user_name_view.exists():
                        logger.info(
                            "Next item not found: probably reached end of the screen.",
                            extra={"color": f"{Fore.GREEN}"},
                        )
                        can_continue = False

                    username = user_name_view.get_text()
                    screen_iterated_followers.append(username)
                    scroll_end_detector.notify_username_iterated(username)
                    if storage.is_user_in_blacklist(username):
                        logger.info(f"@{username} is in blacklist. Skip.")
                    else:
                        welcomed = storage.check_user_was_welcomed(username)
                        if welcomed:
                            skip_counter += 1
                            logger.info(
                                f"@{username} has already being welcomed ({skip_counter}/{max_skips if max_skips is not None else 'infinite'}). Skip."
                            )
                            if max_skips is not None and skip_counter == max_skips:
                                logger.info("Reached the skip limit! Ending.")
                                can_continue = False
                        else:
                            logger.info(
                                f"@{username}: interact",
                                extra={"color": f"{Fore.YELLOW}"},
                            )
                            element_opened = user_name_view.click_retry()
                            if element_opened:
                                profile_data, _ = profile_filter.check_profile(
                                    device, username, dont_filter=True
                                )
                                has_been_welcomed = _send_PM(
                                    device,
                                    session_state,
                                    my_username,
                                    private=profile_data.is_private,
                                    welcoming=True,
                                    check_chat=self.args.check_chat_before_welcoming,
                                )
                                if has_been_welcomed is None:
                                    logger.warning(
                                        "Unable to welcome the user. PM are very likely to get soft-banned. Abort."
                                    )
                                    can_continue = False
                                elif has_been_welcomed:
                                    logger.info(f"{username} welcomed successfully.")
                                    users_welcomed += 1
                                    if self.session_state.check_limit(
                                        limit_type=self.session_state.Limit.PM,
                                        output=True,
                                    ):
                                        logger.info("Reached the total PM limit.")
                                        can_continue = False
                                    if self.session_state.check_limit(
                                        limit_type=self.session_state.Limit.SUCCESS
                                    ):
                                        logger.info(
                                            "Reached Successful Interactions limit."
                                        )
                                        can_continue = False
                                else:
                                    logger.info(f"{username} was not welcomed. Skip.")
                                    skip_counter += 1
                                    if (
                                        max_skips is not None
                                        and skip_counter == max_skips
                                    ):
                                        logger.info("Reached the skip limit! Ending.")
                                        can_continue = False
                                storage.add_interacted_user(
                                    username,
                                    self.session_state.id,
                                    welcomed=has_been_welcomed,
                                    update_status=False,
                                )
                                logger.info("Back to followers list")
                                device.back(modulable=False)
                                if self.session_state.check_limit(
                                    limit_type=self.session_state.Limit.TOTAL
                                ):
                                    logger.info("Reached Total Interactions limit.")
                                    can_continue = False
                            logger.info(
                                f"{users_welcomed}/{users_to_welcoming} users welcomed!",
                                extra={"color": f"{Fore.CYAN}"},
                            )
                            if users_welcomed >= users_to_welcoming:
                                logger.info("Reached the welcoming limit! Ending.")
                                can_continue = False
                    if not can_continue:
                        break
                end = time.time()
                logger.debug(
                    f"Iterated {len(screen_iterated_followers)} followers in {end - start:.2} seconds."
                )

                if not can_continue:
                    break

                list_view = device.find(
                    resourceId=self.ResourceID.LIST,
                )
                list_view.scroll(Direction.DOWN)

            except IndexError:
                logger.info(
                    "Cannot get next item: probably reached end of the screen.",
                    extra={"color": f"{Fore.GREEN}"},
                )
        # going back to profile view
        device.back()
