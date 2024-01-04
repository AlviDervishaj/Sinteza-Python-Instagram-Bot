from time import sleep
from subprocess import Popen


username = str(input("Enter username that you want to simulate : "))
configFile = str(input("Enter config file (example: config.yml): "))
ammount_of_runs = 1000
index = 0

if not username:
    print("Please enter a valid username")
    exit(0)
if not configFile:
    print(configFile, username)
    print("Please enter a valid config file")
    exit(0)
print(configFile, username)

while index <= ammount_of_runs:
    # sleep 5 seconds before starting
    sleep(5)
    process = Popen(f'python run.py --config accounts/{username}/{configFile}',
                    shell=False)
    # wait 5 minutes before executing next iteration
    sleep(60 * 1)
    process.kill()
    process.terminate()
    print("Killed Bot...")
