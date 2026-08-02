
from pytrends.request import TrendReq

pytrends = TrendReq()

pytrends.build_payload(
    ["chatgpt"],
    timeframe="today 12-m",
    geo="GB"
)

df = pytrends.interest_over_time()

print(df)