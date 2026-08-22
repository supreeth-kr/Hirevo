"""
Hirevo AI Recommendation Engine
Weighted scoring model - explainable and transparent.
Scores are calculated from real database values.
"""
from .models import FreelancerProfile, Gig, Order, Review, Skill


WEIGHTS = {
    'skill_match': 0.50,
    'experience': 0.15,
    'rating': 0.15,
    'availability': 0.10,
    'price': 0.10,
}


def _skill_match_score(freelancer_skills, required_skills):
    if not required_skills:
        return 50.0
    freelancer_skill_names = {s.name.lower() for s in freelancer_skills}
    required = [s.lower().strip() for s in required_skills if s.strip()]
    if not required:
        return 50.0
    matched = sum(1 for s in required if s in freelancer_skill_names)
    return round((matched / len(required)) * 100, 1)


def _experience_score(years):
    if years >= 10:
        return 100.0
    return round((years / 10) * 100, 1)


def _rating_score(avg_rating):
    return round((avg_rating / 5) * 100, 1)


def _availability_score(availability):
    return {'available': 100.0, 'busy': 50.0, 'unavailable': 0.0}.get(availability, 50.0)


def _price_score(hourly_rate, budget):
    if not budget or budget <= 0:
        return 50.0
    if hourly_rate <= budget:
        return 100.0
    over = (hourly_rate - budget) / budget
    score = max(0, 100 - (over * 100))
    return round(score, 1)


def recommend_freelancers(required_skills=None, budget=None, category=None, limit=10):
    profiles = FreelancerProfile.objects.filter(
        user__is_active=True
    ).prefetch_related('skills', 'user')

    results = []
    for profile in profiles:
        skill_score = _skill_match_score(profile.skills.all(), required_skills or [])
        exp_score = _experience_score(profile.experience_years)
        avg_rating = profile.avg_rating()
        rating_score = _rating_score(avg_rating)
        avail_score = _availability_score(profile.availability)
        price_score = _price_score(float(profile.hourly_rate), budget)

        final_score = round(
            skill_score * WEIGHTS['skill_match'] +
            exp_score * WEIGHTS['experience'] +
            rating_score * WEIGHTS['rating'] +
            avail_score * WEIGHTS['availability'] +
            price_score * WEIGHTS['price'], 1
        )

        results.append({
            'profile': profile,
            'user': profile.user,
            'skill_score': skill_score,
            'experience_score': exp_score,
            'rating_score': rating_score,
            'availability_score': avail_score,
            'price_score': price_score,
            'final_score': final_score,
            'avg_rating': avg_rating,
        })

    results.sort(key=lambda x: x['final_score'], reverse=True)
    return results[:limit]


def recommend_gigs(required_skills=None, budget=None, category=None, limit=10):
    gigs = Gig.objects.filter(status='active').select_related('freelancer', 'category').prefetch_related('packages')

    if category:
        gigs = gigs.filter(category__slug=category)

    results = []
    for gig in gigs:
        try:
            profile = gig.freelancer.freelancer_profile
        except Exception:
            continue

        gig_tags = [t.lower() for t in gig.tags_list()]
        skill_score = _skill_match_score(profile.skills.all(), required_skills or [])

        tag_bonus = 0
        if required_skills:
            for skill in required_skills:
                if skill.lower() in gig_tags or skill.lower() in gig.title.lower():
                    tag_bonus += 10
        skill_score = min(100, skill_score + tag_bonus)

        avg_rating = gig.avg_rating()
        rating_score = _rating_score(avg_rating)
        starting_price = float(gig.starting_price())
        price_score = _price_score(starting_price, budget) if budget else 50.0

        final_score = round(
            skill_score * 0.50 + rating_score * 0.30 + price_score * 0.20, 1
        )

        results.append({
            'gig': gig,
            'skill_score': skill_score,
            'rating_score': rating_score,
            'price_score': price_score,
            'final_score': final_score,
            'avg_rating': avg_rating,
        })

    results.sort(key=lambda x: x['final_score'], reverse=True)
    return results[:limit]
