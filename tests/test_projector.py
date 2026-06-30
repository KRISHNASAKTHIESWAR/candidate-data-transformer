import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rich.console import Console
from models.canonical import CanonicalProfile, ProvenanceEntry
from models.config import RuntimeConfig, ConfigField
from core.projector import Projector

def test_projector():
    console = Console()

    # Create dummy CanonicalProfile
    profile = CanonicalProfile(
        candidate_id='dummy_id',
        full_name='Jane Doe',
        emails=['jane.doe@example.com', 'jane@work.com'],
        phones=[],
        location={},
        links={},
        skills=[{'name': 'Python', 'confidence': 0.9, 'sources': ['github']}],
        headline=None,
        years_experience=None,
        experience=[],
        education=[],
        overall_confidence=0.85,
        provenance=[
            ProvenanceEntry(field='full_name', source='csv', method='direct', confidence=0.85)
        ]
    )

    # Create mock RuntimeConfig
    config = RuntimeConfig(
        fields=[
            ConfigField(path='candidate_name', from_='full_name', type='string', required=True),
            ConfigField(path='primary_email', from_='emails[0]', type='string', required=True),
            ConfigField(path='top_skill', from_='skills[0].name', type='string', required=False, transform='uppercase'),
            ConfigField(path='missing_field', from_='does_not_exist', type='string', required=False)
        ],
        include_confidence=False,
        on_missing='omit'
    )

    # Execute projection
    output_dict = Projector.apply(profile, config)

    # Print output
    console.rule("[bold green]Projector Output Result[/bold green]")
    console.print(output_dict)

if __name__ == '__main__':
    test_projector()
