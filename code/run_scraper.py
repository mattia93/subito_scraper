from scraper import run
from decouple import config
import time

if __name__ == '__main__':
    refresh_time = config('refresh_time_minutes', cast=int)
    while True:
        run()
        print(f"Waiting for {refresh_time} minutes before the next run...")
        time.sleep(refresh_time * 60)