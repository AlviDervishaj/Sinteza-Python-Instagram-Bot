import csv
import json
from GramAddict.core.plugin_loader import Plugin

class CSVReportPlugin(Plugin):
    """Outputs session data to a CSV file"""

    def __init__(self):
        super().__init__()
        self.description = "Outputs session data to a CSV file"
        self.arguments = [
            {
                "arg": "--csv-report",
                "help": "at the end of every session write a report to a CSV file",
                "action": "store_true",
                "operation": True,
            }
        ]

    def run(self, config, plugin, followers_now, following_now, time_left):
        # Get the username from the config.
        username = config.args.username
        print(f'Username: {username}')  # Print the username for debugging.

        # Define the name of the CSV file.
        filename = f'{username}_session_data.csv'
        print(f'Filename: {filename}')  # Print the filename for debugging.

        # Define the fieldnames for the CSV file.
        fieldnames = ['start', 'finish', 'likes', 'watched', 'followed', 'unfollowed', 'comments', 'pm_sent', 'followers', 'following']

        # Load the session data from the JSON file.
        with open(f"accounts/{username}/sessions.json") as json_data:
            sessions = json.load(json_data)
        print(f'Sessions: {sessions}')  # Print the sessions data for debugging.

        # Open the CSV file in append mode.
        with open(filename, 'a', newline='') as csvfile:
            # Create a CSV writer.
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # If the file is empty, write the header.
            if csvfile.tell() == 0:
                writer.writeheader()

            # Write each session to the CSV file.
            for session in sessions:
                writer.writerow(session)
            print('CSV file written.')  # Print a message when the CSV file has been written.
