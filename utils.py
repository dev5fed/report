import pandas as pd


def convert_timedelta_to_hours(duration):
    if isinstance(duration, str):
        duration = pd.to_timedelta(duration)
    elif isinstance(duration, pd.Timedelta):
        pass
    else:
        return 0
    return duration.total_seconds() / 3600
