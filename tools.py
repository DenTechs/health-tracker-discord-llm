import json
from typing import List, Dict, Any
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def append_health(input):
    try:
        # Get current date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # First, read the existing data
        try:
            with open("health_db.json", "r") as file:
                db: Dict[str, List] = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is empty/invalid, start with empty dict
            db = {}

        # Create today's entry if it doesn't exist
        if today not in db:
            db[today] = []

        # Append the new item to today's list
        db[today].append({"name": input.get("name"), "calories": input.get("calories")})

        # Write the updated data back to the file
        with open("health_db.json", "w") as file:
            json.dump(db, file, indent=2)

        return "Successfully added to database"

    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error adding to database: {e}"

def get_total_calories(input):
    try:
        try:
            with open("health_db.json", "r") as file:
                db: Dict[str, List] = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is empty/invalid, return 0 calories
            return "The total calories consumed are 0 (no data found)"

        total_calories = 0
        for date, items in db.items():
            for item in items:
                calories = item.get("calories", 0)
                if isinstance(calories, (int, float)):
                    total_calories += calories

        return f"The total calories consumed across all days are {total_calories}"
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error retrieving total calories: {e}"

def get_daily_calories(input):
    try:
        # Get the date (default to today if not provided)
        date = input.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        try:
            with open("health_db.json", "r") as file:
                db: Dict[str, List] = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is empty/invalid, return 0 calories
            return f"The calories consumed on {date} are 0 (no data found)"

        # Check if the date exists in the database
        if date not in db:
            return f"The calories consumed on {date} are 0 (no data for this date)"

        daily_calories = 0
        for item in db[date]:
            calories = item.get("calories", 0)
            if isinstance(calories, (int, float)):
                daily_calories += calories

        return f"The calories consumed on {date} are {daily_calories}"
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error retrieving daily calories: {e}"
