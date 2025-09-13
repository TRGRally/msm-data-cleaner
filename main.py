import pandas as pd
import numpy as np

# stops pandas skipping columns when printing (for checking the dataframe flattening works)
pd.set_option('display.max_columns', None)

# sanitization options
VALIDATE_MSM_DATE = True  # make sure the provided date exists and is valid
REMOVE_TIME_SINCE_RESET = True  # only required for analysing stuff that resets independently of the date - drops column if not required
ASSUME_ZERO_TORCHES = True  # assume 0 torches if not provided, removes rows with no torch values if False
VALIDATE_PARENTS_EXIST = True  # check that parents are in the list of monsters that can breed
VALIDATE_RESULTS_EXIST = True  # check that results are in the list of monsters that can be bred

# master sheet details
SHEET_ID = "15kDI5lQL7szwh4YbjeZ6c4xRcLNpiMkXwLwfQzqGhCQ"
GID = "0"

# live fetch of the sheet as a csv
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
print("Fetching breeding data from:", url)
df = pd.read_csv(url, header=0)
print("Breeding data fetched")

# monster breeding details
VALIDATION_SHEET_ID = "1jn0Pt8SH0ve0WiH8RZlL-nyQODSriUCOJQlN6yLc9_E"
VALIDATION_GID = "1001758888"
url_val = f"https://docs.google.com/spreadsheets/d/{VALIDATION_SHEET_ID}/export?format=csv&gid={VALIDATION_GID}"
print("Fetching validation data from:", url_val)
df_val = pd.read_csv(url_val, usecols=[1, 2], header=0)
print("Validation data fetched")

all_parent_monsters = df_val['Monsters that breed'].dropna().unique().tolist()
all_result_monsters = df_val['Monsters that are bred'].dropna().unique().tolist()
#print(all_parent_monsters)
#print(all_result_monsters)


# flattening nested columns
unnamed_col_count = 0
for col in df.columns:
    if 'Unnamed' in col:
        prev_col = df.columns[df.columns.get_loc(col) - 1]
        df.rename(columns={col: f"{prev_col} Level"}, inplace=True)
        unnamed_col_count += 1

    # replaces newlines in column names with spaces if present
    if '\n' in col:
        df.rename(columns={col: col.replace('\n', ' ')}, inplace=True)

    # strips double quotes from column names if present
    if '"' in col:
        df.rename(columns={col: col.replace('"', '')}, inplace=True)

    if unnamed_col_count > 2:
        exit(1)  # format has changed, exit

# renaming the old Parent 1/2 columns to Parent 1/2 Species to fit with the flattened structure
df.rename(columns={'Parent 1': 'Parent 1 Species', 'Parent 2': 'Parent 2 Species'}, inplace=True)
# drops the second row which is now redundant
df = df.drop(index=0).reset_index(drop=True)

# date validation
if VALIDATE_MSM_DATE:
    date_col = [col for col in df.columns if 'Date' in col][0]
    print(date_col)
    df = df[pd.to_datetime(df[date_col], errors='coerce').notna()].reset_index(drop=True)

# time since reset validation or removal
if REMOVE_TIME_SINCE_RESET:
    time_col = [col for col in df.columns if 'Time since reset' in col][0]
    df = df.drop(columns=[time_col])
else:
    time_col = [col for col in df.columns if 'Time since reset' in col][0]
    df = df[pd.to_timedelta(df[time_col], errors='coerce').notna()].reset_index(drop=True)


# assume zero torches coercion or removal of blank torch-count entries
if ASSUME_ZERO_TORCHES:
    torch_col = [col for col in df.columns if 'Torches' in col][0]
    df[torch_col] = df[torch_col].fillna(0)
else:
    torch_col = [col for col in df.columns if 'Torches' in col][0]
    df = df[pd.to_numeric(df[torch_col], errors='coerce').notna()].reset_index(drop=True)

# parent monster validation
if VALIDATE_PARENTS_EXIST:
    parent1_col = [col for col in df.columns if 'Parent 1 Species' in col][0]
    parent2_col = [col for col in df.columns if 'Parent 2 Species' in col][0]

    invalid_parents_df = df[~df[parent1_col].isin(all_parent_monsters) | ~df[parent2_col].isin(all_parent_monsters)]
    if not invalid_parents_df.empty:
        print("Invalid parent monster entries:")
        print(invalid_parents_df)

    df = df[df[parent1_col].isin(all_parent_monsters) & df[parent2_col].isin(all_parent_monsters)].reset_index(drop=True)

# result monster validation
if VALIDATE_RESULTS_EXIST:
    result_col = [col for col in df.columns if 'Result Monster' in col][0]

    invalid_results_df = df[~df[result_col].isin(all_result_monsters)]
    if not invalid_results_df.empty:
        print("Invalid result monster entries:")
        print(invalid_results_df)

    df = df[df[result_col].isin(all_result_monsters)].reset_index(drop=True)

print(df)

df.to_csv('msm_data.csv', index=False)

