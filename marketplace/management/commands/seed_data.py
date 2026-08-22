from django.core.management.base import BaseCommand
from marketplace.models import Category, Skill


class Command(BaseCommand):
    help = 'Seeds initial marketplace categories and skills without creating hardcoded users.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding Hirevo categories and skills...'))

        categories_data = [
            {'name': 'Graphics & Design', 'slug': 'graphics-design', 'icon': 'bi-palette', 'description': 'Logo design, brand identity, illustrations, visual arts, and UI/UX design.'},
            {'name': 'Programming & Tech', 'slug': 'programming-tech', 'icon': 'bi-code-slash', 'description': 'Custom software, Python scripts, databases, APIs, algorithms, and backend systems.'},
            {'name': 'Web Development', 'slug': 'web-development', 'icon': 'bi-globe', 'description': 'Full-stack web applications, responsive websites, Django, React, and frontend development.'},
            {'name': 'Mobile App Development', 'slug': 'mobile-app-development', 'icon': 'bi-phone', 'description': 'iOS, Android, React Native, Flutter, and cross-platform mobile apps.'},
            {'name': 'AI Services', 'slug': 'ai-services', 'icon': 'bi-cpu', 'description': 'Machine learning models, NLP, computer vision, LangChain, AI integration, and chatbots.'},
            {'name': 'Digital Marketing', 'slug': 'digital-marketing', 'icon': 'bi-megaphone', 'description': 'Search engine optimization (SEO), social media marketing, PPC campaigns, and email marketing.'},
            {'name': 'Writing & Translation', 'slug': 'writing-translation', 'icon': 'bi-pencil-square', 'description': 'Article writing, copywriting, technical documentation, proofreading, and multilingual translation.'},
            {'name': 'Video & Animation', 'slug': 'video-animation', 'icon': 'bi-camera-video', 'description': 'Video editing, 2D/3D motion graphics, promotional videos, intro animations, and subtitles.'},
            {'name': 'Business', 'slug': 'business', 'icon': 'bi-briefcase', 'description': 'Business planning, financial modeling, market research, virtual assistance, and consulting.'},
            {'name': 'Lifestyle', 'slug': 'lifestyle', 'icon': 'bi-heart', 'description': 'Fitness coaching, gaming coaching, arts & crafts, life lessons, and wellness.'},
        ]

        created_cats = 0
        for cat_info in categories_data:
            cat, created = Category.objects.get_or_create(
                slug=cat_info['slug'],
                defaults={
                    'name': cat_info['name'],
                    'icon': cat_info['icon'],
                    'description': cat_info['description'],
                    'is_active': True
                }
            )
            if created:
                created_cats += 1

        skills_list = [
            'Python', 'Django', 'Java', 'React', 'HTML', 'CSS', 'JavaScript', 'TypeScript',
            'UI/UX', 'Graphic Design', 'Logo Design', 'Video Editing', 'Machine Learning',
            'AI', 'Data Science', 'Mobile Development', 'Flutter', 'Digital Marketing',
            'Content Writing', 'SEO Optimization', 'PostgreSQL', 'MySQL', 'REST API',
            'Node.js', 'Docker', 'AWS', 'TensorFlow', 'PyTorch', 'Git', 'Bootstrap 5'
        ]

        created_skills = 0
        for skill_name in skills_list:
            skill, created = Skill.objects.get_or_create(name=skill_name)
            if created:
                created_skills += 1

        self.stdout.write(
            self.style.SUCCESS(f'Seed complete! Added {created_cats} categories and {created_skills} skills.')
        )
