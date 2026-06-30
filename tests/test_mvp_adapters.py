import os
import json
import csv
from pathlib import Path
from rich import print

from adapters.csv_adapter import CsvAdapter
from adapters.ats_json_adapter import AtsJsonAdapter
from adapters.notes_adapter import NotesAdapter

def main():
    # 1. Setup sample_inputs/
    sample_dir = Path("sample_inputs")
    sample_dir.mkdir(exist_ok=True)
    
    csv_path = sample_dir / "recruiter.csv"
    json_path = sample_dir / "ats.json"
    notes_path = sample_dir / "notes.txt"
    non_existent_path = sample_dir / "does_not_exist.txt"
    
    # Generate dummy CSV
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email", "phone"])
        writer.writeheader()
        writer.writerow({"name": "Alice Smith", "email": "alice@example.com", "phone": "123-456-7890"}) # Perfect
        writer.writerow({"name": "Bob Jones", "email": "", "phone": "987-654-3210"}) # Missing email
        writer.writerow({"name": "", "email": "", "phone": ""}) # Empty row
        
    # Generate dummy JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "applicant": {
                "name": "Jane Doe",
                "contact": {
                    "phone": "555-1234",
                    "email": "jane.doe@example.org"
                }
            }
        }, f, indent=2)
        
    # Generate dummy txt
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("I spoke with candidate Charlie Brown today.\n")
        f.write("He seems like a great fit. His email is charlie.b@test.com and phone is (555) 999-8888.\n")
        f.write("Check out his github at https://github.com/charlieb\n")
        
    # 2. Instantiate Adapters
    csv_adapter = CsvAdapter()
    json_adapter = AtsJsonAdapter()
    notes_adapter = NotesAdapter()
    
    # 3. Test extractions
    print("[bold green]--- Testing CsvAdapter ---[/bold green]")
    csv_result = csv_adapter.safe_extract(str(csv_path))
    print(csv_result)
    
    print("\n[bold green]--- Testing AtsJsonAdapter ---[/bold green]")
    json_result = json_adapter.safe_extract(str(json_path))
    print(json_result)
    
    print("\n[bold green]--- Testing NotesAdapter ---[/bold green]")
    notes_result = notes_adapter.safe_extract(str(notes_path))
    print(notes_result)
    
    # 4. Test error handling on base class
    # CsvAdapter does not catch FileNotFoundError, so it bubbles up to BaseAdapter.safe_extract
    print("\n[bold red]--- Testing Error Handling (Non-existent File with CsvAdapter) ---[/bold red]")
    error_result = csv_adapter.safe_extract(str(non_existent_path))
    print(error_result)

if __name__ == "__main__":
    main()
