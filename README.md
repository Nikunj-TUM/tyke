# Company Credit Rating Data Extractor

This Python script extracts company credit rating information from the provided markdown file (`body_json_md.md`) and exports it to multiple formats.

## What it extracts:

- **Company Names**: Names of companies being rated
- **Instrument Categories**: Types of financial instruments (e.g., "Long Term Bank Facilities", "Short Term Bank Facilities")
- **Ratings**: Credit ratings assigned by Infomerics (e.g., "IVR BBB-", "IVR A-")
- **Outlook**: Rating outlook (Positive, Negative, Stable, Nil)
- **Instrument Amount**: Financial amounts associated with each instrument
- **Date**: "As on" dates mentioned in the ratings
- **URL**: Links to detailed instrument reports

## Usage:

```bash
python3 extract_company_data.py
```

## Output Files:

1. **extracted_company_data.json** - JSON format with all extracted data
2. **extracted_company_data.csv** - CSV format for spreadsheet applications
3. **extracted_company_data.xlsx** - Excel format with analysis sheets (requires pandas)

## Optional Dependencies:

For Excel export with additional analysis sheets:
```bash
pip install pandas openpyxl
```

## Data Summary:

The script provides a comprehensive summary including:
- Total number of instruments extracted
- Number of unique companies
- Distribution of ratings
- Sample data preview

## Features:

- ✅ Handles literal `\n` characters in markdown
- ✅ Cleans and normalizes text data
- ✅ Extracts precise instrument amounts
- ✅ Provides detailed analysis and statistics
- ✅ Multiple export formats
- ✅ Error handling and validation

## Example Output:

```
=== EXTRACTION SUMMARY ===
Total instruments extracted: 169
Unique companies: 143

Sample data:
1. Company: Chandanpani Limited
   Category: Long Term Bank Facilities
   Rating: IVR BBB- (Reaffirmed)
   Date: Oct 10, 2025
   URL: https://www.infomerics.com/admin/uploads/PR-ChandanpaniLtd10Oct25.pdf
```
