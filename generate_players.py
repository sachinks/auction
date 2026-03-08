import csv
import random

roles = (
    ["BAT"] * 60 +
    ["BOWL"] * 50 +
    ["AR"] * 40 +
    ["PLY"] * 50
)

places = [
"Bangalore","Mumbai","Delhi","Chennai","Hyderabad",
"Kolkata","Ahmedabad","Jaipur","Lucknow","Pune",
"Mangalore","Mysore","Udupi","Hubli","Belgaum"
]

names = []

for i in range(1, 201):
    names.append(f"Player{i}")

with open("players.csv", "w", newline="") as f:

    writer = csv.writer(f)

    writer.writerow(["name","role","phone","place"])

    for i, name in enumerate(names):

        role = roles[i]

        phone = f"9{random.randint(100000000,999999999)}"

        place = random.choice(places)

        writer.writerow([name, role, phone, place])

print("Generated players.csv with 200 players")