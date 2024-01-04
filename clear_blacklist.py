import os

def locate_blacklist_in_directory(directory):
    if os.path.isfile(directory):
        with open(directory, "w") as f:
            f.truncate(0)
    else:
        print(f"{directory} does not exists.")

for d in os.listdir("./accounts"):
    blacklist_folder_path = f"./accounts/{d}/blacklist.txt"
    locate_blacklist_in_directory(blacklist_folder_path)