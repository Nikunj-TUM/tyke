# Group Companies with Instruments Script

## Overview

This script (`group_companies_instruments.py`) processes Infomerics JSON data files and groups companies with their financial instruments. It provides both structured JSON output and human-readable text format, along with statistics and summaries.

## Features

- **Group by Company**: Automatically groups all instruments by company name
- **Multiple Output Formats**: 
  - JSON format for programmatic use
  - Pretty text format for human readability
- **Statistics & Summary**: Displays summary statistics including:
  - Total companies and instruments
  - Average instruments per company
  - Top 10 companies by number of instruments
- **Comprehensive Data**: Captures:
  - All instruments per company
  - Ratings and outlooks
  - Instrument amounts
  - Dates and reference URLs
- **Flexible Usage**: Can be used as a command-line tool or imported as a Python module

## Installation

No additional dependencies required beyond standard Python 3 libraries.

## Command Line Usage

### Basic Usage

```bash
# Group data from a JSON file (creates output file automatically)
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json

# Output: json_data/infomerics_2024-10-01_2024-10-15_grouped.json
```

### Custom Output File

```bash
# Specify custom output filename
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -o my_output.json
```

### Pretty Text Format

```bash
# Generate human-readable text format instead of JSON
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -f pretty -o output.txt
```

### Summary Only (No File Output)

```bash
# View summary statistics without saving output file
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json --no-save
```

### Quiet Mode

```bash
# Save file without printing summary
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json --no-summary
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `input_file` | Path to the input JSON file (required) |
| `-o, --output` | Custom output file path |
| `-f, --format` | Output format: `json` or `pretty` (default: json) |
| `--no-save` | Only print summary, don't save output file |
| `--no-summary` | Skip printing summary statistics |
| `-h, --help` | Show help message |

## Programmatic Usage

You can also import and use the functions in your own Python scripts:

```python
from group_companies_instruments import load_json_data, group_by_company

# Load and group data
data = load_json_data('json_data/infomerics_2024-10-01_2024-10-15.json')
grouped_data = group_by_company(data)

# Access specific company
company_info = grouped_data['Marwadi Shares & Finance Limited']
print(f"Total instruments: {company_info['total_instruments']}")

# Iterate through all instruments
for instrument in company_info['instruments']:
    print(f"{instrument['instrument_category']}: {instrument['rating']}")
```

See `example_grouping_usage.py` for more detailed examples.

## Output Format

### JSON Format

The JSON output structure:

```json
{
  "Company Name": {
    "company_name": "Company Name",
    "total_instruments": 3,
    "dates": ["Oct 15, 2024"],
    "urls": ["https://www.infomerics.com/..."],
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

### Pretty Text Format

The text format includes:
- Company name header
- Total instrument count
- All dates referenced
- Detailed list of each instrument
- Reference URLs

Example:

```
================================================================================
COMPANY: ABC Company Limited
================================================================================
Total Instruments: 2
Dates: Oct 15, 2024

Instruments:
--------------------------------------------------------------------------------

  1. Long Term Bank Facilities
     Rating: IVR BBB
     Outlook: Stable
     Amount: Rs. 100.00 Cr.
     Date: Oct 15, 2024

  2. Short Term Bank Facilities
     Rating: IVR A2
     Outlook: Stable
     Amount: Rs. 50.00 Cr.
     Date: Oct 15, 2024

References:
  - https://www.infomerics.com/admin/uploads/pr-ABC-Company-15oct24.pdf
```

## Summary Statistics

When run with default settings, the script displays:

```
================================================================================
SUMMARY
================================================================================
Total Companies: 115
Total Instruments: 237
Average Instruments per Company: 2.06

Top 10 Companies by Number of Instruments:
--------------------------------------------------------------------------------
 1. Company A: 9 instruments
 2. Company B: 6 instruments
 ...
================================================================================
```

## Use Cases

1. **Data Analysis**: Convert flat JSON records into grouped structure for easier analysis
2. **Report Generation**: Create human-readable reports of companies and their instruments
3. **Data Validation**: Quickly identify companies with multiple instruments
4. **API Development**: Use grouped data structure for building APIs
5. **Database Import**: Prepare data for relational database import

## Examples

### Process All JSON Files in a Directory

```bash
# Process all JSON files and save with default names
for file in json_data/*.json; do
    python3 group_companies_instruments.py "$file"
done
```

### Create Both JSON and Text Outputs

```bash
# Create both formats for the same data
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -o grouped.json
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -f pretty -o grouped.txt
```

### Quick Statistics Check

```bash
# Just see the summary without creating files
python3 group_companies_instruments.py json_data/*.json --no-save
```

## Data Structure

### Input Data Format

The script expects JSON files with this structure:

```json
[
  {
    "company_name": "Company Name",
    "instrument_category": "Long Term Bank Facilities",
    "rating": "IVR BBB",
    "outlook": "Stable",
    "instrument_amount": "Rs. 100.00 Cr.",
    "date": "Oct 15, 2024",
    "url": "https://..."
  }
]
```

### Output Data Structure

Each company entry in the output contains:

- `company_name`: The company's name
- `total_instruments`: Count of instruments for this company
- `dates`: List of unique dates (sorted)
- `urls`: List of reference URLs
- `instruments`: Array of instrument objects with:
  - `instrument_category`: Type of instrument
  - `rating`: Credit rating
  - `outlook`: Rating outlook
  - `instrument_amount`: Amount in currency
  - `date`: Date of rating

## Performance

The script efficiently handles:
- Files with thousands of records
- Multiple companies with many instruments each
- Large date ranges

Typical performance:
- 237 records (115 companies): < 1 second
- 6,864 records: ~2-3 seconds

## Error Handling

The script handles:
- Missing files (with clear error message)
- Invalid JSON (with parse error details)
- Missing or null fields in data (uses 'N/A' defaults)
- Invalid output paths (with write error details)

## Tips

1. **Large Files**: For very large JSON files, consider using `--no-summary` to speed up processing
2. **Batch Processing**: Use shell loops to process multiple files
3. **Data Quality**: Review the summary statistics to identify data quality issues
4. **Integration**: Import the module functions for custom data processing pipelines

## Related Scripts

- `scrape_press_release_page.py`: Scrapes data from Infomerics website
- `extract_data_press_release_page.py`: Extracts structured data from scraped HTML
- `combine_csv_files.py`: Combines multiple CSV files
- `example_grouping_usage.py`: Examples of programmatic usage

## Support

For issues or questions:
1. Check that input JSON file exists and is valid
2. Verify Python 3.x is installed
3. Review error messages for specific issues
4. Check file permissions for output directory

## License

This script is part of the Infomerics data extraction project.

