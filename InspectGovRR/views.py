from django.shortcuts import render

def home(request):
    return render(request, 'pages/home/index.html')
