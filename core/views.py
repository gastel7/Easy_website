from django.shortcuts import render

from account.models import EasyMember

# Create your views here.
def index(request):
    return render(request, 'core/base.html')


def a_propos(request):
    # Liste simple de tous tes membres
    users = EasyMember.objects.all()

    context = {
        'users': users
    }

    return render(request, 'core/easy/a_propos.html', context)
