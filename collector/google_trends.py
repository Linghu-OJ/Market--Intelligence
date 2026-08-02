from pytrends.request import TrendReq


class GoogleTrendsCollector:
    """Collect unanalysed UK Google Trends data."""

    def __init__(self):
        self.client = TrendReq(
            hl="en-GB",
            tz=0,
        )

    def collect(self):
        trending_searches = self.client.today_searches(pn="GB")
        related_topics = {}
        interest_over_time = {}

        for keyword in trending_searches.tolist():
            self.client.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe="today 5-y",
                geo="GB",
                gprop="",
            )

            related_topics[keyword] = self.client.related_topics()
            interest_over_time[keyword] = self.client.interest_over_time()

        return {
            "trending_searches": trending_searches,
            "related_topics": related_topics,
            "interest_over_time": interest_over_time,
        }





