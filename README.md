### Configuration

1. **Work Item**:
   - If `payload` exists, parameters are read from the work item.
   - Default `max_pages` is set to 5 if not provided.
2. **Config File**:
   - Parameters are read from `config/config.json` if no payload exists
  
### Parameters
- `search_phrase`: The keyword(s) to search for in the news.
- `category`: Optional category filter for news.
- `months`: Number of months to consider for news articles.
- `max_pages`: Maximum number of pages to scrape.
