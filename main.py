import pandas as pd
import numpy as np


# OPTIONS ==============================================================================================================

# pre-processing options
ASSUME_ZERO_TORCHES = True  # assume 0 torches if not provided, removes rows with no torch values if False
TITLE_CASE_ISLAND_NAME = True  # some island names have incorrect capitalisation, this fixes them

# validation options
VALIDATE_MSM_DATE = True  # make sure the provided date exists and is valid
VALIDATE_DAY_OR_NIGHT = False  # for paironormals: of the two day/night columns, at least one must be true
VALIDATE_ISLAND_NAME = True  # checks the island name is in the list of possible island names
VALIDATE_TORCH_COUNT = True  # checks that torches is a number between 0-10
VALIDATE_PARENTS_EXIST = True  # check that parents are in the list of monsters that can breed
VALIDATE_PARENT_LEVELS = True  # levels must exist and be between 4-20
VALIDATE_RESULTS_EXIST = True  # check that results are in the list of monsters that can be bred

# post-processing options
REMOVE_TIME_SINCE_RESET = True  # only required for analysing stuff that resets independently of the date - drops column if not required
RARE_PARENTS_AS_COMMON = False  # makes all parents common. OFF by default as it messes with rare + common same species breeding, but can be useful for other analysis

# ======================================================================================================================

# list of possible island names
island_names = ["Plant", "Cold", "Air", "Water", "Earth", "Shugabush", "Ethereal", "Haven", "Oasis", "Mythical", "Light", "Psychic", "Faerie", "Bone", "Sanctum", "Shanty", "M Plant", "M Cold", "M Air", "M Water", "M Earth", "M Light", "M Psychic", "M Faerie", "M Bone"]

# live fetching the master sheet as a csv
SHEET_ID = "15kDI5lQL7szwh4YbjeZ6c4xRcLNpiMkXwLwfQzqGhCQ"
GID = "0"
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
print("Fetching breeding data from:", url)
df = pd.read_csv(url, header=0)

print("Breeding data fetched")

# live fetching the list of monsters as a csv
VALIDATION_SHEET_ID = "1jn0Pt8SH0ve0WiH8RZlL-nyQODSriUCOJQlN6yLc9_E"
VALIDATION_GID = "1001758888"
url_val = f"https://docs.google.com/spreadsheets/d/{VALIDATION_SHEET_ID}/export?format=csv&gid={VALIDATION_GID}"
print("Fetching validation data from:", url_val)
df_val = pd.read_csv(url_val, usecols=[1, 2], header=0)
print("Validation data fetched")

all_parent_monsters = df_val['Monsters that breed'].dropna().unique().tolist()
all_result_monsters = df_val['Monsters that are bred'].dropna().unique().tolist()

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
        print("there should only be two unnamed columns, one for each parent level")
        exit(1)  # format has changed, exit

# renaming the old Parent 1/2 columns to Parent 1/2 Species to fit with the flattened structure
df.rename(columns={'Parent 1': 'Parent 1 Species', 'Parent 2': 'Parent 2 Species'}, inplace=True)
# drops the second row which is now redundant
df = df.drop(index=0).reset_index(drop=True)

# saving the flattened csv for reference (to test sanitization and validation steps)
df.to_csv('msm_data_flattened.csv', index=False)

# storing row coercions for summary at end
coerced = {}

# cleaning up island names if required
if TITLE_CASE_ISLAND_NAME:
    island_col = [col for col in df.columns if 'Island' in col][0]
    coerced['title_case_island_name'] = (df[island_col] != df[island_col].str.title()).sum()
    df[island_col] = df[island_col].str.title()

# coercing blank torch entries to zero if required
if ASSUME_ZERO_TORCHES:
    torch_col = [col for col in df.columns if 'Torches' in col][0]
    coerced['assume_zero_torches'] = df[torch_col].isna().sum() + (df[torch_col] == '').sum()
    df[torch_col] = pd.to_numeric(df[torch_col], errors='coerce').fillna(0).astype(int)


# the df is now in a workable format so can start validation
# each check runs on the original then a cleaned version is created at the end with violations removed or coerced
original = df.copy()
# storing row violation indexes for each rule
bad = {}  # dict of {rule_name: set(indexes)}

# date validation
if VALIDATE_MSM_DATE:
    date_col = [col for col in df.columns if 'Date' in col][0]
    bad['date'] = set(original.index[pd.to_datetime(original[date_col], errors='coerce').isna()])
else:
    bad['date'] = set()

# day? or night? validation
if VALIDATE_DAY_OR_NIGHT:
    day_col = [col for col in df.columns if 'Day?' in col][0]
    night_col = [col for col in df.columns if 'Night?' in col][0]
    # at least one of the two columns must be True
    ok = (original[day_col] == True) | (original[night_col] == True)
    bad['daynight'] = set(original.index[~ok])

# time since reset validation or removal
if REMOVE_TIME_SINCE_RESET:
    time_col = [col for col in df.columns if 'Time since reset' in col][0]
    bad['time'] = set()
else:
    time_col = [col for col in df.columns if 'Time since reset' in col][0]
    bad['time'] = set(original.index[pd.to_timedelta(original[time_col], errors='coerce').isna()])


# island name validation
if VALIDATE_ISLAND_NAME:
    island_col = [col for col in df.columns if 'Island' in col][0]
    ok = original[island_col].isin(island_names)
    bad['island'] = set(original.index[~ok])
else:
    bad['island'] = set()

# torch count validation
if VALIDATE_TORCH_COUNT:
    torch_col = [col for col in df.columns if 'Torches' in col][0]
    torches = pd.to_numeric(original[torch_col], errors='coerce')
    ok = torches.between(0, 10)
    bad['torches'] = set(original.index[~ok])
else:
    bad['torches'] = set()


# parent monster validation
if VALIDATE_PARENTS_EXIST:
    parent1_col = [col for col in df.columns if 'Parent 1 Species' in col][0]
    parent2_col = [col for col in df.columns if 'Parent 2 Species' in col][0]
    ok = original[parent1_col].isin(all_parent_monsters) & original[parent2_col].isin(all_parent_monsters)
    bad['parents'] = set(original.index[~ok])
else:
    bad['parents'] = set()

# parent level validation
if VALIDATE_PARENT_LEVELS:
    parent1_level_col = [col for col in df.columns if 'Parent 1 Level' in col][0]
    parent2_level_col = [col for col in df.columns if 'Parent 2 Level' in col][0]
    level1 = pd.to_numeric(original[parent1_level_col], errors='coerce')
    level2 = pd.to_numeric(original[parent2_level_col], errors='coerce')
    ok = (level1.between(4, 20)) & (level2.between(4, 20))
    bad['levels'] = set(original.index[~ok])

# result monster validation
if VALIDATE_RESULTS_EXIST:
    result_col = [col for col in df.columns if 'Result Monster' in col][0]
    ok = original[result_col].isin(all_result_monsters)
    bad['result'] = set(original.index[~ok])
else:
    bad['results'] = set()

to_drop = set()
for rule, indexes in bad.items():
    if len(indexes) > 0:
        print(f"Found {len(indexes)} violations of rule: {rule}")
        to_drop = to_drop.union(indexes)
        print(original.loc[list(indexes)])

# making the clean data set
cleaned = original

cleaned = cleaned.drop(index=to_drop).reset_index(drop=True)

# post processing

# treat rare parents as common?
if RARE_PARENTS_AS_COMMON:
    parent1_col = [col for col in cleaned.columns if 'Parent 1 Species' in col][0]
    parent2_col = [col for col in cleaned.columns if 'Parent 2 Species' in col][0]
    coerced['rare_parents_as_common'] = cleaned[parent1_col].str.startswith('Rare ').sum() + cleaned[parent2_col].str.startswith('Rare ').sum()
    cleaned[parent1_col] = cleaned[parent1_col].str.replace('Rare ', '', regex=False)
    cleaned[parent2_col] = cleaned[parent2_col].str.replace('Rare ', '', regex=False)
    print(f"[x] Converted {coerced['rare_parents_as_common']} rare parents to common\n")

# drop time since reset?
if REMOVE_TIME_SINCE_RESET:
    cleaned = cleaned.drop(columns=[time_col])


print("\nSummary ================================")

if REMOVE_TIME_SINCE_RESET:
    print(f" [✓] Dropped column: {time_col}")

total_coercions = 0
for rule, count in coerced.items():
    if count > 0:
        total_coercions += count
        print(f" [✓] Coerced {count} entries for: {rule}")


total_violations = 0
for rule, indexes in bad.items():
    if len(indexes) > 0:
        total_violations += len(indexes)
        print(f" [✓] Removed {len(indexes)} violations of rule: {rule}")

print("\n Original row count:", len(original))
print(f" Unique rows dropped: {len(to_drop)}")
print(" Cleaned row count:", len(cleaned))

print("========================================")

cleaned.to_csv('msm_data.csv', index=False)

print("Exported cleaned data to msm_data.csv")







