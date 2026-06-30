import os
import sys

# Add project root to sys.path to allow importing 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rich.console import Console
from core.normalizer import normalize_phone, normalize_date, normalize_skill

def run_tests():
    console = Console()
    
    console.rule("[bold blue]Testing Phone Normalizer[/bold blue]")
    phone1 = '(415) 555-0100'
    console.print(f"'{phone1}' -> [green]{normalize_phone(phone1)}[/green]")
    
    phone2 = '0800 555 0199'
    console.print(f"'{phone2}' (GB) -> [green]{normalize_phone(phone2, region_hint='GB')}[/green]")
    
    phone3 = 'not-a-phone'
    console.print(f"'{phone3}' -> [green]{normalize_phone(phone3)}[/green]")
    
    console.rule("[bold blue]Testing Date Normalizer[/bold blue]")
    for date_str in ['January 2020', '01/2020', '2020-01', '2019']:
        console.print(f"'{date_str}' -> [green]{normalize_date(date_str)}[/green]")
        
    for date_str in ['Present', 'current', 'unknown date']:
        console.print(f"'{date_str}' -> [green]{normalize_date(date_str)}[/green]")
        
    console.rule("[bold blue]Testing Skill Normalizer[/bold blue]")
    for skill_str in ['js', 'REACT.JS', 'python3', 'some_niche_framework']:
        console.print(f"'{skill_str}' -> [green]{normalize_skill(skill_str)}[/green]")

if __name__ == "__main__":
    run_tests()
