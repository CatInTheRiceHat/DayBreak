import os
from pathlib import Path
import pandas as pd
import numpy as np
import hashlib

DATA_DIR = Path("datasets")
PROCESSED_CSV = DATA_DIR / "processed_dataset.csv"
ITEMS_PARQUET = Path("VK-LSVD/metadata/items_metadata.parquet")

TOPICS = ["entertainment", "education", "lifestyle", "news", "gaming", "music", "sports"]
TRAITS = ["urban", "rural", "suburban", "international"]

def get_hash_index(val, length):
    h = int(hashlib.sha256(str(val).encode('utf-8')).hexdigest(), 16)
    return h % length

def process_vklsvd_data(max_items=1000):
    """
    Reads the anonymized VK-LSVD items metadata, formats it,
    and generates simulated attributes required by the algorithm plan.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    if not ITEMS_PARQUET.exists():
        print(f"Warning: {ITEMS_PARQUET} not found. Creating a dummy dataset.")
        df = pd.DataFrame({
            "item_id": range(max_items),
            "author_id": np.random.randint(0, 100, max_items),
            "train_interactions_rank": np.random.randint(1, 100000, max_items),
        })
    else:
        df = pd.read_parquet(ITEMS_PARQUET)
        df = df.head(max_items).copy()
    
    # Bridge anonymized integer IDs and mathematical embeddings
    # We use hashing to ensure deterministic but semi-random assignment
    
    # Basic mapping
    df["video_id"] = "vid_" + df["item_id"].astype(str)
    df["channel"] = "creator_" + df["author_id"].astype(str)
    
    # Treat interactions rank as a proxy for view count (inverted if rank 1 is best, or just use raw if it's count)
    # The dataset says 'rank', so smaller is better? Let's just use it dynamically as view_count
    df["view_count"] = df["train_interactions_rank"] 
    if len(df) > 0 and df["view_count"].max() > 10000:
        # If it's truly a rank, let's invert it so higher is better
        max_rank = df["view_count"].max()
        df["view_count"] = max_rank - df["view_count"] + 1

    # Simulate required attributes
    df["topic"] = df["item_id"].apply(lambda x: TOPICS[get_hash_index(x, len(TOPICS))])
    df["creator_trait"] = df["author_id"].apply(lambda x: TRAITS[get_hash_index(x, len(TRAITS))])
    
    # Simulate tagging classes
    # Deterministic pseudo-randomness for reproducibility (using item_id)
    np.random.seed(42)
    df["prosocial"] = np.random.choice([0, 1], p=[0.7, 0.3], size=len(df))
    df["risk"] = np.random.choice([0, 1], p=[0.8, 0.2], size=len(df))

    # Simulate continuous comparison scores
    df["appearance_comparison"] = np.random.rand(len(df))
    df["opinion_comparison"] = np.random.rand(len(df))

    # Research-backed additions (§2.1 and §2.4 of Chrysalis research doc)
    # active_engagement_ratio: proxy for (comments + shares) / views — 0 to 1
    # Lower is typical; skew toward 0 to reflect real platform distributions
    df["active_engagement_ratio"] = np.random.beta(1.5, 8, size=len(df))

    # creator_authenticity: consistency of creator voice; moderate default distribution
    df["creator_authenticity"] = np.random.beta(5, 3, size=len(df))
    
    df.to_csv(PROCESSED_CSV, index=False)
    print(f"Saved {len(df)} records to {PROCESSED_CSV}")
    return df

if __name__ == "__main__":
    process_vklsvd_data()
