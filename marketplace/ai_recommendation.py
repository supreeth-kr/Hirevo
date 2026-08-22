"""
Hirevo AI Recommendation Engine
Multi-factor transparent and explainable scoring model utilizing Scikit-learn TF-IDF Vectorizer
combined with deterministic skill matching, experience grading, reputation ratings, availability, and budget alignment.
"""
from .models import FreelancerProfile, Gig, Skill
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


WEIGHTS = {
    'skill_match': 0.40,
    'nlp_relevance': 0.15,
    'experience': 0.15,
    'rating': 0.15,
    'availability': 0.10,
    'price': 0.05,
}


def _skill_match_score(freelancer_skills, required_skills):
    """Calculate percentage overlap between required skills and freelancer skills."""
    if not required_skills:
        return 70.0
    freelancer_skill_names = {s.name.lower().strip() for s in freelancer_skills}
    required = [s.lower().strip() for s in required_skills if s.strip()]
    if not required:
        return 70.0
    
    matched = 0
    for req in required:
        # Check direct or substring match
        if any(req in fs or fs in req for fs in freelancer_skill_names):
            matched += 1
            
    return round((matched / len(required)) * 100, 1)


def _nlp_similarity_score(project_text, freelancer_corpus):
    """Compute cosine similarity of TF-IDF vectors between project text and freelancer profile."""
    if not SKLEARN_AVAILABLE or not project_text.strip() or not freelancer_corpus.strip():
        return 65.0
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([project_text, freelancer_corpus])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return round(float(sim) * 100, 1)
    except Exception:
        return 60.0


def _experience_score(years):
    """Normalize years of experience into a 0-100 scale (10+ years = 100%)."""
    if years >= 10:
        return 100.0
    if years <= 0:
        return 40.0
    return round(40.0 + (years / 10.0) * 60.0, 1)


def _rating_score(avg_rating):
    """Normalize 1-5 star rating into a 0-100 score."""
    if avg_rating <= 0:
        return 75.0  # Fair default for new unrated talent
    return round((avg_rating / 5.0) * 100, 1)


def _availability_score(availability):
    """Map availability status to numerical readiness score."""
    mapping = {
        'available': 100.0,
        'busy': 50.0,
        'unavailable': 10.0
    }
    return mapping.get(availability, 60.0)


def _price_score(hourly_rate, budget):
    """Score how well the freelancer's rate fits within the client budget."""
    if not budget or budget <= 0:
        return 75.0
    rate = float(hourly_rate)
    if rate <= 0:
        return 75.0
    if rate <= budget:
        # Within budget -> full score
        return 100.0
    # Over budget -> linear decay
    over_ratio = (rate - budget) / budget
    score = max(10.0, 100.0 - (over_ratio * 80.0))
    return round(score, 1)


def recommend_freelancers(project_title='', project_description='', required_skills=None, budget=None, category=None, limit=10):
    """
    Generate rank-ordered freelancer recommendations with full explainability metadata.
    """
    profiles = FreelancerProfile.objects.filter(
        user__is_active=True
    ).prefetch_related('skills', 'user')

    project_text = f"{project_title} {project_description} {' '.join(required_skills or [])}"

    results = []
    for profile in profiles:
        skills = list(profile.skills.all())
        skill_names = [s.name for s in skills]
        freelancer_corpus = f"{profile.user.full_name} {profile.bio} {profile.education} {' '.join(skill_names)}"

        skill_score = _skill_match_score(skills, required_skills or [])
        nlp_score = _nlp_similarity_score(project_text, freelancer_corpus)
        exp_score = _experience_score(profile.experience_years)
        avg_rating = profile.avg_rating()
        rating_score = _rating_score(avg_rating)
        avail_score = _availability_score(profile.availability)
        price_score = _price_score(profile.hourly_rate, budget)

        final_score = round(
            skill_score * WEIGHTS['skill_match'] +
            nlp_score * WEIGHTS['nlp_relevance'] +
            exp_score * WEIGHTS['experience'] +
            rating_score * WEIGHTS['rating'] +
            avail_score * WEIGHTS['availability'] +
            price_score * WEIGHTS['price'],
            1
        )

        # Cap between 10% and 99.9%
        final_score = min(99.9, max(15.0, final_score))

        results.append({
            'profile': profile,
            'user': profile.user,
            'skill_score': skill_score,
            'nlp_score': nlp_score,
            'experience_score': exp_score,
            'rating_score': rating_score,
            'availability_score': avail_score,
            'price_score': price_score,
            'final_score': final_score,
            'avg_rating': avg_rating,
            'total_reviews': profile.total_reviews(),
            'skills_list': skill_names,
        })

    results.sort(key=lambda x: x['final_score'], reverse=True)
    return results[:limit]


def recommend_gigs(project_title='', project_description='', required_skills=None, budget=None, category=None, limit=10):
    """
    Generate rank-ordered gig recommendations with matching breakdown.
    """
    gigs = Gig.objects.filter(status=Gig.STATUS_ACTIVE).select_related('freelancer', 'category').prefetch_related('packages')

    if category:
        if isinstance(category, str):
            gigs = gigs.filter(category__slug=category)
        else:
            gigs = gigs.filter(category=category)

    project_text = f"{project_title} {project_description} {' '.join(required_skills or [])}"

    results = []
    for gig in gigs:
        try:
            profile = gig.freelancer.freelancer_profile
        except Exception:
            continue

        gig_corpus = f"{gig.title} {gig.description} {gig.tags} {gig.requirements}"
        skill_score = _skill_match_score(profile.skills.all(), required_skills or [])
        
        # Tag boost
        if required_skills:
            tags = [t.lower().strip() for t in gig.tags_list()]
            for req in required_skills:
                if req.lower().strip() in tags or req.lower().strip() in gig.title.lower():
                    skill_score = min(100.0, skill_score + 15.0)

        nlp_score = _nlp_similarity_score(project_text, gig_corpus)
        avg_rating = gig.avg_rating()
        rating_score = _rating_score(avg_rating)
        starting_price = float(gig.starting_price())
        price_score = _price_score(starting_price, budget) if budget else 75.0

        final_score = round(
            skill_score * 0.45 +
            nlp_score * 0.25 +
            rating_score * 0.20 +
            price_score * 0.10,
            1
        )
        final_score = min(99.9, max(15.0, final_score))

        results.append({
            'gig': gig,
            'freelancer': gig.freelancer,
            'skill_score': skill_score,
            'nlp_score': nlp_score,
            'rating_score': rating_score,
            'price_score': price_score,
            'final_score': final_score,
            'avg_rating': avg_rating,
            'total_reviews': gig.total_reviews(),
            'starting_price': starting_price,
        })

    results.sort(key=lambda x: x['final_score'], reverse=True)
    return results[:limit]
