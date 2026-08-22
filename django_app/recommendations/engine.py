import math
from collections import defaultdict

def _tfidf(docs):
    """Pure Python TF-IDF vectorizer."""
    N = len(docs)
    tokenized = [doc.lower().split() for doc in docs]
    df = defaultdict(int)
    for tokens in tokenized:
        for word in set(tokens):
            df[word] += 1
    idf = {w: math.log(N / (1 + df[w])) for w in df}

    vectors = []
    for tokens in tokenized:
        tf = defaultdict(float)
        for w in tokens:
            tf[w] += 1
        vec = {w: (tf[w] / len(tokens)) * idf[w] for w in tf}
        vectors.append(vec)
    return vectors

def _cosine(v1, v2):
    keys = set(v1) & set(v2)
    dot = sum(v1[k] * v2[k] for k in keys)
    mag1 = math.sqrt(sum(x**2 for x in v1.values()))
    mag2 = math.sqrt(sum(x**2 for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0
    return dot / (mag1 * mag2)

def get_recommendations(user, limit=6):
    try:
        from gigs.models import Gig
        from orders.models import Order

        all_gigs = list(Gig.objects.all())
        if not all_gigs:
            return []

        purchased_ids = set(Order.objects.filter(buyer=user, is_completed=True).values_list('gig_id', flat=True))

        if not purchased_ids:
            return list(Gig.objects.order_by('-sales')[:limit])

        corpus = [f"{g.title} {g.category} {g.description}" for g in all_gigs]
        vectors = _tfidf(corpus)

        purchased_indices = [i for i, g in enumerate(all_gigs) if g.id in purchased_ids]

        # Average profile vector
        profile = defaultdict(float)
        for idx in purchased_indices:
            for k, v in vectors[idx].items():
                profile[k] += v / len(purchased_indices)

        scores = [_cosine(dict(profile), vectors[i]) for i in range(len(all_gigs))]
        ranked = sorted(
            [(scores[i], all_gigs[i]) for i in range(len(all_gigs)) if all_gigs[i].id not in purchased_ids],
            key=lambda x: x[0], reverse=True
        )
        return [g for _, g in ranked[:limit]]
    except Exception:
        return []
