from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_remove_certificate_certificate_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='EmailVerificationOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('otp_code', models.CharField(max_length=6)),
                ('purpose', models.CharField(choices=[('registration', 'Registration'), ('password_reset', 'Password Reset')], default='registration', max_length=30)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('is_verified', models.BooleanField(default=False)),
                ('attempts', models.IntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Email Verification OTP',
                'verbose_name_plural': 'Email Verification OTPs',
                'ordering': ['-created_at'],
            },
        ),
    ]
