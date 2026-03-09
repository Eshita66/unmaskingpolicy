import pandas as pd
import os

# ---------- SET YOUR PATHS HERE ----------
INPUT_CSV  = r"\dsurls_nodup.csv"   
OUTPUT_CSV = r"\app_names_unique.csv"        
# ----------------------------------------


def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Input file not found: {INPUT_CSV}")
        return

  
    df = pd.read_csv(INPUT_CSV)

    df.columns = [c.strip().lower() for c in df.columns]
    print("Columns detected:", df.columns.tolist())

    if "app_name" not in df.columns:
        print(f"'app_name' column not found. Columns are: {df.columns.tolist()}")
        return

    print(f"Rows before making app_name unique: {len(df)}")

 
    df_unique = df.drop_duplicates(subset=["app_name"], keep="first")

    print(f"Rows after making app_name unique: {len(df_unique)}")

    # Save to new CSV
    df_unique.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved CSV with unique app_name to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
