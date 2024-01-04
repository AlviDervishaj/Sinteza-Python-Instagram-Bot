import logging
import os
import time
from enum import Enum, auto
from random import uniform
from functools import partial
from os import path

from atomicwrites import atomic_write
from colorama import Fore

from GramAddict.core.device_facade import Direction, Timeout
from GramAddict.core.navigation import (
    nav_to_blogger,
    nav_to_feed,
    nav_to_hashtag_or_place,
    nav_to_post_likers,
)
from GramAddict.core.resources import ClassName , ResourceID
from GramAddict.core.session_state import SessionState
from GramAddict.core.storage import FollowingStatus
from GramAddict.core.utils import (
    generate_list_of_users,
    get_value,
    inspect_current_view,
    random_choice,
    random_sleep,
)
from GramAddict.core.views import (
    FollowingView,
    LikeMode,
    OpenedPostView,
    Owner,
    PostsViewList,
    ProfileView,
    SwipeTo,
    TabBarView,
    UniversalActions,
    case_insensitive_re,
)

logger = logging.getLogger(__name__)
already_interacted_per_user = {}


class Mode(Enum):
    AUTOGEN = auto()
    FILE = auto()


def interact(
    storage,
    is_follow_limit_reached,
    username,
    interaction,
    device,
    session_state,
    current_job,
    target,
    on_interaction,
):
    can_follow = False
    if is_follow_limit_reached is not None:
        can_follow = not is_follow_limit_reached() and storage.get_following_status(
            username
        ) in [FollowingStatus.NONE, FollowingStatus.NOT_IN_LIST]

    (
        interaction_succeed,
        followed,
        is_private,
        scraped,
        pm_sent,
        welcomed,
        number_of_liked,
        number_of_watched,
        number_of_comments,
    ) = interaction(device, username=username, can_follow=can_follow, blogger_competitor=target)

    add_interacted_user = partial(
        storage.add_interacted_user,
        session_id=session_state.id,
        job_name=current_job,
        target=target,
    )

    add_interacted_user(
        username,
        followed=followed,
        is_private=is_private,
        scraped=scraped,
        liked=number_of_liked,
        watched=number_of_watched,
        commented=number_of_comments,
        pm_sent=pm_sent,
        welcomed=welcomed,
    )
    return on_interaction(
        succeed=interaction_succeed,
        followed=followed,
        scraped=scraped,
    )


def handle_blogger(
    self,
    device,
    session_state,
    blogger,
    current_job,
    storage,
    profile_filter,
    on_interaction,
    interaction,
    is_follow_limit_reached,
):
    if not nav_to_blogger(device, blogger, session_state.my_username):
        return
    can_interact = False
    if storage.is_user_in_blacklist(blogger):
        logger.info(f"@{blogger} is in blacklist. Skip.")
    else:
        filtered_when, interacted_when = storage.check_user_was_interacted(blogger)
        if interacted_when is not None:
            can_reinteract = storage.can_be_reinteract(
                interacted_when, get_value(self.args.can_reinteract_after, None, 0)
            )
            logger.info(
                f"@{blogger}: already interacted on {interacted_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_reinteract else 'Skip'}."
            )
            if can_reinteract:
                can_interact = True
        else:
            can_interact = True

    if can_interact:
        logger.info(
            f"@{blogger}: interact",
            extra={"color": f"{Fore.YELLOW}"},
        )
        if not interact(
            storage=storage,
            is_follow_limit_reached=is_follow_limit_reached,
            username=blogger,
            interaction=interaction,
            device=device,
            session_state=session_state,
            current_job=current_job,
            target=blogger,
            on_interaction=on_interaction,
        ):
            return


def handle_blogger_from_file(
    self,
    device,
    parameter_passed,
    current_job,
    storage,
    on_interaction,
    interaction,
    is_follow_limit_reached,
):
    need_to_refresh = True
    on_following_list = False
    limit_reached = False

    min_days: int = get_value(
        self.args.unfollow_delay, "Unfollow delay set to {} days.", 3
    )
    filename_passed: str = parameter_passed.split(" ")[0]
    if filename_passed == "autogen":
        mode = Mode.AUTOGEN
    else:
        filename: str = os.path.join(storage.account_path, filename_passed)
        mode = Mode.FILE
    try:
        amount_of_users = get_value(parameter_passed.split(" ")[1], None, 10)
    except IndexError:
        amount_of_users = 10
        logger.warning(
            f"You didn't passed how many users should be processed from the list! Default is {amount_of_users} users."
        )

    if mode == Mode.AUTOGEN:
        usernames = generate_list_of_users(storage.interacted_users_path, min_days)
        logger.info(
            f"{len(usernames)} usernames have been loaded (last interaction >= {min_days} days)."
        )
    elif path.isfile(filename):
        with open(filename, "r", encoding="utf-8") as f:
            usernames = [line.replace(" ", "") for line in f if line != "\n"]
    else:
        logger.warning(
            f"File {filename} not found. You have to specify the right relative path from this point: {os.getcwd()}"
        )
        return

    if not usernames:
        return
    len_usernames = len(usernames)
    if len_usernames < amount_of_users:
        amount_of_users = len_usernames
    logger.info(
        f"There are {len_usernames} entries, {amount_of_users} users will be processed."
    )
    not_found = []
    processed_users = 0
    try:
        for line, username_raw in enumerate(usernames, start=1):
            username = username_raw.strip()
            can_interact = False
            if current_job == "unfollow-from-file":
                unfollowed = do_unfollow_from_list(device, username, on_following_list)
                on_following_list = True
                if unfollowed:
                    storage.add_interacted_user(
                        username, self.session_state.id, unfollowed=True
                    )
                    self.session_state.totalUnfollowed += 1
                    limit_reached = self.session_state.check_limit(
                        limit_type=self.session_state.Limit.UNFOLLOWS
                    )
                    processed_users += 1
                else:
                    not_found.append(username_raw)
                    storage.add_interacted_user(
                        username, self.session_state.id, exists=False
                    )
                if limit_reached:
                    logger.info("Unfollows limit reached.")
                    break
                if processed_users == amount_of_users:
                    logger.info(
                        f"{processed_users} users have been unfollowed, going to the next job."
                    )
                    break
            else:
                if storage.is_user_in_blacklist(username):
                    logger.info(f"@{username} is in blacklist. Skip.")
                else:
                    (
                        filtered_when,
                        interacted_when,
                    ) = storage.check_user_was_interacted(username)
                    if interacted_when is not None:
                        can_reinteract = storage.can_be_reinteract(
                            interacted_when,
                            get_value(self.args.can_reinteract_after, None, 0),
                        )
                        logger.info(
                            f"@{username}: already interacted on {interacted_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_reinteract else 'Skip'}."
                        )
                        if can_reinteract:
                            can_interact = True
                    else:
                        can_interact = True

                if not can_interact:
                    continue
                if need_to_refresh:
                    search_view = TabBarView(device).navigate_to_search()
                profile_view = search_view.navigate_to_target(username, current_job)
                need_to_refresh = False
                if not profile_view:
                    not_found.append(username_raw)
                    continue

                if not interact(
                    storage=storage,
                    is_follow_limit_reached=is_follow_limit_reached,
                    username=username,
                    interaction=interaction,
                    device=device,
                    session_state=self.session_state,
                    current_job=current_job,
                    target=username,
                    on_interaction=on_interaction,
                ):
                    return
                device.back()
                processed_users += 1
                if processed_users == amount_of_users:
                    logger.info(
                        f"{processed_users} users have been interacted, going to the next job."
                    )
                    return
    finally:
        if not_found and mode == mode.FILE:
            with open(
                f"{os.path.splitext(filename)[0]}_not_found.txt",
                mode="a+",
                encoding="utf-8",
            ) as f:
                f.writelines(not_found)

        if mode == Mode.AUTOGEN:
            logger.info(
                f"Interact with user generated completed. There are {len_usernames-processed_users} user left that match criteria."
            )
        else:
            logger.info(
                f"Interact with users in {filename} completed. There are {len_usernames-processed_users} user left in that file."
            )
            if self.args.delete_interacted_users and len_usernames != 0:
                with atomic_write(filename, overwrite=True, encoding="utf-8") as f:
                    f.writelines(usernames[line:])
        device.back()


def do_unfollow_from_list(device, username, on_following_list):
    if not on_following_list:
        ProfileView(device).click_on_avatar()
        if ProfileView(device).navigateToFollowing() and UniversalActions(
            device
        ).search_text(username):
            return FollowingView(device).do_unfollow_from_list(username)
    else:
        if username is not None:
            UniversalActions(device).search_text(username)
        return FollowingView(device).do_unfollow_from_list(username)


def handle_likers(
    self,
    device,
    session_state,
    target,
    current_job,
    storage,
    profile_filter,
    posts_end_detector,
    on_interaction,
    interaction,
    is_follow_limit_reached,
):
    if (
        current_job == "blogger-post-likers"
        and not nav_to_post_likers(device, target, session_state.my_username)
        or current_job != "blogger-post-likers"
        and not nav_to_hashtag_or_place(device, target, current_job)
    ):
        return False
    post_description = ""
    nr_same_post = 0
    nr_same_posts_max = 3
    while True:
        flag, post_description, _, _, _, _ = PostsViewList(device).check_if_last_post(
            post_description, current_job
        )
        has_likers, number_of_likers = PostsViewList(device).find_likers_container()
        if flag:
            nr_same_post += 1
            logger.info(f"Warning: {nr_same_post}/{nr_same_posts_max} repeated posts.")
            if nr_same_post == nr_same_posts_max:
                logger.info(
                    f"Scrolled through {nr_same_posts_max} posts with same description and author. Finish.",
                    extra={"color": f"{Fore.CYAN}"},
                )
                break
        else:
            nr_same_post = 0

        if (
            has_likers
            and profile_filter.is_num_likers_in_range(number_of_likers)
            and number_of_likers >= 1
        ):
            PostsViewList(device).open_likers_container()
        else:
            PostsViewList(device).swipe_to_fit_posts(SwipeTo.NEXT_POST)
            continue

        posts_end_detector.notify_new_page()

        likes_list_view = OpenedPostView(device).get_listview_likers()
        if likes_list_view is None:
            return
        prev_screen_iterated_likers = []
        user_container = OpenedPostView(device).get_user_container()
        if not user_container or user_container is None:
            session_state.totalCrashes += 1
            logger.error("User Container is not found.")
            continue
        std_height = user_container.get_height()
        job_iterated_users = []

        while True:
            start = time.time()
            logger.info("Iterate over visible likers.")
            screen_iterated_likers = []
            opened = False

            if user_container is None:
                logger.warning("Likers list didn't load :(")
                return
            skip, n_users = inspect_current_view(user_container, std_height)
            try:
                for idx, item in enumerate(user_container):
                    if idx in skip:
                        continue
                    element_opened = False
                    # grab username
                    username_view = OpenedPostView(device).get_user_name(item)
                    # Check and see if the user has uploaded an story
                    has_story_view = OpenedPostView(device).has_story(item)
                    if not username_view.exists(Timeout.MEDIUM):
                        logger.info(
                            "Next item not found: probably reached end of the screen.",
                            extra={"color": f"{Fore.GREEN}"},
                        )
                        break
                    username = username_view.get_text()
                    has_story_description = has_story_view.content_desc()
                    logger.info(f"{has_story_description}")
                    if username in job_iterated_users:
                        continue
                    screen_iterated_likers.append(username)
                    job_iterated_users.append(username)
                    posts_end_detector.notify_username_iterated(username)
                    can_interact = False
                    if storage.is_user_in_blacklist(username):
                        logger.info(f"@{username} is in blacklist. Skip.")
                    elif username == session_state.my_username:
                        logger.info(f"@{username} is me. Skip.")
                    else:
                        (
                            filtered_when,
                            interacted_when,
                        ) = storage.check_user_was_interacted(username)

                        if has_story_description == f"View {username}'s story":
                            logger.info(
                                f"@{username}: has story. Can interact.",
                                extra={"color": f"{Fore.YELLOW}"},
                            )
                            if interacted_when is not None:
                                can_interact = storage.can_be_reinteract(
                                    interacted_when,
                                    get_value(self.args.can_reinteract_after, None, 0),
                                )
                                logger.info(
                                    f"@{username}: already interacted on {interacted_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_interact else 'Skip'}."
                                )
                            elif filtered_when is not None:
                                can_interact = storage.can_be_rechecked(
                                    filtered_when,
                                    get_value(self.args.can_recheck_after, None, 0),
                                )
                                logger.info(
                                    f"@{username}: already filtered on {filtered_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_interact else 'Skip'}."
                                )
                            else:
                               can_interact=True,
                        else:
                            logger.info(
                                f"@{username}: has no story. Can not interact.",
                                extra={"color": f"{Fore.YELLOW}"},)

                    if can_interact:
                        logger.info(
                            f"@{username}: interact",
                            extra={"color": f"{Fore.YELLOW}"},
                        )
                        element_opened = username_view.click_retry()

                        if element_opened and not interact(
                            storage=storage,
                            is_follow_limit_reached=is_follow_limit_reached,
                            username=username,
                            interaction=interaction,
                            device=device,
                            session_state=session_state,
                            current_job=current_job,
                            target=target,
                            on_interaction=on_interaction,
                        ):
                            return
                    else:
                        pass  # TODO: screen skipped limit
                    if element_opened:
                        opened = True
                        logger.info("Back to likers list.")
                        device.back()
                end = time.time()
                logger.debug(
                    f"Iterated {len(screen_iterated_likers)} likers in {end-start:.2f} seconds."
                )

            except IndexError:
                logger.info(
                    "Cannot get next item: probably reached end of the screen.",
                    extra={"color": f"{Fore.GREEN}"},
                )
                break
            go_back = False
            if screen_iterated_likers == prev_screen_iterated_likers:
                logger.info(
                    "Iterated exactly the same likers twice.",
                    extra={"color": f"{Fore.GREEN}"},
                )
                go_back = True
            if go_back:
                prev_screen_iterated_likers.clear()
                prev_screen_iterated_likers += screen_iterated_likers
                logger.info(
                    f"Back to {target}'s posts list.",
                    extra={"color": f"{Fore.GREEN}"},
                )
                device.back()
                logger.info("Going to the next post.")
                PostsViewList(device).swipe_to_fit_posts(SwipeTo.NEXT_POST)
                break
            if posts_end_detector.is_fling_limit_reached():
                logger.info(
                    "Reached fling limit. Fling to see other likers.",
                    extra={"color": f"{Fore.GREEN}"},
                )
                likes_list_view.fling(Direction.DOWN)
            else:
                logger.info(
                    "Scroll to see other likers.",
                    extra={"color": f"{Fore.GREEN}"},
                )
                likes_list_view.scroll(Direction.DOWN)

            prev_screen_iterated_likers.clear()
            prev_screen_iterated_likers += screen_iterated_likers
            if posts_end_detector.is_the_end():
                device.back()
                PostsViewList(device).swipe_to_fit_posts(SwipeTo.NEXT_POST)
                break
            if not opened:
                logger.info(
                    "All likers skipped.",
                    extra={"color": f"{Fore.GREEN}"},
                )
                posts_end_detector.notify_skipped_all()
                if posts_end_detector.is_skipped_limit_reached():
                    posts_end_detector.reset_skipped_all()
                    return


def handle_posts(
    self,
    device,
    session_state,
    target,
    current_job,
    storage,
    profile_filter,
    on_interaction,
    interaction,
    is_follow_limit_reached,
    interact_percentage,
    scraping_file,
):
    skipped_posts_limit = get_value(
        self.args.skipped_posts_limit,
        "Skipped post limit: {}",
        5,
    )
    if current_job == "feed":
        if scraping_file:
            logger.warning(
                "Scraping and interacting with own feed doesn't make any sense. Skip."
            )
            return
        nav_to_feed(device)
        count_feed_limit = get_value(
            self.args.feed,
            "Feed interact count: {}",
            10,
        )
        count = 0
        PostsViewList(device)._refresh_feed()
    elif not nav_to_hashtag_or_place(device, target, current_job):
        return

    post_description = ""
    likes_failed = 0
    nr_same_post = 0
    nr_same_posts_max = 3
    nr_consecutive_already_interacted = 0
    already_liked_count = 0
    already_liked_count_limit = 20
    post_view_list = PostsViewList(device)
    opened_post_view = OpenedPostView(device)
    while True:
        (
            is_same_post,
            post_description,
            username,
            is_ad,
            is_hashtag,
            has_tags,
        ) = post_view_list.check_if_last_post(post_description, current_job)
        has_likers, number_of_likers = post_view_list.find_likers_container()
        already_liked, _ = opened_post_view.is_post_liked()
        if not (is_ad or is_hashtag) and number_of_likers >= 1:
            if already_liked_count == already_liked_count_limit:
                logger.info(
                    f"Limit of {already_liked_count_limit} already liked posts limit reached, finish."
                )
                break
            if is_same_post:
                nr_same_post += 1
                logger.info(
                    f"Warning: {nr_same_post}/{nr_same_posts_max} repeated posts."
                )
                if nr_same_post == nr_same_posts_max:
                    logger.info(
                        f"Scrolled through {nr_same_posts_max} posts with same description and author. Finish."
                    )
                    break
            else:
                nr_same_post = 0
            if already_liked:
                logger.info(
                    "Post already liked, SKIP.", extra={"color": f"{Fore.CYAN}"}
                )
                already_liked_count += 1
            elif random_choice(interact_percentage):
                can_interact = False
                if storage.is_user_in_blacklist(username):
                    logger.info(f"@{username} is in blacklist. Skip.")
                else:
                    likes_in_range = profile_filter.is_num_likers_in_range(
                        number_of_likers
                    )
                    if current_job != "feed":
                        (
                            filtered_when,
                            interacted_when,
                        ) = storage.check_user_was_interacted(username)
                        if interacted_when is not None:
                            can_reinteract = storage.can_be_reinteract(
                                interacted_when,
                                get_value(self.args.can_reinteract_after, None, 0),
                            )
                            logger.info(
                                f"@{username}: already interacted on {interacted_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_reinteract else 'Skip'}."
                            )
                            if can_reinteract:
                                can_interact = True
                                nr_consecutive_already_interacted = 0
                            else:
                                nr_consecutive_already_interacted += 1
                        else:
                            can_interact = True
                            nr_consecutive_already_interacted = 0
                    else:
                        can_interact = True

                if nr_consecutive_already_interacted == skipped_posts_limit:
                    logger.info(
                        f"Reached the limit of already interacted {skipped_posts_limit}. Going to the next source/job!"
                    )
                    break
                if can_interact and (likes_in_range or not has_likers):
                    logger.info(
                        f"@{username}: interact", extra={"color": f"{Fore.YELLOW}"}
                    )
                    if scraping_file is None:
                        opened_post_view.start_video()
                        if not session_state.check_limit(
                            limit_type=session_state.Limit.LIKES, output=True
                        ):
                            if has_tags:
                                post_view_list.like_in_post_view(LikeMode.SINGLE_CLICK)
                            else:
                                post_view_list.like_in_post_view(LikeMode.DOUBLE_CLICK)
                            UniversalActions.detect_block(device)
                            liked = post_view_list.check_if_liked()
                            if not liked:
                                post_view_list.like_in_post_view(
                                    LikeMode.SINGLE_CLICK, already_watched=True
                                )
                                UniversalActions.detect_block(device)
                                liked = post_view_list.check_if_liked()
                            if liked:
                                session_state.totalLikes += 1
                                if current_job == "feed":
                                    count += 1
                                    logger.info(
                                        f"Interacted feed bloggers: {count}/{count_feed_limit}"
                                    )
                                    likes_limit = self.session_state.check_limit(
                                        limit_type=self.session_state.Limit.LIKES
                                    )
                                    success_limit = self.session_state.check_limit(
                                        limit_type=self.session_state.Limit.SUCCESS
                                    )
                                    total_limit = self.session_state.check_limit(
                                        limit_type=self.session_state.Limit.TOTAL
                                    )
                                    if likes_limit or success_limit or total_limit:
                                        logger.info("Limit reached, finish.")
                                        break
                                    if count >= count_feed_limit:
                                        logger.info(
                                            f"Interacted {count} bloggers in feed, finish."
                                        )
                                        break
                            else:
                                likes_failed += 1
                    if current_job != "feed":
                        opened, _, _ = post_view_list.post_owner(
                            current_job, Owner.OPEN, username
                        )
                        if opened:
                            if not interact(
                                storage=storage,
                                is_follow_limit_reached=is_follow_limit_reached,
                                username=username,
                                interaction=interaction,
                                device=device,
                                session_state=session_state,
                                current_job=current_job,
                                target=target,
                                on_interaction=on_interaction,
                            ):
                                break
                            device.back()
            else:
                logger.info(
                    f"Skipped because your interact % is {interact_percentage}/100 and {username}'s post was unlucky!"
                )
        if likes_failed == 10:
            logger.warning("You failed to do 10 likes! Soft-ban?!")
            return
        post_view_list.swipe_to_fit_posts(SwipeTo.HALF_PHOTO)
        post_view_list.swipe_to_fit_posts(SwipeTo.NEXT_POST)
    TabBarView(device).navigate_to_profile()


def handle_followers(
    self,
    device,
    session_state,
    username,
    current_job,
    storage,
    on_interaction,
    interaction,
    is_follow_limit_reached,
    scroll_end_detector,
    args=None,
):
    is_myself = username == session_state.my_username
    if not nav_to_blogger(device, username, current_job):
        return

    iterate_over_followers(
        self,
        device,
        interaction,
        is_follow_limit_reached,
        storage,
        on_interaction,
        is_myself,
        scroll_end_detector,
        session_state,
        current_job,
        username,
        args=args,
    )

skipped_lists = {}

def iterate_over_followers(
    self,
    device,
    interaction,
    is_follow_limit_reached,
    storage,
    on_interaction,
    is_myself,
    scroll_end_detector,
    session_state: SessionState,
    current_job,
    target,
    args=None,
):
    # keep track of the number of interacted users
    global username
    interacted_users = 0
    device.find(
        resourceId=self.ResourceID.FOLLOW_LIST_CONTAINER,
        className=ClassName.LINEAR_LAYOUT,
    ).wait(Timeout.LONG)

    def scrolled_to_top():
        row_search = device.find(
            resourceId=self.ResourceID.ROW_SEARCH_EDIT_TEXT,
            className=ClassName.EDIT_TEXT,
        )
        return row_search.exists()

    user_list = device.find(
        resourceIdMatches=self.ResourceID.USER_LIST_CONTAINER,
    )
    std_height = user_list.get_height()
    list_view = device.find(
        resourceId=self.ResourceID.LIST,
        className=ClassName.LIST_VIEW,
    )
    for _ in range(int(args.fling_when_skipped)):
        list_view.fling(Direction.DOWN)
        time.sleep(5)
    while True:
        start = time.time()
        logger.info("Iterate over visible followers.")
        screen_iterated_followers = []
        screen_skipped_followers_count = 0
        scroll_end_detector.notify_new_page()

        skip, n_users = inspect_current_view(user_list, std_height)
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
                    break

                username = user_name_view.get_text()
                screen_iterated_followers.append(username)
                scroll_end_detector.notify_username_iterated(username)

                can_interact = False
                if storage.is_user_in_blacklist(username):
                    logger.info(f"@{username} is in blacklist. Skip.")
                elif username == session_state.my_username:
                    logger.info(f"@{username} is me. Skip.")
                else:
                    filtered_when, interacted_when = storage.check_user_was_interacted(
                        username
                    )
                    if interacted_when is not None:
                        can_interact = storage.can_be_reinteract(
                            interacted_when,
                            get_value(self.args.can_reinteract_after, None, 0),
                        )
                        logger.info(
                            f"@{username}: already interacted on {interacted_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_interact else 'Skip'}."
                        )
                    elif filtered_when is not None:
                        can_interact = storage.can_be_rechecked(
                            filtered_when,
                            get_value(self.args.can_recheck_after, None, 0),
                        )
                        logger.info(
                            f"@{username}: already filtered on {filtered_when:%Y/%m/%d %H:%M:%S}. {'Interacting again now' if can_interact else 'Skip'}."
                        )
                    else:
                        can_interact = True
                if can_interact:
                    logger.info(
                        f"@{username}: interact", extra={"color": f"{Fore.YELLOW}"}
                    )
                    element_opened = user_name_view.click_retry()
                    interacted_users += 1
                    if element_opened:
                        if not interact(
                            storage=storage,
                            is_follow_limit_reached=is_follow_limit_reached,
                            username=username,
                            interaction=interaction,
                            device=device,
                            session_state=session_state,
                            current_job=current_job,
                            target=target,
                            on_interaction=on_interaction,
                        ):
                            return
                    if element_opened:
                        logger.info("Back to followers list")
                        device.back()
                else:
                    screen_skipped_followers_count += 1
            random_sleep_time = uniform(0, 2)
            logger.info(f"Pause for {random_sleep_time:.2} seconds.")
            time.sleep(random_sleep_time)
            end = time.time()
            logger.debug(
                f"Iterated {len(screen_iterated_followers)} followers in {end - start:.2} seconds."
            )
        except IndexError:
            logger.info(
                "Cannot get next item: probably reached end of the screen.",
                extra={"color": f"{Fore.GREEN}"},
            )

        if is_myself and scrolled_to_top():
            logger.info("Scrolled to top, finish.", extra={"color": f"{Fore.GREEN}"})
            return
        elif len(screen_iterated_followers) > 0:
            load_more_button = device.find(
                resourceId=self.ResourceID.ROW_LOAD_MORE_BUTTON
            )
            load_more_button_exists = load_more_button.exists()

            if scroll_end_detector.is_the_end(session_state.my_username, target):
                # sleep some time to avoid false positives
                time.sleep(1.4)
                return

            need_swipe = screen_skipped_followers_count == len(
                screen_iterated_followers
            )
            list_view = device.find(
                resourceId=self.ResourceID.LIST, className=ClassName.LIST_VIEW
            )
            if not list_view.exists():
                logger.error(
                    "Cannot find the list of followers. Trying to press back again."
                )
                device.back()
                list_view = device.find(
                    resourceId=self.ResourceID.LIST,
                    className=ClassName.LIST_VIEW,
                )
            if is_myself:
                logger.info("Need to scroll now", extra={"color": f"{Fore.GREEN}"})
                list_view.scroll(Direction.UP)
            else:
                pressed_retry = False
                if load_more_button_exists:
                    retry_button = load_more_button.child(
                        className=ClassName.IMAGE_VIEW,
                        descriptionMatches=case_insensitive_re("Retry"),
                    )
                    if retry_button.exists():
                        random_sleep()
                        """It exist but can disappear without pressing on it"""
                        if retry_button.exists():
                            logger.info('Press "Load" button and wait few seconds.')
                            retry_button.click_retry()
                            random_sleep(5, 10, modulable=False)
                            pressed_retry = True

                if need_swipe and not pressed_retry:
                    scroll_end_detector.notify_skipped_all()
                    if scroll_end_detector.is_skipped_limit_reached():
                        # with open(
                        #     f"accounts/{session_state.my_username}/blacklist.txt",
                        #     "a+",
                        # ) as f:
                        #     # write the username of the instagram account
                        #     f.write(f"{target}\n")
                        session_state.totalComments = 1
                        logger.error("LIMIT REACHED ")
                        return
                    if scroll_end_detector.is_fling_limit_reached():
                        logger.info(
                            "Limit of all followers skipped reached, let's fling.",
                            extra={"color": f"{Fore.GREEN}"},
                        )
                        if target in skipped_lists:
                            skipped_lists[target] += 1
                        else:
                            skipped_lists[target] = 1
                        session_state.skipped_lists_per_competitor.update(skipped_lists)
                        list_view.fling(Direction.DOWN)
                    else:
                        logger.info(
                            "All followers skipped, let's scroll.",
                            extra={"color": f"{Fore.GREEN}"},
                        )
                        if target in skipped_lists:
                            skipped_lists[target] += 1
                        else:
                            skipped_lists[target] = 1
                        session_state.skipped_lists_per_competitor.update(skipped_lists)
                        list_view.scroll(Direction.DOWN)
                else:
                    logger.info("Need to scroll now", extra={"color": f"{Fore.GREEN}"})
                    list_view.scroll(Direction.DOWN)
        else:
            logger.info(
                "No followers were iterated, finish.",
                extra={"color": f"{Fore.GREEN}"},
            )
            return
