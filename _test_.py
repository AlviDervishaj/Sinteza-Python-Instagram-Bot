session_state = {
    "my_username": "a.lvii",
    "my_following_count": 365,
}


def main():
    # check if file exists

    with open(
        f"accounts/{session_state['my_username']}/following_compared.txt", "r"
    ) as f:
        f.seek(0)
        # read file
        data: str = f.read()

        print(data)

        if len(data) == 0:
            print("No previous following count found.")
            f.write(f'{session_state["my_following_count"]}')
            return
        elif len(data) == 1:
            # if not empty, check if my following count is the same
            if data[0] == session_state["my_following_count"]:
                print(
                    f"Either bot did not unfollow anyone or {session_state['my_following_count']} has been soft-banned. Aborting."
                )
                # stop_bot(device, sessions, session_state)
                return
            else:
                print(
                    f"Following count in file and current following count are different. Updating..."
                )
                f.write(f'session_state["my_following_count"]')
        else:
            print(f"following_compared.txt has more than one line. Aborting.")


if __name__ == "__main__":
    main()
