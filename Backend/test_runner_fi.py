from fi_runner import generate_burnt_area_report

result = generate_burnt_area_report(
    state="Firozpur",
    season="Rabi",
    year=2026
)

print("\nRESULT:\n")
print(result)