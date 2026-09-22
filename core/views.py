from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'core/base.html')

def a_propos(request):
    return render(request, 'core/easy/a_propos.html')