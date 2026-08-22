from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()

@login_required
def conversations_list(request):
    if request.user.is_seller:
        convs = Conversation.objects.filter(seller=request.user).select_related('buyer').order_by('-updated_at')
    else:
        convs = Conversation.objects.filter(buyer=request.user).select_related('seller').order_by('-updated_at')
    return render(request, 'messaging/conversations.html', {'conversations': convs})

@login_required
def conversation_detail(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    if request.user not in [conv.seller, conv.buyer]:
        return redirect('conversations')
    if request.user == conv.seller:
        conv.read_by_seller = True
    else:
        conv.read_by_buyer = True
    conv.save()
    messages_qs = conv.messages.select_related('sender').order_by('created_at')
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            Message.objects.create(conversation=conv, sender=request.user, text=text)
            conv.last_message = text
            conv.read_by_seller = request.user == conv.seller
            conv.read_by_buyer = request.user == conv.buyer
            conv.save()
        return redirect('conversation_detail', pk=pk)
    return render(request, 'messaging/conversation.html', {'conv': conv, 'messages': messages_qs})

@login_required
def start_conversation(request, seller_id):
    seller = get_object_or_404(User, pk=seller_id, is_seller=True)
    conv, _ = Conversation.objects.get_or_create(seller=seller, buyer=request.user)
    return redirect('conversation_detail', pk=conv.pk)
