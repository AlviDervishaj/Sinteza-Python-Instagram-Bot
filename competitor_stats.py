import os
import json
import sys
from datetime import datetime, timedelta

def get_sessions_for_user(username: str) -> list:
    sessions_path: str = os.path.join(os.getcwd(), 'accounts', username, 'sessions.json')
    if not os.path.exists(sessions_path):
        return None, None
    with open(sessions_path, 'r') as f:
        sessions = json.load(f)
    if len(sessions) == 0:
        return None, None
    return sessions


def get_most_recent_following_and_followers() -> list:
    most_recent_session = sessions[-1]
    return most_recent_session['profile']['followers'], most_recent_session['profile']['following']

def get_all_time_stats() -> list:
    total_interactions = 0
    successful_interactions = 0
    total_followed = 0
    total_unfollowed = 0
    total_likes = 0
    total_comments = 0
    args = []
    total_watched = 0
    hashtags = []
    target_accounts = []
    for session in sessions:
        # check if start time is in the past 7 days
        date: list = session['start_time']
        date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S.%f')
        if date > datetime.now() - timedelta(days=7):
            total_interactions += session['total_interactions']
            successful_interactions += session['successful_interactions']
            total_followed += session['total_followed']
            total_unfollowed += session['total_unfollowed']
            total_likes += session['total_likes']
            total_comments += session['total_comments']
            total_watched += session['total_watched']
            if with_args == "with_args":
                args = session['args']
            elif with_args == "with_hashtags":
                if session['args']['hashtag_likers_top'] is not None:
                    for hashtag in session['args']['hashtag_likers_top']:
                        if hashtag in hashtags:
                            continue
                        else:
                            hashtags.append(hashtag)
                else:
                    continue
            if session['args']['blogger_followers'] is not None:
                for account in session['args']['blogger_followers']:
                    if account in target_accounts:
                        continue
                    else:
                        target_accounts.append(account)
            else:
                continue
        else:
            continue
    if with_args == "with_args":
        return {
            'Total Interactions': total_interactions,
            'Successful Interactions': successful_interactions,
            'Total Followed': total_followed,
            'Total Unfollowed': total_unfollowed,
            'Total Likes': total_likes,
            'Total Comments': total_comments,
            'Args': args,
            'Total Watched': total_watched,
            'Target Accounts': target_accounts,
        }
    elif with_args == "with_hashtags":
        return {
            'Total Interactions': total_interactions,
            'Successful Interactions': successful_interactions,
            'Total Followed': total_followed,
            'Total Unfollowed': total_unfollowed,
            'Total Likes': total_likes,
            'Total Comments': total_comments,
            'Hashtags Used': hashtags,
            'Total Watched': total_watched,
            'Target Accounts': target_accounts,
        }
    else:
        return {
            'Total Interactions': total_interactions,
            'Successful Interactions': successful_interactions,
            'Total Followed': total_followed,
            'Total Unfollowed': total_unfollowed,
            'Total Likes': total_likes,
            'Total Comments': total_comments,
            'Total Watched': total_watched,
            'Target Accounts': target_accounts,
        }


if __name__ == "__main__":
    with_args = sys.argv[1] if len(sys.argv) > 1 else ""
    username = str(input("Enter username: "))
    sessions = get_sessions_for_user(username)
    followers, following = get_most_recent_following_and_followers()
    stats = get_all_time_stats()
    stats['Followers'] = followers
    stats['Following'] = following
    stats['Time Generated'] = str(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
    print(f"Stats: {json.dumps(stats, indent=2)}")
    # save to json file
    print(f"Writing to stats/{username}.json ...")
    # create directory if it doesn't exist
    if not os.path.exists('stats'):
        os.mkdir('stats')
    with open(f'stats/{username}.json', 'w') as f:
        json.dump(stats, f, indent=2)
    print("Finished.")

