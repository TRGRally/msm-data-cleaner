import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry
from io import StringIO
import numpy as np
import Dataset


# OPTIONS ==============================================================================================================

# pre-processing options
ASSUME_ZERO_TORCHES = True  # assume 0 torches if not provided, removes rows with no torch values if False
ASSUME_NO_TITAN_SKIN = True  # assume titan skin is false if not provided, removes rows with no titan skin values if False
TITLE_CASE_ISLAND_NAME = True  # some island names have incorrect capitalisation, this fixes them

# validation options
VALIDATE_MSM_DATE = True  # make sure the provided date exists and is valid
VALIDATE_DAY_OR_NIGHT = False  # for paironormals: of the two day/night columns, at least one must be true
VALIDATE_ISLAND_NAME = True  # checks the island name is in the list of possible island names
VALIDATE_TITAN_SKIN = True  # checks titan skin is either true or false
VALIDATE_TORCH_COUNT = True  # checks that torches is a number between 0-10
VALIDATE_PARENTS_EXIST = True  # check that parents are in the list of monsters that can breed
VALIDATE_PARENT_LEVELS = True  # levels must exist and be between 4-20
VALIDATE_RESULTS_EXIST = True  # check that results are in the list of monsters that can be bred
VALIDATE_AVAILABILITY = False  # checks that a monster was available on the date of breeding if event based

# post-processing options
REMOVE_TIME_SINCE_RESET = True  # only required for analysing stuff that resets independently of the date - drops column if not required
RARE_PARENTS_AS_COMMON = False  # makes all parents common. OFF by default as it messes with rare + common same species breeding, but is useful for the majority of stuff
USE_SOURCE_PSEUDONYMS = True  # replaces usernames in the sources column with Player1, Player2 etc. to preserve privacy. Lets me leave the results data on GitHub without feeling bad.

# ======================================================================================================================

# list of possible island names
island_names = ["Plant", "Cold", "Air", "Water", "Earth", "Shugabush", "Ethereal", "Haven", "Oasis", "Mythical", "Light", "Psychic", "Faerie", "Bone", "Sanctum", "Shanty", "M Plant", "M Cold", "M Air", "M Water", "M Earth", "M Light", "M Psychic", "M Faerie", "M Bone"]

# session setup with retry logic as google sheets errors on request sometimes
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
)
session.mount("https://", HTTPAdapter(max_retries=retries))


# live fetching the master sheet as a csv
SHEET_ID = "15kDI5lQL7szwh4YbjeZ6c4xRcLNpiMkXwLwfQzqGhCQ"
GID = "0"
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
print("Fetching breeding data from:", url)
resp = session.get(url)
resp.raise_for_status()
df = pd.read_csv(StringIO(resp.text), header=0)
print("Breeding data fetched")


# live fetching the list of monsters as a csv
VALIDATION_SHEET_ID = "1jn0Pt8SH0ve0WiH8RZlL-nyQODSriUCOJQlN6yLc9_E"
VALIDATION_GID = "1001758888"
url_val = f"https://docs.google.com/spreadsheets/d/{VALIDATION_SHEET_ID}/export?format=csv&gid={VALIDATION_GID}"
print("Fetching validation data from:", url_val)
resp_val = session.get(url_val)
resp_val.raise_for_status()
df_val = pd.read_csv(StringIO(resp_val.text), usecols=[1, 2], header=0)
print("Validation data fetched")

all_parent_monsters = df_val['Monsters that breed'].dropna().unique().tolist()
all_result_monsters = df_val['Monsters that are bred'].dropna().unique().tolist()

# opening availabilities.csv as a dataframe, contains an incomplete list of breeding availabilities (WIP)
df_avail = pd.read_csv('./other data/availabilities.csv', header=0)
# creating a dict of {monster: [(start1, stop1), (start2, stop2), ...]}
availabilities = {}
for idx, row in df_avail.iterrows():
    start = pd.to_datetime(row['startdate'], errors='coerce')
    stop = pd.to_datetime(row['stopdate'], errors='coerce')
    monsters = [m.strip() for m in row['monsters'].split(',')]
    for monster in monsters:
        if monster not in availabilities:
            availabilities[monster] = []
        availabilities[monster].append((start, stop))
print("Loaded availabilities for", len(availabilities), "monsters from ./other data/availabilities.csv")


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
df.to_csv('./intermediary logs/msm_data_flattened.csv', index=False)


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

# coercing blank titan skin entries to false if required
if ASSUME_NO_TITAN_SKIN:
    # pandas freaks out unless this nonsense is here
    with pd.option_context('future.no_silent_downcasting', True):
        skin_col = [col for col in df.columns if 'Titan' in col][0]
        coerced['assume_no_titan_skin'] = df[skin_col].isna().sum() + (df[skin_col] == '').sum()
        df[skin_col] = df[skin_col].fillna(False)
        df[skin_col] = df[skin_col].astype(bool)


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

# titan skin validation
if VALIDATE_TITAN_SKIN:
    skin_col = [col for col in df.columns if 'Titan' in col][0]
    ok = original[skin_col].isin([True, False, 'TRUE', 'FALSE', 'True', 'False', 1, 0, '1', '0'])
    bad['skin'] = set(original.index[~ok])
else:
    bad['skin'] = set()

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

# monster is available validation
if VALIDATE_AVAILABILITY:
    # availability isn't a complete list! off by default
    date_col = [col for col in df.columns if 'Date' in col][0]
    result_col = [col for col in df.columns if 'Result Monster' in col][0]
    bad['availability'] = set()
    for idx, row in original.iterrows():
        monster = row[result_col]
        date = row[date_col]
        if monster in availabilities:
            ok = False
            for start, stop in availabilities[monster]:
                if start <= date <= stop:
                    ok = True
                    break
            if not ok:
                bad['availability'].add(idx)
else:
    bad['availability'] = set()


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

# replace source names with pseudonyms?
pseudonym_count = 0
if USE_SOURCE_PSEUDONYMS:
    source_col = [col for col in cleaned.columns if 'Source' in col][0]
    unique_names = cleaned[source_col].dropna().unique().tolist()
    name_map = {name: f"Player{idx+1}" for idx, name in enumerate(unique_names)}
    pseudonym_count = len(unique_names)
    cleaned[source_col] = cleaned[source_col].map(name_map).fillna(cleaned[source_col])
    print(f"[x] Replaced {len(unique_names)} unique source names with pseudonyms\n")


print("\nSummary ================================")

if USE_SOURCE_PSEUDONYMS:
    print(f" [✓] Replaced {pseudonym_count} unique source names with pseudonyms")

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

#print(availabilities)

print("Exported cleaned data to msm_data.csv")

# loading the dataset class for analysis
dataset = Dataset.Dataset('msm_data.csv')
dataset.export_results_grouped_by_combo()







