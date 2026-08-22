from django.db import models
from django.conf import settings

CATEGORY_CHOICES = [
    ('ai', 'AI Services'),
    ('design', 'Graphics & Design'),
    ('wordpress', 'Programming & Tech'),
    ('voice', 'Music & Audio'),
    ('video', 'Video & Animation'),
    ('social', 'Digital Marketing'),
    ('seo', 'SEO'),
    ('illustration', 'Illustration'),
    ('translation', 'Writing & Translation'),
    ('books', 'Book Covers'),
    ('writing', 'Data Entry'),
]

class Gig(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gigs')
    title = models.CharField(max_length=255)
    description = models.TextField()
    short_title = models.CharField(max_length=100)
    short_desc = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cover = models.URLField()
    delivery_time = models.CharField(max_length=50)
    revision_number = models.IntegerField(default=1)
    features = models.TextField(blank=True, help_text='Comma separated features')
    total_stars = models.IntegerField(default=0)
    star_number = models.IntegerField(default=0)
    sales = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def avg_rating(self):
        if self.star_number == 0:
            return 0
        return round(self.total_stars / self.star_number, 1)

    def features_list(self):
        return [f.strip() for f in self.features.split(',') if f.strip()]

    def __str__(self):
        return self.title

class GigImage(models.Model):
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='images')
    image = models.URLField()
