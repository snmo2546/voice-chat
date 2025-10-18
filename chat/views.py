from django.shortcuts import render


def chat_interface(request):
    """Render the main chat interface."""
    return render(request, 'chat/chat_interface.html')