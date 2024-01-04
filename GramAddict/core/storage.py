import json
import logging
import os
import sys
from datetime import datetime, timedelta
from enum import Enum, unique
from typing import Optional, Tuple, Union

from atomicwrites import atomic_write
from colorama import Fore, Style

logger = logging.getLogger(__name__)

ACCOUNTS = "accounts"
REPORTS = "reports"
FILENAME_HISTORY_FILTER_USERS = "history_filters_users.json"
FILENAME_INTERACTED_USERS = "interacted_users.json"
FILENAME_SESSIONS = "sessions.json"
OLD_FILTER = "filter.json"
FILTER = "filters.yml"
USER_LAST_INTERACTION = "last_interaction"
USER_LAST_FILTER = "datetime"
USER_LAST_CHECK = "last_check"
USER_FOLLOWING_STATUS = "following_status"

FILENAME_WHITELIST = "whitelist.txt"
FILENAME_BLACKLIST = "blacklist.txt"
FILENAME_COMMENTS = "comments_list.txt"
FILENAME_MESSAGES = "pm_list.txt"
FILENAME_WELCOME_MESSAGES = "pm_welcome.txt"


class Storage:
    def __init__(self, my_username):
        if my_username is None:
            logger.error(
                "No username, thus the script won't get access to interacted users and sessions data."
            )
            return
        self.account_path = os.path.join(ACCOUNTS, my_username)
        if not os.path.exists(self.account_path):
            os.makedirs(self.account_path)
        self.interacted_users = {}
        self.history_filter_users = {}
        self.welcomed_users = []
        self.interacted_users_path = os.path.join(
            self.account_path, FILENAME_INTERACTED_USERS
        )
        self.sessions_path = os.path.join(self.account_path, FILENAME_SESSIONS)
        if os.path.isfile(self.interacted_users_path):
            with open(self.interacted_users_path, encoding="utf-8") as json_file:
                try:
                    self.interacted_users = json.load(json_file)
                    self.welcomed_users = [
                        user
                        for user in self.interacted_users
                        if self.interacted_users[user].get("welcomed")
                    ]
                except Exception as e:
                    logger.error(
                        f"Please check {json_file.name}, it contains this error: {e}"
                    )
                    sys.exit(0)
        self.history_filter_users_path = os.path.join(
            self.account_path, FILENAME_HISTORY_FILTER_USERS
        )

        if os.path.isfile(self.history_filter_users_path):
            with open(self.history_filter_users_path, encoding="utf-8") as json_file:
                try:
                    self.history_filter_users = json.load(json_file)
                except Exception as e:
                    logger.error(
                        f"Please check {json_file.name}, it contains this error: {e}"
                    )
                    sys.exit(0)
        self._clean_data()
        self.filter_path = os.path.join(self.account_path, FILTER)
        if not os.path.exists(self.filter_path):
            self.filter_path = os.path.join(self.account_path, OLD_FILTER)

        whitelist_path = os.path.join(self.account_path, FILENAME_WHITELIST)
        if os.path.exists(whitelist_path):
            with open(whitelist_path, encoding="utf-8") as file:
                self.whitelist = [line.rstrip() for line in file]
        else:
            self.whitelist = []

        blacklist_path = os.path.join(self.account_path, FILENAME_BLACKLIST)
        if os.path.exists(blacklist_path):
            with open(blacklist_path, encoding="utf-8") as file:
                self.blacklist = [line.rstrip() for line in file]
        else:
            self.blacklist = []

        self.report_path = os.path.join(self.account_path, REPORTS)

    def _clean_data(self):
        interactions = [
            "liked",
            "watched",
            "commented",
            "followed",
            "unfollowed",
            "scraped",
            "pm_sent",
            "welcomed",
        ]

        def _is_interacted(interacted_user: dict) -> bool:
            return any(interacted_user.get(u, False) for u in interactions)

        cleaned = {}
        not_in_history = 0
        probably_interacted = 0
        for user in self.interacted_users:
            if _is_interacted(self.interacted_users[user]):
                cleaned[user] = self.interacted_users[user]
            else:
                if user not in self.history_filter_users:
                    not_in_history += 1
                else:
                    skip_reason = self.history_filter_users[user].get("skip_reason")
                    if skip_reason is None:
                        logger.debug(
                            f"{user} was actually interacted! {self.history_filter_users[user].get('following_status')}"
                        )
                        probably_interacted += 1
                    else:
                        logger.debug(f"{user} skipped because {skip_reason}")
        if len(cleaned) < len(self.interacted_users):
            logger.info(
                f"Data has been cleaned {len(self.interacted_users)} -> {len(cleaned)} ({not_in_history} were also not in history)"
            )
            self.interacted_users = cleaned
        if probably_interacted:
            logger.info(
                f"{probably_interacted} users were probably interacted! (maybe bot crashes!)"
            )

    def can_be_reinteract(
        self,
        last_interaction: datetime,
        hours_that_have_to_pass: Optional[Union[int, float]],
    ) -> bool:  # TODO: should be merged with can_be_rechecked
        if hours_that_have_to_pass is None:
            return False
        elif hours_that_have_to_pass == 0:
            return True
        return self._check_time(
            last_interaction, timedelta(hours=hours_that_have_to_pass)
        )

    def can_be_unfollowed(
        self, last_interaction: datetime, days_that_have_to_pass: Optional[int]
    ) -> bool:
        if days_that_have_to_pass is None:
            return False
        return self._check_time(
            last_interaction, timedelta(days=days_that_have_to_pass)
        )

    def _check_time(
        self, stored_time: Optional[datetime], limit_time: timedelta
    ) -> bool:
        if stored_time is None or limit_time == timedelta(hours=0):
            return True
        return datetime.now() - stored_time >= limit_time

    def check_user_was_interacted(
        self, username
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Returns the last filter time and the last time the user was interacted.
        """
        filtered_user = self.history_filter_users.get(username, False)
        interacted_user = self.interacted_users.get(username, False)
        last_filtration = filtered_user.get(USER_LAST_FILTER) if filtered_user else None
        last_interaction = (
            interacted_user.get(USER_LAST_INTERACTION) if interacted_user else None
        )
        return self._get_time(last_filtration), self._get_time(last_interaction)

    def _get_time(self, datetime_string: str) -> Optional[datetime]:
        if datetime_string is None:
            return None
        return datetime.strptime(datetime_string, "%Y-%m-%d %H:%M:%S.%f")

    def check_user_was_checked(self, username):
        user = self.interacted_users.get(username)
        if user is None:
            return None
        last_check = user.get(USER_LAST_CHECK)
        if last_check is None:
            return None
        return datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S.%f")

    def check_user_was_welcomed(self, username):
        return username in self.welcomed_users

    def get_following_status(self, username):
        user = self.interacted_users.get(username)
        if user is None:
            return FollowingStatus.NOT_IN_LIST
        following_status = (
            user.get(USER_FOLLOWING_STATUS).upper()
            if user.get(USER_FOLLOWING_STATUS)
            else "NONE"
        )
        if FollowingStatus[following_status] == FollowingStatus.NONE:
            has_been_followed = user.get("followed", False)
            has_been_welcomed = user.get("welcomed", False)
            if has_been_followed:
                return FollowingStatus.FOLLOWED
            if has_been_welcomed:
                logger.debug(f"{username} has probably only welcomed!")
                return FollowingStatus.NONE
            logger.warning(
                f"{username} has been interacted but not followed by this bot!"
            )
        return FollowingStatus[following_status]

    def get_check_time(self, username):
        user = self.history_filter_users.get(username)
        if user is None:
            return None
        return datetime.strptime(user["datetime"], "%Y-%m-%d %H:%M:%S.%f")

    def can_be_rechecked(self, filtered_when, time_since_last_check):
        if filtered_when is not None and time_since_last_check:
            return datetime.now() - filtered_when > timedelta(
                hours=time_since_last_check
            )
        return False

    def add_filter_user(self, username, profile_data, skip_reason=None):
        user = profile_data.__dict__
        user["follow_button_text"] = (
            None if profile_data.is_restricted else profile_data.follow_button_text.name
        )
        if skip_reason is not None and not skip_reason:
            if username in self.history_filter_users:
                user["skip_reason"] = self.history_filter_users[username].get(
                    "skip_reason"
                )
        else:
            user["skip_reason"] = None if skip_reason is None else skip_reason.name
        self.history_filter_users[username] = user
        if self.history_filter_users_path is not None:
            with atomic_write(
                self.history_filter_users_path, overwrite=True, encoding="utf-8"
            ) as outfile:
                json.dump(self.history_filter_users, outfile, indent=4, sort_keys=False)

    def add_interacted_user(
        self,
        username,
        session_id,
        followed=False,
        is_private=False,
        unfollowed=False,
        scraped=False,
        liked=0,
        watched=0,
        commented=0,
        pm_sent=False,
        welcomed=False,
        exists=True,
        checked=False,
        job_name=None,
        target=None,
        update_status=True,
    ):
        if not any(
            [
                liked,
                watched,
                commented,
                pm_sent,
                welcomed,
                followed,
                unfollowed,
                scraped,
            ]
        ):
            return

        user = self.interacted_users.get(username, {})
        user["exists"] = exists
        if welcomed:
            user["welcomed"] = True
            self.welcomed_users.append(username)
        user[USER_LAST_INTERACTION] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        # Save only the last session_id
        user["session_id"] = session_id

        # Save only the last job_name and target
        if not user.get("job_name"):
            user["job_name"] = job_name
        if not user.get("target"):
            user["target"] = target
        if update_status:
            if followed:
                if is_private:
                    user[
                        USER_FOLLOWING_STATUS
                    ] = FollowingStatus.REQUESTED.name.casefold()
                else:
                    user[
                        USER_FOLLOWING_STATUS
                    ] = FollowingStatus.FOLLOWED.name.casefold()
            elif unfollowed:
                user[USER_FOLLOWING_STATUS] = FollowingStatus.UNFOLLOWED.name.casefold()
            elif scraped:
                user[USER_FOLLOWING_STATUS] = FollowingStatus.SCRAPED.name.casefold()
            else:
                user[USER_FOLLOWING_STATUS] = FollowingStatus.NONE.name.casefold()
            if user.get(USER_FOLLOWING_STATUS) is None:
                user[USER_FOLLOWING_STATUS] = FollowingStatus.NONE.name.casefold()

            # Increase the value of liked, watched or commented if we have already a value
            user["liked"] = liked if "liked" not in user else (user["liked"] + liked)
            user["watched"] = (
                watched if "watched" not in user else (user["watched"] + watched)
            )
            user["commented"] = (
                commented
                if "commented" not in user
                else (user["commented"] + commented)
            )

            # Update the followed or unfollowed boolean only if we have a real update
            user["followed"] = (
                followed
                if "followed" not in user or user["followed"] != followed
                else user["followed"]
            )
            user["unfollowed"] = (
                unfollowed
                if "unfollowed" not in user or user["unfollowed"] != unfollowed
                else user["unfollowed"]
            )
            user["scraped"] = (
                scraped
                if "scraped" not in user or user["scraped"] != scraped
                else user["scraped"]
            )
            user["pm_sent"] = (
                pm_sent
                if "pm_sent" not in user or user["pm_sent"] != pm_sent
                else user["pm_sent"]
            )
            user["welcomed"] = (
                welcomed
                if "welcomed" not in user or user["welcomed"] != welcomed
                else user["welcomed"]
            )
        self.interacted_users[username] = user
        logger.debug(
            f"{username} added to interacted_users",
            extra={"color": f"{Fore.WHITE}{Style.DIM}"},
        )
        self._update_file()

    def is_user_in_whitelist(self, username):
        return username in self.whitelist

    def is_user_in_blacklist(self, username):
        return username in self.blacklist

    def _get_last_day_interactions_count(self):
        count = 0
        users_list = list(self.interacted_users.values())
        for user in users_list:
            last_interaction = datetime.strptime(
                user[USER_LAST_INTERACTION], "%Y-%m-%d %H:%M:%S.%f"
            )
            is_last_day = datetime.now() - last_interaction <= timedelta(days=1)
            if is_last_day:
                count += 1
        return count

    def _update_file(self):
        if self.interacted_users_path is not None:
            with atomic_write(
                self.interacted_users_path, overwrite=True, encoding="utf-8"
            ) as outfile:
                json.dump(self.interacted_users, outfile, indent=4, sort_keys=False)


@unique
class FollowingStatus(Enum):
    NONE = 0
    FOLLOWED = 1
    REQUESTED = 2
    UNFOLLOWED = 3
    NOT_IN_LIST = 4
    SCRAPED = 5
