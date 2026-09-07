"""Bounds shared by calendar searches and mapping operations."""

# Calendar days; the existing public search contract permits 1000 attempts so
# sparse calendars can span multiple years while every navigation remains bounded.
MAX_BUSINESS_DAY_GAP_DAYS = 1000
# Calendar days; the existing primitive-mapping contract chooses 100 to allow
# multi-month adjustments while rejecting accidental distant target mappings.
MAX_BUSINESS_DAY_SHIFT_DAYS = 100
