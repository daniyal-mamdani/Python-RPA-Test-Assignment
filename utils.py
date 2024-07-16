import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def load_config(config_file):
    with open(config_file) as f:
        return json.load(f)


def convert_timestamp_to_datetime(timestamp):
    timestamp_seconds = int(timestamp) / 1000
    return datetime.fromtimestamp(timestamp_seconds)


def save_to_excel(articles):
    excel_file = Path("output/news_articles.xlsx")
    df = pd.DataFrame(articles)
    df.to_excel(excel_file, index=False, header=True)
