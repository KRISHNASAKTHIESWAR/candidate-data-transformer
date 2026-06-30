import datetime
from models.canonical import CanonicalProfile, ProvenanceEntry

def enrich_profile(profile: CanonicalProfile) -> CanonicalProfile:
    if not profile.experience:
        return profile
    
    total_days = 0
    # A simple sum of durations as MVP
    for job in profile.experience:
        start_str = job.get('start')
        end_str = job.get('end')
        
        if not start_str:
            continue
            
        try:
            start_date = datetime.datetime.strptime(start_str, "%Y-%m").date()
        except ValueError:
            continue
            
        if end_str:
            try:
                end_date = datetime.datetime.strptime(end_str, "%Y-%m").date()
            except ValueError:
                now = datetime.datetime.now()
                end_date = datetime.date(now.year, now.month, 1)
        else:
            now = datetime.datetime.now()
            end_date = datetime.date(now.year, now.month, 1)
            
        if end_date < start_date:
            continue
            
        total_days += (end_date - start_date).days
        
    if total_days > 0:
        total_years = round(total_days / 365.25, 1)
        profile.total_years_experience = total_years
        
        # Calculate Average Tenure & Career Velocity
        job_count = len([j for j in profile.experience if j.get('start')])
        if job_count > 0:
            avg_tenure = round(total_years / job_count, 1)
            profile.average_tenure = avg_tenure
            
            if avg_tenure < 1.5:
                profile.career_velocity = 'High Mobility'
            elif avg_tenure > 3.5:
                profile.career_velocity = 'High Retention'
            else:
                profile.career_velocity = 'Normal'
                
            profile.provenance.append(ProvenanceEntry(field='average_tenure', source='derived_engine', method='calculated', confidence=profile.overall_confidence))
            profile.provenance.append(ProvenanceEntry(field='career_velocity', source='derived_engine', method='calculated', confidence=profile.overall_confidence))
            
        # Seniority level
        if total_years < 3:
            profile.seniority_level = 'Junior'
        elif total_years < 7:
            profile.seniority_level = 'Mid-Level'
        else:
            profile.seniority_level = 'Senior'
            
        # Executive Summary Generation
        current_company = "an undisclosed company"
        if profile.experience and profile.experience[0].get('company'):
            current_company = profile.experience[0].get('company')
            
        top_skills = [s.get('name') for s in profile.skills[:3] if isinstance(s, dict) and s.get('name')]
        skills_str = f" Specializes in {', '.join(top_skills)}." if top_skills else ""
        
        summary = f"{profile.seniority_level} candidate with {total_years} years of experience, recently at {current_company}.{skills_str}"
        profile.executive_summary = summary
        profile.provenance.append(ProvenanceEntry(field='executive_summary', source='derived_engine', method='calculated', confidence=profile.overall_confidence))
            
        # Add provenance
        profile.provenance.append(
            ProvenanceEntry(
                field='total_years_experience',
                source='derived_engine',
                method='calculated',
                confidence=profile.overall_confidence
            )
        )
        profile.provenance.append(
            ProvenanceEntry(
                field='seniority_level',
                source='derived_engine',
                method='calculated',
                confidence=profile.overall_confidence
            )
        )
        
    return profile
