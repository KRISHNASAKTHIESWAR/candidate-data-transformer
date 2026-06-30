import os
import sys

# Add project root to sys.path to allow importing 'core' and 'adapters'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rich.console import Console
from adapters.base import AdapterResult
from core.merger import MergeEngine

def test_merge_engine():
    console = Console()
    
    # Create Result 1
    result1 = AdapterResult(
        raw_fields={
            'full_name': 'Alice Smith',
            'emails': ['alice@example.com'],
            'phones': ['+14155550100']
        },
        source_name='recruiter_csv',
        trust_weight=0.85,
        error=None
    )
    
    # Create Result 2
    result2 = AdapterResult(
        raw_fields={
            'full_name': 'Alice J. Smith',
            'emails': ['alice@example.com', 'alice.work@test.com'],
            'skills': [{'name': 'JavaScript'}, {'name': 'React'}]
        },
        source_name='recruiter_notes',
        trust_weight=0.50,
        error=None
    )
    
    engine = MergeEngine()
    profile = engine.merge_candidate([result1, result2])
    
    console.rule("[bold magenta]Merge Result[/bold magenta]")
    console.print(f"[bold cyan]Resolved Full Name:[/bold cyan] {profile.full_name}")
    console.print(f"[bold cyan]Unioned Emails:[/bold cyan] {profile.emails}")
    console.print(f"[bold cyan]Overall Confidence:[/bold cyan] {profile.overall_confidence:.2f}")
    
    console.rule("[bold magenta]Provenance Audit Trail[/bold magenta]")
    for entry in profile.provenance:
        console.print(f"- [green]{entry.field}[/green] via [yellow]{entry.source}[/yellow] "
                      f"({entry.method}, conf: {entry.confidence:.2f})")

if __name__ == '__main__':
    test_merge_engine()
