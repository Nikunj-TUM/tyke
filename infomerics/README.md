# Infomerics Press Release Scraper

This directory contains tools to scrape and extract data from Infomerics press release pages.

## Files

### Core Scripts
- `scrape_press_release_page.py` - Main scraper script that fetches HTML from Infomerics website
- `extract_data_press_release_page.py` - Data extraction module using BeautifulSoup
- `group_companies_instruments.py` - Groups companies with their instruments from JSON files
- `combine_csv_files.py` - Combines multiple CSV files into one

### Example & Usage
- `example_usage.py` - Examples for using the scraper
- `example_grouping_usage.py` - Examples for programmatic grouping

### Configuration
- `requirements.txt` - Python dependencies

### Documentation
- `GROUP_COMPANIES_README.md` - Full documentation for grouping script
- `QUICK_START_GROUPING.md` - Quick start guide for grouping
- `PROJECT_SUMMARY.md` - Project overview and summary

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python scrape_press_release_page.py <from_date> <to_date>
```

### Example

```bash
python scrape_press_release_page.py 2025-10-09 2025-10-12
```

This will:
1. Make a GET request to `https://www.infomerics.com/latest-press-release_date_wise.php?fromdate=2025-10-09&todate=2025-10-12`
2. Extract company data from the HTML response
3. Save the data in multiple formats with date-specific filenames

## Output Files

The scraper generates files with the naming pattern `infomerics_<from_date>_<to_date>`:

### Raw Data
- `infomerics_2025-10-09_2025-10-12.json` - Raw response data from the website

### Extracted Data
- `infomerics_2025-10-09_2025-10-12.json` - Extracted company data in JSON format
- `infomerics_2025-10-09_2025-10-12.csv` - Extracted data in CSV format
- `infomerics_2025-10-09_2025-10-12.xlsx` - Excel file with analysis sheets (if pandas available)

## Features

### Scraper (`scrape_press_release_page.py`)
- **HTTP Requests**: Makes GET requests to Infomerics website with proper headers
- **Date Validation**: Validates input dates are in YYYY-MM-DD format
- **Error Handling**: Comprehensive error handling for network issues
- **Data Preservation**: Saves raw HTML response for debugging/reprocessing
- **Integration**: Seamlessly integrates with the extraction module

### Extractor (`extract_data_press_release_page.py`)
- **BeautifulSoup Parsing**: Robust HTML parsing
- **Complete Data Extraction**: Extracts company names, ratings, amounts, dates, URLs
- **Duplicate Detection**: Automatically filters duplicate entries
- **Multiple Output Formats**: JSON, CSV, and Excel with analysis
- **Data Cleaning**: Proper text and URL cleaning

### Grouping Tool (`group_companies_instruments.py`)
- **Company Grouping**: Groups all instruments by company name
- **Multiple Formats**: JSON (structured) and Pretty (human-readable) outputs
- **Statistics**: Summary statistics and top companies by instrument count
- **Flexible Usage**: Command-line tool or Python module
- **Data Aggregation**: Collects dates, URLs, and all instruments per company

## Data Fields Extracted

For each financial instrument:

1. **Company Name** - Full company name
2. **Instrument Category** - Type of financial instrument
3. **Rating** - Credit rating assigned
4. **Outlook** - Rating outlook (Positive, Negative, Stable, etc.)
5. **Instrument Amount** - Financial amount with proper formatting
6. **Date** - "As on" date from the rating
7. **URL** - Direct link to the rating document (PDF)

## Error Handling

The scraper includes comprehensive error handling for:
- Network connectivity issues
- Invalid date formats
- HTTP errors (4xx, 5xx)
- Parsing errors
- File I/O errors

## Example Output

```
Scraping Infomerics data from 2025-10-09 to 2025-10-12...
Response status: 200
Response size: 1234567 characters
Response data saved to: infomerics_2025-10-09_2025-10-12.json

Extracting company data...
Found 308 company headers
Processing company 1: Acute retail Infra Private Limited
...

=== HTML EXTRACTION SUMMARY ===
Total instruments extracted: 622
Unique companies: 308
URLs found: 622/622
Amounts found: 622/622
Dates found: 622/622

=== SCRAPING AND EXTRACTION COMPLETE ===
Date range: 2025-10-09 to 2025-10-12
Total instruments extracted: 622
```

## Troubleshooting

1. **Network Issues**: Check internet connection and try again
2. **Date Format Errors**: Ensure dates are in YYYY-MM-DD format
3. **No Data Found**: Check if the date range contains press releases
4. **Import Errors**: Install missing dependencies with `pip install -r requirements.txt`

## Rate Limiting

The scraper includes appropriate delays and user-agent headers to be respectful to the Infomerics website. If you need to scrape multiple date ranges, consider adding delays between requests.

## Grouping Companies with Instruments

After scraping and extracting data, you can group companies with their instruments:

### Quick Usage

```bash
# Group companies from a JSON file
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json

# Create human-readable text report
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -f pretty -o report.txt

# Just view summary statistics
python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json --no-save
```

### Example Output

**Console Summary:**
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

**Grouped JSON Structure:**
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

### Documentation

- **Quick Start**: See `QUICK_START_GROUPING.md`
- **Full Documentation**: See `GROUP_COMPANIES_README.md`
- **Code Examples**: Run `python3 example_grouping_usage.py`

## Complete Workflow

1. **Scrape Data**: `python3 scrape_press_release_page.py 2024-10-01 2024-10-15`
2. **Group Companies**: `python3 group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json`
3. **Analyze Results**: Review the generated JSON or text files
