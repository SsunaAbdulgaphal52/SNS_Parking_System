from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parking', '0002_lotstaff'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='carowner',
            name='license_no',
        ),
    ]
