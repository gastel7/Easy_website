from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paiement',
            name='statut',
            field=models.CharField(
                choices=[
                    ('en_attente', 'En attente de paiement'),
                    ('en_cours', 'Paiement en cours'),
                    ('reussi', 'Payé'),
                    ('echoue', 'Échec du paiement'),
                    ('expire', 'Paiement expiré'),
                    ('annule', 'Paiement annulé'),
                    ('rembourse', 'Paiement remboursé'),
                ],
                db_index=True,
                default='en_attente',
                max_length=20,
                verbose_name='Statut',
            ),
        ),
    ]
