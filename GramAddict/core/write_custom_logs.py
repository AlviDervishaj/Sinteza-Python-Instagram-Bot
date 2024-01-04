from datetime import datetime


def write(text: str) -> None:
    # write to log file
    with open(f"accounts/{USERNAME}/{USERNAME}.log", "a") as f:
        hours = datetime.now().strftime("%H:%M")
        # get day and month
        day = datetime.now().strftime("%d")
        month = datetime.now().strftime("%m")
        f.write(f"[{hours} {day}/{month}] | {text}\n")
        f.close()


def override() -> None:
    # clean the log file each time bot is started
    with open(f"accounts/{USERNAME}/{USERNAME}.log", "w+") as f:
        f.write("")
        f.close()


def init(username: str) -> None:
    global USERNAME
    USERNAME = username
