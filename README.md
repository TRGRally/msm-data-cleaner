## Created for use with the Technical MSM Combined Data sheet

## Disclaimer

This is a work in progress! Make sure to pull for the latest changes regularly.

### Features
    
You can either use the exported file from this script or include the code in your own project to use the dataframe directly. 

Current features:

- Imports live breeding data from the master sheet as a pandas dataframe
- Flattens nested headers into a single row
- Sanitizes column names by removing newlines and quotes present in the master sheet
- Checks dates are valid (master sheet uses "not empty" to include rows but these could be any text)
- Option to assume a blank entry in the torches column means "zero torches"
- Option to drop the "time since reset" column or keep only entries that include it (very few entries track this)
- CSV Export

Planned stuff:

- Proper validation for all columns including value constraints (check all columns have data and of the right format and range)
- Island name validation against a known list
- Parent species and result species validation against a known list
- Optional username anonymization

### Usage

1. Python, pandas, numpy required
2. Edit the options at the top of "main.py" to your liking
3. Run "main.py"
4. msm_data.csv should be created in the same directory, this is the cleaned data