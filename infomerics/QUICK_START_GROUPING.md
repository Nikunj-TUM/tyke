# Quick Start Guide - Group Companies Script

## What Does This Script Do?

Takes JSON files with individual company/instrument records and groups them by company name, making it easy to see all instruments for each company.

**Before (Original JSON):**
```json
[
  {"company_name": "ABC Ltd", "instrument_category": "Long Term", ...},
  {"company_name": "ABC Ltd", "instrument_category": "Short Term", ...},
  {"company_name": "XYZ Ltd", "instrument_category": "Long Term", ...}
]
```

**After (Grouped JSON):**
```json
{
  "ABC Ltd": {
    "company_name": "ABC Ltd",
    "total_instruments": 2,
    "instruments": [
      {"instrument_category": "Long Term", ...},
      {"instrument_category": "Short Term", ...}
    ]
  },
  "XYZ Ltd": {
    "company_name": "XYZ Ltd",
    "total_instruments": 1,
    "instruments": [...]
  }
}
```

## Quick Commands

### 1. Basic Usage (Most Common)
```bash
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json
```
Creates: `json_data/infomerics_2024-10-01_2024-10-15_grouped.json`

### 2. Custom Output Name
```bash
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -o my_output.json
```

### 3. Human-Readable Text Format
```bash
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -f pretty -o report.txt
```

### 4. Just Show Summary
```bash
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json --no-save
```

## Example Output

### Console Summary
```
================================================================================
SUMMARY
================================================================================
Total Companies: 115
Total Instruments: 237
Average Instruments per Company: 2.06

Top 10 Companies by Number of Instruments:
--------------------------------------------------------------------------------
 1. Marwadi Shares & Finance Limited: 9 instruments
 2. Capri Global Capital Limited: 6 instruments
 ...
```

### JSON File Structure
```json
{
  "Company Name": {
    "company_name": "Company Name",
    "total_instruments": 2,
    "dates": ["Oct 15, 2024"],
    "urls": ["https://..."],
    "instruments": [
      {
        "instrument_category": "Long Term Bank Facilities",
        "rating": "IVR BBB",
        "outlook": "Stable",
        "instrument_amount": "Rs. 100.00 Cr.",
        "date": "Oct 15, 2024"
      }
    ]
  }
}
```

## Process All Files at Once

```bash
# Process all JSON files in the json_data directory
for file in json_data/*.json; do
    python3 group_companies_instruments.py "$file"
done
```

## Use in Python Code

```python
from group_companies_instruments import load_json_data, group_by_company

# Load and group
data = load_json_data('json_data/infomerics_2024-10-01_2024-10-15.json')
grouped = group_by_company(data)

# Access specific company
company = grouped['Marwadi Shares & Finance Limited']
print(f"Total instruments: {company['total_instruments']}")

# Loop through instruments
for instrument in company['instruments']:
    print(f"{instrument['instrument_category']}: {instrument['rating']}")
```

## Common Use Cases

1. **Analysis**: See which companies have the most instruments
2. **Reports**: Generate human-readable reports
3. **Data Export**: Prepare data for database import
4. **API**: Use grouped structure for REST API responses
5. **Comparison**: Compare companies side-by-side

## Files

- `group_companies_instruments.py` - Main script
- `example_grouping_usage.py` - Code examples
- `GROUP_COMPANIES_README.md` - Full documentation
- `grouped_example.json` - Example output

## Need Help?

View all options:
```bash
python3 group_companies_instruments.py --help
```

See code examples:
```bash
python3 example_grouping_usage.py
```

Read full documentation: `GROUP_COMPANIES_README.md`

