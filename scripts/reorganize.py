#!/usr/bin/env python3
"""
Reorganize graveyard.json:
1. Remove duplicate SuperLearn (keep the detailed one)
2. Update SuperLearn funding to $2M
3. Sort by status: Shut Down (famous first) > Struggling > Pivoted > others
"""
import json

# Read the JSON file
with open('data/graveyard.json', 'r') as f:
    data = json.load(f)

startups = data['startups']

# Remove duplicate SuperLearn - keep the one with detailed content
superlearn_entries = []
other_entries = []

for s in startups:
    if s.get('startup_name') == 'SuperLearn':
        superlearn_entries.append(s)
    else:
        other_entries.append(s)

# Keep the SuperLearn with founders (the detailed one)
detailed_superlearn = None
for sl in superlearn_entries:
    if sl.get('founders') and len(sl['founders']) > 0:
        detailed_superlearn = sl
        break

# Fallback: keep the one with longer short_summary
if not detailed_superlearn:
    detailed_superlearn = max(superlearn_entries, key=lambda x: len(x.get('short_summary', '')))

# Update funding to $2M
detailed_superlearn['funding_burned_usd'] = 2000000

# Add back the single SuperLearn
all_startups = other_entries + [detailed_superlearn]

# Famous "Shut Down" startups to appear first
famous_shutdowns = ["Byju's", "BluSmart", "Dunzo", "Koo App", "Hike", "Zilingo", "TaxiForSure", "Staples India", "Peppertap", "AskMe"]

# Status priority
status_priority = {
    "Shut Down": 1,
    "Struggling": 2,
    "Pivoted": 3,
    "Comeback": 4,
    "Pre-IPO": 5,
    "Growing": 6,
}

def sort_key(startup):
    status = startup.get('status', 'Unknown')
    name = startup.get('startup_name', '')
    
    # Get status priority (default high number for unknown)
    status_order = status_priority.get(status, 99)
    
    # For Shut Down, famous ones come first
    if status == "Shut Down":
        if name in famous_shutdowns:
            famous_order = famous_shutdowns.index(name)
        else:
            famous_order = 999
        # Sort by: status_order, famous_order, then by funding burned (bigger = more famous)
        funding = startup.get('funding_burned_usd') or 0
        return (status_order, famous_order, -funding)
    else:
        # For other statuses, sort by funding (bigger = more prominent)
        funding = startup.get('funding_burned_usd') or 0
        return (status_order, 0, -funding)

# Sort the startups
sorted_startups = sorted(all_startups, key=sort_key)

# Update the data
data['startups'] = sorted_startups

# Write back
with open('data/graveyard.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Print summary
status_counts = {}
for s in sorted_startups:
    status = s.get('status', 'Unknown')
    status_counts[status] = status_counts.get(status, 0) + 1

print("✓ Reorganized graveyard.json")
print(f"✓ Total startups: {len(sorted_startups)}")
print(f"✓ Status breakdown:")
for status, count in sorted(status_counts.items(), key=lambda x: status_priority.get(x[0], 99)):
    print(f"   - {status}: {count}")

print(f"\n✓ SuperLearn funding updated to: ${detailed_superlearn['funding_burned_usd']:,}")
print("\n✓ First 10 startups (should be famous Shut Downs):")
for s in sorted_startups[:10]:
    print(f"   - {s['startup_name']} ({s['status']})")
