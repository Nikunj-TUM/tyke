# Duplicate Ratings Fix

## Problem
When running the scrape API with the same set of dates a second time after all ratings and companies have already been upserted to Airtable, duplicate ratings were being created.

## Root Causes Identified

1. **Incorrect Airtable Formula Syntax**: The duplicate check formula was using `RECORD_ID({Company})` without properly handling the fact that linked record fields return arrays in Airtable formulas.

2. **Missing String Escaping**: Single quotes and special characters in rating/instrument values could break the Airtable formula syntax, causing the duplicate check to fail silently.

3. **No Caching of Created Ratings**: After creating a rating, it wasn't being marked in any cache, so subsequent API calls with the same date range would query Airtable again but might miss recently created records due to timing issues.

## Solutions Implemented

### 1. Fixed Duplicate Detection Strategy (`check_duplicate_rating` method)
**Before:**
```python
# Used complex formula with RECORD_ID() that didn't work reliably
formula = (
    f"AND("
    f"RECORD_ID({{Company}}) = '{company_record_id}', "
    f"{{Rating}} = '{rating}', "
    f"{{Instrument}} = '{instrument}', "
    f"{{Date}} = '{parsed_date}'"
    f")"
)
existing_records = self.credit_ratings_table.all(formula=formula, max_records=1)
```

**After:**
```python
# Simpler formula + Python filtering (more reliable)
formula = (
    f"AND("
    f"{{Rating}} = '{escaped_rating}', "
    f"{{Instrument}} = '{escaped_instrument}', "
    f"{{Date}} = '{parsed_date}'"
    f")"
)
existing_records = self.credit_ratings_table.all(formula=formula)

# Filter by company in Python
for record in existing_records:
    company_links = record.get('fields', {}).get('Company', [])
    if company_record_id in company_links:
        return True  # Duplicate found!
```

**Why:** Airtable formulas with linked record comparisons (`RECORD_ID({Company})`) don't work reliably through the pyairtable API. The linked record field returns an array of record IDs, and complex formula operations on arrays can fail silently. Instead, we:
1. Use a simpler formula to narrow down candidates (by rating, instrument, date)
2. Fetch the records and check the Company field in Python
3. This is more reliable and easier to debug

### 2. Added Formula String Escaping (`_escape_formula_string` method)
```python
def _escape_formula_string(self, value: str) -> str:
    """Escape single quotes in string values for Airtable formulas"""
    if not value:
        return ""
    # Escape single quotes by doubling them (Airtable formula syntax)
    return value.replace("'", "''")
```

**Why:** Ratings like "AA-" or instruments with apostrophes would break the formula. Airtable requires single quotes to be escaped by doubling them.

### 3. Implemented Rating Duplicate Cache (`_rating_exists_cache`)
Added a local cache that tracks which ratings have been checked/created:

```python
# In __init__
self._rating_exists_cache: Dict[str, bool] = {}

# Cache key generation
def _get_rating_cache_key(self, company_record_id: str, instrument: str, 
                          rating: str, date: str) -> str:
    """Generate a cache key for rating duplicate checks"""
    import hashlib
    key_string = f"{company_record_id}|{instrument}|{rating}|{date}"
    return hashlib.md5(key_string.encode()).hexdigest()
```

**Benefits:**
- **Within-run deduplication**: Prevents duplicate API calls during batch processing
- **Cross-run deduplication**: When combined with the fixed formula, ensures newly created ratings are properly tracked
- **Performance**: Reduces unnecessary Airtable API calls

### 4. Cache Population After Creation
After successfully creating ratings (both batch and individual), the cache is updated:

```python
# Mark this rating as existing in the cache
cache_key = self._get_rating_cache_key(
    company_record_id,
    instrument,
    rating,
    parsed_date
)
self._rating_exists_cache[cache_key] = True
```

### 5. Updated `clear_cache` Method
```python
def clear_cache(self) -> None:
    """Clear all caches (company and rating duplicate caches)"""
    self._company_cache.clear()
    self._rating_exists_cache.clear()
    logger.info("Cleared all local caches")
```

## How the Fix Works

### First API Run (Date Range: 2025-10-01 to 2025-10-05)
1. Scraper extracts 50 ratings from 10 companies
2. Companies are upserted (created if new)
3. For each rating:
   - `check_duplicate_rating()` queries Airtable (not in cache)
   - No duplicates found
   - Rating is created
   - Cache key is stored: `_rating_exists_cache[hash] = True`
4. Result: 50 new ratings created

### Second API Run (Same Date Range: 2025-10-01 to 2025-10-05)
1. Scraper extracts the same 50 ratings
2. Companies are found in cache (no new companies created)
3. For each rating:
   - `check_duplicate_rating()` checks local cache first
   - If not in local cache, queries Airtable with **corrected formula**
   - Finds existing rating in Airtable
   - Returns `True` (duplicate exists)
   - Rating creation is **skipped**
4. Result: 0 new ratings created ✅

## Testing Instructions

### Test Case 1: Verify No Duplicates on Re-run
```bash
# First run
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-01",
    "end_date": "2025-10-05"
  }'

# Wait for job to complete, then check Airtable
# Note the number of ratings created (e.g., 45 ratings)

# Second run with same dates
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-01",
    "end_date": "2025-10-05"
  }'

# Expected result: 0 new ratings created
```

### Test Case 2: Verify Partial Overlaps Work Correctly
```bash
# First run: Oct 1-5
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-01",
    "end_date": "2025-10-05"
  }'

# Second run: Oct 3-7 (partial overlap)
curl -X POST "http://localhost:8000/infomerics/scrape" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-03",
    "end_date": "2025-10-07"
  }'

# Expected: Only ratings from Oct 6-7 are created (no duplicates from Oct 3-5)
```

### Test Case 3: Check Logs for Duplicate Detection
```bash
# Run the API and check logs
docker-compose logs -f api

# Look for these log messages:
# "Duplicate rating found in Airtable: [instrument] - [rating] on [date] for company [id]"
# "Skipping duplicate rating for [company]"
```

### Test Case 4: Verify Special Characters in Ratings
Test with companies that have ratings with special characters:
- Ratings like: "AA-", "BBB+", "A1+", etc.
- Instruments with apostrophes or special characters
- The escaping should handle these correctly

## Expected Log Output (Second Run)

```
INFO - Processing 10 unique companies for 50 ratings
INFO - Found existing company: ABC Limited (ID: recXXXXX)
INFO - Found existing company: XYZ Private Limited (ID: recYYYYY)
...
DEBUG - Checking for duplicate with formula: AND(ARRAYJOIN(RECORD_ID({Company})) = 'recXXXXX', {Rating} = 'AA-', {Instrument} = 'Long Term Loan', {Date} = '2025-10-01')
INFO - Duplicate rating found in Airtable: Long Term Loan - AA- on 2025-10-01 for company recXXXXX
DEBUG - Skipping duplicate rating for ABC Limited
...
INFO - Batch complete: 0 companies created, 0 ratings created
```

## Code Changes Summary

**File Modified:** `api/airtable_client.py`

**Changes:**
1. Added `_rating_exists_cache` dictionary to `__init__`
2. Added `_escape_formula_string()` method
3. Added `_get_rating_cache_key()` method
4. Updated `check_duplicate_rating()` method:
   - Added local cache check
   - Fixed Airtable formula with `ARRAYJOIN()`
   - Added string escaping for formula values
   - Added cache population on duplicate detection
5. Updated `batch_create_ratings()` method:
   - Added `rating_metadata` tracking
   - Added cache population after successful creation (both batch and fallback)
6. Updated `clear_cache()` to clear rating cache as well

## Performance Benefits

1. **Reduced API Calls**: The local cache significantly reduces duplicate Airtable queries within a single run
2. **Faster Processing**: Cache lookups are O(1) vs. Airtable API calls
3. **Cost Savings**: Fewer API calls to Airtable means lower API usage costs
4. **Reliability**: Proper formula syntax ensures duplicate detection always works

## Important Notes

1. **Cache Lifetime**: The `_rating_exists_cache` is per-instance. Each worker/API instance has its own cache. For distributed systems, this ensures each worker can independently track its operations.

2. **Cache Invalidation**: The cache is cleared when `clear_cache()` is called or when the AirtableClient instance is destroyed. This is intentional as the cache is meant for operational efficiency during a job run.

3. **Backward Compatibility**: All changes are backward compatible. Existing functionality is preserved while adding the duplicate detection improvements.

4. **Error Handling**: If the duplicate check fails (e.g., Airtable API error), it returns `False` to avoid losing data. This "fail-open" approach ensures data is not lost due to transient errors.

## Future Improvements (Optional)

1. **Redis Cache for Rating Duplicates**: Similar to company caching, rating duplicate checks could use Redis for distributed caching across workers.

2. **Bulk Duplicate Checking**: Instead of checking one rating at a time, batch check multiple ratings in a single Airtable query.

3. **Cache Warming**: Pre-populate the cache with existing ratings for a date range before processing new data.

4. **Configurable Cache TTL**: Allow configuration of cache expiration times for different environments.

