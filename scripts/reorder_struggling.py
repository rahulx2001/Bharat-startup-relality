#!/usr/bin/env python3
"""
Reorder 'Struggling' startups in graveyard.json as per user request.
Target Order: Ola Electric, Swiggy, Udaan, MPL, Groww, Slice, Chingari
Also maintains the previous sort order for 'Shut Down' (Famous first).
"""
import json

# Read the JSON file
with open('data/graveyard.json', 'r') as f:
    data = json.load(f)

startups = data['startups']

# Define priority lists
famous_shutdowns = ["Byju's", "BluSmart", "Dunzo", "Koo App", "Hike", "Zilingo", "TaxiForSure", "Staples India", "Peppertap", "AskMe"]
struggling_priority = [
    "Ola Electric",
    "Swiggy",
    "Udaan",
    "MPL (Mobile Premier League)",
    "Groww",
    "Slice",
    "Chingari"
]

# Status priority (Global order of sections)
status_priority = {
    "Shut Down": 1,
    "Struggling": 2,
    "Pivoted": 3,
    "Comeback": 4,
    "Pre-IPO": 5,
    "Growing": 6,
    "Recovery": 7
}

def sort_key(startup):
    status = startup.get('status', 'Unknown')
    name = startup.get('startup_name', '')
    funding = startup.get('funding_burned_usd') or 0
    
    # 1. Primary Sort: Status Section
    status_order = status_priority.get(status, 99)
    
    # 2. Secondary Sort: Specific Ordering within Status
    specific_order = 999
    
    if status == "Shut Down":
        if name in famous_shutdowns:
            specific_order = famous_shutdowns.index(name)
        # If not in famous list, keep 999
        
    elif status == "Struggling":
        # Check for exact match or partial match if needed (e.g. "MPL" vs "MPL (Mobile Premier League)")
        # The user was specific, so we try exact match first
        if name in struggling_priority:
            specific_order = struggling_priority.index(name)
        else:
             # Try partial match if exact match fails (e.g. for MPL)
            for i, p_name in enumerate(struggling_priority):
                if p_name.lower() in name.lower() or name.lower() in p_name.lower():
                     # Be careful with short names, but here names are distinct enough
                     # MPL is "MPL (Mobile Premier League)" in JSON vs "MPL (Mobile Premier League)" in list
                     # So exact match should work if strings aren't weird.
                     # Let's trust exact match first.
                     if name == "MPL (Mobile Premier League)": 
                         specific_order = struggling_priority.index("MPL (Mobile Premier League)")
                         break
            
            # If still not found, it keeps 999
    
    # 3. Tertiary Sort: Funding (Descending) as tie-breaker for items not in priority list
    return (status_order, specific_order, -funding)

# Sort the startups
sorted_startups = sorted(startups, key=sort_key)

# Update the data
data['startups'] = sorted_startups

# Write back
with open('data/graveyard.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Validation Print
print("✓ Reordered graveyard.json")
print("\nTop 10 Struggling Startups:")
count = 0
for s in sorted_startups:
    if s['status'] == 'Struggling':
        print(f"   {count+1}. {s['startup_name']}")
        count += 1
        if count >= 10: break
