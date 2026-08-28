from datetime import datetime, time

def normalize_range(value, fallback):
    if isinstance(value, (list,tuple)) and len(value)==2:
        return value[0], value[1]
    return fallback

def bounds(start_date, end_date):
    return datetime.combine(start_date,time.min), datetime.combine(end_date,time.max)
