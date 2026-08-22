from django.db import models
from django.conf import settings
from gigs.models import Gig

class Review(models.Model):
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    star = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('gig', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.gig.title} ({self.star}★)"
