import json
import csv
import os

import pandas as pd


# desired order
desired_order = [
                 "username",
                 "posts",
                 "following",
                 "followers",
                 "total_interactions",
                 "successful_interactions",
                 "total_followed",
                 "total_likes",
                 "total_watched",
                 "total_unfollowed",
                 "start_time",
                 "finish_time",
                 "id",
                 ]

def logger(x):
    return print(x, flush=True)


def check_usernames_in_scraped_sessions():
    if not os.path.isfile("accounts/scraped_sessions.json"):
        return None
    with open("accounts/scraped_sessions.json", "r") as _f:
        _data = json.load(_f)
        return _data.keys()

def scraped_sessions_write(values):
    with open("accounts/scraped_sessions.txt", "w+") as _f:
        # write headers
        logger("Writing headers.")
        for header in desired_order:
            _f.write(f"{header};; ")

        # write values
        logger("Writing values.")
        for value in values:
            _f.write("\n")
            for val in value.values():
                _f.write(f"{val};; ")

accounts_path = "accounts"

# get usernames
usernames = []
# get folder names under accounts folder
for folder in os.listdir(accounts_path):
    # check if folder is a folder
    if os.path.isdir(os.path.join(accounts_path, folder)):
        usernames.append(folder)

_previous_usernames = check_usernames_in_scraped_sessions()
if(_previous_usernames == None):
    logger("No previous usernames found.")
else:
    logger(f"{len(_previous_usernames)} previous usernames found.")
    [usernames.append(username) for username in _previous_usernames if username not in usernames]

# get data
data = {}
for username in usernames:
    if os.path.isfile(os.path.join(accounts_path, username, "sessions.json")):
        logger("Scraping " + username)
        with open(os.path.join(accounts_path, username, "sessions.json"), "r") as json_data:
            _temp_ = json.load(json_data)
            for temp in _temp_:
                del temp["args"]
                profile = temp.pop("profile")
                temp["username"] = username 
                temp["posts"] = profile["posts"]
                temp["following"] = profile["following"]
                temp["followers"] = profile["followers"]
            data[username] = _temp_
    else:
        logger(f"Could not find accounts/{username}/sessions.json")
        logger(f"Trying /accounts/scraped_sessions.json")
        if os.path.isfile(os.path.join(accounts_path, "scraped_sessions.json")):
            logger(f"Found file")
            keys = check_usernames_in_scraped_sessions()
            if(username in keys):
                logger(f"Found {username} in json file")
                with open("accounts/scraped_sessions.json", "r") as f:
                    __data = json.load(f)
                    ___temp = []
                    for _user_data in __data[username]:
                        ___temp.append(_user_data)
                data[username] = ___temp 
            else:
                logger("Could not find {username} in json file.")
        else: 
            logger(f"Could not find /accounts/scraped_sessions.json")


# store into a file
with open(os.path.join(accounts_path, "scraped_sessions.json"), "w+") as f:
    json.dump(data, f, indent=2)


logger("Scraped files stored in accounts/scraped_sessions.json")


logger("Generating reports...")

if __name__ == "__main__":
    result = []
    values = []
    for username in data:
        for value in data[username]:
            user = {}
            for key in desired_order:
                user[key] = value[key]
            values.append(user)
    scraped_sessions_write(values)
    logger("Generated file: accounts/scraped_sessions.txt")


