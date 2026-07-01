import datetime
from models.canonical import CanonicalProfile, ProvenanceEntry

def enrich_profile(profile: CanonicalProfile) -> CanonicalProfile:
    total_days = 0
    job_count = 0
    current_company = "an undisclosed company"
    
    if profile.experience:
        for job in profile.experience:
            start_str = job.get('start')
            end_str = job.get('end')
            
            if current_company == "an undisclosed company" and job.get('company'):
                current_company = job.get('company')
            
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
            job_count += 1
            
    if total_days > 0:
        total_years = round(total_days / 365.25, 1)
        profile.total_years_experience = total_years
    else:
        total_years = profile.years_experience if profile.years_experience is not None else 0.0
        profile.total_years_experience = total_years

    if job_count > 0 and total_days > 0:
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
    else:
        profile.career_velocity = 'Normal'

    if total_years < 3:
        profile.seniority_level = 'Junior'
    elif total_years < 7:
        profile.seniority_level = 'Mid-Level'
    else:
        profile.seniority_level = 'Senior'
        
    top_skills = [s.get('name') for s in profile.skills[:3] if isinstance(s, dict) and s.get('name')]
    skills_str = f" Specializes in {', '.join(top_skills)}." if top_skills else ""
    
    summary = f"{profile.seniority_level} candidate with {total_years} years of experience, recently at {current_company}.{skills_str}"
    profile.executive_summary = summary
    
    profile.provenance.extend([
        ProvenanceEntry(field='executive_summary', source='derived_engine', method='calculated', confidence=profile.overall_confidence),
        ProvenanceEntry(field='total_years_experience', source='derived_engine', method='calculated', confidence=profile.overall_confidence),
        ProvenanceEntry(field='seniority_level', source='derived_engine', method='calculated', confidence=profile.overall_confidence)
    ])
    
    return profile
