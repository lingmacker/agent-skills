#!/usr/bin/env python3
import sys, json, urllib.request
from datetime import datetime, timezone, timedelta

tickers = sys.argv[1:]
if not tickers:
    print("Usage: get_stocks.py TICKER [TICKER...]")
    sys.exit(1)

results = []
for ticker in tickers:
    # Need to fetch enough data to cover the start of the month, even if it's the end of a long month
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        res = data['chart']['result'][0]
        price = res['meta']['regularMarketPrice']
        
        timestamps = res['timestamp']
        closes = res['indicators']['quote'][0]['close']
        
        valid_data = [(ts, c) for ts, c in zip(timestamps, closes) if c is not None]
        if len(valid_data) < 2:
            results.append({"ticker": ticker, "error": "Not enough data"})
            continue
        
        # 1. Daily Change (Compared to previous trading day's close)
        daily_prev = valid_data[-2][1]
        daily_pct = ((price - daily_prev) / daily_prev) * 100
        
        # Determine current latest date in NY timezone
        latest_ts = valid_data[-1][0]
        ny_offset = timezone(timedelta(hours=-4))
        latest_date = datetime.fromtimestamp(latest_ts, ny_offset).date()
        
        # 2. This Week (WTD) Change
        current_monday = latest_date - timedelta(days=latest_date.weekday())
        week_prev = valid_data[0][1] # fallback
        for ts, c in reversed(valid_data):
            ts_date = datetime.fromtimestamp(ts, ny_offset).date()
            if ts_date < current_monday:
                week_prev = c
                break
        week_pct = ((price - week_prev) / week_prev) * 100
        
        # 3. This Month (MTD) Change
        current_month_start = latest_date.replace(day=1)
        month_prev = valid_data[0][1] # fallback
        for ts, c in reversed(valid_data):
            ts_date = datetime.fromtimestamp(ts, ny_offset).date()
            if ts_date < current_month_start:
                month_prev = c
                break
        month_pct = ((price - month_prev) / month_prev) * 100
        
        results.append({
            "ticker": ticker,
            "price": price,
            "dailyChange": round(daily_pct, 2),
            "weeklyChange": round(week_pct, 2),
            "monthlyChange": round(month_pct, 2)
        })
    except Exception as e:
        results.append({"ticker": ticker, "error": str(e)})

print(json.dumps(results, indent=2))
