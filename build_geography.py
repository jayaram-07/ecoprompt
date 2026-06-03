import json

# ----------------------------
# Load Raw Countries
# ----------------------------

with open("countries_raw.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

countries_clean = []
continents_set = set()

for country in raw:
    name = country.get("name", {}).get("common")

    capital = None
    if country.get("capital"):
        capital = country["capital"][0]

    currencies = country.get("currencies")
    currency_name = None
    if currencies:
        currency_name = list(currencies.values())[0].get("name")

    continent = country.get("region")
    iso = country.get("cca2")

    if name and capital and currency_name and continent:
        countries_clean.append({
            "name": name,
            "capital": capital,
            "currency": currency_name,
            "iso": iso,
            "continent": continent
        })
        continents_set.add(continent)

countries_clean = sorted(countries_clean, key=lambda x: x["name"])
continents_clean = [{"name": c} for c in sorted(list(continents_set))]

# ----------------------------
# Add Full States (USA + India)
# ----------------------------

states_data = {
    "United States": [
        {"name": "Alabama", "capital": "Montgomery"},
        {"name": "Alaska", "capital": "Juneau"},
        {"name": "Arizona", "capital": "Phoenix"},
        {"name": "Arkansas", "capital": "Little Rock"},
        {"name": "California", "capital": "Sacramento"},
        {"name": "Colorado", "capital": "Denver"},
        {"name": "Connecticut", "capital": "Hartford"},
        {"name": "Delaware", "capital": "Dover"},
        {"name": "Florida", "capital": "Tallahassee"},
        {"name": "Georgia", "capital": "Atlanta"},
        {"name": "Hawaii", "capital": "Honolulu"},
        {"name": "Idaho", "capital": "Boise"},
        {"name": "Illinois", "capital": "Springfield"},
        {"name": "Indiana", "capital": "Indianapolis"},
        {"name": "Iowa", "capital": "Des Moines"},
        {"name": "Kansas", "capital": "Topeka"},
        {"name": "Kentucky", "capital": "Frankfort"},
        {"name": "Louisiana", "capital": "Baton Rouge"},
        {"name": "Maine", "capital": "Augusta"},
        {"name": "Maryland", "capital": "Annapolis"},
        {"name": "Massachusetts", "capital": "Boston"},
        {"name": "Michigan", "capital": "Lansing"},
        {"name": "Minnesota", "capital": "Saint Paul"},
        {"name": "Mississippi", "capital": "Jackson"},
        {"name": "Missouri", "capital": "Jefferson City"},
        {"name": "Montana", "capital": "Helena"},
        {"name": "Nebraska", "capital": "Lincoln"},
        {"name": "Nevada", "capital": "Carson City"},
        {"name": "New Hampshire", "capital": "Concord"},
        {"name": "New Jersey", "capital": "Trenton"},
        {"name": "New Mexico", "capital": "Santa Fe"},
        {"name": "New York", "capital": "Albany"},
        {"name": "North Carolina", "capital": "Raleigh"},
        {"name": "North Dakota", "capital": "Bismarck"},
        {"name": "Ohio", "capital": "Columbus"},
        {"name": "Oklahoma", "capital": "Oklahoma City"},
        {"name": "Oregon", "capital": "Salem"},
        {"name": "Pennsylvania", "capital": "Harrisburg"},
        {"name": "Rhode Island", "capital": "Providence"},
        {"name": "South Carolina", "capital": "Columbia"},
        {"name": "South Dakota", "capital": "Pierre"},
        {"name": "Tennessee", "capital": "Nashville"},
        {"name": "Texas", "capital": "Austin"},
        {"name": "Utah", "capital": "Salt Lake City"},
        {"name": "Vermont", "capital": "Montpelier"},
        {"name": "Virginia", "capital": "Richmond"},
        {"name": "Washington", "capital": "Olympia"},
        {"name": "West Virginia", "capital": "Charleston"},
        {"name": "Wisconsin", "capital": "Madison"},
        {"name": "Wyoming", "capital": "Cheyenne"}
    ],

    "India": [
        {"name": "Andhra Pradesh", "capital": "Amaravati"},
        {"name": "Arunachal Pradesh", "capital": "Itanagar"},
        {"name": "Assam", "capital": "Dispur"},
        {"name": "Bihar", "capital": "Patna"},
        {"name": "Chhattisgarh", "capital": "Raipur"},
        {"name": "Goa", "capital": "Panaji"},
        {"name": "Gujarat", "capital": "Gandhinagar"},
        {"name": "Haryana", "capital": "Chandigarh"},
        {"name": "Himachal Pradesh", "capital": "Shimla"},
        {"name": "Jharkhand", "capital": "Ranchi"},
        {"name": "Karnataka", "capital": "Bengaluru"},
        {"name": "Kerala", "capital": "Thiruvananthapuram"},
        {"name": "Madhya Pradesh", "capital": "Bhopal"},
        {"name": "Maharashtra", "capital": "Mumbai"},
        {"name": "Manipur", "capital": "Imphal"},
        {"name": "Meghalaya", "capital": "Shillong"},
        {"name": "Mizoram", "capital": "Aizawl"},
        {"name": "Nagaland", "capital": "Kohima"},
        {"name": "Odisha", "capital": "Bhubaneswar"},
        {"name": "Punjab", "capital": "Chandigarh"},
        {"name": "Rajasthan", "capital": "Jaipur"},
        {"name": "Sikkim", "capital": "Gangtok"},
        {"name": "Tamil Nadu", "capital": "Chennai"},
        {"name": "Telangana", "capital": "Hyderabad"},
        {"name": "Tripura", "capital": "Agartala"},
        {"name": "Uttar Pradesh", "capital": "Lucknow"},
        {"name": "Uttarakhand", "capital": "Dehradun"},
        {"name": "West Bengal", "capital": "Kolkata"},

        {"name": "Andaman and Nicobar Islands", "capital": "Port Blair"},
        {"name": "Chandigarh", "capital": "Chandigarh"},
        {"name": "Dadra and Nagar Haveli and Daman and Diu", "capital": "Daman"},
        {"name": "Delhi", "capital": "New Delhi"},
        {"name": "Jammu and Kashmir", "capital": "Srinagar"},
        {"name": "Ladakh", "capital": "Leh"},
        {"name": "Lakshadweep", "capital": "Kavaratti"},
        {"name": "Puducherry", "capital": "Puducherry"}
    ]
}

# ----------------------------
# Final Geography Structure
# ----------------------------

geography = {
    "continents": continents_clean,
    "countries": countries_clean,
    "states": states_data
}

with open("kb/geography.json", "w", encoding="utf-8") as f:
    json.dump(geography, f, indent=2, ensure_ascii=False)

print("Geography dataset built successfully.")
print(f"Total countries: {len(countries_clean)}")
print(f"Total continents: {len(continents_clean)}")
print("States added for USA and India.")