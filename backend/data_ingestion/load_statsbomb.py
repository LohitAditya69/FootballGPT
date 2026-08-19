import pandas as pd
from statsbombpy import sb
import os

def fetch_match_data():
    print("[INFO] Fetching available StatsBomb competitions...")
    
    # Pull matches for the 2022 FIFA World Cup (comp_id=43, season_id=106)
    world_cup_matches = sb.matches(competition_id=43, season_id=106)
    print(f"\n[SUCCESS] Loaded {len(world_cup_matches)} World Cup matches.")

    # Pull granular event data for a specific sample match
    sample_match_id = world_cup_matches.iloc[0]['match_id']
    match_events = sb.events(match_id=sample_match_id)
    
    print(f"[SUCCESS] Loaded {len(match_events)} tactical events for match ID {sample_match_id}.")
    
    # Save a sample to CSV locally for inspection (this won't be pushed to GitHub)
    os.makedirs("data/statsbomb_raw", exist_ok=True)
    match_events.to_csv(f"data/statsbomb_raw/match_{sample_match_id}.csv", index=False)
    print("[INFO] Sample match data saved locally.")

if __name__ == "__main__":
    fetch_match_data()