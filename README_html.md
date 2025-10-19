# HTML Company Data Extractor

This script `extract_html_company_data.py` extracts company names, instrument categories, ratings, instrument amounts, dates, and URLs from the HTML content stored in the `body` field of a JSON file containing credit rating information from Infomerics.

## Features

- **JSON Input Processing**: Reads HTML content from the `body` field of a JSON file
- **Proper HTML Parsing**: Uses BeautifulSoup instead of regex for robust HTML parsing
- **Complete Data Extraction**: Extracts all required fields (company names, instrument categories, ratings, outlooks, amounts, dates, URLs)
- **Duplicate Detection**: Automatically filters out duplicate entries
- **Multiple Output Formats**: Saves data in JSON, CSV, and Excel formats
- **Data Analysis**: Provides summary statistics and analysis sheets in Excel
- **Clean Data**: Properly cleans URLs, dates, and text content

## Requirements

### Required Dependencies
- `beautifulsoup4>=4.9.0` - For HTML parsing

### Optional Dependencies (for Excel export)
- `pandas>=1.3.0` - For data analysis and Excel export
- `openpyxl>=3.0.0` - For Excel file creation

## Installation

1. Install required dependencies:
   ```bash
   pip install beautifulsoup4
   ```

2. Install optional dependencies for Excel export:
   ```bash
   pip install pandas openpyxl
   ```

   Or install all at once:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Place the JSON file**: Ensure that `bright_data_response_json_.json` is in the same directory as the script.

2. **Run the script**:
   ```bash
   python3 extract_html_company_data.py
   ```

## Input File Format

The script expects a JSON file with the following structure:
```json
{
  "status_code": 200,
  "headers": {...},
  "body": "<html>...</html>"
}
```

The HTML content should be in the `body` field of the JSON file.

## Output Files

The script generates the following files:

- **`extracted_html_company_data.json`**: Complete data in JSON format
- **`extracted_html_company_data.csv`**: Data in CSV format for spreadsheet applications
- **`extracted_html_company_data.xlsx`**: Excel file with multiple sheets:
  - `All Data`: Complete extracted data
  - `Rating Analysis`: Rating distribution analysis
  - `Company Analysis`: Number of instruments per company
  - `Outlook Analysis`: Outlook distribution
  - `Category Analysis`: Instrument category distribution

## Extracted Data Fields

For each instrument, the script extracts:

1. **Company Name**: Full company name
2. **Instrument Category**: Type of financial instrument
3. **Rating**: Credit rating assigned
4. **Outlook**: Rating outlook (Positive, Negative, Stable, etc.)
5. **Instrument Amount**: Financial amount (properly cleaned)
6. **Date**: "As on" date from the rating
7. **URL**: Direct link to the rating document (PDF)

## Key Improvements Over Regex Approach

1. **Robust HTML Parsing**: BeautifulSoup handles malformed HTML better than regex
2. **Accurate Data Extraction**: Properly navigates HTML structure to find related data
3. **URL Extraction**: Successfully extracts all PDF URLs (622/622 found)
4. **Duplicate Filtering**: Automatically removes duplicate entries
5. **Better Error Handling**: Graceful handling of missing or malformed data

## Script Performance

Latest extraction results:
- **Companies Found**: 308 companies
- **Instruments Extracted**: 622 unique instruments
- **URLs Found**: 622/622 (100% success rate)
- **Dates Found**: 622/622 (100% success rate)
- **Amounts Found**: 622/622 (100% success rate)

## Example Output

```
=== HTML EXTRACTION SUMMARY ===
Total instruments extracted: 622
Unique companies: 308

Rating distribution (top 10):
  IVR BBB- (Reaffirmed): 38
  IVR BBB- (Assigned): 30
  IVR BBB (Reaffirmed): 29
  Withdrawn: 25
  ...

URLs found: 622/622
Amounts found: 622/622
Dates found: 622/622
```

## Data Quality Features

- **Duplicate Detection**: Automatically identifies and removes duplicate entries
- **URL Cleaning**: Removes escaped quotes and formatting issues from URLs
- **Text Cleaning**: Removes HTML entities, extra whitespace, and formatting artifacts
- **Data Validation**: Ensures all extracted data meets quality standards

## Why BeautifulSoup Instead of Regex?

The script uses **BeautifulSoup** for HTML parsing instead of regular expressions because:

1. **Robustness**: BeautifulSoup handles malformed HTML gracefully
2. **Maintainability**: DOM-based parsing is easier to understand and modify
3. **Reliability**: Less prone to breaking when HTML structure changes slightly
4. **Feature-rich**: Built-in methods for finding elements, handling attributes, and text extraction
5. **Error handling**: Better error reporting and recovery from parsing issues

While regex can be faster for simple text patterns, BeautifulSoup is the better choice for complex HTML parsing tasks like this one.

## Troubleshooting

1. **BeautifulSoup not found**: Install with `pip install beautifulsoup4`
2. **Excel export fails**: Install pandas and openpyxl with `pip install pandas openpyxl`
3. **JSON format errors**: Ensure your JSON file has a valid `body` field containing HTML
4. **No data extracted**: Check that `bright_data_response_json_.json` exists and contains valid HTML in the `body` field
5. **Partial data**: The script includes detailed logging to help identify parsing issues

The script includes comprehensive error handling and debugging output to help identify issues.