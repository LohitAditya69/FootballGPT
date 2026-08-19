import os
import urllib3
from SoccerNet.Downloader import SoccerNetDownloader

# Disable telemetry and suppress SSL warnings
os.environ["SOCCERNET_DISABLE_TELEMETRY"] = "1"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_soccernet_data():
    download_dir = os.path.join(os.getcwd(), "data", "soccernet_raw")
    os.makedirs(download_dir, exist_ok=True)
    
    print("[INFO] Initializing SoccerNet Downloader...")
    downloader = SoccerNetDownloader(LocalDirectory=download_dir)
    
    try:
        downloader.downloadGames(files=["Labels-v2.json"], split=["train"])
        print("[SUCCESS] SoccerNet action annotations downloaded successfully.")
    except Exception as e:
        print(f"[NOTE] Download status/cached: {e}")

if __name__ == "__main__":
    fetch_soccernet_data()