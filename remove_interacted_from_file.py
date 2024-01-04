import json
import os


def logger(x):
    return print(x, flush=True)


# read text file
def read_text_file():
    with open("keep_usernames.txt", "r") as f:
        data = f.read().split("----")
        return data


def remove_interacted_from_file():
    # check if accounts/accountName/interacted_users.json exists
    # if true check if any key in that json file matches usernameToBeKept
    # if false delete that key from the json file
    lines = read_text_file()
    for line in lines:
        line = list(filter(None, line.split("\n")))
        username = line[0]
        logger(f"Username: {username}")
        if not os.path.isfile(f"accounts/{username}/interacted_users.json"):
            logger(f"Could not find interacted_users.json in {username}")
            continue
        with open(f"accounts/{username}/interacted_users.json", "r") as f:
            interacted_users = json.load(f)
        # loop over keys
        temp = interacted_users.copy()
        for key in temp.keys():
            if key in line:
                logger(f"Found {key} in keep_usernames.txt")
                continue
            else:
                logger(f"Deleting {key}")
                del interacted_users[key]
        with open(f"accounts/{username}/interacted_users.json", "w") as f:
            json.dump(interacted_users, f, indent=4)


if __name__ == "__main__":
    remove_interacted_from_file()
