import os, shutil

def read_folders():
    with open("keep.txt", "r+") as f:
        to_keep = [line for line in f.read().split("\n") if line.strip() != "" and os.path.isdir(f"./accounts/{line}")]
    return to_keep

def remove_folders():
    to_keep = read_folders()
    removed = []
    for directory in os.listdir("./accounts"):
        if directory in to_keep:
            # leave it, do not delete
            pass
        else:
            shutil.rmtree(f"./accounts/{directory}")
            removed.append(directory)
    print(f"{removed} Removed.")

remove_folders()