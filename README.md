## Created for use with the Technical MSM Combined Data sheet

You can either use the exported file from this script or include this as the first step in your own data processing pipeline.

## Disclaimers

This is a work in progress! Make sure to pull for the latest changes regularly.

The msm_data.csv file in this repo is intended for reference as it only includes data up to the last commit.

### Features

- Imports live breeding data from the master sheet as a pandas dataframe
- Flattens nested headers into a single row
- Sanitizes column names by removing newlines and quotes present in the master sheet
- Checks dates are valid (master sheet uses "not empty" to include rows but these could be any text)
- Island name validation against a known list
- Parent monster names and result monster names validation against a known list (not verification of breeding possibility)
- Parent monster level validation (between 4-20)
- Option to assume a blank entry in the torches column means "zero torches"
- Option to assume a blank entry in the titan skin column means "no titan skin"
- Option to drop the "time since reset" column or keep only entries that include it (very few entries track this)
- Option to replace source usernames with pseudonyms for privacy
- CSV Export

Planned stuff:

- Check if the breed was possible with the given parents (excluding event monsters)
- Track availability of event monsters and output possible breeds for each attempt given its date
- Track breeding bonanzas (ethereal, mythical) and output the multiplier for each mythical/ethereal attempt given its date


### Usage

1. Python, requests, pandas, numpy required
2. Edit the options at the top of "main.py" to your liking
3. Run "main.py"
4. msm_data.csv should be created in the same directory, this is the cleaned data

### Credits and Attribution
- availabilties.csv, groups.csv, specials.csv adapted from https://github.com/Bram-Arts/MSM-analysis